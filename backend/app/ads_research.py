import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, DateTime, Integer, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from .db import Base, get_db
from .config import settings

router = APIRouter(prefix="/api/ads-research", tags=["Facebook Ads Research"])

class FacebookAdResearch(Base):
    __tablename__ = "facebook_ad_research"
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String(250), default="")
    country: Mapped[str] = mapped_column(String(2), default="US")
    source: Mapped[str] = mapped_column(String(30), default="manual")
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
    ai_analysis: Mapped[str] = mapped_column(Text, default="")
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    evidence_label: Mapped[str] = mapped_column(String(60), default="user_saved_unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=250)
    country: str = Field(default="US", min_length=2, max_length=2)
    mode: str = Field(default="manual", pattern="^(manual|auto)$")
    active_only: bool = True

class SaveAdRequest(BaseModel):
    query: str = Field(default="", max_length=250)
    country: str = Field(default="US", min_length=2, max_length=2)
    page_name: str = Field(default="", max_length=250)
    ad_text: str = Field(min_length=5, max_length=12000)
    headline: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=5000)
    creative_url: str = Field(default="", max_length=1500)
    ad_library_url: str = Field(default="", max_length=1500)
    landing_page_url: str = Field(default="", max_length=1500)
    source: str = Field(default="manual", pattern="^(manual|meta_ad_library_api)$")
    ad_archive_id: str = Field(default="", max_length=160)
    started_running: str = Field(default="", max_length=40)
    active_status: str = Field(default="unknown", max_length=30)
    platforms: list[str] = Field(default_factory=list, max_length=10)
    evidence_label: str = Field(default="user_saved_unverified", max_length=60)

def library_url(query: str, country: str) -> str:
    params = {"active_status": "active", "ad_type": "ALL", "country": country.upper(), "q": query, "search_type": "keyword_unordered"}
    return "https://www.facebook.com/ads/library/?" + urlencode(params)

def serialize(item: FacebookAdResearch) -> dict:
    try:
        platforms = json.loads(item.platforms or "[]")
    except Exception:
        platforms = []
    return {"id": item.id, "query": item.query, "country": item.country, "source": item.source,
            "ad_archive_id": item.ad_archive_id, "page_name": item.page_name, "ad_text": item.ad_text,
            "headline": item.headline, "description": item.description, "creative_url": item.creative_url,
            "ad_library_url": item.ad_library_url, "landing_page_url": item.landing_page_url,
            "started_running": item.started_running, "active_status": item.active_status,
            "platforms": platforms, "ai_analysis": item.ai_analysis, "opportunity_score": item.opportunity_score,
            "evidence_label": item.evidence_label, "created_at": item.created_at.isoformat() if item.created_at else None}

@router.get("/ads")
def list_ads(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(FacebookAdResearch).order_by(FacebookAdResearch.created_at.desc()).limit(max(1, min(limit, 200)))).all()
    return [serialize(row) for row in rows]

@router.post("/search")
def search_ads(payload: SearchRequest):
    country = payload.country.upper()
    url = library_url(payload.query, country)
    if payload.mode == "manual":
        return {"mode": "manual", "provider": "meta_ad_library_web", "search_url": url, "results": [],
                "message": "Mở Meta Ad Library để xem kết quả. Lưu quảng cáo vào AffPilot bằng cách nhập nội dung công khai; website không tự đọc dữ liệu từ tab trình duyệt."}
    # Meta's public Ad Library API provides comprehensive commercial-ad access for ads delivered in the EU.
    # For other markets, API access is generally limited to political/social-issue ads.
    eu_countries = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE","GB"}
    if country not in eu_countries:
        return {"mode": "auto", "provider": "meta_ad_library_api", "search_url": url, "results": [],
                "status": "region_not_supported_for_commercial_ads",
                "message": "Meta Ad Library API không cung cấp dữ liệu quảng cáo thương mại đầy đủ cho thị trường này. Dùng Manual Research hoặc nhà cung cấp dữ liệu được cấp phép; không giả lập kết quả."}
    token = settings.meta_ad_library_access_token
    if not token:
        return {"mode": "auto", "provider": "meta_ad_library_api", "search_url": url, "results": [],
                "status": "credentials_required",
                "message": "Chưa cấu hình META_AD_LIBRARY_ACCESS_TOKEN. Manual Research vẫn hoạt động."}
    params = {"access_token": token, "ad_reached_countries": json.dumps([country]),
              "ad_type": "ALL", "search_terms": payload.query,
              "ad_active_status": "ACTIVE" if payload.active_only else "ALL",
              "fields": "id,page_name,ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,ad_snapshot_url,publisher_platforms,ad_delivery_start_time,ad_delivery_stop_time",
              "limit": "50"}
    endpoint = f"https://graph.facebook.com/{settings.meta_graph_api_version}/ads_archive?{urlencode(params)}"
    try:
        req = Request(endpoint, headers={"Accept": "application/json", "User-Agent": "AffPilot/1.0"})
        with urlopen(req, timeout=25) as response:
            payload_data = json.loads(response.read().decode("utf-8"))
        results = []
        for ad in payload_data.get("data", []):
            bodies = ad.get("ad_creative_bodies") or []
            titles = ad.get("ad_creative_link_titles") or []
            descriptions = ad.get("ad_creative_link_descriptions") or []
            results.append({"ad_archive_id": ad.get("ad_archive_id") or ad.get("id") or "",
                            "page_name": ad.get("page_name") or "", "ad_text": bodies[0] if bodies else "",
                            "headline": titles[0] if titles else "", "description": descriptions[0] if descriptions else "",
                            "ad_library_url": ad.get("ad_snapshot_url") or "", "started_running": ad.get("ad_delivery_start_time") or "",
                            "active_status": "active" if not ad.get("ad_delivery_stop_time") else "inactive",
                            "platforms": ad.get("publisher_platforms") or [], "source": "meta_ad_library_api",
                            "evidence_label": "meta_api_public_data"})
        return {"mode": "auto", "provider": "meta_ad_library_api", "search_url": url,
                "status": "ok", "count": len(results), "results": results,
                "paging": payload_data.get("paging", {})}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:600]
        raise HTTPException(502, f"Meta Ad Library API returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(502, f"Could not retrieve Meta Ad Library data: {str(exc)[:300]}") from exc

@router.post("/ads", status_code=201)
def save_ad(payload: SaveAdRequest, db: Session = Depends(get_db)):
    item = FacebookAdResearch(query=payload.query, country=payload.country.upper(), source="manual",
        page_name=payload.page_name, ad_text=payload.ad_text, headline=payload.headline,
        description=payload.description, creative_url=payload.creative_url,
        ad_library_url=payload.ad_library_url or library_url(payload.query or payload.ad_text[:80], payload.country),
        landing_page_url=payload.landing_page_url, source=payload.source, ad_archive_id=payload.ad_archive_id,\n        started_running=payload.started_running, active_status=payload.active_status, platforms=json.dumps(payload.platforms),\n        evidence_label=payload.evidence_label if payload.source == "meta_ad_library_api" else "user_saved_unverified")
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize(item)

@router.post("/ads/{ad_id}/analyze")
def analyze_ad(ad_id: int, db: Session = Depends(get_db)):
    item = db.get(FacebookAdResearch, ad_id)
    if not item:
        raise HTTPException(404, "Ad research record not found")
    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY is not configured.")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model, temperature=0.25, response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Analyze the supplied public ad creative as a marketing research analyst. Return JSON with: summary, target_audience, pain_point, hook, offer, creative_strategy, funnel_hypothesis, risks, test_ideas (array), opportunity_score (integer 0-100). Never claim spend, ROAS, conversions, profitability, or winning status from ad-library presence or run time. Clearly label hypotheses. Score creative/research attractiveness, not verified performance."},
                {"role": "user", "content": json.dumps({"page": item.page_name, "copy": item.ad_text, "headline": item.headline, "description": item.description, "country": item.country, "started_running": item.started_running, "platforms": json.loads(item.platforms or "[]")}, ensure_ascii=False)}
            ])
        data = json.loads(response.choices[0].message.content or "{}")
        item.ai_analysis = json.dumps(data, ensure_ascii=False)
        item.opportunity_score = max(0, min(100, int(data.get("opportunity_score", 0))))
        db.commit()
        return {"id": item.id, "analysis": data, "opportunity_score": item.opportunity_score,
                "score_type": "AI creative opportunity estimate, not ad performance"}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, f"AI ad analysis failed: {str(exc)[:300]}") from exc
