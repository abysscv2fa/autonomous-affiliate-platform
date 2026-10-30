export default defineNuxtConfig({
  devtools: { enabled: true },
  runtimeConfig: { public: { apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000' } },
  app: { head: { title: 'Autonomous Affiliate Platform' } }
})