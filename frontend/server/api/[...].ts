import { createHash } from 'node:crypto'
import { getRequestURL, proxyRequest } from 'h3'

// Normalize whitespace and accidental surrounding quotes from Render env values.
const norm = (value: unknown) => String(value ?? '').trim().replace(/^["']+|["']+$/g, '').trim()
let announced = false

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  // Prefer process env at runtime; fall back to Nuxt runtime config.
  const base = norm(process.env.BACKEND_API_BASE || config.backendApiBase)
  const token = norm(process.env.BACKEND_API_TOKEN || config.backendApiToken)

  if (!base || !token) {
    throw createError({
      statusCode: 503,
      statusMessage: 'Backend proxy is not configured.',
      data: { backendApiBaseSet: !!base, backendApiTokenSet: !!token },
    })
  }

  let backendUrl: URL
  try {
    backendUrl = new URL(base)
  } catch {
    throw createError({ statusCode: 503, statusMessage: 'BACKEND_API_BASE must be a valid absolute URL.' })
  }
  if (!['http:', 'https:'].includes(backendUrl.protocol)) {
    throw createError({ statusCode: 503, statusMessage: 'BACKEND_API_BASE must start with http:// or https://' })
  }

  if (!announced) {
    announced = true
    console.log(
      `[affpilot-proxy] base=${backendUrl.host} token_len=${token.length} token_fp=${createHash('sha256').update(token).digest('hex').slice(0, 8)}`,
    )
  }

  const incoming = getRequestURL(event)
  const target = new URL(
    `${incoming.pathname}${incoming.search}`,
    base.replace(/\/$/, ''),
  ).toString()

  // The internal credential remains server-side and is never exposed to browsers.
  return proxyRequest(event, target, {
    headers: {
      'x-affpilot-internal-token': token,
      'x-affpilot-via': 'nuxt-proxy',
    },
  })
})
