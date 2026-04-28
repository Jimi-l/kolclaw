from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.xingtu_cpm import (
    ChartPoint,
    ScreenshotType,
    VlmExtractedPayload,
    XingtuCpmAnalyzeResponse,
    XingtuCpmEvaluateRequest,
    XingtuCpmParseResult,
    XingtuCpmRuleConfig,
)
from app.services.xingtu_cpm_rules import evaluate_xingtu_cpm
from app.services.xingtu_cpm_extraction import analyze_images, parse_images, parse_vlm_extracted_payload
from app.services.xingtu_cpm_vlm import vlm_config_status

router = APIRouter(prefix="/api/xingtu-cpm", tags=["xingtu-cpm"])


@router.post("/evaluate")
def evaluate_xingtu_cpm_request(request: XingtuCpmEvaluateRequest):
    return evaluate_xingtu_cpm(request.input, request.config)


@router.post("/vlm-only", response_model=XingtuCpmParseResult)
async def vlm_only_xingtu_cpm(files: list[UploadFile] = File(...)) -> XingtuCpmParseResult:
    return await _parse_uploads(files, mode="vlm_only")


@router.post("/analyze", response_model=XingtuCpmAnalyzeResponse)
async def analyze_xingtu_cpm_uploads(files: list[UploadFile] = File(...)) -> XingtuCpmAnalyzeResponse:
    return await _analyze_uploads(files, mode="vlm_only")


@router.post("/analyze-vlm-only", response_model=XingtuCpmAnalyzeResponse)
async def analyze_xingtu_cpm_vlm_only(files: list[UploadFile] = File(...)) -> XingtuCpmAnalyzeResponse:
    return await _analyze_uploads(files, mode="vlm_only")


@router.get("/sample", response_model=XingtuCpmAnalyzeResponse)
def sample_xingtu_cpm() -> XingtuCpmAnalyzeResponse:
    payload = VlmExtractedPayload(
        detected_screenshot_types=[
            ScreenshotType.OVERVIEW_PRICING,
            ScreenshotType.VALUE_PERSONAL_VIDEO,
            ScreenshotType.LATEST15_PERSONAL_CHART,
            ScreenshotType.LATEST15_STAR_CHART,
        ],
        creator_name="Example Creator A",
        price_20s=300000,
        price_20_60s=300000,
        price_60s_plus=320000,
        post_count_30d=7,
        platform_expected_cpm=26.1,
        platform_expected_play=11513000,
        natural_plays=[19097000, 15970000, 5601000, 13507000, 18380000, 11547000, 25130000, 10585000, 8852000, 8670000, 16114000, 16677000, 12714000, 11457000, 6934000],
        sponsored_plays=[16469000, 16510000, 15448000, 22821000, 23283000, 3147000, 10628000, 14824000, 32698000, 84248000, 24004000, 15930000, 5601000, 13507000, 8852000],
        personal_chart_points=[
            ChartPoint(date=date_value, play=play, image_name="latest15_personal_chart.png")
            for date_value, play in zip(
                ["26/02/11", "26/02/13", "26/02/17", "26/02/21", "26/02/27", "26/03/04", "26/03/08", "26/03/17", "26/03/21", "26/03/24", "26/03/27", "26/04/03", "26/04/06", "26/04/10", "26/04/13"],
                [19097000, 15970000, 5601000, 13507000, 18380000, 11547000, 25130000, 10585000, 8852000, 8670000, 16114000, 16677000, 12714000, 11457000, 6934000],
            )
        ],
        star_chart_points=[
            ChartPoint(date=date_value, play=play, image_name="latest15_star_chart.png")
            for date_value, play in zip(
                ["25/10/25", "25/11/17", "25/12/05", "25/12/12", "25/12/17", "25/12/18", "25/12/26", "26/01/06", "26/01/17", "26/01/23", "26/01/30", "26/02/13", "26/02/17", "26/02/21", "26/03/21"],
                [16469000, 16510000, 15448000, 22821000, 23283000, 3147000, 10628000, 14824000, 32698000, 84248000, 24004000, 15930000, 5601000, 13507000, 8852000],
            )
        ],
    )
    parse_result = parse_vlm_extracted_payload(payload, XingtuCpmRuleConfig(), vlm_model_used="fixture", extraction_engine_used="fixture")
    response = XingtuCpmAnalyzeResponse(parse_result=parse_result, assessment=evaluate_xingtu_cpm(parse_result.parsed_input, XingtuCpmRuleConfig()))
    response.parse_result = response.parse_result.model_copy(
        update={
            "extraction_engine_used": "fixture",
            "warnings": ["样例模式使用固定 fixture，不代表真实 VLM 上传结果。"],
        }
    )
    return response


@router.get("/vlm-status")
def get_xingtu_cpm_vlm_status():
    return vlm_config_status()


async def _parse_uploads(files: list[UploadFile], mode: str) -> XingtuCpmParseResult:
    with tempfile.TemporaryDirectory(prefix="xingtu-cpm-") as tmpdir:
        return parse_images(await _save_uploads(files, Path(tmpdir)), mode=mode, config=XingtuCpmRuleConfig())


async def _analyze_uploads(files: list[UploadFile], mode: str) -> XingtuCpmAnalyzeResponse:
    upload_names = [upload.filename or f"upload_{index}" for index, upload in enumerate(files)]
    with tempfile.TemporaryDirectory(prefix="xingtu-cpm-") as tmpdir:
        try:
            response = analyze_images(await _save_uploads(files, Path(tmpdir)), mode=mode, config=XingtuCpmRuleConfig())
        except Exception as exc:
            _write_debug_run_log(
                {
                    "status": "error",
                    "mode": mode,
                    "upload_filenames": upload_names,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            raise
        _write_debug_run_log(
            {
                "status": "ok",
                "mode": mode,
                "upload_filenames": upload_names,
                "response": response.model_dump(mode="json"),
            }
        )
        return response


async def _save_uploads(files: list[UploadFile], tmpdir: Path) -> list[Path]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    paths: list[Path] = []
    for upload in files:
        suffix = Path(upload.filename or "upload.png").suffix or ".png"
        path = tmpdir / f"{len(paths)}_{Path(upload.filename or 'upload').stem}{suffix}"
        path.write_bytes(await upload.read())
        paths.append(path)
    return paths


def _write_debug_run_log(payload: dict) -> Path | None:
    enabled = os.getenv("XINGTU_CPM_DEBUG_RUN_LOG_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return None
    log_dir = Path(
        os.getenv(
            "XINGTU_CPM_DEBUG_RUN_LOG_DIR",
            str(Path(__file__).resolve().parents[4] / "runtime" / "debug_runs" / "xingtu_cpm"),
        )
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{timestamp}_{uuid4().hex[:8]}.json"
    record = {"created_at": datetime.now().isoformat(timespec="seconds"), **payload}
    log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return log_path
