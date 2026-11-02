# Autonomous Affiliate Platform

AI-assisted affiliate research and campaign management MVP.

## Status

MVP source is being added. Cloud deployment and affiliate network integrations are not yet configured.

This project helps research and manage affiliate opportunities; it does not guarantee earnings. Affiliate applications, approvals, and publishing remain subject to provider rules and human review.


## Facebook Ads Research

The dashboard includes a Facebook Ads Research workspace at `/ads-research`.

- **Manual mode:** creates a keyword/country search link for the public Meta Ad Library. The user opens Meta's site, reviews public ads, and pastes the ad copy/links into AffPilot to save and analyze. It does not scrape the browser or bypass Meta access controls.
- **Auto mode:** uses Meta's official Ad Library API (`ads_archive`) when an access token is configured. Meta documents broad commercial-ad API coverage for ads delivered in the UK and EU during the past year; ordinary commercial ads delivered only in the US and other non-EU markets are not generally available through this API. For those markets, use Manual mode or a separately licensed data provider.
- **AI analysis:** summarizes the audience, pain point, hook, offer, creative strategy, funnel hypothesis, risks, and test ideas. Its 0–100 score estimates creative/research opportunity, not spend, ROAS, conversions, or proven winning performance.
- **Saved research:** records ad copy, advertiser, country, source, public Ad Library URL, optional landing-page URL, platform metadata, and AI analysis in the existing PostgreSQL database.

### Optional environment variables

- `META_AD_LIBRARY_ACCESS_TOKEN`: access token authorized for Meta Ad Library API.
- `META_GRAPH_API_VERSION`: Graph API version (defaults to `v22.0`).

Without the Meta token, Manual mode and saved-ad AI analysis remain available (AI analysis still requires the existing `OPENAI_API_KEY`).
