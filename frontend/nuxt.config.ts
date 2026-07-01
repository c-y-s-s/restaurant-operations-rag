export default defineNuxtConfig({
  compatibilityDate: '2025-05-15',
  devtools: { enabled: false },
  css: ['~/assets/main.css'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000'
    }
  },
  app: {
    head: {
      htmlAttrs: { lang: 'zh-Hant' },
      title: 'Service Notes｜餐廳營運助手',
      meta: [
        {
          name: 'description',
          content: '附來源、可驗證的餐廳內部營運知識助手。'
        }
      ]
    }
  },
  typescript: {
    typeCheck: true,
    strict: true
  }
})

