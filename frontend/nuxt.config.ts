export default defineNuxtConfig({
  devtools: { enabled: false },
  runtimeConfig: {
    backendApiBase: process.env.BACKEND_API_BASE || '',
    backendApiToken: process.env.BACKEND_API_TOKEN || '',
    public: { apiBase: '' }
  },
  app: { head: { title: 'Autonomous Affiliate Platform' } }
})
