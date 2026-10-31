from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now_utc():
    return datetime.now(timezone.utc)

class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    niche: Mapped[str] = mapped_column(String(120), default="general")
    network: Mapped[str] = mapped_column(String(80), default="unselected")
    status: Mapped[str] = mapped_column(String(30), default="research")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    contents: Mapped[list["ContentDraft"]] = relationship(back_populates="campaign")

class ContentDraft(Base):
    __tablename__ = "content_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(1500), nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    campaign: Mapped[Campaign] = relationship(back_populates="contents")

class Conversion(Base):
    __tablename__ = "conversions"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    external_order_id: Mapped[str] = mapped_column(String(160), unique=True)
    commission: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    source: Mapped[str] = mapped_column(String(80), default="network_postback")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

class ResearchOpportunity(Base):
    __tablename__ = "research_opportunities"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_name: Mapped[str] = mapped_column(String(200))
    vendor_name: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(120), default="software")
    network: Mapped[str] = mapped_column(String(80), default="direct")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    target_regions: Mapped[str] = mapped_column(String(120), default="US,UK,EU")
    price_usd: Mapped[float] = mapped_column(Float, default=0)
    commission_pct: Mapped[float] = mapped_column(Float, default=0)
    recurring: Mapped[bool] = mapped_column(default=False)
    evidence_quality: Mapped[int] = mapped_column(Integer, default=1)
    audience_fit: Mapped[int] = mapped_column(Integer, default=3)
    differentiation: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    score_breakdown: Mapped[str] = mapped_column(Text, default="{}")
    recommendation: Mapped[str] = mapped_column(String(40), default="needs_review")
    research_notes: Mapped[str] = mapped_column(Text, default="")
    ai_brief: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(String(500))
    details: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    secure_url: Mapped[str] = mapped_column(String(1500))
    filename: Mapped[str] = mapped_column(String(300), default="")
    format: Mapped[str] = mapped_column(String(20), default="")
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
