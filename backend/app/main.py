import json
import secrets
import base64
from datetime import date, datetime, time, timedelta, timezone
from pydantic import BaseModel, Field
from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from zoneinfo import ZoneInfo
from sqlalchemy import inspect, text
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .config import settings
from .db import Base, engine, get_db
from .models import Campaign, ContentDraft, Conversion, ResearchOpportunity, ActivityLog, MediaAsset, AppSetting, AgentMessage
from .schemas import CampaignCreate, CampaignOut, DraftCreate, DraftOut, ConversionCreate, OpportunityCreate, OpportunityOut
from .research import score_opportunity, ai_research_brief

Base.metadata.create_all(bind=engine)
# Backward-compatible column addition for existing deployments.
if 'image_url' not in {c['name'] for c in inspect(engine).get_columns('content_drafts')}:
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE content_drafts ADD COLUMN image_url VARCHAR(1500)'))

def log_activity(db: Session, event_type: str, message: str, status: str = "success", details: dict | None = None):
    db.add(ActivityLog(event_type=event_type, message=message, status=status, details=json.dumps(details or {}, ensure_ascii=False)))

app = FastAPI(title="Autonomous Affiliate Platform API", version="0.2.0")
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PublishRequest(BaseModel):
    date_time: str = Field(min_length=16, max_length=19)
    networks: list[str] = Field(min_length=1)

class PublishSettingsRequest(BaseModel):
    auto_publish: bool

class GenerateImageRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=1800)
    draft_id: int | None = None

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

@app.post("/api/autopilot/run")
def run_autopilot(db: Session = Depends(get_db)):
    """Create a deduplicated batch of three daily affiliate content drafts."""
    campaign = db.scalar(select(Campaign).where(Campaign.name == "SaaS Tools for Small Businesses"))
    if not campaign:
        raise HTTPException(409, "Load the SaaS starter shortlist first")
    affiliate_url = "https://systeme.io/fr?sa=sa028522389209c1b0fb00f4f72d0250aa9dca6f5f"
    today = date.today().isoformat()
    templates = [
        ("Beginner guide: what systeme.io does for a small business", f"""Starting an online business often means comparing separate tools for landing pages, email marketing, sales funnels and online courses. systeme.io combines several of these functions in one platform.

WHO MAY FIND IT USEFUL
Solo founders, creators and small teams who want to test an online offer without stitching together many separate services.

A SIMPLE WAY TO EVALUATE IT
Map one real workflow: publish a landing page, collect a lead, send a follow-up email and deliver your offer. Then compare the current plan limits, email rules, integrations, payment availability in your country and support options.

Do not choose based on a feature list alone. Check the latest pricing and terms directly and decide whether the platform fits your actual workflow.

Explore systeme.io: {affiliate_url}

Affiliate disclosure: This article contains an affiliate link. I may earn a commission if you register or purchase through it, at no extra cost to you."""),
        ("How to compare an all-in-one funnel and email marketing platform", f"""Choosing an online-business platform is easier when you start with the workflow rather than the feature list.

1. Define the offer and the audience.
2. Build one focused landing page.
3. Decide how leads will be collected and followed up.
4. Check integrations, payment methods and data-export options.
5. Calculate the total cost as your list and sales grow.

systeme.io is one platform to include in that evaluation because it brings funnel-building and email-marketing tools together. It will not automatically create demand or guarantee sales; the offer, audience and execution still matter.

See the platform and current plans: {affiliate_url}

Affiliate disclosure: I may earn a commission if you sign up through this affiliate link, with no additional cost to you."""),
        ("Checklist: six things to verify before choosing systeme.io", f"""Use this checklist before moving your business workflow to a new platform.

- Can it support the landing page and checkout flow you actually need?
- Are the email limits and automation features sufficient?
- Does it support your preferred payment methods and country?
- Can you connect your domain and essential integrations?
- Can you export contacts and other important data?
- Does the current plan remain affordable as usage grows?

systeme.io may be worth testing if you want several online-business tools in one place. Confirm the latest terms and feature limits directly before making a decision.

Visit systeme.io: {affiliate_url}

Affiliate disclosure: This page contains an affiliate link. I may receive a commission from eligible referrals at no extra cost to you.""")
    ]
    created_titles, skipped_titles = [], []
    for angle, body in templates:
        title = f"{today} | {angle}"
        existing = db.scalar(select(ContentDraft).where(ContentDraft.campaign_id == campaign.id, ContentDraft.title == title))
        if existing:
            skipped_titles.append(title)
        else:
            db.add(ContentDraft(campaign_id=campaign.id, title=title, body=body, status="draft"))
            created_titles.append(title)
    if created_titles:
        db.add(ActivityLog(event_type="autopilot.run", message=f"Autopilot tạo {len(created_titles)} bản nháp", details=json.dumps({"created": len(created_titles), "skipped": len(skipped_titles), "date": today})))
        db.commit()
    total = db.scalar(select(func.count()).select_from(ContentDraft).where(ContentDraft.campaign_id == campaign.id)) or 0
    drafts = list(db.scalars(select(ContentDraft).where(ContentDraft.campaign_id == campaign.id, ContentDraft.title.in_(created_titles) if created_titles else ContentDraft.id == -1).order_by(ContentDraft.created_at.desc())).all())
    return {"campaign_id": campaign.id, "created": len(created_titles), "skipped": len(skipped_titles), "created_titles": created_titles, "drafts_total": total, "run_date": today, "status": "drafts_ready_for_review", "publishing": "not_connected", "drafts": [{"id": d.id, "title": d.title, "status": d.status} for d in drafts]}

@app.post("/api/autopilot/scheduled")
def run_scheduled_autopilot(db: Session = Depends(get_db), x_autopilot_token: str | None = Header(default=None)):
    """Secret-protected daily job: create content and publish one image post to Facebook."""
    if not settings.autopilot_token or not x_autopilot_token or not secrets.compare_digest(x_autopilot_token, settings.autopilot_token):
        raise HTTPException(401, "Unauthorized")
    setting = db.get(AppSetting, "auto_publish")
    auto_publish = setting.value.lower() == "true" if setting else True
    if not auto_publish:
        return {"status": "paused", "publishing": "disabled", "message": "Tự động đăng đang tắt trong cài đặt."}
    result = run_autopilot(db=db)
    from .direct_social import publish_facebook, SocialPublishError
    titles = result.get("created_titles") or []
    draft = None
    if titles:
        draft = db.scalar(select(ContentDraft).where(ContentDraft.campaign_id == result["campaign_id"], ContentDraft.title.in_(titles), ContentDraft.status == "draft").order_by(ContentDraft.created_at.asc()))
    if not draft:
        # Prefer the draft prepared by the 18:30 Image Agent before falling back to older backlog.
        today_local = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
        draft = db.scalar(select(ContentDraft).where(
            ContentDraft.campaign_id == result["campaign_id"],
            ContentDraft.title.like(f"{today_local} |%"),
            ContentDraft.status == "draft"
        ).order_by(ContentDraft.created_at.asc()))
    if not draft:
        draft = db.scalar(select(ContentDraft).where(ContentDraft.campaign_id == result["campaign_id"], ContentDraft.status == "draft").order_by(ContentDraft.created_at.asc()))
    if not draft:
        result.update({"publishing": "skipped_no_eligible_draft", "message": "Không còn bản nháp chưa đăng."})
        log_activity(db, "publishing.scheduled_skipped", "Lịch tự động: không có bản nháp đủ điều kiện", "warning")
        db.commit()
        return result
    selected_asset = None
    if not draft.image_url:
        selected_asset = db.scalar(select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(1))
        if not selected_asset:
            result.update({"publishing": "skipped_no_image", "draft_id": draft.id, "message": "Không có ảnh trong Cloudinary; bỏ qua để tránh đăng bài không ảnh."})
            log_activity(db, "publishing.scheduled_skipped", f"Lịch tự động bỏ qua bài #{draft.id}: thiếu ảnh", "warning", {"draft_id": draft.id})
            db.commit()
            return result
        draft.image_url = selected_asset.secure_url
    try:
        published = publish_facebook(draft.body, draft.image_url)
        draft.status = "published"
        log_activity(db, "publishing.scheduled", f"Lịch tự động đã đăng bài #{draft.id} lên Facebook", details={"draft_id": draft.id, **published})
        db.commit()
        result.update({"publishing": "published", "draft_id": draft.id, "title": draft.title, "published": published, "image_url": draft.image_url})
        return result
    except SocialPublishError as exc:
        log_activity(db, "publishing.scheduled_failed", f"Lịch tự động đăng bài #{draft.id} thất bại", "failed", {"draft_id": draft.id, "error": str(exc)[:500]})
        db.commit()
        raise HTTPException(502, f"Không thể tự động đăng Facebook: {str(exc)[:400]}")

@app.post("/api/autopilot/run-and-publish-facebook")
def run_and_publish_facebook(db: Session = Depends(get_db)):
    """Generate the daily batch and automatically publish one newly-created Facebook draft."""
    from .direct_social import publish_facebook, SocialPublishError
    result = run_autopilot(db=db)
    created_titles = result.get("created_titles") or []
    draft = None
    selected_existing_draft = False
    if created_titles:
        draft = db.scalar(
            select(ContentDraft)
            .where(
                ContentDraft.campaign_id == result["campaign_id"],
                ContentDraft.title.in_(created_titles),
                ContentDraft.status == "draft",
            )
            .order_by(ContentDraft.created_at.asc())
        )
    # If today's batch already exists, use an unpublished draft from this
    # same Autopilot campaign rather than silently skipping publication.
    if not draft:
        draft = db.scalar(
            select(ContentDraft)
            .where(
                ContentDraft.campaign_id == result["campaign_id"],
                ContentDraft.status == "draft",
            )
            .order_by(ContentDraft.created_at.asc())
        )
        selected_existing_draft = draft is not None
    if not draft:
        return {
            **result,
            "publishing": "skipped_no_eligible_draft",
            "message": "Không còn bản nháp Autopilot nào chưa đăng. Hãy tạo nội dung mới trước.",
        }

    # Reuse an existing Cloudinary library image when the selected draft has
    # no image. This keeps the generated copy and its image in one Facebook post.
    selected_media_asset = None
    if not draft.image_url:
        selected_media_asset = db.scalar(
            select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(1)
        )
        if not selected_media_asset:
            return {
                **result,
                "publishing": "skipped_no_image",
                "draft_id": draft.id,
                "title": draft.title,
                "message": "Bản nháp chưa có ảnh và Image library Cloudinary đang trống. Hãy thêm ảnh rồi thử lại.",
            }
        draft.image_url = selected_media_asset.secure_url

    try:
        published = publish_facebook(draft.body, draft.image_url)
        draft.status = "published"
        log_activity(db, "publishing.autopilot", f"Autopilot tự động đăng bài #{draft.id} lên Facebook", details={"draft_id": draft.id, **published})
        db.commit()
        return {**result, "publishing": "published", "published": published, "draft_id": draft.id, "title": draft.title, "selected_existing_draft": selected_existing_draft, "image_url": draft.image_url, "image_source": "cloudinary_library" if selected_media_asset else ("draft" if draft.image_url else "none")}
    except SocialPublishError as exc:
        log_activity(db, "publishing.autopilot_failed", f"Autopilot đăng Facebook bài #{draft.id} thất bại", "failed", {"draft_id": draft.id, "error": str(exc)[:500]})
        db.commit()
        raise HTTPException(502, f"Không thể tự động đăng Facebook: {str(exc)[:400]}")
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


@app.get("/api/activity")
def list_activity(date_from: date | None = None, date_to: date | None = None, limit: int = 100, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 300))
    query = select(ActivityLog)
    if date_from:
        start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        query = query.where(ActivityLog.created_at >= start)
    if date_to:
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        query = query.where(ActivityLog.created_at < end)
    rows = db.scalars(query.order_by(ActivityLog.created_at.desc()).limit(limit)).all()
    return [{"id": x.id, "event_type": x.event_type, "message": x.message, "status": x.status, "details": json.loads(x.details or "{}"), "created_at": x.created_at.isoformat()} for x in rows]

@app.get("/api/media")
def list_media(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(max(1, min(limit, 200)))).all()
    return [{"id": x.id, "public_id": x.public_id, "url": x.secure_url, "filename": x.filename, "format": x.format, "bytes": x.bytes, "width": x.width, "height": x.height, "created_at": x.created_at.isoformat()} for x in rows]

@app.post("/api/media/upload")
async def upload_media(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise HTTPException(503, "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Only JPG, PNG and WebP images are supported.")
    data = await file.read()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be between 1 byte and 10 MB.")
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(cloud_name=settings.cloudinary_cloud_name, api_key=settings.cloudinary_api_key, api_secret=settings.cloudinary_api_secret, secure=True)
        result = cloudinary.uploader.upload(data, resource_type="image", folder="affiliate-command-center", use_filename=True, unique_filename=True)
    except Exception as exc:
        log_activity(db, "media.upload", f"Upload ảnh thất bại: {file.filename or 'image'}", "failed", {"error": str(exc)[:300]})
        db.commit()
        raise HTTPException(502, "Cloudinary upload failed. Check credentials and Cloudinary account.") from exc
    asset = MediaAsset(public_id=result["public_id"], secure_url=result["secure_url"], filename=file.filename or "", format=result.get("format",""), bytes=result.get("bytes",len(data)), width=result.get("width",0), height=result.get("height",0))
    db.add(asset)
    log_activity(db, "media.upload", f"Đã lưu ảnh {file.filename or result['public_id']} lên Cloudinary", details={"public_id": result["public_id"], "url": result["secure_url"]})
    db.commit()
    db.refresh(asset)
    return {"id": asset.id, "public_id": asset.public_id, "url": asset.secure_url, "format": asset.format, "bytes": asset.bytes, "width": asset.width, "height": asset.height}


@app.post("/api/media/generate-daily")
def generate_daily_media(db: Session = Depends(get_db), x_autopilot_token: str | None = Header(default=None)):
    """Daily Image Agent: create one campaign-matched image and save it to Cloudinary."""
    if not settings.autopilot_token or not x_autopilot_token or not secrets.compare_digest(x_autopilot_token, settings.autopilot_token):
        raise HTTPException(401, "Unauthorized")
    agent_setting = db.get(AppSetting, "auto_generate_images")
    if agent_setting and agent_setting.value.lower() != "true":
        return {"status": "paused", "message": "Daily Image Agent đang tắt."}
    if not settings.openai_api_key or not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise HTTPException(503, "Image Agent cần OPENAI_API_KEY và Cloudinary credentials.")
    campaign = db.scalar(select(Campaign).where(Campaign.name == "SaaS Tools for Small Businesses"))
    if not campaign:
        raise HTTPException(409, "Chưa có chiến dịch SaaS starter.")
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    daily_drafts = list(db.scalars(
        select(ContentDraft).where(
            ContentDraft.campaign_id == campaign.id,
            ContentDraft.title.like(f"{today} |%"),
            ContentDraft.status == "draft"
        ).order_by(ContentDraft.created_at.asc())
    ).all())
    if not daily_drafts:
        run_autopilot(db=db)
        daily_drafts = list(db.scalars(
            select(ContentDraft).where(
                ContentDraft.campaign_id == campaign.id,
                ContentDraft.title.like(f"{today} |%"),
                ContentDraft.status == "draft"
            ).order_by(ContentDraft.created_at.asc())
        ).all())
    draft = next((item for item in daily_drafts if not item.image_url), None)
    if not draft:
        return {"status": "already_ready", "message": "Hôm nay chưa có bài cần tạo ảnh hoặc ảnh đã sẵn sàng."}
    try:
        from openai import OpenAI
        import cloudinary
        import cloudinary.uploader
        client = OpenAI(api_key=settings.openai_api_key)
        brief = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.7,
            messages=[
                {"role": "system", "content": "You are a senior commercial art director. Return only one detailed image-generation prompt in English. Create a realistic, premium social-media campaign photograph that visually explains the article. No text, typography, logos, UI screenshots, watermarks, or brand marks. Specify subject, setting, composition, lighting, color palette, and camera style. Avoid generic stock-photo clichés."},
                {"role": "user", "content": f"Campaign niche: {campaign.niche}. Article title: {draft.title}. Article content: {draft.body[:3500]}"}
            ],
        )
        image_prompt = brief.choices[0].message.content or ""
        if len(image_prompt.strip()) < 30:
            raise RuntimeError("Image Agent did not return a usable prompt")
        generated = client.images.generate(
            model=settings.openai_image_model,
            prompt=image_prompt,
            size="1024x1024",
            quality=settings.openai_image_quality,
            n=1,
        )
        image_b64 = generated.data[0].b64_json
        if not image_b64:
            raise RuntimeError("Image provider returned no image data")
        image_bytes = base64.b64decode(image_b64)
        cloudinary.config(cloud_name=settings.cloudinary_cloud_name, api_key=settings.cloudinary_api_key, api_secret=settings.cloudinary_api_secret, secure=True)
        uploaded = cloudinary.uploader.upload(image_bytes, resource_type="image", folder="affiliate-command-center/generated/daily", format="png")
        asset = MediaAsset(
            public_id=uploaded["public_id"], secure_url=uploaded["secure_url"],
            filename=f"daily-agent-{today}.png", format="png",
            bytes=uploaded.get("bytes", len(image_bytes)),
            width=uploaded.get("width", 1024), height=uploaded.get("height", 1024)
        )
        db.add(asset)
        draft.image_url = uploaded["secure_url"]
        log_activity(db, "media.daily_agent", f"Image Agent tạo ảnh và lưu kho cho bài #{draft.id}",
                     details={"draft_id": draft.id, "public_id": uploaded["public_id"], "model": settings.openai_image_model, "prompt": image_prompt[:1200]})
        db.commit()
        db.refresh(asset)
        return {"status": "generated", "draft_id": draft.id, "title": draft.title, "asset_id": asset.id, "url": asset.secure_url, "public_id": asset.public_id}
    except Exception as exc:
        log_activity(db, "media.daily_agent_failed", "Daily Image Agent tạo ảnh thất bại", "failed", {"draft_id": draft.id, "error": str(exc)[:400]})
        db.commit()
        raise HTTPException(502, "Daily Image Agent không tạo được ảnh. Kiểm tra API key, quyền model và hạn mức.") from exc


@app.post("/api/media/generate")
def generate_media(payload: GenerateImageRequest, db: Session = Depends(get_db)):
    """Generate one editorial image with OpenAI and persist it in Cloudinary."""
    if not settings.openai_api_key:
        raise HTTPException(503, "Chưa cấu hình OPENAI_API_KEY để tạo ảnh AI.")
    if not settings.cloudinary_cloud_name or not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise HTTPException(503, "Cloudinary chưa được cấu hình.")
    draft = db.get(ContentDraft, payload.draft_id) if payload.draft_id else None
    if payload.draft_id and not draft:
        raise HTTPException(404, "Không tìm thấy bản nháp.")
    try:
        from openai import OpenAI
        import cloudinary
        import cloudinary.uploader
        client = OpenAI(api_key=settings.openai_api_key)
        result = client.images.generate(
            model=settings.openai_image_model,
            prompt=("Create a polished, photorealistic commercial social-media image. No text, no logos, no watermark. "
                    "Use clear visual hierarchy, natural lighting and a professional composition. " + payload.prompt),
            size="1024x1024",
            quality=settings.openai_image_quality,
            n=1,
        )
        image_b64 = result.data[0].b64_json
        if not image_b64:
            raise RuntimeError("Image provider returned no image data")
        image_bytes = base64.b64decode(image_b64)
        cloudinary.config(cloud_name=settings.cloudinary_cloud_name, api_key=settings.cloudinary_api_key, api_secret=settings.cloudinary_api_secret, secure=True)
        uploaded = cloudinary.uploader.upload(image_bytes, resource_type="image", folder="affiliate-command-center/generated", format="png")
        asset = MediaAsset(public_id=uploaded["public_id"], secure_url=uploaded["secure_url"], filename="ai-generated.png", format="png", bytes=uploaded.get("bytes", len(image_bytes)), width=uploaded.get("width", 1024), height=uploaded.get("height", 1024))
        db.add(asset)
        if draft:
            draft.image_url = uploaded["secure_url"]
        log_activity(db, "media.generate", f"AI tạo ảnh và lưu Cloudinary" + (f" cho bản nháp #{draft.id}" if draft else ""), details={"public_id": uploaded["public_id"], "draft_id": draft.id if draft else None, "model": settings.openai_image_model})
        db.commit()
        db.refresh(asset)
        return {"id": asset.id, "url": asset.secure_url, "public_id": asset.public_id, "draft_id": draft.id if draft else None}
    except HTTPException:
        raise
    except Exception as exc:
        log_activity(db, "media.generate", "Tạo ảnh AI thất bại", "failed", {"error": str(exc)[:300]})
        db.commit()
        raise HTTPException(502, "Không thể tạo ảnh AI. Kiểm tra API key, quyền truy cập model và hạn mức tài khoản.") from exc


@app.post("/api/autopilot/publish-latest-image")
def publish_latest_image_now(db: Session = Depends(get_db)):
    """Create a post from the newest Cloudinary asset and publish it to the configured Facebook Page."""
    from .direct_social import publish_facebook, SocialPublishError

    if not settings.facebook_page_id or not settings.facebook_page_access_token:
        raise HTTPException(503, "Facebook Page chưa được kết nối. Kiểm tra FACEBOOK_PAGE_ID và FACEBOOK_PAGE_ACCESS_TOKEN trên Render.")

    asset = db.scalar(select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(1))
    if not asset:
        raise HTTPException(404, "Thư viện Cloudinary chưa có ảnh. Hãy tải ảnh lên trước.")

    # Prevent accidental duplicate publishing of the same image by this one-click workflow.
    already_published = db.scalar(
        select(ActivityLog).where(
            ActivityLog.event_type == "publishing.latest_image",
            ActivityLog.details.like(f'%"{asset.public_id}"%')
        ).limit(1)
    )
    if already_published:
        raise HTTPException(409, "Ảnh mới nhất này đã được đăng bằng tính năng tự động chọn ảnh. Không đăng lặp.")

    campaign = db.scalar(select(Campaign).where(Campaign.name == "SaaS Tools for Small Businesses"))
    if not campaign:
        campaign = Campaign(name="Chiu Chiu · Social content", niche="technology", network="facebook")
        db.add(campaign)
        db.flush()

    title = f"Không gian làm việc gọn gàng hơn · {asset.filename or asset.public_id}"
    body = (
        "Một góc làm việc với hai màn hình có thể giúp bạn sắp xếp nhiều tác vụ rõ ràng hơn: "
        "một màn hình để tập trung xử lý công việc, màn hình còn lại để theo dõi tài liệu và trao đổi.\n\n"
        "Điều quan trọng không phải là có thật nhiều thiết bị, mà là thiết lập phù hợp với cách bạn làm việc. "
        "Bạn thích dùng một màn hình lớn hay hai màn hình song song?\n\n"
        "#WorkSetup #DeskSetup #Productivity"
    )
    draft = ContentDraft(campaign_id=campaign.id, title=title[:240], body=body, image_url=asset.secure_url, status="draft")
    db.add(draft)
    db.flush()

    try:
        result = publish_facebook(body, asset.secure_url)
    except SocialPublishError as exc:
        log_activity(db, "publishing.failed", f"Đăng ảnh Cloudinary lên Facebook thất bại", "failed",
                     {"draft_id": draft.id, "public_id": asset.public_id, "error": str(exc)[:500]})
        db.commit()
        raise HTTPException(502, f"Facebook từ chối đăng bài: {str(exc)[:500]}") from exc

    draft.status = "published"
    log_activity(db, "publishing.latest_image", "Đã tự chọn ảnh Cloudinary mới nhất và đăng lên Facebook",
                 details={"draft_id": draft.id, "public_id": asset.public_id, "image_url": asset.secure_url, **result})
    db.commit()
    return {"status": "published", "draft_id": draft.id, "title": draft.title, "image_url": asset.secure_url, "platform": "facebook", "post_id": result["post_id"]}


ALLOWED_METRICOOL_NETWORKS = {"facebook", "instagram", "threads", "pinterest", "tiktok"}
def metricool_request(method: str, path: str, payload: dict | None = None):
    if not settings.metricool_user_token:
        raise HTTPException(503, "Thiếu METRICOOL_USER_TOKEN. Hãy thêm API token trong Render Environment.")
    query = urlencode({"userId": settings.metricool_user_id, "blogId": settings.metricool_blog_id})
    url = f"https://app.metricool.com/api{path}?{query}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method, headers={"X-Mc-Auth": settings.metricool_user_token, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=25) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {"ok": True}
    except Exception as exc:
        detail = getattr(exc, "read", lambda: b"")()
        message = detail.decode("utf-8", "ignore")[:500] if detail else str(exc)[:300]
        raise HTTPException(502, f"Metricool API error: {message}") from exc



class AgentCollaborationRequest(BaseModel):
    topic: str = Field(default="Lên ý tưởng nội dung affiliate hôm nay", min_length=5, max_length=500)
    campaign_id: int | None = None
    rounds: int = Field(default=2, ge=1, le=3)

@app.get("/api/agents/conversations")
def list_agent_conversations(limit: int = 60, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(AgentMessage).order_by(AgentMessage.created_at.desc()).limit(min(max(limit, 1), 150))).all())
    rows.reverse()
    return [{"id": x.id, "session_id": x.session_id, "agent": x.agent, "message": x.message, "created_at": x.created_at.isoformat()} for x in rows]

@app.post("/api/agents/collaborate")
def agents_collaborate(payload: AgentCollaborationRequest, db: Session = Depends(get_db)):
    if not settings.openai_api_key:
        raise HTTPException(503, "Chưa cấu hình OPENAI_API_KEY.")
    campaign = db.get(Campaign, payload.campaign_id) if payload.campaign_id else db.scalar(select(Campaign).order_by(Campaign.created_at.desc()))
    context = {"campaign": campaign.name if campaign else "Affiliate content", "niche": campaign.niche if campaign else "general", "network": campaign.network if campaign else "Facebook"}
    history = []
    session_id = secrets.token_hex(12)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        previous = ""
        for turn in range(payload.rounds * 2):
            agent = "Content Agent" if turn % 2 == 0 else "Image Agent"
            role = ("You are the Content Agent: an evidence-conscious affiliate editor. Propose a useful, audience-specific post concept and concise draft brief. Avoid unsupported claims, fake reviews, guaranteed results, and deceptive urgency. Include a clear affiliate disclosure when relevant."
                    if agent == "Content Agent" else
                    "You are the Image Agent: a senior commercial art director. Critique the content brief, propose a coherent visual concept, composition, subject, lighting, palette and image-generation prompt. Flag any misleading visual implication. Respond to the Content Agent's latest message directly.")
            response = client.chat.completions.create(
                model=settings.openai_model, temperature=0.65,
                messages=[
                    {"role":"system","content":role + " You are collaborating with another specialist agent. Be concrete and concise. Do not claim to have generated an image or published anything."},
                    {"role":"user","content":json.dumps({"campaign":context,"topic":payload.topic,"conversation_so_far":history,"previous_agent_message":previous},ensure_ascii=False)}
                ])
            message = (response.choices[0].message.content or "").strip()
            if not message:
                raise RuntimeError("Agent returned an empty message")
            row=AgentMessage(session_id=session_id,agent=agent,message=message)
            db.add(row)
            history.append({"agent":agent,"message":message})
            previous=message
        log_activity(db,"agents.collaboration",f"Hai AI Agent đã trao đổi {len(history)} lượt",details={"session_id":session_id,"topic":payload.topic,"campaign":context["campaign"]})
        db.commit()
        return {"session_id":session_id,"topic":payload.topic,"messages":[{"agent":x["agent"],"message":x["message"]} for x in history],"status":"discussion_complete"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(502,"Hai AI Agent chưa thể hoàn tất trao đổi. Kiểm tra API key, model và hạn mức OpenAI.") from exc

@app.get("/api/publishing/status")
def publishing_status(db: Session = Depends(get_db)):
    setting = db.get(AppSetting, "auto_publish")
    facebook_ready = bool(settings.facebook_page_id and settings.facebook_page_access_token)
    threads_ready = bool(settings.threads_user_id and settings.threads_access_token)
    instagram_ready = bool(settings.instagram_user_id and settings.instagram_access_token)
    return {
        "provider": "direct_meta_api",
        "connected": facebook_ready or threads_ready,
        "facebook_connected": facebook_ready,
        "threads_connected": threads_ready,
        "instagram_connected": instagram_ready,
        "auto_publish": setting.value.lower() == "true" if setting else True,
        "timezone": "Asia/Ho_Chi_Minh",
        "schedule_time": "19:30",
        "schedule_frequency": "daily",
        "networks": ["facebook", "instagram", "threads"],
        "requires_credentials": not facebook_ready,
    }

@app.put("/api/publishing/settings")
def update_publishing_settings(payload: PublishSettingsRequest, db: Session = Depends(get_db)):
    if payload.auto_publish and not (settings.facebook_page_id and settings.facebook_page_access_token):
        raise HTTPException(409, "Cần cấu hình Facebook Page ID và Page Access Token trong Render trước khi bật lịch.")
    setting = db.get(AppSetting, "auto_publish")
    if not setting:
        setting = AppSetting(key="auto_publish", value=str(payload.auto_publish).lower())
        db.add(setting)
    else:
        setting.value = str(payload.auto_publish).lower()
    log_activity(db, "publishing.schedule_settings", "Đã bật lịch tự động đăng Facebook" if payload.auto_publish else "Đã tắt lịch tự động đăng Facebook", details={"auto_publish": payload.auto_publish, "schedule_time": "19:30", "timezone": "Asia/Ho_Chi_Minh"})
    db.commit()
    return {"auto_publish": payload.auto_publish, "provider": "direct_meta_api", "schedule_time": "19:30", "timezone": "Asia/Ho_Chi_Minh"}

@app.put("/api/drafts/{draft_id}/image")
def attach_draft_image(draft_id: int, asset_id: int, db: Session = Depends(get_db)):
    draft = db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Không tìm thấy bản nháp.")
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(404, "Không tìm thấy ảnh trong thư viện Cloudinary.")
    if draft.status == "published":
        raise HTTPException(409, "Bài đã đăng; không thể thay ảnh sau khi xuất bản.")
    draft.image_url = asset.secure_url
    log_activity(db, "content.image_attached", f"Đã gắn ảnh vào bài #{draft.id}", details={"draft_id": draft.id, "asset_id": asset.id, "public_id": asset.public_id})
    db.commit()
    return {"draft_id": draft.id, "asset_id": asset.id, "image_url": asset.secure_url}

@app.post("/api/drafts/{draft_id}/publish")
def publish_draft_now(draft_id: int, payload: PublishRequest, db: Session = Depends(get_db)):
    """Publish an approved draft immediately through Meta's direct APIs."""
    from .direct_social import publish_facebook, publish_threads, publish_instagram, SocialPublishError
    draft = db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(404, "Không tìm thấy bản nháp.")
    if draft.status not in {"approved", "draft"}:
        raise HTTPException(409, "Bản nháp này không ở trạng thái có thể đăng.")
    networks = list(dict.fromkeys(payload.networks))
    if not networks or any(n not in {"facebook", "instagram", "threads"} for n in networks):
        raise HTTPException(422, "Nền tảng không được hỗ trợ.")
    results, failures = [], []
    for network in networks:
        try:
            if network == "facebook":
                result = publish_facebook(draft.body, draft.image_url)
            elif network == "instagram":
                result = publish_instagram(draft.body, draft.image_url)
            else:
                result = publish_threads(draft.body, draft.image_url)
            results.append(result)
            log_activity(db, "publishing.published", f"Đã đăng bài #{draft.id} lên {network}", details={"draft_id": draft.id, **result})
        except SocialPublishError as exc:
            failures.append({"platform": network, "error": str(exc)[:500]})
            log_activity(db, "publishing.failed", f"Đăng bài #{draft.id} lên {network} thất bại", "failed", {"error": str(exc)[:500]})
    if results:
        draft.status = "published"
    db.commit()
    if failures:
        return {"status": "partial" if results else "failed", "published": results, "failures": failures}
    return {"status": "published", "published": results}

