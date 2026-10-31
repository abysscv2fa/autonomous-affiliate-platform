import json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .config import settings
from .db import Base, engine, get_db
from .models import Campaign, ContentDraft, Conversion, ResearchOpportunity
from .schemas import CampaignCreate, CampaignOut, DraftCreate, DraftOut, ConversionCreate, OpportunityCreate, OpportunityOut
from .research import score_opportunity, ai_research_brief

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Autonomous Affiliate Platform API", version="0.2.0")
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "affiliate-api"}

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    campaigns = db.scalar(select(func.count()).select_from(Campaign)) or 0
    drafts = db.scalar(select(func.count()).select_from(ContentDraft)) or 0
    earned = db.scalar(select(func.coalesce(func.sum(Conversion.commission), 0)).where(Conversion.status == "confirmed")) or 0
    return {"campaigns": campaigns, "content_drafts": drafts, "confirmed_commission": float(earned), "currency": "USD"}

@app.get("/api/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return list(db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all())

@app.post("/api/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    item = Campaign(name=payload.name, niche=payload.niche, network=payload.network)
    db.add(item); db.commit(); db.refresh(item)
    return item

@app.post("/api/campaigns/{campaign_id}/drafts", response_model=DraftOut, status_code=201)
def create_draft(campaign_id: int, payload: DraftCreate, db: Session = Depends(get_db)):
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, "Campaign not found")
    draft = ContentDraft(campaign_id=campaign_id, title=payload.title, body=payload.body, status="draft")
    db.add(draft); db.commit(); db.refresh(draft)
    return draft

@app.post("/api/drafts/{draft_id}/approve", response_model=DraftOut)
def approve_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")
    draft.status = "approved"
    db.commit(); db.refresh(draft)
    return draft

@app.post("/api/conversions", status_code=201)
def record_conversion(payload: ConversionCreate, db: Session = Depends(get_db)):
    if not db.get(Campaign, payload.campaign_id):
        raise HTTPException(404, "Campaign not found")
    if db.scalar(select(Conversion).where(Conversion.external_order_id == payload.external_order_id)):
        raise HTTPException(409, "Duplicate external order id")
    if payload.status not in {"pending", "confirmed", "reversed"}:
        raise HTTPException(422, "Invalid conversion status")
    item = Conversion(**payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "status": item.status, "commission": item.commission, "currency": item.currency}

@app.get("/api/campaigns/{campaign_id}/drafts", response_model=list[DraftOut])
def list_drafts(campaign_id: int, db: Session = Depends(get_db)):
    return list(db.scalars(select(ContentDraft).where(ContentDraft.campaign_id == campaign_id).order_by(ContentDraft.created_at.desc())).all())

@app.get("/api/research/opportunities", response_model=list[OpportunityOut])
def list_opportunities(db: Session = Depends(get_db)):
    return list(db.scalars(select(ResearchOpportunity).order_by(ResearchOpportunity.score.desc(), ResearchOpportunity.created_at.desc())).all())

@app.post("/api/research/opportunities", response_model=OpportunityOut, status_code=201)
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)):
    item = ResearchOpportunity(**payload.model_dump())
    item.score, breakdown, item.recommendation = score_opportunity(item)
    item.score_breakdown = json.dumps(breakdown)
    db.add(item); db.commit(); db.refresh(item)
    return item

@app.post("/api/research/opportunities/{opportunity_id}/analyze")
def analyze_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    item = db.get(ResearchOpportunity, opportunity_id)
    if not item:
        raise HTTPException(404, "Opportunity not found")
    item.score, breakdown, item.recommendation = score_opportunity(item)
    item.score_breakdown = json.dumps(breakdown)
    brief = ai_research_brief(item)
    item.ai_brief = brief["brief"]
    db.commit()
    return {"id": item.id, "score": item.score, "score_breakdown": breakdown, "recommendation": item.recommendation, **brief}

@app.post("/api/setup/saas-starter")
def setup_saas_starter(db: Session = Depends(get_db)):
    """Idempotently seed a small SaaS shortlist using published vendor terms."""
    campaign = db.scalar(select(Campaign).where(Campaign.name == "SaaS Tools for Small Businesses"))
    if not campaign:
        campaign = Campaign(name="SaaS Tools for Small Businesses", niche="software", network="direct / PartnerStack / Impact")
        db.add(campaign)
        db.flush()
    catalog = [
        {"product_name": "systeme.io", "vendor_name": "systeme.io", "network": "Direct", "source_url": "https://systeme.io/affiliate-program", "commission_pct": 60, "recurring": True, "evidence_quality": 5, "audience_fit": 4, "differentiation": "All-in-one funnels, email marketing and online course platform for solo founders and small businesses.", "research_notes": "Official vendor page states 60% lifetime commission. Verify payout setup and applicable terms in the affiliate dashboard."},
        {"product_name": "HubSpot", "vendor_name": "HubSpot", "network": "Impact", "source_url": "https://www.hubspot.com/partners/affiliates", "commission_pct": 30, "recurring": True, "evidence_quality": 5, "audience_fit": 4, "differentiation": "CRM and marketing platform for growing businesses; stronger fit for educational comparison and setup content.", "research_notes": "Official vendor page states 30% recurring for up to one year and a 180-day cookie. Application/review required."},
        {"product_name": "Thinkific", "vendor_name": "Thinkific", "network": "PartnerStack", "source_url": "https://www.thinkific.com/affiliates/", "commission_pct": 30, "recurring": True, "evidence_quality": 5, "audience_fit": 3, "differentiation": "Online course platform for experts, educators and businesses monetizing knowledge.", "research_notes": "Official vendor page states 30% lifetime recurring on standard paid plans; Plus plans have a different fixed commission. 90-day cookie."}
    ]
    added = 0
    for data in catalog:
        exists = db.scalar(select(ResearchOpportunity).where(ResearchOpportunity.product_name == data["product_name"]))
        if exists:
            continue
        item = ResearchOpportunity(category="software", target_regions="US,UK,EU", price_usd=0, **data)
        item.score, breakdown, item.recommendation = score_opportunity(item)
        item.score_breakdown = json.dumps(breakdown)
        db.add(item)
        added += 1
    db.commit()
    return {"campaign_id": campaign.id, "campaign": campaign.name, "opportunities_added": added, "opportunities_total": db.scalar(select(func.count()).select_from(ResearchOpportunity)) or 0}

@app.get("/api/research/networks")
def affiliate_network_catalog():
    return [
        {"name": "Awin", "best_for": "Retail and ecommerce brands across the UK and Europe", "cost": "Publisher joining terms vary by region; verify current signup terms", "url": "https://www.awin.com/gb/", "priority": 1},
        {"name": "CJ Affiliate", "best_for": "Established US and international advertisers", "cost": "Publisher account signup is free; advertiser approvals are separate", "url": "https://www.cj.com/join", "priority": 2},
        {"name": "PartnerStack", "best_for": "B2B SaaS and recurring software partnerships", "cost": "Apply as a partner; individual programs approve partners", "url": "https://partnerstack.com/our-partner-program/partners-affiliate", "priority": 1},
        {"name": "Amazon Associates", "best_for": "Physical products and buyer-intent comparison content", "cost": "No paid inventory; separate locale applications and program rules apply", "url": "https://affiliate-program.amazon.com/", "priority": 3}
    ]
