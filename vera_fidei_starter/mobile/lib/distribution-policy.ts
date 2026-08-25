export type DistributionMode = 'reader' | 'direct'

export type SubscriptionResource = 'pdf' | 'verification' | 'search'

export type SubscriptionGatePolicy = {
  title: string
  message: string
  showPlansAction: boolean
}

/** Store builds fail closed: only the explicit `direct` value enables billing UI. */
export function normalizeDistributionMode(value: unknown): DistributionMode {
  return value === 'direct' ? 'direct' : 'reader'
}

export function allowsExternalBilling(mode: DistributionMode): boolean {
  return mode === 'direct'
}

export function allowsAccountWeb(mode: DistributionMode, destination: unknown): boolean {
  return mode === 'direct' && (destination === 'profile' || destination === 'plans')
}

export function subscriptionGatePolicy(
  mode: DistributionMode,
  resource: SubscriptionResource,
): SubscriptionGatePolicy {
  if (mode === 'reader') {
    const resourceLabel = resource === 'pdf'
      ? 'A leitura do PDF digitalizado'
      : resource === 'verification'
        ? 'Esta verificação'
        : 'Esta pesquisa'
    return {
      title: 'Assinatura necessária',
      message: `${resourceLabel} requer uma assinatura ativa com acesso a este recurso.`,
      showPlansAction: false,
    }
  }

  if (resource === 'pdf') {
    return {
      title: 'PDF completo no Apologeta',
      message: 'A localização continua visível. Para abrir a edição digitalizada, conheça o plano Apologeta.',
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

export function isReaderPdfNavigationAllowed(url: string, webBase: string): boolean {
  if (url === 'about:blank') return true
  try {
    const candidate = new URL(url)
    const trusted = new URL(webBase.trim().replace(/\/+$/, ''))
    if (
      candidate.protocol !== 'https:'
      || candidate.username
      || candidate.password
      || candidate.origin !== trusted.origin
    ) return false

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
