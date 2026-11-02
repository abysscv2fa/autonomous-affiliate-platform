<script setup lang="ts">
useHead({ title: 'Facebook Ads Research · AffPilot' })
const query = ref('')
const country = ref('US')
const mode = ref<'manual'|'auto'|'both'>('both')
const activeOnly = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const results = ref<any[]>([])
const saved = ref<any[]>([])
const searchUrl = ref('')
const selected = ref<any>(null)
const adText = ref('')
const pageName = ref('')
const headline = ref('')
const description = ref('')
const creativeUrl = ref('')
const landingUrl = ref('')
const analyzeBusy = ref<number|null>(null)
const analysis = ref<any>(null)
const countries = [{code:'US',name:'United States'},{code:'GB',name:'United Kingdom'},{code:'DE',name:'Germany'},{code:'FR',name:'France'},{code:'IT',name:'Italy'},{code:'ES',name:'Spain'},{code:'NL',name:'Netherlands'},{code:'SE',name:'Sweden'},{code:'CA',name:'Canada'},{code:'AU',name:'Australia'}]
async function loadSaved(){ try { saved.value = await $fetch<any[]>('/api/ads-research/ads?limit=100') } catch {} }
async function search(){ if(query.value.trim().length<2)return; busy.value=true; error.value=''; notice.value=''; results.value=[]; analysis.value=null
 try {
   const modes = mode.value==='both' ? ['manual','auto'] : [mode.value]
   let autoResult:any=null
   for (const m of modes) {
     const r:any=await $fetch('/api/ads-research/search',{method:'POST',body:{query:query.value,country:country.value,mode:m,active_only:activeOnly.value}})
     searchUrl.value=r.search_url || searchUrl.value
     if(m==='auto'){ autoResult=r; results.value=r.results || []; if(r.message) notice.value=r.message }
   }
   await loadSaved()
   if(mode.value==='manual') notice.value='Đã tạo truy vấn. Mở Meta Ad Library để duyệt quảng cáo và lưu mẫu phù hợp vào AffPilot.'
   else if(mode.value==='both' && !results.value.length) notice.value=(autoResult?.message || 'Không có dữ liệu API tự động cho lựa chọn này.')+' Chế độ thủ công vẫn sẵn sàng.'
 } catch(e:any){ error.value=e?.data?.detail || 'Không thể tìm kiếm Meta Ad Library.' }
 finally{busy.value=false}
}
function selectResult(ad:any){ selected.value=ad; pageName.value=ad.page_name||''; adText.value=ad.ad_text||''; headline.value=ad.headline||''; description.value=ad.description||''; creativeUrl.value=ad.ad_library_url||''; landingUrl.value=''; analysis.value=null }
async function saveCurrent(){ if(!adText.value.trim())return; try{ await $fetch('/api/ads-research/ads',{method:'POST',body:{query:query.value,country:country.value,page_name:pageName.value,ad_text:adText.value,headline:headline.value,description:description.value,creative_url:creativeUrl.value,ad_library_url:selected.value?.ad_library_url||searchUrl.value,landing_page_url:landingUrl.value,source:selected.value?.source||'manual',ad_archive_id:selected.value?.ad_archive_id||'',started_running:selected.value?.started_running||'',active_status:selected.value?.active_status||'unknown',platforms:selected.value?.platforms||[],evidence_label:selected.value?.evidence_label||'user_saved_unverified'}}); notice.value='Đã lưu quảng cáo vào Ad Research Library.'; selected.value=null; await loadSaved() }catch(e:any){error.value=e?.data?.detail||'Không thể lưu quảng cáo.'}}
async function analyze(id:number){analyzeBusy.value=id;error.value='';try{const r:any=await $fetch('/api/ads-research/ads/'+id+'/analyze',{method:'POST'});analysis.value=r.analysis;await loadSaved()}catch(e:any){error.value=e?.data?.detail||'AI không thể phân tích quảng cáo.'}finally{analyzeBusy.value=null}}
onMounted(loadSaved)
</script>

<template>
  <main class="ads-shell">
    <header class="top"><div><NuxtLink to="/" class="back">← AffPilot Command Center</NuxtLink><p class="eyebrow">AFFPILOT · MARKET INTELLIGENCE</p><h1>Facebook Ads Research</h1><p class="sub">Research quảng cáo công khai · phân tích creative · tìm cơ hội sản phẩm</p></div><span class="status">RESEARCH WORKSPACE</span></header>
    <section class="panel">
      <div class="panel-title"><div><h2>Discover ads</h2><p>Tìm theo từ khóa, sản phẩm, thương hiệu hoặc fanpage.</p></div><span class="tag">Manual + Auto</span></div>
      <form @submit.prevent="search">
        <label class="wide">Keyword<input v-model="query" placeholder="e.g. posture corrector, CRM software, pet accessories" minlength="2" required></label>
        <label>Market<select v-model="country"><option v-for="c in countries" :key="c.code" :value="c.code">{{c.name}}</option></select></label>
        <label>Research mode<select v-model="mode"><option value="both">Both · Manual + Auto</option><option value="manual">Manual only</option><option value="auto">Auto only</option></select></label>
        <label class="check"><input v-model="activeOnly" type="checkbox"> Active ads only (API mode)</label>
        <button :disabled="busy">{{busy?'Researching…':'Search Ad Library'}}</button>
      </form>
      <p v-if="error" class="error">{{error}}</p><p v-if="notice" class="notice">{{notice}}</p>
      <a v-if="searchUrl" class="library-link" :href="searchUrl" target="_blank" rel="noopener">Open this search in Meta Ad Library ↗</a>
    </section>
    <section class="panel" v-if="results.length || selected">
      <div class="panel-title"><div><h2>API results</h2><p>Public records returned by Meta API; availability depends on country and Meta permissions.</p></div><span class="tag">{{results.length}} ads</span></div>
      <article v-for="ad in results" :key="ad.ad_archive_id" class="ad-row"><div><b>{{ad.page_name || 'Advertiser'}}</b><p>{{ad.ad_text || 'No ad copy returned'}}</p><small>{{ad.started_running || 'Start date unavailable'}} · {{(ad.platforms||[]).join(', ')}}</small><p v-if="ad.headline"><b>{{ad.headline}}</b></p></div><button class="secondary" @click="selectResult(ad)">Review / Save</button><a v-if="ad.ad_library_url" :href="ad.ad_library_url" target="_blank" rel="noopener">View ad ↗</a></article>
    </section>
    <section class="panel" v-if="selected || mode==='manual' || mode==='both'">
      <div class="panel-title"><div><h2>Save an ad for AI analysis</h2><p>Paste public ad text or select an API result. Manual saves are labelled unverified until checked.</p></div></div>
      <div class="editor">
        <label>Advertiser / Page<input v-model="pageName" placeholder="Page name"></label>
        <label>Headline<input v-model="headline" placeholder="Ad headline"></label>
        <label class="wide">Primary text<textarea v-model="adText" rows="5" placeholder="Paste the public ad copy here…"></textarea></label>
        <label class="wide">Description<textarea v-model="description" rows="2" placeholder="Optional description"></textarea></label>
        <label>Creative / Ad Library URL<input v-model="creativeUrl" placeholder="https://…"></label>
        <label>Landing page URL<input v-model="landingUrl" placeholder="https://…"></label>
      </div>
      <button :disabled="adText.trim().length<5" @click="saveCurrent">Save ad & research</button>
    </section>
    <section class="panel">
      <div class="panel-title"><div><h2>Saved research</h2><p>Ad records collected in your AffPilot database.</p></div><button class="secondary" @click="loadSaved">Refresh</button></div>
      <div v-if="!saved.length" class="empty">No saved ads yet. Search a keyword, then save a public ad to start.</div>
      <article v-for="ad in saved" :key="ad.id" class="saved-row"><div class="saved-copy"><b>{{ad.page_name || 'Advertiser not supplied'}}</b><span class="tag">{{ad.country}} · {{ad.evidence_label}}</span><p>{{ad.headline}}</p><p>{{ad.ad_text}}</p><small>Saved {{new Date(ad.created_at).toLocaleString()}} · AI score {{ad.opportunity_score || '—'}}</small></div><button :disabled="analyzeBusy===ad.id" @click="analyze(ad.id)">{{analyzeBusy===ad.id?'Analyzing…':'AI Analyze'}}</button><a v-if="ad.ad_library_url" :href="ad.ad_library_url" target="_blank" rel="noopener">Source ↗</a></article>
    </section>
    <section v-if="analysis" class="panel analysis"><div class="panel-title"><div><h2>AI Creative Analysis</h2><p>Score is a creative opportunity estimate, not proof of ad performance.</p></div><strong>{{analysis.opportunity_score}} / 100</strong></div><div class="analysis-grid"><article v-for="(value,key) in analysis" :key="String(key)"><b>{{String(key).replaceAll('_',' ')}}</b><p>{{Array.isArray(value)?value.join(' · '):typeof value==='object'?JSON.stringify(value):value}}</p></article></div></section>
    <footer>AffPilot does not scrape behind login, bypass access controls, or infer spend, ROAS, sales, or profitability from Ad Library presence. API availability is governed by Meta's access rules.</footer>
  </main>
</template>

<style scoped>
:global(body){margin:0;background:#07111f;color:#e8f2ff;font-family:Inter,ui-sans-serif,system-ui}.ads-shell{max-width:1180px;margin:auto;padding:30px 22px 55px}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:24px}.back,.library-link{color:#5ce4cf;text-decoration:none;font-size:13px}.eyebrow{margin:22px 0 5px;color:#5ce4cf;font-size:10px;letter-spacing:.18em}.top h1{font-size:clamp(30px,5vw,46px);margin:0}.sub,.panel-title p{color:#91a9c1}.status,.tag{border:1px solid #286f6c;color:#63e6d2;border-radius:30px;padding:8px 12px;font-size:10px;white-space:nowrap}.panel{background:#101e31;border:1px solid #203a54;border-radius:16px;padding:22px;margin:16px 0}.panel-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:16px}.panel-title h2{margin:0 0 5px}.panel-title p{margin:0;font-size:12px}form,.editor{display:grid;grid-template-columns:2fr 1fr 1.2fr;gap:12px;align-items:end}label{display:grid;gap:7px;color:#a8bdd1;font-size:12px}.wide{grid-column:span 1}.editor{grid-template-columns:1fr 1fr}.editor .wide{grid-column:1/-1}input,select,textarea{width:100%;min-width:0;background:#081525;color:#fff;border:1px solid #29435e;border-radius:9px;padding:12px;font:inherit}.check{display:flex;align-items:center;gap:8px}.check input{width:auto}button{border:0;border-radius:9px;padding:12px 16px;background:#16b8a6;color:#04151b;font-weight:700;cursor:pointer}button:disabled{opacity:.5}.secondary{background:#203d59;color:#d9eaff}.notice{color:#b9d8ed;font-size:13px;line-height:1.5}.error{color:#ff9d9d}.library-link{display:inline-block;margin-top:8px}.ad-row,.saved-row{display:flex;align-items:flex-start;gap:16px;padding:16px 0;border-top:1px solid #20354b}.ad-row>div,.saved-copy{flex:1;min-width:0}.ad-row p,.saved-row p{white-space:pre-wrap;color:#c4d5e5;line-height:1.5}.ad-row small,.saved-row small{color:#819bb3}.saved-copy .tag{display:inline-block;margin-left:10px}.saved-copy p{max-height:110px;overflow:auto}.empty{padding:30px;text-align:center;color:#91a9c1}.analysis>strong,.analysis .panel-title strong{font-size:24px;color:#61e5d0}.analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.analysis-grid article{background:#081525;border:1px solid #29435e;border-radius:10px;padding:14px}.analysis-grid b{text-transform:capitalize;color:#70e5d2}.analysis-grid p{font-size:13px;line-height:1.55;color:#c5d6e5}footer{color:#7892aa;font-size:11px;line-height:1.6;margin-top:24px}@media(max-width:760px){.top,.panel-title{flex-direction:column}form,.editor{grid-template-columns:1fr}.wide,.editor .wide{grid-column:auto}.ad-row,.saved-row{flex-direction:column}.analysis-grid{grid-template-columns:1fr}}
</style>
