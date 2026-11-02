const el = (id) => document.getElementById(id);
let activeUrl = "";
async function init() {
  const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
  activeUrl = tab && tab.url ? tab.url : "";
  if (activeUrl.startsWith("https://www.facebook.com/ads/library")) {
    el("sourceUrl").value = activeUrl;
    el("tabStatus").textContent = "Ad Library tab detected";
  } else {
    el("tabStatus").textContent = "Open Ad Library to detect source URL";
  }
}
el("openLibrary").addEventListener("click", async () => {
  const keyword = el("query").value.trim();
  if (keyword.length < 2) {
    el("message").textContent = "Enter a keyword with at least 2 characters.";
    return;
  }
  const url = new URL("https://www.facebook.com/ads/library/");
  url.searchParams.set("active_status","active");
  url.searchParams.set("ad_type","ALL");
  url.searchParams.set("country",el("country").value);
  url.searchParams.set("q",keyword);
  url.searchParams.set("search_type","keyword_unordered");
  await chrome.tabs.create({url:url.toString()});
  el("message").textContent = "Ad Library opened. Review an ad and enter its public details below.";
});
el("openDashboard").addEventListener("click", async () => {
  const keyword = el("query").value.trim();
  const copy = el("adText").value.trim();
  if (copy.length < 5) {
    el("message").textContent = "Paste the ad copy you want to research.";
    return;
  }
  const params = new URLSearchParams({
    import:"manual",
    query:keyword,
    country:el("country").value,
    page_name:el("pageName").value.trim(),
    ad_text:copy,
    headline:el("headline").value.trim(),
    description:el("description").value.trim(),
    ad_library_url:el("sourceUrl").value.trim() || activeUrl,
    landing_page_url:el("landingUrl").value.trim()
  });
  await chrome.tabs.create({url:"https://affiliate-frontend-qhop.onrender.com/ads-research?"+params.toString()});
  el("message").textContent = "Opened AffPilot AdSpy. Review the imported details and save from the dashboard.";
});
init().catch(() => { el("tabStatus").textContent = "Could not inspect active tab"; });
