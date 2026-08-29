const SAME_ORIGIN_API_BASE = '/api'
const INTERNAL_API_FALLBACK = 'http://backend:8000'

function normalizeApiBase(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

/** Browser requests stay on whichever supported host served the application. */
export function getPublicApiBase(): string {
  return normalizeApiBase(process.env.NEXT_PUBLIC_API_URL || SAME_ORIGIN_API_BASE)
}

/** Server Components and Route Handlers reach FastAPI on the private network. */
export function getServerApiBase(): string {
  const internal = process.env.INTERNAL_API_URL?.trim()
  if (internal) return normalizeApiBase(internal)

  // Docker image builds run before the private Compose hostname exists. This
  // server-only fallback lets ISR pages pre-render from the still-supported
  // legacy host without leaking that host into the browser bundle.
  const buildApi = process.env.SERVER_BUILD_API_URL?.trim()
  if (buildApi && /^https?:\/\//i.test(buildApi)) {
    return normalizeApiBase(buildApi)
  }

  const configuredPublic = process.env.NEXT_PUBLIC_API_URL?.trim()
  if (configuredPublic && /^https?:\/\//i.test(configuredPublic)) {
    return normalizeApiBase(configuredPublic)
  }
  return INTERNAL_API_FALLBACK
}

export function getApiBase(): string {
  return typeof window === 'undefined' ? getServerApiBase() : getPublicApiBase()
}
