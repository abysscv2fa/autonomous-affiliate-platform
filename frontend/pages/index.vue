<script setup lang="ts">
const config = useRuntimeConfig()
const api = config.public.apiBase
const { data: stats, refresh } = await useFetch<any>(`${api}/api/dashboard`, { default: () => ({ campaigns: 0, content_drafts: 0, confirmed_commission: 0, currency: 'USD' }) })
const { data: campaigns, refresh: refreshCampaigns } = await useFetch<any[]>(`${api}/api/campaigns`, { default: () => [] })
const { data: opportunities, refresh: refreshOpportunities } = await useFetch<any[]>(`${api}/api/research/opportunities`, { default: () => [] })
const { data: networks } = await useFetch<any[]>(`${api}/api/research/networks`, { default: () => [] })
const productName = ref(''), vendor = ref(''), commission = ref(20), recurring = ref(false), evidence = ref(3)
const systemeAffiliateLink = 'https://systeme.io/fr?sa=sa028522389209c1b0fb00f4f72d0250aa9dca6f5f'
const draftBusy = ref(false), draftMessage = ref('')
const autopilotBusy = ref(false), autopilotMessage = ref('')
const drafts = ref<any[]>([])
const selectedDraftId = ref<number | null>(null), selectedMediaId = ref<number | null>(null), draftImageMessage = ref('')
const selectedDraft = computed(() => drafts.value.find((d:any) => d.id === selectedDraftId.value) || null)
const selectedMedia = computed(() => media.value.find((m:any) => m.id === selectedMediaId.value) || null)
const draftSearch = ref(''), draftStatusFilter = ref('all')
const filteredDrafts = computed(() => drafts.value.filter((d:any) => (draftStatusFilter.value === 'all' || d.status === draftStatusFilter.value) && `${d.title || ''} ${d.body || ''}`.toLowerCase().includes(draftSearch.value.toLowerCase().trim())))
const activity = ref<any[]>([]), media = ref<any[]>([]), mediaBusy = ref(false), mediaMessage = ref('')
const imageBusy = ref<number | null>(null), autoGenerateImages = ref(false), activityDate = ref('')
const publishStatus = ref<any>({ connected: false, auto_publish: false }), publishBusy = ref<number | null>(null)
const publishNetworks = ref(['facebook','threads'])
const publishDate = ref(new Date(Date.now() + 86400000).toISOString().slice(0,16))
async function loadPublishing() { publishStatus.value = await $fetch<any>(`${api}/api/publishing/status`) }
async function toggleAutoPublish() { try { publishStatus.value = await $fetch<any>(`${api}/api/publishing/settings`, { method:'PUT', body:{auto_publish:publishStatus.value.auto_publish} }); await loadActivity() } catch(e:any) { publishStatus.value.auto_publish = false; autopilotMessage.value = e?.data?.detail || 'Không thể bật tự đăng.' } }
async function scheduleDraft(d:any) { if (!publishNetworks.value.length) { autopilotMessage.value='Hãy chọn ít nhất một nền tảng.'; return }; publishBusy.value=d.id; try { const result:any = await $fetch(`${api}/api/drafts/${d.id}/publish`, {method:'POST',body:{date_time:new Date().toISOString().slice(0,16),networks:publishNetworks.value}}); if (result.published?.length) d.status='published'; const ok=(result.published || []).map((x:any)=>x.platform); const failed=(result.failures || []).map((x:any)=>`${x.platform}: ${x.error}`); autopilotMessage.value = failed.length ? `Đã đăng: ${ok.join(', ') || 'không có'}. Thất bại: ${failed.join(' | ')}` : `Đã đăng bài #${d.id} lên: ${ok.join(', ')}.`; await Promise.all([loadActivity(),loadDrafts()]) } catch(e:any) { autopilotMessage.value=e?.data?.detail || 'Không thể đăng bài.' } finally { publishBusy.value=null } }
async function attachSelectedImage(d:any) { if (!selectedMedia.value) return; draftImageMessage.value=''; try { const result:any=await $fetch(`${api}/api/drafts/${d.id}/image?asset_id=${selectedMedia.value.id}`,{method:'PUT'}); d.image_url=result.image_url; draftImageMessage.value=`Đã gắn ảnh ${selectedMedia.value.filename || selectedMedia.value.public_id} vào bài #${d.id}.`; await loadDrafts() } catch(e:any) { draftImageMessage.value=e?.data?.detail || 'Không thể gắn ảnh vào bài viết.' } }
async function loadActivity() { const q = activityDate.value ? `&date_from=${activityDate.value}&date_to=${activityDate.value}` : ''; activity.value = await $fetch<any[]>(`${api}/api/activity?limit=100${q}`) }
async function generateDraftImage(d: any) { imageBusy.value = d.id; mediaMessage.value = ''; try { const result: any = await $fetch(`${api}/api/media/generate`, { method: 'POST', body: { draft_id: d.id, prompt: `Create an image that visually communicates this social post. Topic: ${d.title}. Context: ${String(d.body || '').slice(0, 700)}. Audience: small business owners, creators and online entrepreneurs. Square 1:1 composition.` } }); d.image_url = result.url; mediaMessage.value = 'Đã tạo ảnh AI và lưu lên Cloudinary.'; await Promise.all([loadMedia(), loadActivity()]); } catch (e: any) { mediaMessage.value = e?.data?.detail || 'Không thể tạo ảnh AI.'; } finally { imageBusy.value = null } }
const latestImagePublishBusy = ref(false), latestImagePublishMessage = ref('')
async function publishLatestImage() {
  latestImagePublishBusy.value = true; latestImagePublishMessage.value = ''
  try {
    const result: any = await $fetch(`${api}/api/autopilot/publish-latest-image`, { method: 'POST' })
    latestImagePublishMessage.value = `Đã đăng ảnh mới nhất lên Facebook. Mã bài viết: ${result.post_id}`
    await Promise.all([loadActivity(), loadDrafts(), refresh()])
  } catch (e: any) {
    latestImagePublishMessage.value = e?.data?.detail || 'Không thể đăng ảnh mới nhất lên Facebook.'
  } finally { latestImagePublishBusy.value = false }
}
async function loadMedia() { media.value = await $fetch<any[]>(`${api}/api/media?limit=100`) }
async function uploadMedia(event: Event) { const input = event.target as HTMLInputElement; const file = input.files?.[0]; if (!file) return; mediaBusy.value = true; mediaMessage.value = ''; try { const body = new FormData(); body.append('file', file); await $fetch(`${api}/api/media/upload`, { method: 'POST', body }); mediaMessage.value = 'Đã tải ảnh lên Cloudinary.'; await Promise.all([loadMedia(), loadActivity()]); } catch (e: any) { mediaMessage.value = e?.data?.detail || 'Tải ảnh thất bại.' } finally { mediaBusy.value = false; input.value = '' } }
await Promise.all([loadActivity(), loadMedia(), loadPublishing()]).catch(() => {})
const selectedCampaignId = computed(() => campaigns.value.find((c: any) => c.name === 'SaaS Tools for Small Businesses')?.id)
async function loadDrafts() {
  if (!selectedCampaignId.value) { drafts.value = []; return }
  drafts.value = await $fetch<any[]>(`${api}/api/campaigns/${selectedCampaignId.value}/drafts`)
}
async function runAutopilot() {
  autopilotBusy.value = true; autopilotMessage.value = ''
  try {
    const result: any = await $fetch(api + '/api/autopilot/run', { method: 'POST' })
    autopilotMessage.value = `Created ${result.created} drafts; skipped ${result.skipped} duplicates. ${result.drafts_total} total drafts in campaign.`
    if (autoGenerateImages.value && result.drafts?.length) { for (const d of result.drafts) { try { await $fetch(`${api}/api/media/generate`, { method: 'POST', body: { draft_id: d.id, prompt: `Square editorial image for a helpful social post titled: ${d.title}. Audience: small business owners and creators. No text or logos.` } }); } catch (e: any) { autopilotMessage.value += ` Image generation failed for draft #${d.id}.`; } } }
    await Promise.all([refresh(), loadDrafts(), loadActivity(), loadMedia()])
  } catch (e: any) { autopilotMessage.value = e?.data?.detail || 'Autopilot could not run.' }
  finally { autopilotBusy.value = false }
}
async function runAndPublishFacebook() {
  if (!confirm('Autopilot sẽ tạo nội dung mới và tự đăng ngay một bài lên Facebook Page. Tiếp tục?')) return
  autopilotBusy.value = true; autopilotMessage.value = ''
  try {
    const result:any = await $fetch(api + '/api/autopilot/run-and-publish-facebook', { method:'POST' })
    autopilotMessage.value = result.publishing === 'published' ? `Đã tự đăng Facebook: ${result.title} · Post ID: ${result.published.post_id}` : (result.message || 'Không có bài mới để đăng.')
    await Promise.all([refresh(),loadDrafts(),loadActivity(),loadMedia()])
  } catch(e:any) { autopilotMessage.value=e?.data?.detail || 'Tự động đăng Facebook thất bại.' }
  finally { autopilotBusy.value=false }
}
async function createSystemeDraft() {
  const campaign = campaigns.value.find((c: any) => c.name === 'SaaS Tools for Small Businesses')
  if (!campaign) { draftMessage.value = 'Load the SaaS starter shortlist first.'; return }
  draftBusy.value = true; draftMessage.value = ''
  const title = 'systeme.io review: an all-in-one toolkit for small businesses'
  const body = `Looking for a simpler way to build a website funnel, collect leads and send marketing emails?

systeme.io brings several online-business tools together, including sales funnels, email marketing, websites and online courses. It may be worth comparing if you are a solo founder, creator or small business trying to reduce the number of separate tools you manage.

Before choosing, check the current plan limits, integrations, support options and pricing against your needs. Start with the free plan if it fits your use case, and upgrade only when you need the additional features.

Explore systeme.io here: ${systemeAffiliateLink}

Disclosure: This is an affiliate link. If you sign up or buy through it, I may earn a commission at no extra cost to you. Please review the provider's current terms before purchasing.`
  try {
    await $fetch(`${api}/api/campaigns/${campaign.id}/drafts`, { method: 'POST', body: { title, body } })
    draftMessage.value = 'Created the first content draft. Review it before publishing.'
    await refresh()
  } catch (e: any) { draftMessage.value = e?.data?.detail || 'Could not create the draft.' }
  finally { draftBusy.value = false }
}
const seedBusy = ref(false), seedMessage = ref('')
async function loadSaaSStarter() {
  seedBusy.value = true; seedMessage.value = ''
  try {
    const result: any = await $fetch(api + '/api/setup/saas-starter', { method: 'POST' })
    seedMessage.value = 'Added ' + result.opportunities_added + ' new candidates. ' + result.opportunities_total + ' total in the shortlist.'
    await Promise.all([refreshOpportunities(), refresh(), refreshCampaigns()])
  } catch (e: any) { seedMessage.value = e?.data?.detail || 'Could not load the SaaS shortlist.' }
  finally { seedBusy.value = false }
}
const researchBusy = ref(false), researchError = ref('')
async function addOpportunity() {
  if (productName.value.trim().length < 2) return
  researchBusy.value = true; researchError.value = ''
  try {
    await $fetch(`${api}/api/research/opportunities`, { method: 'POST', body: { product_name: productName.value, vendor_name: vendor.value, category: 'software', network: 'PartnerStack / direct', target_regions: 'US,UK,EU', commission_pct: commission.value, recurring: recurring.value, evidence_quality: evidence.value, audience_fit: 4, differentiation: 'Solves a specific recurring workflow problem for small businesses and creators.' } })
    productName.value = ''; vendor.value = ''; await refreshOpportunities()
  } catch (e: any) { researchError.value = e?.data?.detail || 'Could not save opportunity' }
  finally { researchBusy.value = false }
}
async function analyzeOpportunity(id: number) { await $fetch(`${api}/api/research/opportunities/${id}/analyze`, { method: 'POST' }); await refreshOpportunities() }
const name = ref(''), niche = ref('technology'), busy = ref(false), error = ref('')
async function createCampaign() {
  if (name.value.trim().length < 2) return
  busy.value = true; error.value = ''
  try {
    await $fetch(`${api}/api/campaigns`, { method: 'POST', body: { name: name.value, niche: niche.value, network: 'unselected' } })
    name.value = ''; await Promise.all([refresh(), refreshCampaigns()])
  } catch (e: any) { error.value = e?.data?.detail || 'Could not create campaign' }
  finally { busy.value = false }
}
</script>
<template>
  <main class="shell">
    <header><div><p class="eyebrow">AUTONOMOUS BUSINESS / MVP 0.3</p><h1>Affiliate Command Center</h1><p class="muted">Research → Content → Approval → Conversion</p></div><span class="live">● SYSTEM ONLINE</span></header>
    <section class="metrics"><article><small>CAMPAIGNS</small><strong>{{ stats.campaigns }}</strong></article><article><small>CONTENT DRAFTS</small><strong>{{ stats.content_drafts }}</strong></article><article><small>CONFIRMED COMMISSION</small><strong>${{ Number(stats.confirmed_commission || 0).toFixed(2) }}</strong><em>Only confirmed conversions</em></article></section>
    <section class="panel"><h2>Create a campaign</h2><p class="muted">Start with one niche and validate demand before scaling.</p><form @submit.prevent="createCampaign"><input v-model="name" placeholder="Campaign name" required minlength="2"><select v-model="niche"><option value="technology">Technology</option><option value="home">Home & living</option><option value="fashion">Fashion</option><option value="software">Software / SaaS</option><option value="other">Other</option></select><button :disabled="busy">{{ busy ? 'Creating…' : 'Create campaign' }}</button></form><p v-if="error" class="error">{{ error }}</p></section>
    <section class="panel"><div class="panel-head"><h2>Campaign pipeline</h2><span class="muted">{{ campaigns.length }} total</span></div><div v-if="!campaigns.length" class="empty">No campaigns yet. Create the first campaign above.</div><div v-for="c in campaigns" :key="c.id" class="campaign"><div><b>{{ c.name }}</b><small>{{ c.niche }} · {{ c.network }}</small></div><span class="tag">{{ c.status }}</span></div></section>
    <section class="panel"><div class="panel-head"><div><h2>Start SaaS campaign</h2><p class="muted">Load an initial shortlist with commission terms linked to official vendor pages.</p></div><button :disabled="seedBusy" @click="loadSaaSStarter">{{ seedBusy ? "Loading…" : "Load SaaS starter shortlist" }}</button></div><p v-if="seedMessage" class="muted">{{ seedMessage }}</p></section>
    <section class="panel"><h2>AI Research Agent · Opportunity intake</h2><p class="muted">Add a candidate program using facts verified from its official page. The score prioritizes research; it is not a revenue forecast.</p><form @submit.prevent="addOpportunity"><input v-model="productName" placeholder="Product / SaaS name" required minlength="2"><input v-model="vendor" placeholder="Vendor name"><input v-model.number="commission" type="number" min="0" max="100" step="0.5" aria-label="Commission percent"><label class="check"><input v-model="recurring" type="checkbox"> Recurring</label><button :disabled="researchBusy">{{ researchBusy ? 'Saving…' : 'Score opportunity' }}</button></form><p v-if="researchError" class="error">{{ researchError }}</p><div v-for="o in opportunities" :key="o.id" class="campaign"><div><b>{{ o.product_name }}</b><small>{{ o.vendor_name || 'Vendor not specified' }} · {{ o.network }} · {{ o.commission_pct }}% {{ o.recurring ? 'recurring' : 'one-time' }}</small><small v-if="o.ai_brief" class="brief">{{ o.ai_brief }}</small></div><div class="score"><b>{{ o.score }}/100</b><small>{{ o.recommendation.replaceAll('_',' ') }}</small><button class="mini" @click="analyzeOpportunity(o.id)">Analyze</button></div></div><div v-if="!opportunities.length" class="empty">No opportunities yet. Add a product or SaaS program to begin.</div></section>
    <section class="panel"><div class="panel-head"><div><h2>systeme.io · Your affiliate link</h2><p class="muted">60% lifetime commission is the advertised program rate; actual earnings depend on eligible referrals and program terms.</p></div><button :disabled="draftBusy" @click="createSystemeDraft">{{ draftBusy ? 'Creating…' : 'Create first content draft' }}</button></div><div class="affiliate-link"><code>{{ systemeAffiliateLink }}</code><button class="mini" @click="globalThis.navigator?.clipboard?.writeText(systemeAffiliateLink)">Copy link</button></div><p v-if="draftMessage" class="muted">{{ draftMessage }}</p><p class="muted">Draft includes an affiliate disclosure. It is saved for review and is not published automatically.</p></section>
<section class="workspace-grid">
    <section class="panel content-panel"><div class="panel-head"><div><h2>Content library</h2><p class="muted">Danh sách nội dung · chọn bài để xem ảnh và đăng.</p></div><button class="mini" @click="loadDrafts">Refresh</button></div><div class="content-tools"><input v-model="draftSearch" placeholder="Tìm nội dung..." aria-label="Tìm nội dung"><select v-model="draftStatusFilter" aria-label="Lọc trạng thái"><option value="all">Tất cả trạng thái</option><option value="draft">Bản nháp</option><option value="published">Đã đăng</option></select><span class="muted">{{ filteredDrafts.length }} bài</span></div><div v-if="!filteredDrafts.length" class="empty">No drafts loaded yet. Run the autopilot or refresh this list.</div><div v-if="selectedDraft" class="selected-draft panel"><b>Đang chọn: {{ selectedDraft.title }}</b><p class="draft-body">{{ selectedDraft.body }}</p><div v-if="selectedDraft.image_url" class="draft-image"><img :src="selectedDraft.image_url" alt="Ảnh xem trước bài đăng"></div><p class="muted">Chọn ảnh trong thư viện bên cạnh rồi gắn vào bài đang chọn.</p><button class="mini" :disabled="!selectedMedia" @click="attachSelectedImage(selectedDraft)">Gắn ảnh đang chọn vào bài</button><p v-if="draftImageMessage" class="muted">{{ draftImageMessage }}</p></div><article v-for="d in filteredDrafts" :key="d.id" class="draft-card"><div class="panel-head"><b>{{ d.title }}</b><span class="tag">{{ d.status }}</span></div><button class="mini" @click="selectedDraftId=d.id">{{ selectedDraftId === d.id ? 'Đang xem bài này' : 'Chọn / xem bài' }}</button><p class="draft-body">{{ d.body }}</p><div v-if="d.image_url" class="draft-image"><img :src="d.image_url" alt="AI generated post image"><a :href="d.image_url" target="_blank" rel="noopener">Open image ↗</a></div><button class="mini" :disabled="imageBusy === d.id" @click="generateDraftImage(d)">{{ imageBusy === d.id ? "Generating image…" : d.image_url ? "Regenerate image" : "Generate AI image" }}</button><button class="mini publish-btn" :disabled="publishBusy === d.id || d.status === 'published'" @click="scheduleDraft(d)">{{ publishBusy === d.id ? "Publishing…" : d.status === 'published' ? "Published" : "Publish now" }}</button></article></section>
    <section class="panel image-panel"><div class="panel-head"><div><h2>Image library · Cloudinary</h2><p class="muted">Ảnh dùng cho nội dung · upload và chọn ảnh mới nhất để đăng.</p></div><label class="upload-btn">{{ mediaBusy ? 'Uploading…' : 'Upload image' }}<input type="file" accept="image/jpeg,image/png,image/webp" :disabled="mediaBusy" @change="uploadMedia"></label></div><p v-if="mediaMessage" class="muted">{{ mediaMessage }}</p><div class="publish-controls" style="margin:12px 0"><button class="publish-btn" :disabled="latestImagePublishBusy || !media.length" @click="publishLatestImage">{{ latestImagePublishBusy ? "Đang đăng ảnh mới nhất…" : "Tự chọn ảnh mới nhất và đăng Facebook" }}</button></div><p v-if="latestImagePublishMessage" class="muted">{{ latestImagePublishMessage }}</p><div v-if="!media.length" class="empty">Chưa có ảnh nào được lưu. Hãy tải ảnh lên để bắt đầu thư viện.</div><div class="media-grid"><article v-for="m in media" :key="m.id" class="media-card" :class="{ selected: selectedMediaId === m.id }"><button class="mini" @click="selectedMediaId=m.id">{{ selectedMediaId === m.id ? 'Đã chọn ảnh' : 'Chọn ảnh này' }}</button><img :src="m.url" :alt="m.filename"><small>{{ m.filename || m.public_id }}</small><a :href="m.url" target="_blank" rel="noopener">Mở ảnh ↗</a></article></div></section>
    </section>
    <section class="panel"><div class="panel-head"><div><h2>Affiliate Autopilot</h2><p class="muted">Generate three distinct useful content drafts per daily run. Duplicate drafts are skipped.</p></div><button :disabled="autopilotBusy" @click="runAutopilot">{{ autopilotBusy ? 'Running…' : 'Run content autopilot' }}</button><button :disabled="autopilotBusy" @click="runAndPublishFacebook">Tạo nội dung và tự đăng Facebook thử</button></div><p v-if="autopilotMessage" class="muted">{{ autopilotMessage }}</p><label class="check"><input v-model="autoGenerateImages" type="checkbox"> Tự tạo ảnh AI cho các bài mới (có thể phát sinh phí API)</label><p class="muted">Khi bật, mỗi bản nháp mới sẽ được tạo một ảnh và lưu lên Cloudinary. Nút tự đăng sẽ đăng ngay một bài mới lên Facebook; khung giờ tự động sẽ cấu hình ở bước tiếp theo.</p></section>
    <section class="panel"><div class="panel-head"><div><h2>Social publishing · Direct Meta API</h2><p class="muted">Đăng trực tiếp lên Facebook Page và Threads bằng Meta API.</p></div><span class="tag">{{ publishStatus.connected ? 'META API READY' : 'META LOGIN REQUIRED' }}</span></div><p class="muted">Brand: Chiu Chiu · Asia/Ho_Chi_Minh · Facebook, Instagram, Threads, Pinterest, TikTok</p><label class="check"><input type="checkbox" v-model="publishStatus.auto_publish" disabled @change="toggleAutoPublish"> Tự động đăng theo lịch hiện đang tắt; chỉ đăng khi bạn bấm Publish now</label><p class="muted">Cần cấu hình Facebook Page ID + Page Access Token và Threads User ID + Access Token trong Render. Nút Publish now sẽ đăng ngay, không qua Metricool. Hiện chỉ hỗ trợ Facebook và Threads.</p><div class="publish-controls"><div class="check-list"><label class="check"><input type="checkbox" value="facebook" v-model="publishNetworks"> Facebook</label><label class="check"><input type="checkbox" value="threads" v-model="publishNetworks"> Threads</label></div></div><p class="muted">Chọn Facebook/Threads, sau đó nhấn “Publish now” trong bản nháp. Đây là thao tác đăng thật.</p></section>
    <section class="panel"><div class="panel-head"><div><h2>Activity log · Lịch sử hoạt động</h2><p class="muted">Lọc nhật ký theo ngày, xem trạng thái từng thao tác.</p></div><div class="activity-tools"><input v-model="activityDate" type="date" aria-label="Lọc ngày"><button class="mini" @click="loadActivity">Lọc / Refresh</button><button class="mini ghost" @click="activityDate = ''; loadActivity()">Tất cả</button></div></div><div v-if="!activity.length" class="empty">Chưa có hoạt động được ghi log trong phiên bản này.</div><div v-for="a in activity" :key="a.id" class="campaign"><div><b>{{ a.message }}</b><small>{{ new Date(a.created_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) }} · {{ a.event_type }}</small></div><span class="tag">{{ a.status }}</span></div></section>
    <section class="panel"><h2>Affiliate network shortlist</h2><div v-for="n in networks" :key="n.name" class="campaign"><div><b>{{ n.name }}</b><small>{{ n.best_for }} · {{ n.cost }}</small></div><a :href="n.url" target="_blank" rel="noopener">Official site ↗</a></div></section>
    <footer>Human approval is required before publishing, outreach, or spending. No revenue is assumed.</footer>
  </main>
</template>
<style>
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui;background:#07111f;color:#e8f2ff}*{box-sizing:border-box}body{margin:0}.shell{max-width:1500px;margin:0 auto;padding:28px 24px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.shell>header,.shell>.metrics,.shell>footer{grid-column:1/-1}.shell>.panel{margin:0;min-width:0}.shell>.panel:nth-of-type(8){grid-column:1/-1}.workspace-grid{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:16px;align-items:start}.workspace-grid>.panel{margin:0;min-width:0}.content-tools{display:flex;gap:8px;align-items:center;margin:14px 0;flex-wrap:wrap}.content-tools input{min-width:160px}.content-tools select{max-width:190px}.content-tools span{margin-left:auto}.content-panel .draft-card{padding:14px 0}.image-panel .media-grid{grid-template-columns:repeat(auto-fill,minmax(115px,1fr));max-height:620px;overflow:auto;padding-right:4px}.image-panel .media-card img{aspect-ratio:1}.image-panel .publish-controls{display:block}.image-panel .publish-btn{width:100%;padding:12px}.content-panel .draft-body{max-height:150px}header,.panel-head{display:flex;justify-content:space-between;align-items:center;gap:18px}h1{font-size:clamp(30px,5vw,48px);margin:6px 0}.eyebrow{color:#45e4d0;letter-spacing:.16em;font-size:11px}.muted,small,footer{color:#8da5bd}.live,.tag{color:#45e4d0;border:1px solid #1c716f;padding:8px 12px;border-radius:30px;font-size:11px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:30px 0}.metrics article,.panel{background:#101e31;border:1px solid #203a54;border-radius:16px;padding:22px}.metrics small{display:block;letter-spacing:.12em}.metrics strong{display:block;font-size:32px;margin:12px 0}.metrics em{font-size:11px;color:#8da5bd;font-style:normal}.panel{margin:16px 0}.panel h2{margin:0 0 8px}form{display:flex;gap:10px;margin-top:18px}input,select{background:#081525;border:1px solid #29435e;border-radius:9px;color:#fff;padding:12px;min-width:0}input{flex:1}button{background:#16b8a6;color:#04151b;font-weight:700;border:0;border-radius:9px;padding:0 18px;cursor:pointer}button:disabled{opacity:.5}.draft-card{padding:14px 0;border-bottom:1px solid #20354b}.draft-body{white-space:pre-wrap;line-height:1.55;color:#c0d2e5;max-height:260px;overflow:auto}.publish-btn{background:#287cdb;color:#fff}.publish-controls{display:flex;gap:22px;align-items:flex-start;flex-wrap:wrap}.publish-controls>label{display:grid;gap:8px;color:#8da5bd}.check-list{display:flex;gap:14px;flex-wrap:wrap}.draft-image{display:flex;align-items:center;gap:12px;margin:10px 0}.draft-image img{width:112px;height:112px;object-fit:cover;border-radius:9px;border:1px solid #29435e}.activity-tools{display:flex;align-items:center;gap:8px}.activity-tools input{max-width:150px}.ghost{background:transparent;color:#8da5bd;border:1px solid #29435e}.campaign{display:flex;justify-content:space-between;align-items:center;padding:16px 0;border-bottom:1px solid #20354b}.campaign small{display:block;margin-top:5px}.campaign .brief{max-width:760px;white-space:pre-wrap;line-height:1.5;color:#c0d2e5}.score{text-align:right;min-width:120px}.score b{color:#45e4d0}.mini{display:block;margin:6px 0 0 auto;padding:6px 10px;font-size:11px}.check{display:flex;align-items:center;gap:6px;color:#9bb0c6;font-size:12px}a{color:#45e4d0;font-size:12px}.affiliate-link{display:flex;gap:12px;align-items:center;background:#081525;border:1px solid #29435e;border-radius:9px;padding:12px;margin-top:14px}.affiliate-link code{overflow-wrap:anywhere;color:#b8d5eb;font-size:12px;flex:1}.upload-btn{display:inline-flex;align-items:center;background:#16b8a6;color:#04151b;font-weight:700;border-radius:9px;padding:12px 16px;cursor:pointer}.upload-btn input{display:none}.media-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px}.media-card{background:#081525;border:1px solid #29435e;border-radius:10px;padding:10px;min-width:0}.media-card img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:7px}.media-card small{display:block;overflow-wrap:anywhere;margin:8px 0}.empty{padding:28px;color:#8da5bd;text-align:center}.error{color:#ff9d9d}footer{font-size:12px;margin-top:28px}@media(max-width:850px){.shell{grid-template-columns:1fr}.workspace-grid{grid-template-columns:1fr}.shell>header,.shell>.metrics,.shell>footer,.shell>.panel{grid-column:1/-1}}@media(max-width:650px){.metrics{grid-template-columns:1fr}header{align-items:flex-start;flex-direction:column}form{flex-direction:column}button{padding:13px}}
</style>
