#!/usr/bin/env python3
"""Read-only inspector for local WeChat SQLite-like database files."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_NAMES = [
    "contact.db",
    "session.db",
    "message_0.db",
    "message_resource.db",
    "media_0.db",
]
SQLITE_MAGIC = b"SQLite format 3\x00"
SENSITIVE_NAME_PARTS = (
    "wxid",
    "user",
    "name",
    "nick",
    "remark",
    "content",
    "message",
    "msg",
    "path",
    "url",
    "phone",
    "email",
)


def mask_value(column: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if not isinstance(value, str):
        return value

    lowered = column.lower()
    should_mask = any(part in lowered for part in SENSITIVE_NAME_PARTS)
    if not should_mask:
        return value
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}...{value[-2:]} (len={len(value)})"


def read_prefix(path: Path, size: int = 64) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(size)
    except OSError:
        return b""


def file_info(path: Path) -> dict[str, Any]:
    prefix = read_prefix(path)
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "first_64_hex": prefix.hex(),
        "sqlite_magic": prefix.startswith(SQLITE_MAGIC),
    }


def sibling_info(path: Path, suffix: str) -> dict[str, Any]:
    sibling = Path(f"{path}{suffix}")
    return {
        "path": str(sibling),
        "exists": sibling.exists(),
        "size_bytes": sibling.stat().st_size if sibling.exists() else None,
    }


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def classify_table(name: str, create_sql: str | None) -> list[str]:
    lowered_name = name.lower()
    lowered_sql = (create_sql or "").lower()
    tags: list[str] = []
    if "virtual table" in lowered_sql:
        tags.append("virtual_table")
    if "using fts" in lowered_sql or lowered_name.endswith(("_data", "_idx", "_docsize", "_config")):
        tags.append("possible_fts_or_technical_table")
    if lowered_name.startswith("sqlite_"):
        tags.append("sqlite_internal")
    return tags


def inspect_readable_db(path: Path, sample_rows: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "connect_mode_ro": None,
        "integrity_check": None,
        "objects": [],
        "tables": [],
        "errors": [],
    }
    uri = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        result["connect_mode_ro"] = "ok"
    except sqlite3.Error as exc:
        result["connect_mode_ro"] = "error"
        result["errors"].append({"stage": "connect", "error": f"{type(exc).__name__}: {exc}"})
        return result

    try:
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            result["integrity_check"] = row[0] if row else None
        except sqlite3.Error as exc:
            result["errors"].append(
                {"stage": "pragma_integrity_check", "error": f"{type(exc).__name__}: {exc}"}
            )

        try:
            objects = rows_as_dicts(
                connection.execute(
                    """
                    SELECT type, name, tbl_name, sql
                    FROM sqlite_master
                    ORDER BY type, name
                    """
                )
            )
            result["objects"] = objects
        except sqlite3.Error as exc:
            result["errors"].append(
                {"stage": "read_sqlite_master", "error": f"{type(exc).__name__}: {exc}"}
            )
            return result

        for obj in result["objects"]:
            if obj.get("type") != "table":
                continue
            table_name = obj["name"]
            table: dict[str, Any] = {
                "name": table_name,
                "tags": classify_table(table_name, obj.get("sql")),
                "columns": [],
                "indexes": [],
                "sample_rows": [],
                "errors": [],
            }
            try:
                table["columns"] = rows_as_dicts(
                    connection.execute(f"PRAGMA table_info({quote_identifier(table_name)})")
                )
            except sqlite3.Error as exc:
                table["errors"].append({"stage": "table_info", "error": f"{type(exc).__name__}: {exc}"})
            try:
                table["indexes"] = rows_as_dicts(
                    connection.execute(f"PRAGMA index_list({quote_identifier(table_name)})")
                )
            except sqlite3.Error as exc:
                table["errors"].append({"stage": "index_list", "error": f"{type(exc).__name__}: {exc}"})
            try:
                sample_cursor = connection.execute(
                    f"SELECT * FROM {quote_identifier(table_name)} LIMIT ?", (sample_rows,)
                )
                sample = []
                for row in sample_cursor.fetchall():
                    sample.append({key: mask_value(key, row[key]) for key in row.keys()})
                table["sample_rows"] = sample
            except sqlite3.Error as exc:
                table["errors"].append({"stage": "sample_rows", "error": f"{type(exc).__name__}: {exc}"})
            result["tables"].append(table)
    finally:
        connection.close()

    return result


def inspect_db(path: Path, sample_rows: int) -> dict[str, Any]:
    result = {
        "file": file_info(path),
        "wal": sibling_info(path, "-wal"),
        "shm": sibling_info(path, "-shm"),
        "sqlite": {},
    }
    if not path.exists():
        result["sqlite"] = {"errors": [{"stage": "file", "error": "missing database file"}]}
        return result
    result["sqlite"] = inspect_readable_db(path, sample_rows)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect WeChat database files without writing to them.")
    parser.add_argument(
        "--data-dir",
        default="/home/tuo/project/we_chat/data",
        help="Directory containing WeChat database files.",
    )
    parser.add_argument(
        "--db",
        action="append",
        dest="db_names",
        help="Database filename to inspect. Can be passed multiple times.",
    )
    parser.add_argument("--sample-rows", type=int, default=3, help="Rows to sample per readable table.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def print_text(results: list[dict[str, Any]]) -> None:
    for result in results:
        file_meta = result["file"]
        print(f"\n== {Path(file_meta['path']).name} ==")
        print(f"path: {file_meta['path']}")
        print(f"exists: {file_meta['exists']}")
        print(f"size_bytes: {file_meta['size_bytes']}")
        print(f"sqlite_magic: {file_meta['sqlite_magic']}")
        print(f"first_64_hex: {file_meta['first_64_hex']}")
        print(f"wal: exists={result['wal']['exists']} size_bytes={result['wal']['size_bytes']}")
        print(f"shm: exists={result['shm']['exists']} size_bytes={result['shm']['size_bytes']}")

        sqlite_result = result["sqlite"]
        print(f"connect_mode_ro: {sqlite_result.get('connect_mode_ro')}")
        print(f"integrity_check: {sqlite_result.get('integrity_check')}")
        for error in sqlite_result.get("errors", []):
            print(f"error[{error['stage']}]: {error['error']}")

        objects = sqlite_result.get("objects", [])
        print(f"object_count: {len(objects)}")
        if objects:
            for obj in objects:
                print(f"  {obj['type']}: {obj['name']} (table={obj['tbl_name']})")

        for table in sqlite_result.get("tables", []):
            print(f"\n  table: {table['name']}")
            if table["tags"]:
                print(f"  tags: {', '.join(table['tags'])}")
            print("  columns:")
            for col in table["columns"]:
                print(
                    "    "
                    f"{col['cid']}: {col['name']} {col['type']} "
                    f"pk={col['pk']} notnull={col['notnull']} default={col['dflt_value']}"
                )
            print("  indexes:")
            for index in table["indexes"]:
                print(f"    {index['name']} unique={index['unique']} origin={index['origin']}")
            print("  sample_rows:")
            for row in table["sample_rows"]:
                print(f"    {json.dumps(row, ensure_ascii=False)}")
            for error in table["errors"]:
                print(f"  error[{error['stage']}]: {error['error']}")


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    db_names = args.db_names or DEFAULT_DB_NAMES
    results = [inspect_db(data_dir / name, args.sample_rows) for name in db_names]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_text(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
