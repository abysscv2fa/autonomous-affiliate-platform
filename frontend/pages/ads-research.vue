<script setup lang="ts">
useHead({ title: 'AffPilot AdSpy · EU & UK' })
const query = ref('')
const market = ref('EU_UK')
const busy = ref(false)
const error = ref('')
const notice = ref('')
const results = ref<any[]>([])
const saved = ref<any[]>([])
const selected = ref<any>(null)
const adText = ref('')
const pageName = ref('')
const headline = ref('')
const description = ref('')
const creativeUrl = ref('')
const landingUrl = ref('')
const analyzeBusy = ref<number|null>(null)
const analysis = ref<any>(null)
const apiStatus = ref<any>(null)
const route = useRoute()
const marketLabel = computed(() => market.value === 'EU_UK' ? 'EU + UK' : market.value)
const countryForSave = computed(() => market.value === 'UK' ? 'GB' : 'EU')
async function loadSaved(){ try { saved.value = await $fetch<any[]>('/api/ads-research/ads?limit=200') } catch {} }
async function loadStatus(){ try { apiStatus.value = await $fetch<any>('/api/ads-research/status') } catch { apiStatus.value = {connected:false} } }
async function search(){
 if(query.value.trim().length<2)return
 busy.value=true; error.value=''; notice.value=''; results.value=[]; analysis.value=null
 try {
   const r:any=await $fetch('/api/ads-research/search',{method:'POST',body:{query:query.value.trim(),market:market.value,max_results:200}})
   results.value=r.results||[]
   notice.value=r.message || 'Meta Ad Library API search completed.'
   await loadSaved()
 } catch(e:any){
   const st=e?.statusCode||e?.response?.status||e?.status
   error.value=e?.data?.detail || e?.data?.statusMessage || e?.statusMessage || ('Request failed ('+(st||'network')+'). Check backend availability and Meta API access token.')
 }
 finally{busy.value=false}
}
function selectResult(ad:any){
 selected.value=ad; pageName.value=ad.page_name||''; adText.value=ad.ad_text||''
 headline.value=ad.headline||''; description.value=ad.description||''
 creativeUrl.value=ad.ad_library_url||''; landingUrl.value=''; analysis.value=null
}
async function saveCurrent(){
 if(!adText.value.trim())return
 try{
  await $fetch('/api/ads-research/ads',{method:'POST',body:{
   query:query.value,country:countryForSave.value,page_name:pageName.value,
   ad_text:adText.value,headline:headline.value,description:description.value,
   creative_url:creativeUrl.value,ad_library_url:selected.value?.ad_library_url||'',
   landing_page_url:landingUrl.value,started_running:selected.value?.started_running||'',
   active_status:selected.value?.active_status||'unknown',platforms:selected.value?.platforms||[]
  }})
  notice.value='Đã lưu quảng cáo vào Ad Research Library.'; selected.value=null; await loadSaved()
 }catch(e:any){error.value=e?.data?.detail||'Không thể lưu quảng cáo.'}
}
async function analyze(id:number){
 analyzeBusy.value=id;error.value=''
 try{const r:any=await $fetch('/api/ads-research/ads/'+id+'/analyze',{method:'POST'});analysis.value=r.analysis;await loadSaved()}
 catch(e:any){error.value=e?.data?.detail||'AI không thể phân tích quảng cáo.'}
 finally{analyzeBusy.value=null}
}
onMounted(()=>{
 const params=route.query
 if(params.import==='manual'){
  const imported = new URLSearchParams(window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash)
  query.value=imported.get('query')||''
  pageName.value=imported.get('page_name')||''
  adText.value=imported.get('ad_text')||''
  headline.value=imported.get('headline')||''
  description.value=imported.get('description')||''
  landingUrl.value=imported.get('landing_page_url')||''
  creativeUrl.value=imported.get('creative_url')||''
  notice.value='Imported from AffPilot AdSpy extension. Review the details, then save to your research library.'
  window.history.replaceState(null,'',window.location.pathname+window.location.search)
 }
 loadStatus(); loadSaved()
})
</script>

<template>
  <main class="ads-shell">
    <header class="top"><div><NuxtLink to="/" class="back">← AffPilot Command Center</NuxtLink><p class="eyebrow">AFFPILOT · MARKET INTELLIGENCE</p><h1>AffPilot AdSpy</h1><p class="sub">Official Meta Ad Library API · EU & UK · automatic collection</p></div><span class="status">META OFFICIAL API</span></header>
    <section class="panel connection">
      <div><h2>Meta API connection</h2><p v-if="apiStatus?.connected" class="connected">Connected · Graph API {{apiStatus.graph_api_version}}</p><p v-else class="disconnected">Not connected · Meta access token is not configured on the backend.</p><p class="hint">Access is granted by Meta to your Facebook identity and Developer App. The token stays server-side in Render and is never sent to the browser.</p></div>
      <a href="https://www.facebook.com/ads/library/api/" target="_blank" rel="noopener">Meta API access setup ↗</a>
    </section>
    <section class="panel">
      <div class="panel-title"><div><h2>Search & collect ads</h2><p>AffPilot calls Meta Graph API, stores returned ads and displays them below.</p></div><span class="tag">365-day archive</span></div>
      <form @submit.prevent="search">
        <label class="wide">Keyword<input v-model="query" placeholder="e.g. skincare, coffee, SaaS, pet accessories" minlength="2" maxlength="100" required></label>
        <label>Market<select v-model="market"><option value="EU_UK">European Union + United Kingdom</option><option value="EU">European Union only</option><option value="UK">United Kingdom only</option></select></label>
        <button :disabled="busy || !apiStatus?.connected">{{busy?'Collecting from Meta…':'Search & collect ads'}}</button>
      </form>
      <p v-if="!apiStatus?.connected" class="hint">After creating your Meta Developer App, add META_AD_LIBRARY_ACCESS_TOKEN to the backend Render service environment variables, then redeploy.</p>
      <p v-if="error" class="error">{{error}}</p><p v-if="notice" class="notice">{{notice}}</p>
    </section>
    <section class="panel" v-if="results.length">
      <div class="panel-title"><div><h2>New API results</h2><p>Official Meta records · saved automatically to AffPilot.</p></div><span class="tag">{{results.length}} ads collected</span></div>
      <article v-for="ad in results" :key="ad.ad_archive_id" class="ad-row">
        <div class="ad-copy">
          <div class="row-head"><b>{{ad.page_name || 'Advertiser'}}</b><span class="tag">{{ad.country}} · {{ad.active_status}}</span></div>
          <p>{{ad.headline}}</p><p>{{ad.ad_text || 'No ad copy returned'}}</p>
          <small>{{ad.started_running || 'Start date unavailable'}} · {{(ad.platforms||[]).join(', ')}}</small>
          <small v-if="ad.eu_total_reach">EU estimated reach: {{Number(ad.eu_total_reach).toLocaleString()}}</small>
          <small v-if="ad.beneficiary_payers?.length">Beneficiary / payer: {{JSON.stringify(ad.beneficiary_payers)}}</small>
        </div>
        <a v-if="ad.ad_library_url" :href="ad.ad_library_url" target="_blank" rel="noopener">View ad ↗</a>
        <button class="secondary" @click="selectResult(ad)">Review</button>
      </article>
    </section>
    <section class="panel" v-if="selected">
      <div class="panel-title"><div><h2>Selected Meta ad</h2><p>{{selected.page_name}} · {{selected.ad_archive_id}}</p></div></div>
      <p>{{selected.ad_text}}</p><p class="hint">This ad was already stored automatically. You can add a landing-page URL and save a separate research note below.</p>
    </section>
    <section class="panel" v-if="selected">
      <div class="panel-title"><div><h2>Add research notes</h2><p>Optional landing page and manual context.</p></div></div>
      <div class="editor">
        <label>Advertiser / Page<input v-model="pageName"></label>
        <label>Headline<input v-model="headline"></label>
        <label class="wide">Primary text<textarea v-model="adText" rows="4"></textarea></label>
        <label class="wide">Description<textarea v-model="description" rows="2"></textarea></label>
        <label>Creative / Ad Library URL<input v-model="creativeUrl"></label>
        <label>Landing page URL<input v-model="landingUrl" placeholder="https://…"></label>
      </div>
      <button :disabled="adText.trim().length<5" @click="saveCurrent">Save research note</button>
    </section>
    <section class="panel">
      <div class="panel-title"><div><h2>Saved EU & UK research</h2><p>Ads collected from Meta API and saved in the AffPilot database.</p></div><button class="secondary" @click="loadSaved">Refresh</button></div>
      <div v-if="!saved.length" class="empty">No collected ads yet. Connect the Meta API, then search a keyword.</div>
      <article v-for="ad in saved" :key="ad.id" class="saved-row">
        <div class="saved-copy"><div class="row-head"><b>{{ad.page_name || 'Advertiser not supplied'}}</b><span class="tag">{{ad.country}} · {{ad.evidence_label}}</span></div><p>{{ad.headline}}</p><p>{{ad.ad_text}}</p><small>{{ad.started_running || 'Date unavailable'}} · {{(ad.platforms||[]).join(', ')}}</small><small v-if="ad.eu_total_reach">EU estimated reach: {{Number(ad.eu_total_reach).toLocaleString()}}</small><small v-if="ad.beneficiary_payers?.length">Beneficiary / payer: {{JSON.stringify(ad.beneficiary_payers)}}</small><small>Saved {{new Date(ad.created_at).toLocaleString()}} · Creative score {{ad.opportunity_score || '—'}}</small></div>
        <button :disabled="analyzeBusy===ad.id" @click="analyze(ad.id)">{{analyzeBusy===ad.id?'Analyzing…':'AI Analyze'}}</button>
        <a v-if="ad.ad_library_url" :href="ad.ad_library_url" target="_blank" rel="noopener">Source ↗</a>
      </article>
    </section>
    <section v-if="analysis" class="panel analysis"><div class="panel-title"><div><h2>AI Creative Analysis</h2><p>Score is a creative opportunity estimate, not proof of ad performance.</p></div><strong>{{analysis.opportunity_score}} / 100</strong></div><div class="analysis-grid"><article v-for="(value,key) in analysis" :key="String(key)"><b>{{String(key).replaceAll('_',' ')}}</b><p>{{Array.isArray(value)?value.join(' · '):typeof value==='object'?JSON.stringify(value):value}}</p></article></div></section>
    <footer>Official Meta Ad Library API. Search scope: ads delivered to EU and/or UK in the past 365 days. EU reach is estimated; spend, ROAS, sales and profitability are not disclosed for ordinary commercial ads. Meta API access and data retention are subject to Meta Platform Terms.</footer>
  </main>
</template>

<style scoped>
:global(body){margin:0;background:#07111f;color:#e8f2ff;font-family:Inter,ui-sans-serif,system-ui}.ads-shell{max-width:1180px;margin:auto;padding:30px 22px 55px}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:24px}.back{color:#5ce4cf;text-decoration:none;font-size:13px}.eyebrow{margin:22px 0 5px;color:#5ce4cf;font-size:10px;letter-spacing:.18em}.top h1{font-size:clamp(30px,5vw,46px);margin:0}.sub,.panel-title p,.hint{color:#91a9c1}.status,.tag{border:1px solid #286f6c;color:#63e6d2;border-radius:30px;padding:7px 11px;font-size:10px;white-space:nowrap}.panel{background:#101e31;border:1px solid #203a54;border-radius:16px;padding:22px;margin:16px 0}.panel-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:16px}.panel-title h2,.connection h2{margin:0 0 5px}.panel-title p,.connection p{margin:0;font-size:12px}.connection{display:flex;justify-content:space-between;align-items:center;gap:18px}.connection a,.ad-row a,.saved-row a{color:#5ce4cf;text-decoration:none;font-size:12px;white-space:nowrap}.connected{color:#61e5d0}.disconnected,.error{color:#ff9d9d}.hint{font-size:12px;line-height:1.5;margin-top:10px}form,.editor{display:grid;grid-template-columns:2fr 1.2fr 1fr;gap:12px;align-items:end}label{display:grid;gap:7px;color:#a8bdd1;font-size:12px}.editor{grid-template-columns:1fr 1fr}.editor .wide{grid-column:1/-1}input,select,textarea{width:100%;min-width:0;box-sizing:border-box;background:#081525;color:#fff;border:1px solid #29435e;border-radius:9px;padding:12px;font:inherit}button{border:0;border-radius:9px;padding:12px 16px;background:#16b8a6;color:#04151b;font-weight:700;cursor:pointer}button:disabled{opacity:.5}.secondary{background:#203d59;color:#d9eaff}.notice{color:#b9d8ed;font-size:13px;line-height:1.5}.ad-row,.saved-row{display:flex;align-items:flex-start;gap:16px;padding:16px 0;border-top:1px solid #20354b}.ad-copy,.saved-copy{flex:1;min-width:0}.ad-row p,.saved-row p{white-space:pre-wrap;color:#c4d5e5;line-height:1.5}.ad-row small,.saved-row small{display:block;color:#819bb3;margin-top:5px}.row-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.saved-copy p{max-height:110px;overflow:auto}.empty{padding:30px;text-align:center;color:#91a9c1}.analysis .panel-title strong{font-size:24px;color:#61e5d0}.analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.analysis-grid article{background:#081525;border:1px solid #29435e;border-radius:10px;padding:14px}.analysis-grid b{text-transform:capitalize;color:#70e5d2}.analysis-grid p{font-size:13px;line-height:1.55;color:#c5d6e5}footer{color:#7892aa;font-size:11px;line-height:1.6;margin-top:24px}@media(max-width:760px){.top,.panel-title,.connection{flex-direction:column}form,.editor{grid-template-columns:1fr}.editor .wide{grid-column:auto}.ad-row,.saved-row{flex-direction:column}.analysis-grid{grid-template-columns:1fr}}
</style>
