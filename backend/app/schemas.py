from datetime import datetime
from pydantic import BaseModel, Field

class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    niche: str = Field(default="general", max_length=120)
    network: str = Field(default="unselected", max_length=80)

class CampaignOut(BaseModel):
    id: int
    name: str
    niche: str
    network: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}

class DraftCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    body: str = ""

class DraftOut(BaseModel):
    id: int
    campaign_id: int
    title: str
    body: str
    image_url: str | None = None
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}

class ConversionCreate(BaseModel):
    campaign_id: int
    external_order_id: str = Field(min_length=1, max_length=160)
    commission: float = Field(ge=0)
    currency: str = Field(default="USD", max_length=8)
    status: str = "pending"

class OpportunityCreate(BaseModel):
    product_name: str = Field(min_length=2, max_length=200)
    vendor_name: str = Field(default="", max_length=160)
    category: str = Field(default="software", max_length=120)
    network: str = Field(default="direct", max_length=80)
    source_url: str = Field(default="", max_length=1000)
    target_regions: str = Field(default="US,UK,EU", max_length=120)
    price_usd: float = Field(default=0, ge=0)
    commission_pct: float = Field(default=0, ge=0, le=100)
    recurring: bool = False
    evidence_quality: int = Field(default=1, ge=1, le=5)
    audience_fit: int = Field(default=3, ge=1, le=5)
    differentiation: str = ""
    research_notes: str = ""

class OpportunityOut(BaseModel):
    id: int
    product_name: str
    vendor_name: str
    category: str
    network: str
    source_url: str
    target_regions: str
    price_usd: float
    commission_pct: float
    recurring: bool
    evidence_quality: int
    audience_fit: int
    differentiation: str
    score: int
    score_breakdown: str
    recommendation: str
    research_notes: str
    ai_brief: str
    created_at: datetime
    model_config = {"from_attributes": True}
