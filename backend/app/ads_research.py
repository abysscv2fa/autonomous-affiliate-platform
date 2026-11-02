import json
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=250)
    country: str = Field(default="US", min_length=2, max_length=2)
    ad_type: str = Field(default="ALL", pattern="^(ALL|POLITICAL_AND_ISSUE_ADS)$")


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
    started_running: str = Field(default="", max_length=40)
    active_status: str = Field(default="unknown", max_length=30)
    platforms: list[str] = Field(default_factory=list, max_length=10)


def library_url(query: str, country: str = "US", ad_type: str = "ALL") -> str:
    params = {
        "active_status": "active",
        "ad_type": ad_type if ad_type in {"ALL", "POLITICAL_AND_ISSUE_ADS"} else "ALL",
        "country": country.upper() if len(country) == 2 else "US",
        "q": query,
        "search_type": "keyword_unordered",
    }
    return "https://www.facebook.com/ads/library/?" + urlencode(params)


def serialize(item: FacebookAdResearch) -> dict:
    try:
        platforms = json.loads(item.platforms or "[]")
    except (TypeError, ValueError):
        platforms = []
    return {
        "id": item.id,
        "query": item.query,
        "country": item.country,
        "source": item.source,
        "ad_archive_id": item.ad_archive_id,
        "page_name": item.page_name,
        "ad_text": item.ad_text,
        "headline": item.headline,
        "description": item.description,
        "creative_url": item.creative_url,
        "ad_library_url": item.ad_library_url,
        "landing_page_url": item.landing_page_url,
        "started_running": item.started_running,
        "active_status": item.active_status,
        "platforms": platforms,
        "ai_analysis": item.ai_analysis,
        "opportunity_score": item.opportunity_score,
        "evidence_label": item.evidence_label,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/ads")
def list_ads(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(FacebookAdResearch)
        .order_by(FacebookAdResearch.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return [serialize(row) for row in rows]


@router.post("/search")
def search_ads(payload: SearchRequest):
    query = payload.query.strip()
    url = library_url(query, payload.country, payload.ad_type)
    return {
        "mode": "manual",
        "provider": "meta_ad_library_web",
        "market": payload.country.upper(),
        "ad_type": payload.ad_type,
        "search_url": url,
        "results": [],
        "message": (
            ("All active ads" if payload.ad_type == "ALL" else "Social issues, elections and politics ads") + " are searched in the public Meta Ad Library. "
            "Open the source, review an ad, and save only the public details you select. "
            "AffPilot does not scrape the page or claim private performance metrics."
        ),
    }


@router.post("/ads", status_code=201)
def save_ad(payload: SaveAdRequest, db: Session = Depends(get_db)):
    item = FacebookAdResearch(
        query=payload.query.strip(),
        country="US",
        source="manual",
        page_name=payload.page_name.strip(),
        ad_text=payload.ad_text.strip(),
        headline=payload.headline.strip(),
        description=payload.description.strip(),
        creative_url=payload.creative_url.strip(),
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
    score = 35
    if item.headline:
        score += 10
    if len(text) >= 120:
        score += 10
    if cta_terms:
        score += 10
    if offer_terms:
        score += 10
    if item.landing_page_url:
        score += 5
    if item.creative_url or item.ad_library_url:
        score += 5
    score = min(score, 85)
    return {
        "summary": "Rule-based review of the user-saved public ad copy; no external AI service was called.",
        "target_audience": "Hypothesis only: infer the likely audience from the product, problem, and wording; verify against the landing page.",
        "pain_point": "Review the first sentence and repeated product/problem terms for the main customer pain point.",
        "hook": first_line[:300],
        "offer": "Detected offer language: " + (", ".join(offer_terms) if offer_terms else "No explicit offer term detected."),
        "creative_strategy": "Inspect the original Ad Library creative. This text-only record cannot establish visual strategy.",
        "funnel_hypothesis": "Hypothesis only: ad click → landing page → product or lead conversion. Confirm each step from the supplied destination URL.",
        "risks": [
            "Ad Library presence does not prove profitability, conversion volume, or return on ad spend.",
            "Manual records are user-saved and have not been independently verified by Meta API.",
        ],
        "test_ideas": [
            "Test a problem-led hook against a benefit-led hook.",
            "Test a clearer call to action while keeping the offer and audience constant.",
            "Compare the ad promise with the landing-page headline.",
        ],
        "recurring_terms": [word for word, _ in common],
        "detected_cta_terms": cta_terms,
        "opportunity_score": score,
        "score_type": "Heuristic creative completeness score, not ad performance",
        "analysis_provider": "local_rules_free",
    }


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
                model=settings.openai_model,
                temperature=0.25,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Analyze the supplied user-saved public ad creative. Return JSON with "
                            "summary, target_audience, pain_point, hook, offer, creative_strategy, "
                            "funnel_hypothesis, risks, test_ideas (array), opportunity_score (integer 0-100). "
                            "Mark all inferences as hypotheses. Never claim spend, ROAS, conversions, "
                            "profitability, or winning status from ad-library presence or run time. "
                            "Score creative research attractiveness, not verified ad performance."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({
                            "page": item.page_name,
                            "copy": item.ad_text,
                            "headline": item.headline,
                            "description": item.description,
                            "country": "US",
                            "started_running": item.started_running,
                            "platforms": json.loads(item.platforms or "[]"),
                            "landing_page_url": item.landing_page_url,
                        }, ensure_ascii=False),
                    },
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
    return {
        "id": item.id,
        "analysis": data,
        "opportunity_score": item.opportunity_score,
        "score_type": data.get("score_type", "Creative research estimate, not ad performance"),
    }
