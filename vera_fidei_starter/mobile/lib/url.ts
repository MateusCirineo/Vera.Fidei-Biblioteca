export function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

function safePdfCoordinates(fileId: number, page: number): { fileId: number; page: number } {
  if (!Number.isSafeInteger(fileId) || fileId <= 0 || fileId > 2_147_483_647) {
    throw new Error('Arquivo PDF inválido.')
  }
  const safePage = Number.isSafeInteger(page) && page > 0 && page <= 1_000_000 ? page : 1
  return { fileId, page: safePage }
}

export function buildMobileWebRedirect(fileId: number, page = 1): string {
  const safe = safePdfCoordinates(fileId, page)
  return `/visualizar/${safe.fileId}?page=${safe.page}`
}

export function buildMobileWebSessionUrl(apiBase: string): string {
  return `${normalizeBaseUrl(apiBase)}/auth/mobile-web-session`
}

export function buildMobileAccountRedirect(target: string): '/perfil' | '/planos' {
  if (target === 'profile') return '/perfil'
  if (target === 'plans') return '/planos'
  throw new Error('Destino da conta inválido.')
}

export function buildMobileAccountSessionUrl(apiBase: string): string {
  return `${normalizeBaseUrl(apiBase)}/auth/mobile-account-session`
}

export function isTrustedWebNavigation(url: string, webBase: string): boolean {
  if (url === 'about:blank') return true
  try {
    const candidate = new URL(url)
    const trusted = new URL(normalizeBaseUrl(webBase))
    return candidate.protocol === 'https:'
      && !candidate.username
      && !candidate.password
      && candidate.origin === trusted.origin
  } catch {
    return false
  }
}

export function isTrustedStripeNavigation(url: string): boolean {
  try {
    const candidate = new URL(url)
    return candidate.protocol === 'https:'
      && !candidate.username
      && !candidate.password
      && !candidate.port
      && (
      candidate.hostname === 'checkout.stripe.com'
      || candidate.hostname === 'billing.stripe.com'
      )
  } catch {
    return false
  }
}
