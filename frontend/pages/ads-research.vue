<script setup lang="ts">
useHead({ title: 'AffPilot AdSpy · EU & UK' })
const query = ref('')
const market = ref('EU_UK')
const mediaType = ref('ALL')
const busy = ref(false)
const error = ref('')
const notice = ref('')
const results = ref<any[]>([])
const saved = ref<any[]>([])
const selected = ref<any>(null)
const landingUrl = ref('')
const analyzeBusy = ref<number|null>(null)
const analysis = ref<any>(null)
const apiStatus = ref<any>(null)
const route = useRoute()
const previewMedia = ref<any>(null)
const previewBusy = ref(false)
const previewSrc = computed(() => selected.value?.creative_url || '')
const isMetaSnapshot = computed(() => selected.value?.source === 'meta_api' && !!previewSrc.value)
async function loadPreviewMedia(ad:any){
  previewMedia.value = null
  if (!ad?.id || ad.source !== 'meta_api') return
  previewBusy.value = true
  try {
    previewMedia.value = await $fetch<any>('/api/ads-research/ads/'+ad.id+'/media')
  } catch(e:any) {
    previewMedia.value = {images:[],videos:[],message:e?.data?.detail || 'Could not extract media from Meta snapshot.'}
  } finally { previewBusy.value = false }
}
async function loadSaved(){
  try { saved.value = await $fetch<any[]>('/api/ads-research/ads?limit=200') }
  catch(e:any) { error.value = e?.data?.detail || 'Could not load saved ads.' }
}
async function loadStatus(){
  try { apiStatus.value = await $fetch<any>('/api/ads-research/status') }
  catch { apiStatus.value = {connected:false} }
}
async function search(){
  if(query.value.trim().length<2)return
  busy.value=true; error.value=''; notice.value=''; results.value=[]; analysis.value=null; selected.value=null
  try {
    const r:any=await $fetch('/api/ads-research/search',{method:'POST',body:{
      query:query.value.trim(),market:market.value,max_results:200,media_type:mediaType.value
    }})
    results.value=r.results||[]
    selected.value=results.value[0]||null
    if (selected.value) loadPreviewMedia(selected.value)
    notice.value=r.message || 'Meta Ad Library API search completed.'
    await loadSaved()
  } catch(e:any){
    const st=e?.statusCode||e?.response?.status||e?.status
    error.value=e?.data?.detail || e?.data?.statusMessage || e?.statusMessage || ('Request failed ('+(st||'network')+'). Check backend availability and Meta API access token.')
  } finally { busy.value=false }
}
function selectResult(ad:any){
  selected.value=ad; landingUrl.value=ad.landing_page_url||''; analysis.value=null
  loadPreviewMedia(ad)
}
async function saveCurrent(){
  if(!selected.value?.ad_text?.trim())return
  try{
    await $fetch('/api/ads-research/ads',{method:'POST',body:{
      query:selected.value.query||query.value,country:selected.value.country==='GB'?'GB':'EU',
      page_name:selected.value.page_name||'',ad_text:selected.value.ad_text,
      headline:selected.value.headline||'',description:selected.value.description||'',
      creative_url:selected.value.ad_library_url||'',ad_library_url:selected.value.ad_library_url||'',
      landing_page_url:landingUrl.value,started_running:selected.value.started_running||'',
      active_status:selected.value.active_status||'unknown',platforms:selected.value.platforms||[]
    }})
    notice.value='Research note saved to your library.'; await loadSaved()
  }catch(e:any){error.value=e?.data?.detail||'Could not save research note.'}
}
async function analyze(id:number){
  analyzeBusy.value=id;error.value=''
  try{
    const r:any=await $fetch('/api/ads-research/ads/'+id+'/analyze',{method:'POST'})
    analysis.value=r.analysis; await loadSaved()
  }catch(e:any){error.value=e?.data?.detail||'AI could not analyze this ad.'}
  finally{analyzeBusy.value=null}
}
onMounted(()=>{
  const params=route.query
  if(params.import==='manual'){
    const imported = new URLSearchParams(window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash)
    query.value=imported.get('query')||''
    notice.value='Imported from AdSpy extension. Search results and saved ads appear here.'
    window.history.replaceState(null,'',window.location.pathname+window.location.search)
  }
  loadStatus(); loadSaved()
})
</script>

<template>
  <main class="ads-shell">
    <header class="top">
      <div>
        <NuxtLink to="/" class="back">← AffPilot Command Center</NuxtLink>
        <p class="eyebrow">AFFPILOT · MARKET INTELLIGENCE</p>
        <h1>AdSpy</h1>
        <p class="sub">Meta Ad Library · EU & UK · creative research workspace</p>
      </div>
      <div class="top-right"><span class="status">META OFFICIAL API</span><span :class="['connection-state',apiStatus?.connected?'ok':'bad']"><i></i>{{apiStatus?.connected?'API connected':'API disconnected'}}</span></div>
    </header>

    <section class="panel search-panel">
      <div class="search-heading"><div><h2>Find competitor ads</h2><p>Search the official Meta archive and collect up to 200 results.</p></div><span class="range">365-DAY ARCHIVE</span></div>
      <form @submit.prevent="search">
        <label class="keyword">Keyword<input v-model="query" placeholder="skincare, coffee, SaaS, pet accessories…" minlength="2" maxlength="100" required></label>
        <label>Market<select v-model="market"><option value="EU_UK">EU + UK</option><option value="EU">EU only</option><option value="UK">UK only</option></select></label>
        <label>Creative type<select v-model="mediaType"><option value="ALL">All formats</option><option value="IMAGE">Images</option><option value="VIDEO">Videos</option><option value="MEME">Memes</option><option value="NONE">Text only</option></select></label>
        <button :disabled="busy || !apiStatus?.connected">{{busy?'Collecting…':'Search ads'}}</button>
      </form>
      <p v-if="!apiStatus?.connected" class="hint">Add META_AD_LIBRARY_ACCESS_TOKEN to the backend Render environment, then redeploy.</p>
      <p v-if="error" class="error">{{error}}</p><p v-if="notice" class="notice">{{notice}}</p>
    </section>

    <section class="workspace" v-if="results.length || saved.length">
      <div class="list-column">
        <section class="panel list-panel" v-if="results.length">
          <div class="section-head"><div><h2>Search results</h2><p>Newly collected ads · click one to inspect its creative</p></div><span class="count">{{results.length}}</span></div>
          <button v-for="ad in results" :key="ad.ad_archive_id" class="ad-item" :class="{active:selected?.id===ad.id}" @click="selectResult(ad)">
            <span class="ad-item-top"><b>{{ad.page_name||'Advertiser'}}</b><span class="mini-tag">{{ad.country}}</span></span>
            <span class="ad-title">{{ad.headline||'Meta advertisement'}}</span>
            <span class="ad-snippet">{{ad.ad_text||'No primary text returned'}}</span>
            <span class="ad-meta">{{ad.started_running||'Date unavailable'}} · {{(ad.platforms||[]).join(', ')||'Meta'}}</span>
          </button>
        </section>
        <section class="panel list-panel">
          <div class="section-head"><div><h2>Research library</h2><p>Previously collected and saved ads</p></div><button class="refresh" @click="loadSaved">Refresh</button></div>
          <div v-if="!saved.length" class="empty">No saved ads yet.</div>
          <button v-for="ad in saved" :key="ad.id" class="ad-item" :class="{active:selected?.id===ad.id}" @click="selectResult(ad)">
            <span class="ad-item-top"><b>{{ad.page_name||'Advertiser'}}</b><span class="mini-tag">{{ad.country}}</span></span>
            <span class="ad-title">{{ad.headline||'Meta advertisement'}}</span>
            <span class="ad-snippet">{{ad.ad_text||'No primary text returned'}}</span>
            <span class="ad-meta">{{ad.started_running||'Date unavailable'}} · {{(ad.platforms||[]).join(', ')||'Meta'}}</span>
          </button>
        </section>
      </div>

      <aside class="preview-column">
        <section class="panel preview-panel" v-if="selected">
          <div class="section-head"><div><h2>Creative preview</h2><p>{{selected.page_name||'Advertiser'}} · {{selected.country}} · {{selected.ad_archive_id||'Saved note'}}</p></div><span class="preview-badge">LIVE PREVIEW</span></div>
          <div v-if="previewBusy" class="no-preview"><b>Loading creative media…</b></div>
          <div v-else-if="previewMedia && (previewMedia.images?.length || previewMedia.videos?.length)" class="media-preview">
            <img v-if="previewMedia.images?.length" :src="previewMedia.images[0]" alt="Meta ad creative image" loading="lazy">
            <video v-for="(video,index) in previewMedia.videos" :key="index" :src="video" :poster="previewMedia.poster||undefined" controls playsinline preload="metadata"></video>
            <p v-if="previewMedia.images.length>1" class="media-note">{{previewMedia.images.length}} image URLs found · showing first image</p>
          </div>
          <div v-else class="no-preview"><div class="no-preview-icon">▧</div><b>Visual preview unavailable</b><p>{{previewMedia?.message || 'This record does not expose direct media URLs.'}} Open the original source to inspect it.</p></div>
          <div class="creative-actions">
            <a v-if="selected.ad_library_url" :href="selected.ad_library_url" target="_blank" rel="noopener">Open original in Meta ↗</a>
            <button v-if="selected.id" class="secondary" :disabled="analyzeBusy===selected.id" @click="analyze(selected.id)">{{analyzeBusy===selected.id?'Analyzing…':'AI analyze'}}</button>
          </div>
          <div class="copy-block">
            <div class="copy-label">PRIMARY TEXT</div><p>{{selected.ad_text||'No primary text supplied.'}}</p>
            <div v-if="selected.headline" class="copy-label">HEADLINE</div><p v-if="selected.headline">{{selected.headline}}</p>
            <div v-if="selected.description" class="copy-label">DESCRIPTION</div><p v-if="selected.description">{{selected.description}}</p>
          </div>
          <div class="metrics">
            <div><small>Started</small><b>{{selected.started_running||'—'}}</b></div>
            <div><small>EU reach estimate</small><b>{{selected.eu_total_reach?Number(selected.eu_total_reach).toLocaleString():'—'}}</b></div>
            <div><small>Platforms</small><b>{{(selected.platforms||[]).join(', ')||'—'}}</b></div>
          </div>
          <label class="landing">Landing page URL<input v-model="landingUrl" placeholder="https://brand.com/…"></label>
          <button class="save-note" @click="saveCurrent">Save research note</button>
        </section>
        <section class="panel preview-panel blank-preview" v-else>
          <div class="no-preview-icon">▣</div><h2>Select an ad to inspect</h2><p>Choose any result on the left. Its Meta image/video snapshot and copy will appear here.</p>
        </section>
        <section class="panel analysis" v-if="analysis">
          <div class="section-head"><div><h2>Creative analysis</h2><p>Opportunity estimate, not campaign performance</p></div><strong>{{analysis.opportunity_score}}/100</strong></div>
          <div class="analysis-grid"><article v-for="(value,key) in analysis" :key="String(key)"><b>{{String(key).replaceAll('_',' ')}}</b><p>{{Array.isArray(value)?value.join(' · '):typeof value==='object'?JSON.stringify(value):value}}</p></article></div>
        </section>
      </aside>
    </section>
    <section v-else class="panel empty-state"><div class="no-preview-icon">▤</div><h2>Your AdSpy workspace is ready</h2><p>Search a keyword to populate the ad list. Select any result to view its original Meta creative.</p></section>

    <footer>Meta Ad Library API · Ads delivered in the EU/UK within the past 365 days. Meta provides creative snapshots and estimated reach; it does not disclose ordinary commercial ads' spend, ROAS, sales or profitability. Snapshot previews are loaded through the backend so the API token is not exposed to the browser.</footer>
  </main>
</template>

<style scoped>
:global(body){margin:0;background:#08111e;color:#e8f1fb;font-family:Inter,ui-sans-serif,system-ui}
.ads-shell{max-width:1500px;margin:auto;padding:26px 24px 48px}
.top{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:20px}
.back{color:#65dfcd;text-decoration:none;font-size:12px}.eyebrow{margin:16px 0 4px;color:#65dfcd;font-size:10px;letter-spacing:.18em}
.top h1{font-size:34px;line-height:1.1;margin:0}.sub{color:#91a7bd;font-size:13px;margin:7px 0 0}
.top-right{display:flex;align-items:center;gap:12px}.status,.range,.preview-badge{border:1px solid #285d63;color:#72dfd0;border-radius:20px;padding:7px 10px;font-size:9px;letter-spacing:.08em;white-space:nowrap}
.connection-state{display:flex;align-items:center;gap:7px;font-size:11px;color:#a8bacb}.connection-state i{width:7px;height:7px;border-radius:50%;background:#ef7777}.connection-state.ok i{background:#4bd4ae}.connection-state.ok{color:#70dfc7}
.panel{background:#111f30;border:1px solid #21374e;border-radius:13px;padding:17px;margin:0}
.search-panel{margin-bottom:16px}.search-heading,.section-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:13px}
h2{font-size:15px;margin:0 0 4px}.search-heading p,.section-head p{margin:0;color:#8fa5bb;font-size:11px}
form{display:grid;grid-template-columns:minmax(240px,2fr) minmax(130px,.8fr) minmax(130px,.8fr) auto;gap:10px;align-items:end}
label{display:grid;gap:6px;color:#9eb2c7;font-size:11px}input,select{width:100%;min-width:0;box-sizing:border-box;background:#091626;color:#eaf4ff;border:1px solid #2b425b;border-radius:8px;padding:10px 11px;font:inherit}
button{border:0;border-radius:8px;padding:10px 14px;background:#21b9a6;color:#04191b;font-size:11px;font-weight:750;cursor:pointer}button:disabled{opacity:.5;cursor:wait}
.hint,.notice,.error{font-size:11px;line-height:1.5;margin:10px 0 0}.hint{color:#8fa5bb}.notice{color:#80d9c8}.error{color:#ff9999}
.workspace{display:grid;grid-template-columns:minmax(320px,.88fr) minmax(480px,1.35fr);gap:16px;align-items:start}
.list-column,.preview-column{display:grid;gap:16px;min-width:0}.list-panel{padding:14px}.section-head{align-items:center}
.count{background:#203d52;color:#9de8dd;border-radius:8px;padding:5px 9px;font-size:11px}.refresh,.secondary{background:#243b53;color:#d7e8f8}
.ad-item{display:block;text-align:left;width:100%;background:transparent;color:#e8f1fb;border:0;border-top:1px solid #263b50;border-radius:0;padding:12px 8px}
.ad-item:hover,.ad-item.active{background:#172c40}.ad-item.active{box-shadow:inset 3px 0 #3bd0bb}
.ad-item-top{display:flex;justify-content:space-between;align-items:center;gap:8px}.ad-item-top b{font-size:11px}.mini-tag{font-size:9px;color:#77d8c9;border:1px solid #315b62;border-radius:12px;padding:3px 7px}
.ad-title,.ad-snippet,.ad-meta{display:block}.ad-title{font-size:11px;color:#c8d9e8;margin-top:7px;font-weight:650}.ad-snippet{font-size:10px;color:#8ea4ba;line-height:1.45;margin-top:5px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;white-space:pre-line}.ad-meta{font-size:9px;color:#68839b;margin-top:7px}
.preview-column{position:sticky;top:12px}.preview-panel{padding:16px}.preview-badge{font-size:8px}.media-preview{display:grid;gap:10px;place-items:center;width:100%;min-height:260px;max-height:720px;overflow:auto;background:#07111c;border:1px solid #263d53;border-radius:10px;padding:10px;box-sizing:border-box}
.media-preview img,.media-preview video{display:block;max-width:100%;max-height:660px;object-fit:contain;border-radius:6px}
.media-preview video{width:100%}.media-note{font-size:10px;color:#829ab0;margin:0}
.creative-actions{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #253a4f}
.creative-actions a{color:#6fe1d0;font-size:11px;text-decoration:none}.copy-block{padding:12px 0 4px}.copy-label{font-size:9px;letter-spacing:.12em;color:#70d9c9;font-weight:750;margin-top:8px}.copy-block p{font-size:11px;color:#c3d3e2;line-height:1.55;white-space:pre-wrap;margin:5px 0 10px}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;border-top:1px solid #253a4f;padding:12px 0}
.metrics div{min-width:0}.metrics small,.metrics b{display:block}.metrics small{color:#829ab0;font-size:9px}.metrics b{font-size:10px;color:#d3e2ef;margin-top:4px;overflow-wrap:anywhere}
.landing{margin:5px 0 10px}.save-note{width:100%}
.no-preview,.blank-preview,.empty-state{text-align:center;color:#8fa5bb;padding:45px 20px}.no-preview-icon{font-size:26px;color:#61d9c8;margin-bottom:10px}.no-preview b{color:#dceaf5;font-size:12px}.no-preview p,.blank-preview p,.empty-state p{font-size:11px;line-height:1.5;max-width:350px;margin:7px auto}
.analysis strong{color:#6fe0cf;font-size:20px}.analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.analysis-grid article{background:#091726;border:1px solid #293f55;border-radius:8px;padding:10px}.analysis-grid b{text-transform:capitalize;font-size:10px;color:#75dcca}.analysis-grid p{font-size:10px;line-height:1.5;color:#bfd0df;margin:5px 0 0}
.empty{padding:22px;text-align:center;color:#829ab0;font-size:11px}footer{color:#718aa1;font-size:10px;line-height:1.6;margin-top:18px}
@media(max-width:900px){.workspace{grid-template-columns:1fr}.preview-column{position:static;grid-row:1}.creative-frame{height:65vh;min-height:320px}}
@media(max-width:620px){.ads-shell{padding:18px 12px 35px}.top,.top-right{align-items:flex-start;flex-direction:column}form{grid-template-columns:1fr 1fr}.keyword{grid-column:1/-1}form button{grid-column:1/-1}.search-heading{flex-direction:column}.metrics{grid-template-columns:1fr 1fr}.analysis-grid{grid-template-columns:1fr}}
</style>
