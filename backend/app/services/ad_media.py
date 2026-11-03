"""Fetch Meta Ad Library snapshots and lazily cache creative media in Cloudinary."""
import asyncio
import json
import re
import html as html_lib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def redact(value: object) -> str:
    """Redact Meta access tokens from all ad-media diagnostics."""
    return re.sub(r"(?i)(access_token\s*=\s*)[^&\s\"'<>]+", r"\1***", str(value))


class SnapshotHTTPError(Exception):
    def __init__(self, status_code: int, body: str, content_type: str = ""):
        self.status_code = status_code
        self.content_type = content_type[:120]
        # Keep a useful, sanitized diagnostic excerpt; Meta often puts the
        # actual rejection reason after the generic HTML page title.
        plain = re.sub(r"<(script|style)\\b[^>]*>.*?</\\1>", " ", body, flags=re.I | re.S)
        plain = re.sub(r"<[^>]+>", " ", plain)
        plain = html_lib.unescape(re.sub(r"\\s+", " ", plain)).strip()
        self.body = redact(plain[:1800])
        super().__init__(f"Meta snapshot returned HTTP {status_code}: {self.body}")


def _safe_meta_url(value: str) -> str | None:
    try:
        value = value.replace(r"\/", "/").replace(r"\u0026", "&")
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not (host.endswith(".fbcdn.net") or host.endswith(".facebook.com")):
            return None
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "access_token"]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    except Exception:
        return None


def _pick(html: str, key: str) -> list[str]:
    values = []
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:\s*"((?:\\.|[^"\\])*)"')
    for match in pattern.finditer(html):
        try:
            raw_value = json.loads('"' + match.group(1) + '"')
        except (ValueError, TypeError):
            continue
        safe = _safe_meta_url(raw_value) if isinstance(raw_value, str) else None
        if safe and safe not in values:
            values.append(safe)
    return values


async def fetch_snapshot_html(snapshot_url: str, token: str) -> str:
    normalized = html_lib.unescape(snapshot_url)
    parts = urlsplit(normalized)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in {"facebook.com", "www.facebook.com"}:
        raise ValueError("Invalid Meta snapshot URL")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "access_token"]
    query.append(("access_token", token))
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    import logging
    logger = logging.getLogger(__name__)
    logger.info("ad-media normalized snapshot URL=%s has_id=%s", redact(url), any(k == "id" and v for k, v in parse_qsl(urlsplit(url).query, keep_blank_values=True)))
    async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": UA, "Accept": "text/html"}) as client:
        response = await client.get(url)
        if response.status_code >= 400:
            body = response.text[:12000]
            safe_url = redact(str(response.url))
            content_type = response.headers.get("content-type", "")
            logger.warning(
                "ad-media snapshot rejected status=%s content_type=%s final_url=%s body_excerpt=%s",
                response.status_code, content_type[:120], safe_url,
                SnapshotHTTPError(response.status_code, body, content_type).body,
            )
            raise SnapshotHTTPError(response.status_code, body, content_type)
        return response.text[:8_000_000]


def extract_media(html: str) -> dict:
    """Extract CDN media by URL extension, independent of Meta JSON key names."""
    import html as html_lib

    normalized = html_lib.unescape(html)
    normalized = normalized.replace(r"\/", "/").replace(r"\u0026", "&")
    images: list[str] = []
    videos: list[str] = []
    posters: list[str] = []

    # Scan every absolute URL; only accept Meta CDN URLs and known media extensions.
    for match in re.finditer(r"""https://[^\s"'<>\\]+""", normalized, re.I):
        candidate = match.group(0).rstrip("),;]}\\")
        safe = _safe_meta_url(candidate)
        if not safe:
            continue
        path = urlsplit(safe).path.lower()
        if path.endswith(".mp4"):
            if safe not in videos:
                videos.append(safe)
        elif path.endswith((".jpg", ".jpeg", ".png", ".webp")):
            if safe not in images:
                images.append(safe)

    # Keep a poster image when Meta's snapshot exposes og:image.
    poster_match = re.search(
        r"""<meta[^>]+(?:property|name)=["']og:image["'][^>]+content=["']([^"']+)""",
        normalized,
        re.I,
    )
    if poster_match:
        poster = _safe_meta_url(poster_match.group(1))
        if poster and urlsplit(poster).path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            posters.append(poster)
            if poster not in images:
                images.insert(0, poster)

    return {"images": images[:10], "videos": videos[:1], "posters": posters[:1]}

def _upload_remote(url: str, public_id: str, resource_type: str, cloud_name: str, api_key: str, api_secret: str) -> str:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
    result = cloudinary.uploader.upload(url, public_id=public_id, folder="adspy", resource_type=resource_type, overwrite=True)
    return result["secure_url"]


async def persist_to_cloudinary(ad_id: str, media: dict, cloud_name: str, api_key: str, api_secret: str, with_video: bool = True) -> dict:
    result = {"images": [], "videos": [], "posters": []}
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(ad_id))[:100]
    jobs = []
    for index, url in enumerate(media.get("images", [])[:10]):
        jobs.append(("images", url, f"ad_{safe_id}_img_{index}", "image"))
    for index, url in enumerate(media.get("posters", [])[:1]):
        jobs.append(("posters", url, f"ad_{safe_id}_poster_{index}", "image"))
    if with_video:
        for index, url in enumerate(media.get("videos", [])[:1]):
            jobs.append(("videos", url, f"ad_{safe_id}_vid_{index}", "video"))
    for field, url, public_id, kind in jobs:
        try:
            uploaded = await asyncio.to_thread(_upload_remote, url, public_id, kind, cloud_name, api_key, api_secret)
            result[field].append(uploaded)
        except Exception:
            continue
    return result
