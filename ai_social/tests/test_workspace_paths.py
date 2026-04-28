from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = WORKSPACE_ROOT / "code"
API_ROOT = CODE_ROOT / "apps" / "api"

sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings  # noqa: E402


class WorkspaceLayoutSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = get_settings()

    def test_workspace_paths_resolve_from_unified_root(self) -> None:
        settings = self.settings

        self.assertEqual(settings.workspace_root, WORKSPACE_ROOT)
        self.assertEqual(settings.code_root, CODE_ROOT)
        self.assertTrue(settings.playwright_root.exists())
        self.assertTrue(settings.tmp_root.exists())
        self.assertTrue(settings.external_docs_root.exists())
        self.assertTrue(settings.default_xingtu_recording.exists())

    def test_external_docs_directory_discovery(self) -> None:
        settings = self.settings

        operational_files = sorted(settings.external_docs_operational_dir.glob("*"))

        self.assertGreaterEqual(len(operational_files), 2)
        self.assertTrue(settings.external_docs_strategy_dir.exists())
        self.assertTrue(settings.external_docs_archive_dir.exists())

    def test_playwright_auth_file_resolution(self) -> None:
        settings = self.settings

        resolved = settings.resolve_storage_state_path("xingtu.json")
        expected = (WORKSPACE_ROOT / "playwright" / ".auth" / "xingtu.json").resolve()

        self.assertEqual(resolved, expected)
        self.assertTrue(resolved.exists())

    def test_existing_cli_boot_path(self) -> None:
        python_bin = CODE_ROOT / ".venv" / "bin" / "python"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(API_ROOT)

        result = subprocess.run(
            [str(python_bin), str(API_ROOT / "run_xingtu_flow.py"), "--help"],
            capture_output=True,
            text=True,
            cwd=CODE_ROOT,
            env=env,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("Run a minimal authenticated Xingtu creator-detail flow.", result.stdout)


if __name__ == "__main__":
    unittest.main()
