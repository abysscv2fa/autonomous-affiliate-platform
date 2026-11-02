# Autonomous Affiliate Platform

AI-assisted affiliate research and campaign management MVP.

## Status

MVP source is being added. Cloud deployment and affiliate network integrations are not yet configured.

This project helps research and manage affiliate opportunities; it does not guarantee earnings. Affiliate applications, approvals, and publishing remain subject to provider rules and human review.


## AffPilot AdSpy — US-first

The dashboard includes an AdSpy workspace at `/ads-research`, plus a Chrome Manifest V3 companion in `extension/`.

- **US data source:** search the public Meta Ad Library. The user opens a keyword search, manually reviews an ad, and enters/pastes the public details they choose to save.
- **No scraping:** no DOM scraping, automated pagination, bulk crawling, hidden endpoints, cookies/session access, login automation, or access-control circumvention.
- **Free-first analysis:** saved ad copy can be reviewed using local rule-based heuristics without an external AI API key. If `OPENAI_API_KEY` is configured, the optional OpenAI analysis can provide deeper hypotheses.
- **Evidence labels:** manually captured records are labelled `user_saved_unverified`. The score is a heuristic or AI creative-opportunity estimate, not measured ad performance.
- **Performance claims:** Ad Library presence does not prove spend, ROAS, conversions, sales, or profitability. AffPilot does not invent these metrics.

### Chrome extension

1. Open `chrome://extensions` in Chrome and enable Developer mode.
2. Choose **Load unpacked** and select the repository's `extension/` folder.
3. Search a keyword in the US Meta Ad Library.
4. Manually review a public ad and enter its visible details in the extension.
5. Send the details to the AffPilot dashboard, review them, and save.

The extension uses only the `activeTab` permission. It does not need a Facebook password, Meta access token, AffPilot API token, cookies permission, or Facebook host permission.

### Meta API boundary

Meta's Ad Library API does not provide broad access to ordinary US commercial ads. This US-first MVP therefore does not attempt automated commercial-ad API collection for the US. Any future automated collection must use an officially authorized data source and comply with the provider's terms.
