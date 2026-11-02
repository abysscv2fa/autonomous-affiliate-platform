import { getRequestURL, proxyRequest, setRequestHeader } from 'h3'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  if (!config.backendApiBase || !config.backendApiToken) {
    throw createError({ statusCode: 503, statusMessage: 'Backend proxy is not configured.' })
  }
  const incoming = getRequestURL(event)
  const target = `${String(config.backendApiBase).replace(/\\/$/, '')}${incoming.pathname}${incoming.search}`
  setRequestHeader(event, 'x-affpilot-internal-token', String(config.backendApiToken))
  return proxyRequest(event, target)
})
