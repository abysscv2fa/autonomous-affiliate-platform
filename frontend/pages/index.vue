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
const imageAgentBusy = ref(false), imageAgentMessage = ref('')
const collaborationTopic = ref('Lên ý tưởng bài viết affiliate hôm nay')
const collaborationBusy = ref(false), collaborationError = ref(''), collaborationMessages = ref<any[]>([]), collaborationSession = ref('')
async function loadAgentConversation() { try { collaborationMessages.value = await $fetch<any[]>(`${api}/api/agents/conversations?limit=40`) } catch {} }
async function startAgentDiscussion() {
  collaborationBusy.value = true; collaborationError.value = ''
  autopilotBusy.value = true; autopilotMessage.value = ''
  try {
    if (!selectedCampaignId.value) {
      await $fetch(`${api}/api/setup/saas-starter`, { method:'POST' })
      await refreshCampaigns()
    }
    const meeting:any = await $fetch(`${api}/api/agents/collaborate`, { method:'POST', body:{ topic:collaborationTopic.value, campaign_id:selectedCampaignId.value || null, rounds:2 } })
    collaborationSession.value = meeting.session_id
    collaborationMessages.value = (meeting.messages || []).map((m:any,i:number)=>({...m,id:i,session_id:meeting.session_id}))
    const approvedBrief = (meeting.messages || []).map((m:any)=>`${m.agent}: ${m.message}`).join("\n\n").slice(0,9500)
    const imageBrief = [...(meeting.messages || [])].reverse().find((m:any)=>m.agent === 'Trợ lý hình ảnh')?.message || ''
    const result:any = await $fetch(`${api}/api/autopilot/run`, { method:'POST', body:{ topic:collaborationTopic.value, agent_brief:approvedBrief } })
    const imageErrors:string[] = []
    let imagesCreated = 0
    if (autoGenerateImages.value) {
      for (const d of (result.drafts || [])) {
        try {
          await $fetch(`${api}/api/media/generate`, { method:'POST', body:{
            draft_id:d.id,
            prompt:`Create a premium, photorealistic editorial campaign image for this affiliate post. Follow this visual direction agreed by the Trợ lý hình ảnh: ${imageBrief.slice(0,650)}. Title: ${d.title}. Context: ${String(d.body || '').slice(0,500)}. Audience: small business owners, creators and online entrepreneurs. Square 1:1 composition. No text, logos or watermarks.`
          }})
          imagesCreated++
        } catch (e:any) { imageErrors.push(`#${d.id}`) }
      }
    }
    autopilotMessage.value = `Trợ lý nội dung đã tạo ${result.created} bản nháp. ${autoGenerateImages.value ? `Trợ lý hình ảnh đã tạo ${imagesCreated}/${(result.drafts || []).length} ảnh.` : 'Đã bỏ qua tạo ảnh theo cài đặt.'} Tất cả được lưu để bạn duyệt; không tự đăng.`
    if (imageErrors.length) autopilotMessage.value += ` Lỗi tạo ảnh ở bản nháp ${imageErrors.join(', ')}; có thể thử tạo lại trong từng bản nháp.`
    await Promise.all([refresh(),loadDrafts(),loadMedia(),loadActivity()])
  } catch(e:any) {
    collaborationError.value = e?.data?.detail || 'Quy trình hai Agent chưa hoàn tất. Kiểm tra OpenAI và Cloudinary.'
  } finally { collaborationBusy.value=false; autopilotBusy.value=false }
}
async function runImageAgent() {
  const draft = selectedDraft.value || drafts.value[0]
  if (!draft) { imageAgentMessage.value = 'Hãy tạo hoặc chọn một bản nháp trước khi yêu cầu Trợ lý hình ảnh.'; return }
  imageAgentBusy.value = true; imageAgentMessage.value = ''
  try {
    await generateDraftImage(draft)
    imageAgentMessage.value = mediaMessage.value || 'Trợ lý hình ảnh đã tạo ảnh cho bản nháp.'
    await Promise.all([loadDrafts(), loadMedia(), loadActivity()])
  } catch (e:any) {
    imageAgentMessage.value = e?.data?.detail || 'Trợ lý hình ảnh chưa thể tạo ảnh. Kiểm tra OpenAI và Cloudinary.'
  } finally { imageAgentBusy.value = false }
}
const autopilotBusy = ref(false), autopilotMessage = ref('')
const drafts = ref<any[]>([])
const selectedDraftId = ref<number | null>(null), selectedMediaId = ref<number | null>(null), draftImageMessage = ref('')
const selectedDraft = computed(() => drafts.value.find((d:any) => d.id === selectedDraftId.value) || null)
const selectedMedia = computed(() => media.value.find((m:any) => m.id === selectedMediaId.value) || null)
const draftSearch = ref(''), draftStatusFilter = ref('all')
const filteredDrafts = computed(() => drafts.value.filter((d:any) => d.status !== 'published' && (draftStatusFilter.value === 'all' || d.status === draftStatusFilter.value) && `${d.title || ''} ${d.body || ''}`.toLowerCase().includes(draftSearch.value.toLowerCase().trim())))
const activity = ref<any[]>([]), media = ref<any[]>([]), mediaBusy = ref(false), mediaMessage = ref('')
const imageBusy = ref<number | null>(null), autoGenerateImages = ref(false), activityDate = ref('')
const publishStatus = ref<any>({ connected: false, facebook_connected: false, auto_publish: false, schedule_time: '19:30', timezone: 'Asia/Ho_Chi_Minh' }), publishBusy = ref<number | null>(null)
const publishNetworks = ref(['facebook','threads'])
const publishDate = ref(new Date(Date.now() + 86400000).toISOString().slice(0,16))
async function loadPublishing() { publishStatus.value = await $fetch<any>(`${api}/api/publishing/status`) }
async function toggleAutoPublish() { const requested = !publishStatus.value.auto_publish; publishStatus.value.auto_publish = requested; try { const saved:any = await $fetch<any>(`${api}/api/publishing/settings`, { method:'PUT', body:{auto_publish:requested} }); publishStatus.value.auto_publish = saved.auto_publish; await loadActivity() } catch(e:any) { publishStatus.value.auto_publish = !requested; autopilotMessage.value = e?.data?.detail || 'Không thể cập nhật lịch tự đăng.' } }
async function scheduleDraft(d:any) { if (!publishNetworks.value.length) { autopilotMessage.value='Hãy chọn ít nhất một nền tảng.'; return }; publishBusy.value=d.id; try { const result:any = await $fetch(`${api}/api/drafts/${d.id}/publish`, {method:'POST',body:{date_time:new Date().toISOString().slice(0,16),networks:publishNetworks.value}}); if (result.published?.length) d.status='published'; const ok=(result.published || []).map((x:any)=>x.platform); const failed=(result.failures || []).map((x:any)=>`${x.platform}: ${x.error}`); autopilotMessage.value = failed.length ? `Đã đăng: ${ok.join(', ') || 'không có'}. Thất bại: ${failed.join(' | ')}` : `Đã đăng bài viết #${d.id} lên: ${ok.join(', ')}.`; await Promise.all([loadActivity(),loadDrafts()]) } catch(e:any) { autopilotMessage.value=e?.data?.detail || 'Không thể đăng bài viết.' } finally { publishBusy.value=null } }
async function attachSelectedImage(d:any) { if (!selectedMedia.value) return; draftImageMessage.value=''; try { const result:any=await $fetch(`${api}/api/drafts/${d.id}/image?asset_id=${selectedMedia.value.id}`,{method:'PUT'}); d.image_url=result.image_url; draftImageMessage.value=`Đã gắn ảnh ${selectedMedia.value.filename || selectedMedia.value.public_id} vào bài viết #${d.id}.`; await loadDrafts() } catch(e:any) { draftImageMessage.value=e?.data?.detail || 'Không thể gắn ảnh vào bài viết viết.' } }
async function loadActivity() { const q = activityDate.value ? `&date_from=${activityDate.value}&date_to=${activityDate.value}` : ''; activity.value = await $fetch<any[]>(`${api}/api/activity?limit=100${q}`) }
async function generateDraftImage(d: any) { imageBusy.value = d.id; mediaMessage.value = ''; try { const result: any = await $fetch(`${api}/api/media/generate`, { method: 'POST', body: { draft_id: d.id, prompt: `Create an image that visually communicates this social post. Topic: ${d.title}. Context: ${String(d.body || '').slice(0, 700)}. Audience: small business owners, creators and online entrepreneurs. Square 1:1 composition.` } }); d.image_url = result.url; mediaMessage.value = 'Đã tạo ảnh AI và lưu lên Cloudinary.'; await Promise.all([loadMedia(), loadActivity()]); } catch (e: any) { mediaMessage.value = e?.data?.detail || 'Không thể tạo ảnh bằng AI.'; } finally { imageBusy.value = null } }
async function loadMedia() { media.value = await $fetch<any[]>(`${api}/api/media?limit=100`) }
async function uploadMedia(event: Event) { const input = event.target as HTMLInputElement; const file = input.files?.[0]; if (!file) return; mediaBusy.value = true; mediaMessage.value = ''; try { const body = new FormData(); body.append('file', file); await $fetch(`${api}/api/media/upload`, { method: 'POST', body }); mediaMessage.value = 'Đã tải ảnh lên Cloudinary.'; await Promise.all([loadMedia(), loadActivity()]); } catch (e: any) { mediaMessage.value = e?.data?.detail || 'Tải ảnh thất bại.' } finally { mediaBusy.value = false; input.value = '' } }
const selectedCampaignId = computed(() => campaigns.value.find((c: any) => c.name === 'SaaS Tools for Small Businesses')?.id)
await Promise.all([loadActivity(), loadMedia(), loadPublishing(), loadAgentConversation(), loadDrafts()]).catch(() => {})
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
  } catch (e: any) { autopilotMessage.value = e?.data?.detail || 'Không thể chạy trợ lý nội dung. Hãy kiểm tra cấu hình AI và nhật ký máy chủ.' }
  finally { autopilotBusy.value = false }
}
async function createSystemeDraft() {
  const campaign = campaigns.value.find((c: any) => c.name === 'SaaS Tools for Small Businesses')
  if (!campaign) { draftMessage.value = 'Trước tiên hãy tải danh sách SaaS mẫu.'; return }
  draftBusy.value = true; draftMessage.value = ''
  const title = 'systeme.io review: an all-in-one toolkit for small businesses'
  const body = `Looking for a simpler way to build a website funnel, collect leads and send marketing emails?

systeme.io brings several online-business tools together, including sales funnels, email marketing, websites and online courses. It may be worth comparing if you are a solo founder, creator or small business trying to reduce the number of separate tools you manage.

Before choosing, check the current plan limits, integrations, support options and pricing against your needs. Start with the free plan if it fits your use case, and upgrade only when you need the additional features.

Explore systeme.io here: ${systemeAffiliateLink}

Disclosure: This is an affiliate link. If you sign up or buy through it, I may earn a commission at no extra cost to you. Please review the provider's current terms before purchasing.`
  try {
    await $fetch(`${api}/api/campaigns/${campaign.id}/drafts`, { method: 'POST', body: { title, body } })
    draftMessage.value = 'Đã tạo bản nháp đầu tiên. Hãy kiểm duyệt trước khi đăng.'
    await refresh()
  } catch (e: any) { draftMessage.value = e?.data?.detail || 'Không thể tạo bản nháp.' }
  finally { draftBusy.value = false }
}
const seedBusy = ref(false), seedMessage = ref('')
async function loadSaaSStarter() {
  seedBusy.value = true; seedMessage.value = ''
  try {
    const result: any = await $fetch(api + '/api/setup/saas-starter', { method: 'POST' })
    seedMessage.value = 'Added ' + result.opportunities_added + ' new candidates. ' + result.opportunities_total + ' total in the shortlist.'
    await Promise.all([refreshOpportunities(), refresh(), refreshCampaigns()])
  } catch (e: any) { seedMessage.value = e?.data?.detail || 'Không thể tải danh sách SaaS.' }
  finally { seedBusy.value = false }
}
const researchBusy = ref(false), researchError = ref('')
async function addOpportunity() {
  if (productName.value.trim().length < 2) return
  researchBusy.value = true; researchError.value = ''
  try {
    await $fetch(`${api}/api/research/opportunities`, { method: 'POST', body: { product_name: productName.value, vendor_name: vendor.value, category: 'software', network: 'PartnerStack / direct', target_regions: 'US,UK,EU', commission_pct: commission.value, recurring: recurring.value, evidence_quality: evidence.value, audience_fit: 4, differentiation: 'Solves a specific recurring workflow problem for small businesses and creators.' } })
    productName.value = ''; vendor.value = ''; await refreshOpportunities()
  } catch (e: any) { researchError.value = e?.data?.detail || 'Không thể lưu cơ hội tiếp thị' }
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
  } catch (e: any) { error.value = e?.data?.detail || 'Không thể tạo chiến dịch' }
  finally { busy.value = false }
}
</script>
<template>
  <main class="shell compact-shell">
    <header class="compact-header">
      <div><p class="eyebrow">AFFPILOT</p><h1>Trung tâm điều hành</h1><p class="muted">Tạo nội dung · Duyệt · Đăng khi bạn cho phép</p></div>
      <span class="live">● ĐANG HOẠT ĐỘNG</span>
    </header>

    <section class="metrics compact-metrics">
      <article><small>CHIẾN DỊCH</small><strong>{{ stats.campaigns }}</strong></article>
      <article><small>BẢN NHÁP</small><strong>{{ stats.content_drafts }}</strong></article>
      <article><small>HOA HỒNG ĐÃ XÁC NHẬN</small><strong>${{ Number(stats.confirmed_commission || 0).toFixed(2) }}</strong></article>
    </section>

    <section class="panel compact-create">
      <div class="panel-head"><div><p class="eyebrow">BƯỚC 1 · SẢN XUẤT</p><h2>Tạo nội dung bằng AI</h2><p class="muted">Hai trợ lý thảo luận, thống nhất hướng triển khai, sau đó tạo 3 bản nháp.</p></div><span class="tag">NỘI DUNG + HÌNH ẢNH</span></div>
      <label class="compact-label">Chủ đề nội dung</label>
      <div class="compact-run"><input v-model="collaborationTopic" placeholder="Ví dụ: Công cụ AI hữu ích cho doanh nghiệp nhỏ"><button :disabled="collaborationBusy" @click="startAgentDiscussion">{{ collaborationBusy ? 'Đang sản xuất…' : '▶ Bắt đầu tạo' }}</button></div>
      <label class="check compact-check"><input v-model="autoGenerateImages" type="checkbox"> Tạo ảnh cho từng bản nháp và lưu lên Cloudinary</label>
      <p class="muted compact-note">Không tự động đăng bài. Bạn luôn duyệt trước khi xuất bản.</p>
      <p v-if="collaborationError" class="error">{{ collaborationError }}</p>
      <p v-if="autopilotMessage" class="agent-message">{{ autopilotMessage }}</p>
      <details v-if="collaborationMessages.length" class="conversation-details"><summary>Xem nội dung trao đổi của hai trợ lý</summary><div class="conversation-feed"><article v-for="(m,i) in collaborationMessages" :key="m.id || i" class="conversation-message"><div class="conversation-avatar">{{ m.agent === 'Trợ lý hình ảnh' ? '🎨' : '✍️' }}</div><div><b>{{ m.agent }}</b><p>{{ m.message }}</p></div></article></div></details>
    </section>

    <section class="panel compact-drafts">
      <div class="panel-head"><div><p class="eyebrow">BƯỚC 2 · KIỂM DUYỆT</p><h2>Bản nháp nội dung</h2><p class="muted">Kiểm tra bài viết và hình ảnh trước khi đăng.</p></div><button class="mini" @click="loadDrafts">↻ Làm mới</button></div>
      <div class="content-tools"><input v-model="draftSearch" placeholder="Tìm bài viết..." aria-label="Tìm bài viết"><select v-model="draftStatusFilter" aria-label="Lọc trạng thái"><option value="all">Tất cả</option><option value="draft">Bản nháp</option></select><span class="muted">{{ filteredDrafts.length }} bài</span></div>
      <div v-if="!filteredDrafts.length" class="empty">Chưa có bản nháp. Nhập chủ đề và bấm “Bắt đầu tạo”.</div>
      <article v-for="d in filteredDrafts" :key="d.id" class="draft-card compact-draft">
        <div class="panel-head"><div><b>{{ d.title }}</b><small class="draft-id">Bài #{{ d.id }}</small></div><span class="tag">{{ d.status === 'draft' ? 'BẢN NHÁP' : d.status }}</span></div>
        <button class="mini ghost" @click="selectedDraftId = selectedDraftId === d.id ? null : d.id">{{ selectedDraftId === d.id ? 'Thu gọn nội dung' : 'Xem nội dung' }}</button>
        <div v-if="selectedDraftId === d.id"><p class="draft-body">{{ d.body }}</p><div v-if="d.image_url" class="draft-image"><img :src="d.image_url" alt="Ảnh bài viết"><a :href="d.image_url" target="_blank" rel="noopener">Mở ảnh</a></div></div>
        <div class="compact-actions"><button class="mini" :disabled="imageBusy === d.id" @click="generateDraftImage(d)">{{ imageBusy === d.id ? 'Đang tạo ảnh…' : d.image_url ? 'Tạo lại ảnh' : 'Tạo ảnh' }}</button><button class="mini publish-btn" :disabled="publishBusy === d.id" @click="scheduleDraft(d)">{{ publishBusy === d.id ? 'Đang đăng…' : 'Đăng bài' }}</button></div>
      </article>
    </section>

    <section class="panel compact-library">
      <div class="panel-head"><div><p class="eyebrow">BƯỚC 3 · TÀI NGUYÊN</p><h2>Thư viện ảnh</h2><p class="muted">{{ media.length }} ảnh đã lưu trên Cloudinary</p></div><label class="upload-btn">{{ mediaBusy ? 'Đang tải…' : '+ Tải ảnh' }}<input type="file" accept="image/jpeg,image/png,image/webp" :disabled="mediaBusy" @change="uploadMedia"></label></div>
      <p v-if="mediaMessage" class="muted">{{ mediaMessage }}</p><div v-if="!media.length" class="empty">Chưa có ảnh nào.</div>
      <div class="media-grid"><article v-for="m in media" :key="m.id" class="media-card" :class="{ selected: selectedMediaId === m.id }"><img :src="m.url" :alt="m.filename"><small>{{ m.filename || m.public_id }}</small><button class="mini" @click="selectedMediaId = m.id">{{ selectedMediaId === m.id ? 'Đã chọn' : 'Chọn ảnh' }}</button><button v-if="selectedDraft" class="mini" @click="attachSelectedImage(selectedDraft)">Gắn vào bài đang chọn</button></article></div>
      <p v-if="selectedDraft" class="muted">Bài đang chọn: {{ selectedDraft.title }}</p><p v-if="draftImageMessage" class="muted">{{ draftImageMessage }}</p>
    </section>

    <section class="panel compact-activity">
      <div class="panel-head"><div><p class="eyebrow">THEO DÕI</p><h2>Nhật ký hoạt động</h2></div><div class="activity-tools"><input v-model="activityDate" type="date" aria-label="Lọc ngày"><button class="mini" @click="loadActivity">Lọc</button><button class="mini ghost" @click="activityDate = ''; loadActivity()">Tất cả</button></div></div>
      <div v-if="!activity.length" class="empty">Chưa có hoạt động được ghi nhận.</div><div v-for="a in activity" :key="a.id" class="campaign"><div><b>{{ a.message }}</b><small>{{ new Date(a.created_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) }} · {{ a.event_type }}</small></div><span class="tag">{{ a.status }}</span></div>
    </section>

    <details class="panel advanced-panel">
      <summary><span><b>Cài đặt nâng cao</b><small>Chiến dịch · Nghiên cứu sản phẩm · Liên kết affiliate · Mạng lưới</small></span></summary>
      <section class="advanced-section"><h3>Chiến dịch</h3><form @submit.prevent="createCampaign"><input v-model="name" placeholder="Tên chiến dịch" required minlength="2"><select v-model="niche"><option value="technology">Công nghệ</option><option value="home">Nhà cửa & đời sống</option><option value="fashion">Thời trang</option><option value="software">Phần mềm / SaaS</option><option value="other">Khác</option></select><button :disabled="busy">{{ busy ? 'Đang tạo…' : 'Tạo chiến dịch' }}</button></form><p v-if="error" class="error">{{ error }}</p><div v-for="c in campaigns" :key="c.id" class="campaign"><div><b>{{ c.name }}</b><small>{{ c.niche }} · {{ c.network }}</small></div><span class="tag">{{ c.status }}</span></div></section>
      <section class="advanced-section"><div class="panel-head"><div><h3>Danh sách SaaS gợi ý</h3><p class="muted">Nạp chương trình affiliate đã chọn lọc.</p></div><button class="mini" :disabled="seedBusy" @click="loadSaaSStarter">{{ seedBusy ? 'Đang tải…' : 'Tải danh sách' }}</button></div><p v-if="seedMessage" class="muted">{{ seedMessage }}</p><div v-for="o in opportunities" :key="o.id" class="campaign"><div><b>{{ o.product_name }}</b><small>{{ o.vendor_name || 'Chưa có nhà cung cấp' }} · {{ o.network }} · {{ o.commission_pct }}%</small><small v-if="o.ai_brief" class="brief">{{ o.ai_brief }}</small></div><div class="score"><b>{{ o.score }}/100</b><button class="mini" @click="analyzeOpportunity(o.id)">Phân tích</button></div></div></section>
      <section class="advanced-section"><h3>Thêm chương trình affiliate</h3><form @submit.prevent="addOpportunity"><input v-model="productName" placeholder="Tên sản phẩm / SaaS" required minlength="2"><input v-model="vendor" placeholder="Nhà cung cấp"><input v-model.number="commission" type="number" min="0" max="100" step="0.5" aria-label="Phần trăm hoa hồng"><label class="check"><input v-model="recurring" type="checkbox"> Hoa hồng định kỳ</label><button :disabled="researchBusy">{{ researchBusy ? 'Đang lưu…' : 'Lưu chương trình' }}</button></form><p v-if="researchError" class="error">{{ researchError }}</p></section>
      <section class="advanced-section"><h3>Liên kết systeme.io</h3><p class="muted">Liên kết affiliate đang được sử dụng trong bản nháp mẫu.</p><div class="affiliate-link"><code>{{ systemeAffiliateLink }}</code><button class="mini" @click="globalThis.navigator?.clipboard?.writeText(systemeAffiliateLink)">Sao chép</button></div><button class="mini" :disabled="draftBusy" @click="createSystemeDraft">{{ draftBusy ? 'Đang tạo…' : 'Tạo bản nháp mẫu' }}</button><p v-if="draftMessage" class="muted">{{ draftMessage }}</p></section>
      <section class="advanced-section"><h3>Mạng lưới tiếp thị liên kết</h3><div v-for="n in networks" :key="n.name" class="campaign"><div><b>{{ n.name }}</b><small>{{ n.best_for }} · {{ n.cost }}</small></div><a :href="n.url" target="_blank" rel="noopener">Trang chính thức ↗</a></div></section>
      <section class="advanced-section"><h3>Chạy riêng trợ lý nội dung</h3><p class="muted">Dùng khi chỉ muốn tạo bản nháp mà không cần cuộc thảo luận của hai trợ lý.</p><button :disabled="autopilotBusy" @click="runAutopilot">{{ autopilotBusy ? 'Đang chạy…' : 'Chạy trợ lý nội dung' }}</button></section>
    </details>
    <footer>Nội dung chỉ được đăng sau khi bạn kiểm duyệt và chủ động bấm nút đăng.</footer>
  </main>
</template>
<style>
.compact-shell{max-width:1120px;grid-template-columns:minmax(0,1fr);gap:14px;padding:24px 20px}
.compact-shell>header,.compact-shell>.metrics,.compact-shell>footer,.compact-shell>.panel{grid-column:1}
.compact-header{align-items:center}
.compact-header h1{font-size:34px}
.compact-metrics{margin:4px 0 0;gap:10px}
.compact-metrics article{padding:16px 18px}
.compact-metrics strong{font-size:27px;margin:8px 0 0}
.compact-shell>.panel{margin:0;padding:20px}
.compact-create{border-color:#287c78;background:linear-gradient(130deg,#132d40,#101e31)}
.eyebrow{margin:0 0 6px}
.compact-label{display:block;color:#b7cadd;font-size:12px;margin:14px 0 7px}
.compact-run{display:flex;gap:9px}
.compact-run input{flex:1}
.compact-run button{min-width:155px;padding:0 18px}
.compact-check{margin-top:12px}
.compact-note{font-size:11px;margin:8px 0 0}
.agent-message{color:#75e6d3}
.conversation-details{margin-top:14px;border-top:1px solid #29435e;padding-top:12px}
.conversation-details summary,.advanced-panel summary{cursor:pointer;color:#9fc6d9;font-size:13px}
.conversation-feed{display:grid;gap:8px;margin-top:12px;max-height:360px;overflow:auto}
.conversation-message{display:flex;gap:10px;padding:10px;background:#081525;border-radius:9px}
.conversation-message p{white-space:pre-wrap;line-height:1.5;color:#c0d2e5;margin:6px 0}
.compact-draft{padding:14px 0}
.compact-draft .panel-head{align-items:flex-start}
.draft-id{display:block;margin-top:5px}
.compact-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:10px}
.compact-actions .mini{margin:0}
.compact-actions .publish-btn{background:#287cdb;color:#fff}
.compact-draft .draft-body{max-height:320px}
.compact-library .media-grid{grid-template-columns:repeat(auto-fill,minmax(125px,1fr));max-height:440px;overflow:auto}
.compact-library .media-card{padding:8px}
.compact-library .media-card img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:7px}
.media-card.selected{border-color:#45e4d0}
.compact-activity .campaign{gap:12px}
.advanced-panel{padding:0!important}
.advanced-panel summary{list-style:none;padding:18px 20px;display:flex;align-items:center}
.advanced-panel summary::-webkit-details-marker{display:none}
.advanced-panel summary:after{content:'＋';margin-left:auto;font-size:18px}
.advanced-panel[open] summary:after{content:'−'}
.advanced-panel summary small{display:block;margin-top:5px;color:#8da5bd}
.advanced-section{padding:16px 20px;border-top:1px solid #203a54}
.advanced-section h3{margin:0 0 10px;font-size:15px}
.advanced-section form{flex-wrap:wrap}
.advanced-section form input{min-width:140px}
.advanced-section .campaign:last-child{border-bottom:0}
.advanced-section .affiliate-link{flex-wrap:wrap}
.compact-shell footer{text-align:center;padding:8px 0 16px}
@media(max-width:650px){.compact-shell{padding:16px 12px}.compact-shell>.panel{padding:15px}.compact-metrics{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.compact-metrics article{padding:12px 9px}.compact-metrics small{font-size:8px;letter-spacing:0}.compact-metrics strong{font-size:20px}.compact-run{flex-direction:column}.compact-run button{min-height:42px}.compact-header{align-items:flex-start;flex-direction:column}.compact-actions{justify-content:flex-start;flex-wrap:wrap}.advanced-section form{flex-direction:column}}
</style>