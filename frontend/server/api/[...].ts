import { getRequestURL, proxyRequest } from 'h3'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  if (!config.backendApiBase || !config.backendApiToken) {
    throw createError({ statusCode: 503, statusMessage: 'Backend proxy is not configured.' })
  }

  const incoming = getRequestURL(event)
  const backendBase = String(config.backendApiBase).replace(/\/$/, '')
  const target = new URL(`${incoming.pathname}${incoming.search}`, backendBase).toString()

  // H3 v2 supports explicit upstream headers through proxyRequest options.
  // Keep the internal token server-side; never expose it to browser code.
  return proxyRequest(event, target, {
    headers: {
      'x-affpilot-internal-token': String(config.backendApiToken),
    },
  })
})
