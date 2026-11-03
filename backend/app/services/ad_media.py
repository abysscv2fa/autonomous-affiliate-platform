"""Fetch Meta Ad Library snapshots and lazily cache creative media in Cloudinary."""
import asyncio
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


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
    parts = urlsplit(snapshot_url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in {"facebook.com", "www.facebook.com"}:
        raise ValueError("Invalid Meta snapshot URL")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "access_token"]
    query.append(("access_token", token))
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": UA, "Accept": "text/html"}) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text[:8_000_000]


def extract_media(html: str) -> dict:
    images = _pick(html, "original_image_url") or _pick(html, "resized_image_url") or _pick(html, "image_url")
    videos = _pick(html, "video_hd_url") or _pick(html, "video_sd_url")
    posters = _pick(html, "video_preview_image_url")
    if not posters:
        match = re.search(r"""<meta[^>]+(?:property|name)=["']og:image["'][^>]+content=["']([^"']+)""", html, re.I)
        if match:
            safe = _safe_meta_url(match.group(1).replace("&amp;", "&"))
            if safe:
                posters.append(safe)
                if not images:
                    images.append(safe)

    # Fallback: Meta sometimes changes embedded JSON field names.
    normalized = html.replace(r"\/", "/").replace(r"\u0026", "&").replace("&amp;", "&")
    for match in re.finditer(r"""https://[^\s"'<>]+""", normalized):
        safe = _safe_meta_url(match.group(0).rstrip("),;"))
        if not safe:
            continue
        if re.search(r"""\.(?:mp4|m3u8)(?:$|[?])""", safe, re.I):
            if safe not in videos:
                videos.append(safe)
        elif safe not in images:
            images.append(safe)
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
