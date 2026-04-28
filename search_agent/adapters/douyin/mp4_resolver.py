from __future__ import annotations

from dataclasses import dataclass
from urllib import error, request
from urllib.parse import parse_qs, urlparse

from search_agent.models.discovery import CreatorDiscoveryRecord

from .page import _extract_video_id_from_url


MEDIA_URL_HINTS = (
    "mime_type=video_mp4",
    "douyinvod.com",
    "aweme/v1/play",
    "video/tos",
    ".mp4",
    "365yg.com",
)
MEDIA_HOST_HINTS = ("douyinvod.com", "365yg.com")
JSON_RESPONSE_HINTS = ("aweme", "detail", "post", "feed", "item")
EXTERNAL_DIRECT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


@dataclass(slots=True)
class Mp4Candidate:
    url: str
    source: str
    content_type: str | None = None
    content_length: str | None = None
    data_size: int | None = None
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class Mp4ResolveResult:
    direct_mp4_url: str
    source: str
    access_mode: str = "external_direct"
    final_url: str | None = None
    content_type: str | None = None
    content_length: str | None = None
    probe_status_code: int | None = None
    probe_content_range: str | None = None


@dataclass(slots=True)
class Mp4ProbeResult:
    ok: bool
    access_mode: str
    url: str
    final_url: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    content_length: str | None = None
    content_range: str | None = None
    error_text: str | None = None


class BrowserContextOnlyMp4Error(RuntimeError):
    def __init__(self, result: Mp4ResolveResult, error_text: str):
        super().__init__(error_text)
        self.result = result


class DouyinMp4Resolver:
    def __init__(self, page, context, logger, page_wait_ms: int = 8_000) -> None:
        self.page = page
        self.context = context
        self.logger = logger
        self.page_wait_ms = page_wait_ms

    def resolve(self, record: CreatorDiscoveryRecord) -> Mp4ResolveResult:
        video_url = (record.video_url or "").strip()
        if not video_url:
            raise RuntimeError("record has no video_url")

        candidates: list[Mp4Candidate] = []
        target_video_id = _extract_video_id_from_url(video_url)

        def on_response(response) -> None:
            response_url = (getattr(response, "url", "") or "").strip()
            lowered_url = response_url.lower()
            if not lowered_url:
                return
            try:
                headers = response.headers or {}
            except Exception:
                headers = {}
            content_type = (headers.get("content-type") or headers.get("Content-Type") or "").lower()
            content_length = headers.get("content-length") or headers.get("Content-Length")

            if _looks_like_mp4_url(response_url) or "video" in content_type:
                candidates.append(
                    Mp4Candidate(
                        url=response_url,
                        source="media_response",
                        content_type=content_type or None,
                        content_length=str(content_length) if content_length else None,
                    )
                )

            if "json" not in content_type and not any(token in lowered_url for token in JSON_RESPONSE_HINTS):
                return
            try:
                payload = response.json()
            except Exception:
                return
            candidates.extend(extract_mp4_candidates(payload, target_video_id=target_video_id))

        self.page.on("response", on_response)
        try:
            self.page.goto(video_url, wait_until="domcontentloaded", timeout=45_000)
            self.page.wait_for_timeout(self.page_wait_ms)
        finally:
            try:
                self.page.remove_listener("response", on_response)
            except Exception:
                pass

        sorted_candidates = sorted_mp4_candidates(candidates, target_video_id=target_video_id)
        if not sorted_candidates:
            raise RuntimeError("no mp4 candidate found")
        browser_context_only: Mp4ResolveResult | None = None
        probe_errors: list[str] = []

        for candidate in sorted_candidates:
            external_probe = self._probe_external_direct(candidate)
            if external_probe.ok:
                return _build_resolve_result(candidate, external_probe)
            probe_errors.append(external_probe.error_text or f"{candidate.url[:80]} external probe failed")

            if browser_context_only is None:
                context_probe = self._probe_browser_context(candidate)
                if context_probe.ok:
                    browser_context_only = _build_resolve_result(candidate, context_probe)

        if browser_context_only is not None:
            raise BrowserContextOnlyMp4Error(
                browser_context_only,
                "best mp4 candidate is only reachable with browser context/referer; no external-direct MP4 URL found",
            )
        raise RuntimeError("; ".join(probe_errors[-3:]) or "no externally accessible mp4 candidate found")

    def _probe_external_direct(self, candidate: Mp4Candidate) -> Mp4ProbeResult:
        req = request.Request(
            candidate.url,
            headers={
                "Range": "bytes=0-2047",
                "User-Agent": EXTERNAL_DIRECT_UA,
            },
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read(2048)
                content_type = response.headers.get("content-type") or candidate.content_type
                result = Mp4ProbeResult(
                    ok=response.status in {200, 206} and _looks_like_video_response(content_type, body),
                    access_mode="external_direct",
                    url=candidate.url,
                    final_url=response.url,
                    status_code=response.status,
                    content_type=content_type,
                    content_length=response.headers.get("content-length") or candidate.content_length,
                    content_range=response.headers.get("content-range"),
                )
                if not result.ok:
                    result.error_text = f"external probe returned HTTP {response.status} content_type={content_type or 'unknown'}"
                return result
        except error.HTTPError as exc:
            return Mp4ProbeResult(
                ok=False,
                access_mode="external_direct",
                url=candidate.url,
                final_url=getattr(exc, "url", None),
                status_code=exc.code,
                content_type=exc.headers.get("content-type") if exc.headers else None,
                content_length=exc.headers.get("content-length") if exc.headers else None,
                content_range=exc.headers.get("content-range") if exc.headers else None,
                error_text=f"external probe HTTP {exc.code}",
            )
        except Exception as exc:
            return Mp4ProbeResult(
                ok=False,
                access_mode="external_direct",
                url=candidate.url,
                error_text=f"external probe failed: {exc}",
            )

    def _probe_browser_context(self, candidate: Mp4Candidate) -> Mp4ProbeResult:
        try:
            response = self.context.request.get(
                candidate.url,
                headers={
                    "Range": "bytes=0-2047",
                    "Referer": "https://www.douyin.com/",
                    "User-Agent": EXTERNAL_DIRECT_UA,
                },
                timeout=30_000,
            )
            content_type = response.headers.get("content-type") or candidate.content_type
            body = response.body()
            result = Mp4ProbeResult(
                ok=response.status in {200, 206} and _looks_like_video_response(content_type, body),
                access_mode="browser_context_only",
                url=candidate.url,
                final_url=candidate.url,
                status_code=response.status,
                content_type=content_type,
                content_length=response.headers.get("content-length") or candidate.content_length,
                content_range=response.headers.get("content-range"),
            )
            if not result.ok:
                result.error_text = f"browser-context probe returned HTTP {response.status} content_type={content_type or 'unknown'}"
            return result
        except Exception as exc:
            return Mp4ProbeResult(
                ok=False,
                access_mode="browser_context_only",
                url=candidate.url,
                error_text=f"browser-context probe failed: {exc}",
            )


def extract_mp4_candidates(payload, target_video_id: str | None = None) -> list[Mp4Candidate]:
    candidates: list[Mp4Candidate] = []
    for node in _walk_relevant_json_nodes(payload, target_video_id=target_video_id):
        if not isinstance(node, dict):
            continue
        for key in ("play_addr", "play_url", "download_addr"):
            value = node.get(key)
            if not isinstance(value, dict):
                continue
            for url in value.get("url_list") or []:
                if not isinstance(url, str) or not _looks_like_mp4_url(url):
                    continue
                candidates.append(
                    Mp4Candidate(
                        url=url,
                        source=key,
                        data_size=_coerce_int(value.get("data_size")),
                        width=_coerce_int(value.get("width")),
                        height=_coerce_int(value.get("height")),
                    )
                )
    return _dedupe_candidates(candidates)


def select_best_candidate(
    candidates: list[Mp4Candidate],
    target_video_id: str | None = None,
) -> Mp4Candidate | None:
    deduped = _dedupe_candidates(candidates)
    if not deduped:
        return None
    return sorted_mp4_candidates(deduped, target_video_id=target_video_id)[0]


def sorted_mp4_candidates(
    candidates: list[Mp4Candidate],
    target_video_id: str | None = None,
) -> list[Mp4Candidate]:
    deduped = _dedupe_candidates(candidates)
    return sorted(deduped, key=lambda candidate: _candidate_sort_key(candidate, target_video_id), reverse=True)


def _candidate_sort_key(candidate: Mp4Candidate, target_video_id: str | None) -> tuple[int, int, int, int, int, int, int, int, int]:
    lowered = candidate.url.lower()
    host = urlparse(candidate.url).netloc.lower()
    params = parse_qs(urlparse(candidate.url).query)
    target_match = 1 if target_video_id and target_video_id in candidate.url else 0
    host_365yg = 1 if "365yg.com" in host else 0
    unwatermarked = 1 if params.get("lr", [""])[0] == "unwatermarked" or "unwatermarked" in lowered else 0
    app_zero = 1 if params.get("a", [""])[0] == "0" else 0
    download_source = 1 if candidate.source == "download_addr" else 0
    non_web_douyinvod = 1 if "douyinvod.com" in host and "-web." not in host else 0
    mp4_cdn = 1 if "mime_type=video_mp4" in lowered and ("douyinvod.com" in host or "365yg.com" in host) else 0
    aweme_play = 1 if "aweme/v1/play" in lowered else 0
    pixel_count = (candidate.width or 0) * (candidate.height or 0)
    data_size = candidate.data_size or _coerce_int(candidate.content_length) or 0
    bitrate = _coerce_int(params.get("br", [None])[0]) or _coerce_int(params.get("bt", [None])[0]) or 0
    non_media_response = 1 if candidate.source != "media_response" else 0
    return (
        target_match,
        host_365yg + unwatermarked + app_zero,
        download_source,
        non_web_douyinvod,
        mp4_cdn,
        aweme_play,
        bitrate,
        pixel_count + data_size,
        non_media_response,
    )


def _dedupe_candidates(candidates: list[Mp4Candidate]) -> list[Mp4Candidate]:
    seen: set[str] = set()
    deduped: list[Mp4Candidate] = []
    for candidate in candidates:
        if not candidate.url or candidate.url in seen:
            continue
        seen.add(candidate.url)
        deduped.append(candidate)
    return deduped


def _looks_like_mp4_url(url: str) -> bool:
    lowered = url.lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    host = urlparse(url).netloc.lower()
    if any(hint in lowered for hint in MEDIA_URL_HINTS):
        return True
    return any(hint in host for hint in MEDIA_HOST_HINTS) and "/video/" in lowered


def _looks_like_video_response(content_type: str | None, body: bytes) -> bool:
    lowered = (content_type or "").lower()
    if "video" in lowered or "octet-stream" in lowered:
        return True
    return b"ftyp" in body[:64] or body[:4] == b"\x00\x00\x00\x18"


def _walk_relevant_json_nodes(payload, target_video_id: str | None):
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            node_video_id = _node_video_id(node)
            if target_video_id and node_video_id and node_video_id != target_video_id:
                continue
            yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            yield node
            stack.extend(node)
        else:
            yield node


def _node_video_id(node: dict) -> str | None:
    for key in ("aweme_id", "item_id", "group_id"):
        value = node.get(key)
        if value is None:
            continue
        text = str(value)
        if text.isdigit():
            return text
    return None


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_resolve_result(candidate: Mp4Candidate, probe: Mp4ProbeResult) -> Mp4ResolveResult:
    return Mp4ResolveResult(
        direct_mp4_url=probe.final_url or candidate.url,
        source=candidate.source,
        access_mode=probe.access_mode,
        final_url=probe.final_url or candidate.url,
        content_type=probe.content_type or candidate.content_type,
        content_length=probe.content_length or candidate.content_length,
        probe_status_code=probe.status_code,
        probe_content_range=probe.content_range,
    )
