# AffPilot AdSpy Chrome Extension (MVP 0.1)

## What it does
- Opens a keyword search in Meta's public Ad Library, fixed to the United States market.
- Detects whether the current tab URL is an Ad Library URL and offers it as the source link.
- Lets the user explicitly paste public ad copy and enter advertiser/headline/landing-page details.
- Opens the existing AffPilot Ad Research dashboard with those user-submitted fields prefilled. The user reviews and saves the record through AffPilot's normal authenticated frontend.
- Does not need a Facebook login connection, Meta password, access token, AffPilot API token, or separate backend credentials.

## What it deliberately does not do
- No DOM scraping, bulk collection, crawling, automated pagination, hidden endpoint calls, cookie/session access, Facebook login automation, or access-control circumvention.
- It does not automatically inspect or extract the ad currently rendered in Facebook.
- It does not claim to retrieve spend, ROAS, conversions, or sales.

Meta's Automated Data Collection Terms require express written permission before automated data collection unless otherwise explicitly authorized. This MVP is user-directed manual capture. Any future DOM extraction or automated collection must be reviewed against Meta terms and obtain the required written permission first.

## Install locally (unpacked)
1. Merge/deploy the AffPilot Ads Research dashboard and backend module (PR #22 or its successor).
2. Open Chrome and visit `chrome://extensions`.
3. Enable **Developer mode**.
4. Select **Load unpacked** and choose this `extension` directory.
5. Open the extension, enter a keyword (US market), and choose **Open search in Meta Ad Library**.
6. Review the public ads yourself. Copy the ad text and enter the visible advertiser/headline/source URL in the extension.
7. Choose **Send to AdSpy Dashboard**. AffPilot opens with the fields prefilled; review them and press **Save ad & research**.

## Permissions
- `activeTab`: reads only the current tab URL after the user explicitly opens the extension, to prefill a public Ad Library source link.
- No content scripts, no Facebook host permission, no cookies permission, no storage permission, and no direct network connection from the extension to AffPilot.

## Publishing checklist
Before Chrome Web Store submission:
- Add production icons, screenshots, support URL, and privacy policy.
- Disclose the extension's single purpose and exactly what user-entered data is handed to the AffPilot dashboard.
- Obtain informed consent and publish a privacy policy.
- Test on a clean Chrome profile and validate error handling.
- Complete Chrome Web Store developer registration and review.
