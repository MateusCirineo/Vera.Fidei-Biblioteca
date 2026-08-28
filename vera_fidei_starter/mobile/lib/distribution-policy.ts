export type DistributionMode = 'reader' | 'direct' | 'play'

export type SubscriptionResource = 'pdf' | 'verification' | 'search'

export type SubscriptionGatePolicy = {
  title: string
  message: string
  showPlansAction: boolean
}

/** Unknown builds fail closed as reader; store billing requires the explicit `play` value. */
export function normalizeDistributionMode(value: unknown): DistributionMode {
  return value === 'direct' || value === 'play' ? value : 'reader'
}

export function allowsExternalBilling(mode: DistributionMode): boolean {
  return mode === 'direct'
}

export function allowsPlayBilling(mode: DistributionMode, platform: unknown): boolean {
  return mode === 'play' && platform === 'android'
}

export function allowsAccountWeb(mode: DistributionMode, destination: unknown): boolean {
  return mode === 'direct' && (destination === 'profile' || destination === 'plans')
}

export function subscriptionGatePolicy(
  mode: DistributionMode,
  resource: SubscriptionResource,
): SubscriptionGatePolicy {
  if (resource === 'pdf') {
    return {
      title: 'Entre para abrir o PDF',
      message: 'A biblioteca completa, incluindo os PDFs digitalizados, está disponível para todas as contas, inclusive o plano Fiel.',
      showPlansAction: false,
    }
  }

  if (mode === 'reader') {
    const resourceLabel = resource === 'verification'
      ? 'Esta verificação'
      : 'Esta pesquisa'
    return {
      title: 'Assinatura necessária',
      message: `${resourceLabel} requer uma assinatura ativa com acesso a este recurso.`,
      showPlansAction: false,
    }
  }

  if (mode === 'play') {
    const resourceLabel = resource === 'verification'
      ? 'Esta verificação'
      : 'Esta pesquisa'
    return {
      title: 'Assinatura necessária',
      message: `${resourceLabel} requer uma assinatura ativa. Conheça os planos disponíveis no Google Play.`,
      showPlansAction: true,
    }
  }

  if (resource === 'verification') {
    return {
      title: 'Limite do plano atingido',
      message: 'Esta verificação requer um plano com saldo disponível.',
      showPlansAction: true,
    }
  }
  return {
    title: 'Limite do plano atingido',
    message: 'Esta pesquisa requer um plano com saldo disponível.',
    showPlansAction: true,
  }
}

export function plansRouteForMode(mode: DistributionMode, platform: unknown): 'PlayPlans' | 'ContaWeb' | null {
  if (mode === 'play') return platform === 'android' ? 'PlayPlans' : null
  if (mode === 'direct') return 'ContaWeb'
  return null
}

function isTrustedWebOrigin(url: string, webBase: string): boolean {
  if (url === 'about:blank') return true
  try {
    const candidate = new URL(url)
    const trusted = new URL(webBase.trim().replace(/\/+$/, ''))
    return candidate.protocol === 'https:'
      && !candidate.username
      && !candidate.password
      && candidate.origin === trusted.origin
  } catch {
    return false
  }
}

export function isReaderPdfNavigationAllowed(url: string, webBase: string): boolean {
  if (!isTrustedWebOrigin(url, webBase)) return false
  if (url === 'about:blank') return true
  try {
    const candidate = new URL(url)
    if (/^\/visualizar\/\d+\/?$/.test(candidate.pathname)) return true
    if (candidate.pathname === '/api/auth/mobile-web-session') return true
    if (/^\/api\/pdfs\/\d+\/?$/.test(candidate.pathname)) return true
    if (candidate.pathname === '/viewer/pdf') {
      return /^\/api\/pdfs\/\d+$/.test(candidate.searchParams.get('file') ?? '')
    }
    return false
  } catch {
    return false
  }
}

/** Reader and Play builds share the narrow PDF allowlist; only direct trusts the full same-origin site. */
export function isPdfNavigationAllowed(
  mode: DistributionMode,
  url: string,
  webBase: string,
): boolean {
  return mode === 'direct'
    ? isTrustedWebOrigin(url, webBase)
    : isReaderPdfNavigationAllowed(url, webBase)
}
