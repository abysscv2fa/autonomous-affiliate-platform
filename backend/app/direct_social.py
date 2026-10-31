"""Direct publishing adapters for Facebook Pages and Threads.

Credentials are supplied only through server-side environment variables.
This module never reports success until the platform returns a post identifier.
"""
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

GRAPH_VERSION = "v26.0"
THREADS_GRAPH_VERSION = "v1.0"


class SocialPublishError(RuntimeError):
    pass


def _request(url: str, method: str = "POST", data: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            result = json.loads(raw) if raw else {}
    except (HTTPError, URLError, TimeoutError) as exc:
        detail = getattr(exc, "read", lambda: b"")()
        message = detail.decode("utf-8", "ignore")[:700] if detail else str(exc)[:300]
        raise SocialPublishError(message) from exc
    if isinstance(result, dict) and result.get("error"):
        raise SocialPublishError(str(result["error"])[:700])
    return result


def publish_facebook(message: str, image_url: str | None = None) -> dict:
    from .config import settings
    if not settings.facebook_page_id or not settings.facebook_page_access_token:
        raise SocialPublishError("Facebook Page credentials are not configured.")
    edge = "photos" if image_url else "feed"
    payload = {"access_token": settings.facebook_page_access_token}
    if image_url:
        payload.update({"url": image_url, "caption": message})
    else:
        payload["message"] = message
    result = _request(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.facebook_page_id}/{edge}",
        data=payload,
    )
    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise SocialPublishError("Facebook did not return a post ID.")
    return {"platform": "facebook", "post_id": str(post_id)}


def _threads_safe_text(text: str, max_length: int = 500) -> tuple[str, bool]:
    """Keep the Threads API text parameter within its 500-character limit."""
    if len(text) <= max_length:
        return text, False
    shortened = text[: max_length - 3]
    # Avoid cutting a word in half where possible, while handling long unbroken URLs/tokens.
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened.rstrip() + "...", True


def publish_threads(text: str, image_url: str | None = None) -> dict:
    from .config import settings
    if not settings.threads_user_id or not settings.threads_access_token:
        raise SocialPublishError("Threads credentials are not configured.")
    text, was_truncated = _threads_safe_text(text)
    base = f"https://graph.threads.net/{THREADS_GRAPH_VERSION}/{settings.threads_user_id}"
    container = {"text": text}
    if image_url:
        container.update({"media_type": "IMAGE", "image_url": image_url})
    else:
        container["media_type"] = "TEXT"
    created = _request(
        f"{base}/threads",
        data={**container, "access_token": settings.threads_access_token},
    )
    creation_id = created.get("id")
    if not creation_id:
        raise SocialPublishError("Threads did not return a media container ID.")
    # Wait for asynchronous media processing before publishing.
    container_url = f"https://graph.threads.net/{THREADS_GRAPH_VERSION}/{creation_id}?fields=status,error_message"
    deadline = time.monotonic() + 30
    while True:
        status = _request(container_url, method="GET", token=settings.threads_access_token)
        state = str(status.get("status", "")).upper()
        if state == "FINISHED":
            break
        if state in {"ERROR", "EXPIRED"}:
            raise SocialPublishError(str(status.get("error_message") or ("Threads media container status: " + state))[:700])
        if time.monotonic() >= deadline:
            raise SocialPublishError("Threads media container did not finish processing (status: " + (state or "unknown") + ").")
        time.sleep(2)
    published = _request(
        f"{base}/threads_publish",
        data={"creation_id": creation_id, "access_token": settings.threads_access_token},
    )
    post_id = published.get("id")
    if not post_id:
        raise SocialPublishError("Threads did not return a published post ID.")
    return {"platform": "threads", "post_id": str(post_id), "text_truncated": was_truncated}

def publish_instagram(caption: str, image_url: str) -> dict:
    """Publish a single-image feed post to an Instagram Professional account."""
    from .config import settings
    if not settings.instagram_user_id or not settings.instagram_access_token:
        raise SocialPublishError("Instagram credentials are not configured.")
    if not image_url:
        raise SocialPublishError("Instagram feed publishing requires an image URL.")
    base = f"https://graph.facebook.com/{GRAPH_VERSION}/{settings.instagram_user_id}"
    container = _request(
        f"{base}/media",
        data={"image_url": image_url, "caption": caption, "access_token": settings.instagram_access_token},
    )
    creation_id = container.get("id")
    if not creation_id:
        raise SocialPublishError("Instagram did not return a media container ID.")
    published = _request(
        f"{base}/media_publish",
        data={"creation_id": creation_id, "access_token": settings.instagram_access_token},
    )
    post_id = published.get("id")
    if not post_id:
        raise SocialPublishError("Instagram did not return a published media ID.")
    return {"platform": "instagram", "post_id": str(post_id)}
