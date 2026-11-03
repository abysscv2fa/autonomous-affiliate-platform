import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, DateTime, Integer, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from .db import Base, get_db
from .config import settings

router = APIRouter(prefix="/api/ads-research", tags=["Meta Ad Library Research"])

EU_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]
META_FIELDS = ",".join([
    "id", "ad_creation_time", "ad_creative_bodies", "ad_creative_link_captions",
    "ad_creative_link_descriptions", "ad_creative_link_titles",
    "ad_delivery_start_time", "ad_delivery_stop_time", "ad_snapshot_url",
    "page_id", "page_name", "publisher_platforms", "eu_total_reach",
    "beneficiary_payers", "age_country_gender_reach_breakdown",
    "target_ages", "target_gender", "target_locations", "languages",
])


class FacebookAdResearch(Base):
    __tablename__ = "facebook_ad_research"

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String(250), default="")
    country: Mapped[str] = mapped_column(String(2), default="EU")
    source: Mapped[str] = mapped_column(String(30), default="meta_api")
    ad_archive_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    page_name: Mapped[str] = mapped_column(String(250), default="")
    ad_text: Mapped[str] = mapped_column(Text, default="")
    headline: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    creative_url: Mapped[str] = mapped_column(String(1500), default="")
    ad_library_url: Mapped[str] = mapped_column(String(1500), default="")
    landing_page_url: Mapped[str] = mapped_column(String(1500), default="")
    started_running: Mapped[str] = mapped_column(String(40), default="")
    active_status: Mapped[str] = mapped_column(String(30), default="unknown")
    platforms: Mapped[str] = mapped_column(Text, default="[]")
    eu_total_reach: Mapped[int] = mapped_column(Integer, default=0)
    beneficiary_payers: Mapped[str] = mapped_column(Text, default="[]")
    targeting_details: Mapped[str] = mapped_column(Text, default="{}")
    ai_analysis: Mapped[str] = mapped_column(Text, default="")
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    evidence_label: Mapped[str] = mapped_column(String(60), default="meta_api")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=100)
    market: str = Field(default="EU_UK", pattern="^(EU|UK|EU_UK)$")
    max_results: int = Field(default=200, ge=1, le=300)
    media_type: str = Field(default="ALL", pattern="^(ALL|IMAGE|VIDEO|MEME|NONE)$")


class SaveAdRequest(BaseModel):
    query: str = Field(default="", max_length=250)
    country: str = Field(default="EU", min_length=2, max_length=2)
    page_name: str = Field(default="", max_length=250)
    ad_text: str = Field(min_length=5, max_length=12000)
    headline: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    creative_url: str = Field(default="", max_length=1500)
    ad_library_url: str = Field(default="", max_length=1500)
    landing_page_url: str = Field(default="", max_length=1500)
    started_running: str = Field(default="", max_length=40)
    active_status: str = Field(default="unknown", max_length=30)
    platforms: list[str] = Field(default_factory=list, max_length=10)


def library_url(query: str, country: str = "GB") -> str:
    return "https://www.facebook.com/ads/library/?" + urlencode({
        "active_status": "all", "ad_type": "ALL", "country": country,
        "q": query, "search_type": "keyword_unordered",
    })


def _json(value, fallback):
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else fallback)
    except (TypeError, ValueError):
        return fallback


def serialize(item: FacebookAdResearch) -> dict:
    return {
        "id": item.id, "query": item.query, "country": item.country,
        "source": item.source, "ad_archive_id": item.ad_archive_id,
        "page_name": item.page_name, "ad_text": item.ad_text,
        "headline": item.headline, "description": item.description,
        "creative_url": (f"https://autonomous-affiliate-platform.onrender.com/api/ads-research/ads/{item.id}/preview" if item.source == "meta_api" and item.creative_url else item.creative_url),
        "ad_library_url": (f"https://www.facebook.com/ads/library/?id={item.ad_archive_id}" if item.ad_archive_id else item.ad_library_url),
        "landing_page_url": item.landing_page_url, "started_running": item.started_running,
        "active_status": item.active_status, "platforms": _json(item.platforms, []),
        "eu_total_reach": item.eu_total_reach,
        "beneficiary_payers": _json(item.beneficiary_payers, []),
        "targeting_details": _json(item.targeting_details, {}),
        "ai_analysis": _json(item.ai_analysis, {}),
        "opportunity_score": item.opportunity_score,
        "evidence_label": item.evidence_label,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/status")
def ads_api_status():
    return {
        "provider": "Meta Ad Library API",
        "connected": bool(settings.meta_ad_library_access_token.strip()),
        "graph_api_version": settings.meta_graph_api_version,
        "supported_markets": ["EU", "UK", "EU_UK"],
        "lookback_days": 365,
    }


@router.get("/ads")
def list_ads(limit: int = 100, market: str | None = None, db: Session = Depends(get_db)):
    stmt = select(FacebookAdResearch).order_by(FacebookAdResearch.created_at.desc())
    if market == "EU":
        stmt = stmt.where(FacebookAdResearch.country == "EU")
    elif market == "UK":
        stmt = stmt.where(FacebookAdResearch.country == "GB")
    rows = db.scalars(stmt.limit(max(1, min(limit, 300)))).all()
    return [serialize(row) for row in rows]


def _meta_get(url: str) -> dict:
    request = UrlRequest(url, headers={"Accept": "application/json", "User-Agent": "AffPilot-AdSpy/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw).get("error", {}).get("message", raw[:500])
        except (ValueError, AttributeError):
            detail = raw[:500]
        raise HTTPException(status_code=502, detail=f"Meta Graph API returned HTTP {exc.code}: {detail}")
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Meta Graph API: {str(exc)[:250]}")


def _meta_countries(market: str) -> list[str]:
    if market == "UK":
        return ["GB"]
    if market == "EU":
        return EU_COUNTRIES
    return EU_COUNTRIES + ["GB"]


def _text_list(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(x) for x in value if x)
    return str(value or "")


def _upsert_meta_ad(ad: dict, query: str, market: str, db: Session) -> FacebookAdResearch:
    archive_id = str(ad.get("id") or "")
    if not archive_id:
        return None
    row = db.scalar(select(FacebookAdResearch).where(
        FacebookAdResearch.ad_archive_id == archive_id
    ).limit(1))
    if row is None:
        row = FacebookAdResearch(ad_archive_id=archive_id)
        db.add(row)
    start = ad.get("ad_delivery_start_time") or ""
    stop = ad.get("ad_delivery_stop_time") or ""
    bodies = ad.get("ad_creative_bodies") or []
    titles = ad.get("ad_creative_link_titles") or []
    descriptions = ad.get("ad_creative_link_descriptions") or []
    reach = ad.get("eu_total_reach")
    row.query = query
    row.country = "GB" if market == "UK" else "EU"
    row.source = "meta_api"
    row.page_name = (ad.get("page_name") or "")[:250]
    row.ad_text = _text_list(bodies)
    row.headline = _text_list(titles)[:500]
    row.description = _text_list(descriptions)
    snapshot_url = ad.get("ad_snapshot_url") or ""
    # Never persist the Meta access token embedded in ad_snapshot_url.
    if snapshot_url:
        parts = urlsplit(snapshot_url)
        safe_query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "access_token"]
        snapshot_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_query), ""))
    row.creative_url = snapshot_url
    row.ad_library_url = f"https://www.facebook.com/ads/library/?id={archive_id}"
    row.started_running = start
    row.active_status = "inactive" if stop else "active"
    row.platforms = json.dumps(ad.get("publisher_platforms") or [])
    row.eu_total_reach = int(reach) if str(reach or "").isdigit() else 0
    row.beneficiary_payers = json.dumps(ad.get("beneficiary_payers") or [], ensure_ascii=False)
    row.targeting_details = json.dumps({
        "target_ages": ad.get("target_ages"),
        "target_gender": ad.get("target_gender"),
        "target_locations": ad.get("target_locations"),
        "age_country_gender_reach_breakdown": ad.get("age_country_gender_reach_breakdown"),
        "languages": ad.get("languages"),
        "page_id": ad.get("page_id"),
        "ad_creation_time": ad.get("ad_creation_time"),
    }, ensure_ascii=False)
    row.evidence_label = "official_meta_ad_library_api"
    return row


@router.post("/search")
def search_ads(payload: SearchRequest, db: Session = Depends(get_db)):
    token = (settings.meta_ad_library_access_token or "").strip()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Meta Ad Library API chưa được kết nối. Hoàn tất xác minh tài khoản Meta, tạo Developer App và thêm META_AD_LIBRARY_ACCESS_TOKEN trên Render.",
        )
    query = payload.query.strip()
    countries = _meta_countries(payload.market)
    today = datetime.now(timezone.utc).date()
    date_min = (today - timedelta(days=365)).isoformat()
    params = {
        "access_token": token,
        "ad_reached_countries": json.dumps(countries),
        "ad_type": "ALL",
        "media_type": payload.media_type,
        "ad_active_status": "ALL",
        "ad_delivery_date_min": date_min,
        "search_terms": query,
        "search_type": "KEYWORD_UNORDERED",
        "fields": META_FIELDS,
        "limit": min(100, payload.max_results),
    }
    version = (settings.meta_graph_api_version or "v22.0").strip()
    url = f"https://graph.facebook.com/{version}/ads_archive?{urlencode(params)}"
    collected = []
    pages = 0
    while url and len(collected) < payload.max_results and pages < 3:
        response = _meta_get(url)
        data = response.get("data") or []
        for ad in data:
            row = _upsert_meta_ad(ad, query, payload.market, db)
            if row is not None:
                collected.append(row)
        pages += 1
        url = (response.get("paging") or {}).get("next")
    db.commit()
    for row in collected:
        db.refresh(row)
    return {
        "mode": "api",
        "provider": "meta_ad_library_api",
        "market": payload.market,
        "countries": countries,
        "query": query,
        "lookback_days": 365,
        "count": len(collected),
        "pages_fetched": pages,
        "results": [serialize(row) for row in collected],
        "message": f"Meta API returned {len(collected)} ads for {payload.market}. Results were saved to the AffPilot research library.",
    }


@router.post("/ads", status_code=201)
def save_ad(payload: SaveAdRequest, db: Session = Depends(get_db)):
    item = FacebookAdResearch(
        query=payload.query.strip(), country=payload.country.upper(),
        source="manual", page_name=payload.page_name.strip(),
        ad_text=payload.ad_text.strip(), headline=payload.headline.strip(),
        description=payload.description.strip(), creative_url=payload.creative_url.strip(),
        ad_library_url=payload.ad_library_url.strip() or library_url(
            payload.query.strip() or payload.ad_text[:80]
        ),
        landing_page_url=payload.landing_page_url.strip(),
        started_running=payload.started_running.strip(),
        active_status=payload.active_status.strip() or "unknown",
        platforms=json.dumps(payload.platforms),
        evidence_label="user_saved_unverified",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize(item)


def free_creative_analysis(item: FacebookAdResearch) -> dict:
    text = " ".join([item.headline or "", item.ad_text or "", item.description or ""]).strip()
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())
    common = Counter(w for w in words if w not in {
        "the", "and", "for", "you", "your", "with", "that", "this", "are",
        "our", "from", "have", "get", "can", "all", "now", "more", "was",
        "but", "not", "will", "they", "their", "how", "what", "when",
    }).most_common(6)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    first_line = sentences[0] if sentences else text[:220]
    cta_terms = [w for w in ("shop", "learn", "discover", "get", "try", "start", "claim", "order", "join", "download") if re.search(rf"\b{w}\b", text, re.I)]
    offer_terms = [w for w in ("free", "discount", "save", "off", "bonus", "trial", "guarantee", "limited") if re.search(rf"\b{w}\b", text, re.I)]
    score = 35 + (10 if item.headline else 0) + (10 if len(text) >= 120 else 0)
    score += (10 if cta_terms else 0) + (10 if offer_terms else 0)
    score += 5 if item.landing_page_url else 0
    score += 5 if item.creative_url or item.ad_library_url else 0
    return {
        "summary": "Rule-based review of public ad creative; no external AI service was called.",
        "target_audience": "Hypothesis only: infer the likely audience from the product, problem, and wording; verify against the landing page.",
        "pain_point": "Review the first sentence and repeated product/problem terms for the main customer pain point.",
        "hook": first_line[:300],
        "offer": "Detected offer language: " + (", ".join(offer_terms) if offer_terms else "No explicit offer term detected."),
        "creative_strategy": "Inspect the original Ad Library creative. This text-only record cannot establish visual strategy.",
        "funnel_hypothesis": "Hypothesis only: ad click → landing page → product or lead conversion.",
        "risks": [
            "Ad Library presence does not prove profitability, conversion volume, or return on ad spend.",
            "EU reach is an estimate supplied by Meta, not advertiser spend or sales.",
        ],
        "test_ideas": [
            "Test a problem-led hook against a benefit-led hook.",
            "Test a clearer call to action while keeping the offer and audience constant.",
            "Compare the ad promise with the landing-page headline.",
        ],
        "recurring_terms": [word for word, _ in common],
        "detected_cta_terms": cta_terms,
        "opportunity_score": min(score, 85),
        "score_type": "Heuristic creative completeness score, not ad performance",
        "analysis_provider": "local_rules_free",
    }


@router.get("/ads/{ad_id}/preview")
def preview_ad(ad_id: int, db: Session = Depends(get_db)):
    """Proxy the individual Meta snapshot so the long-lived API token stays server-side."""
    item = db.get(FacebookAdResearch, ad_id)
    if not item or not item.creative_url:
        raise HTTPException(404, "Meta ad snapshot is not available for this record")
    token = (settings.meta_ad_library_access_token or "").strip()
    if not token:
        raise HTTPException(503, "Meta Ad Library API is not connected")
    parts = urlsplit(item.creative_url)
    if parts.scheme != "https" or not ((parts.hostname or "") == "facebook.com" or (parts.hostname or "").endswith(".facebook.com")):
        raise HTTPException(400, "Invalid Meta snapshot URL")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "access_token"]
    query.append(("access_token", token))
    snapshot_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    request = UrlRequest(snapshot_url, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 AffPilot-AdSpy/1.0"})
    try:
        with urlopen(request, timeout=25) as upstream:
            html = upstream.read(8_000_000).decode("utf-8", "replace")
            # Meta's snapshot HTML uses root-relative asset and AJAX URLs. Since
            # this document is served from our backend proxy, browsers would
            # otherwise send those requests back to AffPilot (causing 401/404).
            # Set the document base to the validated Facebook origin so all
            # relative resources and follow-up requests go to Meta directly.
            from html import escape
            final_parts = urlsplit(upstream.geturl())
            safe_base_query = [(k, v) for k, v in parse_qsl(final_parts.query, keep_blank_values=True) if k != "access_token"]
            base_url = urlunsplit((final_parts.scheme, final_parts.netloc, final_parts.path, urlencode(safe_base_query), ""))
            base_tag = f'<base href="{escape(base_url, quote=True)}">'
            head_match = re.search(r"<head\b[^>]*>", html, flags=re.IGNORECASE)
            if head_match:
                html = html[:head_match.end()] + base_tag + html[head_match.end():]
            else:
                html = base_tag + html
            # Never reflect the server-side bearer token into the browser HTML.
            html = html.replace(token, "")
            return Response(
                content=html, media_type="text/html",
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
            )
    except HTTPError as exc:
        raise HTTPException(502, f"Meta snapshot returned HTTP {exc.code}")
    except (URLError, TimeoutError) as exc:
        raise HTTPException(502, f"Could not load Meta snapshot: {str(exc)[:200]}")



def _extract_snapshot_media(html: str) -> dict:
    """Best-effort extraction of public creative media URLs from Meta's snapshot HTML."""
    found = {"images": [], "videos": [], "poster": ""}
    patterns = {
        "images": ("original_image_url", "resized_image_url", "image_url"),
        "videos": ("video_hd_url", "video_sd_url"),
    }
    for target, keys in patterns.items():
        for key in keys:
            pattern = r"""["']""" + re.escape(key) + r"""["']\s*:\s*["']([^"']+)["']"""
            for match in re.finditer(pattern, html):
                raw = match.group(1)
                try:
                    value = json.loads('"' + raw.replace('"', '\\"') + '"')
                except (ValueError, TypeError):
                    value = raw.replace("\\/", "/").replace("\\u0026", "&")
                parts = urlsplit(value)
                host = (parts.hostname or "").lower()
                if parts.scheme == "https" and (host.endswith(".fbcdn.net") or host.endswith(".facebook.com")):
                    clean_query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "access_token"]
                    safe_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(clean_query), ""))
                    if safe_url not in found[target]:
                        found[target].append(safe_url)
    poster_match = re.search(r"""<meta[^>]+(?:property|name)=["']og:image["'][^>]+content=["']([^"']+)""", html, re.I)
    if poster_match:
        value = poster_match.group(1).replace("&amp;", "&")
        parts = urlsplit(value)
        if parts.scheme == "https" and ((parts.hostname or "").lower().endswith(".fbcdn.net")):
            found["poster"] = value
            if value not in found["images"]:
                found["images"].insert(0, value)
    return found


@router.get("/ads/{ad_id}/media")
def preview_ad_media(ad_id: int, db: Session = Depends(get_db)):
    """Return extracted creative media URLs; Meta token remains server-side."""
    item = db.get(FacebookAdResearch, ad_id)
    if not item or not item.creative_url:
        raise HTTPException(404, "Meta ad snapshot is not available for this record")
    token = (settings.meta_ad_library_access_token or "").strip()
    if not token:
        raise HTTPException(503, "Meta Ad Library API is not connected")
    parts = urlsplit(item.creative_url)
    if parts.scheme != "https" or not ((parts.hostname or "") == "facebook.com" or (parts.hostname or "").endswith(".facebook.com")):
        raise HTTPException(400, "Invalid Meta snapshot URL")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "access_token"]
    query.append(("access_token", token))
    snapshot_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    request = UrlRequest(snapshot_url, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0 AffPilot-AdSpy/1.0"})
    try:
        with urlopen(request, timeout=25) as upstream:
            html = upstream.read(8_000_000).decode("utf-8", "replace")
    except HTTPError as exc:
        raise HTTPException(502, f"Meta snapshot returned HTTP {exc.code}")
    except (URLError, TimeoutError) as exc:
        raise HTTPException(502, f"Could not load Meta snapshot: {str(exc)[:200]}")
    media = _extract_snapshot_media(html)
    media["ad_library_url"] = item.ad_library_url
    media["source"] = "meta_snapshot_html"
    media["message"] = ("Media links extracted from Meta snapshot." if media["images"] or media["videos"]
                        else "Meta snapshot HTML did not expose direct media URLs; use Open original in Meta.")
    return media


@router.post("/ads/{ad_id}/analyze")
def analyze_ad(ad_id: int, db: Session = Depends(get_db)):
    item = db.get(FacebookAdResearch, ad_id)
    if not item:
        raise HTTPException(404, "Ad research record not found")
    data = None
    if settings.openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model, temperature=0.25,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": (
                        "Analyze the supplied public ad creative. Return JSON with summary, target_audience, "
                        "pain_point, hook, offer, creative_strategy, funnel_hypothesis, risks, test_ideas (array), "
                        "opportunity_score (integer 0-100). Mark inferences as hypotheses. Never claim spend, "
                        "ROAS, conversions, or profitability from ad-library presence or run time."
                    )},
                    {"role": "user", "content": json.dumps({
                        "page": item.page_name, "copy": item.ad_text, "headline": item.headline,
                        "description": item.description, "country": item.country,
                        "started_running": item.started_running,
                        "platforms": _json(item.platforms, []),
                        "landing_page_url": item.landing_page_url,
                        "eu_total_reach": item.eu_total_reach,
                        "beneficiary_payers": _json(item.beneficiary_payers, []),
                        "targeting_details": _json(item.targeting_details, {}),
                    }, ensure_ascii=False)},
                ],
            )
            data = json.loads(response.choices[0].message.content or "{}")
            data["analysis_provider"] = "openai"
            data["score_type"] = "AI creative opportunity estimate, not ad performance"
        except Exception:
            data = None
    if data is None:
        data = free_creative_analysis(item)
    item.ai_analysis = json.dumps(data, ensure_ascii=False)
    item.opportunity_score = max(0, min(100, int(data.get("opportunity_score", 0))))
    db.commit()
    return {"id": item.id, "analysis": data, "opportunity_score": item.opportunity_score,
            "score_type": data.get("score_type", "Creative research estimate, not ad performance")}
