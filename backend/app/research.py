"""Transparent opportunity scoring and optional AI-assisted research notes."""
import json
from .config import settings

def score_opportunity(item):
    commission = min(item.commission_pct / 30.0, 1.0) * 20
    recurring = 15 if item.recurring else 0
    price = min(item.price_usd / 200.0, 1.0) * 10
    evidence = (item.evidence_quality / 5.0) * 25
    fit = (item.audience_fit / 5.0) * 20
    differentiation = 10 if len((item.differentiation or '').strip()) >= 40 else 0
    breakdown = {"commission_potential": round(commission, 1), "recurring_model": recurring, "price_point": round(price, 1), "evidence_quality": round(evidence, 1), "audience_fit": round(fit, 1), "differentiation": differentiation, "max_score": 100}
    score = round(sum(v for k, v in breakdown.items() if k != "max_score"))
    if item.commission_pct <= 0 or item.evidence_quality < 2:
        recommendation = "needs_verification"
    elif score >= 75:
        recommendation = "prioritize"
    elif score >= 55:
        recommendation = "test"
    else:
        recommendation = "low_priority"
    return score, breakdown, recommendation

def ai_research_brief(item):
    """Uses AI only when a server-side key is configured; never invents missing facts."""
    if not settings.openai_api_key:
        return {"mode": "rules_only", "brief": "Add an OPENAI_API_KEY on the server to enable AI-generated research briefs. Verify program terms, commission, geography and cookie window directly with the network before applying."}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model, temperature=0.2,
            messages=[
                {"role": "system", "content": "You are an affiliate opportunity analyst. Use only supplied facts. Do not invent commission rates, eligibility, cookie windows, prices, reviews, market demand, or product capabilities. Identify unknowns explicitly. Give concise English output with: positioning, likely audience, content angles, risks, verification checklist. Do not claim guaranteed revenue."},
                {"role": "user", "content": json.dumps({"product": item.product_name, "vendor": item.vendor_name, "category": item.category, "network": item.network, "source_url": item.source_url, "regions": item.target_regions, "price_usd": item.price_usd, "commission_pct": item.commission_pct, "recurring": item.recurring, "evidence_quality": item.evidence_quality, "audience_fit": item.audience_fit, "differentiation": item.differentiation, "notes": item.research_notes})}
            ])
        return {"mode": "openai", "brief": response.choices[0].message.content or "No brief returned."}
    except Exception as exc:
        return {"mode": "rules_only", "brief": f"AI brief unavailable ({type(exc).__name__}). Use the rules-based score and verify source facts manually."}
