import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  LONG_REQUEST_TIMEOUT_MS,
  fetchWithTimeout,
} from './http.ts'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api'
const AUTH_REQUEST_TIMEOUT_MS = DEFAULT_REQUEST_TIMEOUT_MS
const BILLING_REQUEST_TIMEOUT_MS = 20_000
export const AUTH_STATE_CHANGED_EVENT = 'vf:auth-state-changed'
export const PROFILE_AVATAR_CHANGED_EVENT = 'vf:profile-avatar-changed'

export interface UserInfo {
  id: number
  name: string
  email: string
  plan: string
  is_active: boolean
  billing_provider?: string | null
  billing_status?: string | null
  billing_current_period_end?: string | null
  billing_cancel_at_period_end?: boolean
  is_owner?: boolean
  avatar_url?: string | null
}

export function profileAvatarStorageKey(userId: number): string {
  return `vf_profile_avatar_${userId}`
}

function notifyAuthStateChanged(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_STATE_CHANGED_EVENT))
  }
}

function resolveAvatarUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (/^(?:https?:|data:)/i.test(url)) return url

  try {
    const base = /^https?:/i.test(BASE)
      ? BASE
      : (typeof window !== 'undefined' ? window.location.origin : BASE)
    return new URL(url, base).toString()
  } catch {
    return url
  }
}

export function authBearerHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const apiKey = process.env.NEXT_PUBLIC_API_KEY ?? ''
  const headers: Record<string, string> = { ...extra }
  if (apiKey) headers['X-API-Key'] = apiKey
  return headers
}

async function readError(res: Response, fallback: string): Promise<Error> {
  const err = await res.json().catch(() => ({ detail: fallback }))
  return new Error(err.detail ?? fallback)
}

async function fetchAuth(
  input: RequestInfo | URL,
  init: RequestInit = {},
  options: { timeoutMs?: number; timeoutMessage?: string } = {},
): Promise<Response> {
  return fetchWithTimeout(
    input,
    {
      ...init,
      credentials: init.credentials ?? 'include',
    },
    {
      timeoutMs: options.timeoutMs ?? AUTH_REQUEST_TIMEOUT_MS,
      timeoutMessage: options.timeoutMessage,
    },
  )
}

async function requestCurrentUser(
  sessionFailureMessage = 'O login foi aceito, mas a sessão não pôde ser confirmada. Tente novamente.',
): Promise<UserInfo> {
  const res = await fetchAuth(`${BASE}/auth/me`, {
    credentials: 'include',
    cache: 'no-store',
  })
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error(sessionFailureMessage)
    }
    throw await readError(res, 'Não foi possível confirmar sua sessão.')
  }
  const user = await res.json() as UserInfo
  return { ...user, avatar_url: resolveAvatarUrl(user.avatar_url) }
}

export async function register(name: string, email: string, password: string): Promise<UserInfo> {
  const res = await fetchAuth(`${BASE}/auth/web-register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name, email, password }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao cadastrar')
  const user = await requestCurrentUser(
    'A conta foi criada, mas a sessão não pôde ser confirmada. Entre com seu e-mail e senha.',
  )
  notifyAuthStateChanged()
  return user
}

export async function login(email: string, password: string): Promise<UserInfo> {
  const res = await fetchAuth(`${BASE}/auth/web-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  }, {
    timeoutMessage: 'O login demorou demais. Verifique sua conexão e tente novamente.',
  })
  if (!res.ok) throw await readError(res, 'Credenciais inválidas')
  const user = await requestCurrentUser()
  notifyAuthStateChanged()
  return user
}

export async function logout(): Promise<void> {
  await fetchAuth(`${BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  }).catch(() => undefined)
  notifyAuthStateChanged()
}

export async function forgotPassword(email: string): Promise<void> {
  const res = await fetchAuth(`${BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao solicitar redefinição de senha')
}

export async function resetPassword(token: string, password: string): Promise<void> {
  const res = await fetchAuth(`${BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao redefinir senha')
}

export async function verifyEmail(token: string): Promise<void> {
  const res = await fetchAuth(`${BASE}/auth/verify-email/${encodeURIComponent(token)}`, {
    method: 'POST',
  })
  if (!res.ok) throw await readError(res, 'Erro ao verificar e-mail')
}

export async function resendVerification(): Promise<void> {
  const res = await fetchAuth(`${BASE}/auth/resend-verification`, {
    method: 'POST',
    headers: authBearerHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw await readError(res, 'Erro ao reenviar verificação')
}

export async function getUser(): Promise<UserInfo | null> {
  try {
    return await requestCurrentUser()
  } catch {
    return null
  }
}

export async function uploadProfileAvatar(file: Blob): Promise<{ avatar_url: string }> {
  const res = await fetchAuth(`${BASE}/auth/avatar`, {
    method: 'PUT',
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    credentials: 'include',
    body: file,
  }, {
    timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'O envio da foto demorou demais. Verifique sua conexão e tente novamente.',
  })
  if (!res.ok) throw await readError(res, 'Erro ao salvar a foto do perfil')

  const result = await res.json() as { avatar_url: string }
  return { avatar_url: resolveAvatarUrl(result.avatar_url) ?? result.avatar_url }
}

export async function removeProfileAvatar(): Promise<void> {
  const res = await fetchAuth(`${BASE}/auth/avatar`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) throw await readError(res, 'Erro ao remover a foto do perfil')
}

function legacyAvatarDataUrlToBlob(dataUrl: string): Blob {
  const commaIndex = dataUrl.indexOf(',')
  if (commaIndex < 0) throw new Error('Foto local inválida')

  const metadata = dataUrl.slice(5, commaIndex).split(';')
  if (!metadata.some((part) => part.toLowerCase() === 'base64')) {
    throw new Error('Formato da foto local não suportado')
  }

  let mediaType = (metadata[0] || '').trim().toLowerCase()
  if (mediaType === 'image/jpg' || mediaType === 'image/pjpeg') {
    mediaType = 'image/jpeg'
  }
  if (!mediaType.startsWith('image/')) throw new Error('Foto local inválida')

  const binary = atob(dataUrl.slice(commaIndex + 1).replace(/\s/g, ''))
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new Blob([bytes], { type: mediaType })
}

export async function migrateLegacyProfileAvatar(user: UserInfo): Promise<string> {
  if (typeof window === 'undefined') return user.avatar_url ?? ''

  const key = profileAvatarStorageKey(user.id)
  const legacyAvatar = localStorage.getItem(key) ?? ''
  if (user.avatar_url) {
    if (legacyAvatar) localStorage.removeItem(key)
    return user.avatar_url
  }
  if (!legacyAvatar.startsWith('data:image/')) return ''

  try {
    // Decode locally: fetch(data:) is blocked by the production connect-src CSP.
    const blob = legacyAvatarDataUrlToBlob(legacyAvatar)
    const saved = await uploadProfileAvatar(blob)
    localStorage.removeItem(key)
    window.dispatchEvent(new CustomEvent(PROFILE_AVATAR_CHANGED_EVENT, {
      detail: { userId: user.id, avatar: saved.avatar_url },
    }))
    return saved.avatar_url
  } catch {
    // Preserve the local photo if the one-time migration cannot reach the API.
    return legacyAvatar
  }
}

export async function downloadPersonalData(): Promise<Blob> {
  const res = await fetchAuth(`${BASE}/auth/data-export`, {
    credentials: 'include',
  }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS })
  if (!res.ok) throw await readError(res, 'Erro ao exportar seus dados')
  return res.blob()
}

export async function deleteAccount(password: string, confirmation: string): Promise<void> {
  const res = await fetchAuth(`${BASE}/auth/account`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ password, confirmation }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao excluir a conta')
}

export async function getHistorico(page = 1, perPage = 20) {
  const res = await fetchAuth(`${BASE}/citations/historico?page=${page}&per_page=${perPage}`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw new Error('Erro ao carregar histórico')
  return res.json()
}

export async function deleteHistoricoEntry(id: number): Promise<void> {
  const res = await fetchAuth(`${BASE}/citations/historico/${id}`, {
    method: 'DELETE',
    headers: authBearerHeaders(),
  })
  if (!res.ok) throw new Error('Erro ao remover entrada')
}

export async function downloadHistoricoLaudo(id: number): Promise<Blob> {
  const res = await fetchAuth(`${BASE}/citations/historico/${id}/laudo`, {
    headers: authBearerHeaders(),
  }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS })
  if (!res.ok) throw await readError(res, 'Erro ao baixar laudo')
  return res.blob()
}

export async function exportHistoricoExcel(): Promise<Blob> {
  const res = await fetchAuth(`${BASE}/citations/historico/export.xlsx`, {
    headers: authBearerHeaders(),
  }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS })
  if (!res.ok) throw await readError(res, 'Erro ao exportar histórico')
  return res.blob()
}

export const exportHistoricoCsv = exportHistoricoExcel

export async function getApiKeys() {
  const res = await fetchAuth(`${BASE}/api-keys`, { headers: authBearerHeaders() })
  if (!res.ok) throw new Error('Erro ao listar API keys')
  return res.json()
}

export async function createApiKey(label: string): Promise<{ key: string }> {
  const res = await fetchAuth(`${BASE}/api-keys`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ label }),
  })
  if (!res.ok) throw new Error('Erro ao gerar API key')
  return res.json()
}

export async function revokeApiKey(id: number): Promise<void> {
  const res = await fetchAuth(`${BASE}/api-keys/${id}`, {
    method: 'DELETE',
    headers: authBearerHeaders(),
  })
  if (!res.ok) throw new Error('Erro ao revogar API key')
}

export async function getInstituicao() {
  const res = await fetchAuth(`${BASE}/instituicao`, {
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw new Error('Sem instituicao')
  return res.json()
}

export async function getMembrosInstituicao() {
  const res = await fetchAuth(`${BASE}/instituicao/membros`, {
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw new Error('Erro ao carregar membros')
  return res.json()
}

export async function criarInstituicao(name: string) {
  const res = await fetchAuth(`${BASE}/instituicao`, {
    method: 'POST',
    headers: authBearerHeaders({
      'Content-Type': 'application/json',
      'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '',
    }),
    body: JSON.stringify({ name }),
  })
  if (!res.ok) throw await readError(res, 'Erro')
  return res.json()
}

export async function convidarMembro(email: string) {
  const res = await fetchAuth(`${BASE}/instituicao/convidar`, {
    method: 'POST',
    headers: authBearerHeaders({
      'Content-Type': 'application/json',
      'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '',
    }),
    body: JSON.stringify({ email }),
  })
  if (!res.ok) throw await readError(res, 'Erro')
}

export async function atualizarPapelMembro(memberId: number, role: string) {
  const res = await fetchAuth(`${BASE}/instituicao/membros/${memberId}`, {
    method: 'PATCH',
    headers: authBearerHeaders({
      'Content-Type': 'application/json',
      'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '',
    }),
    body: JSON.stringify({ role }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao atualizar membro')
  return res.json()
}

export async function removerMembro(memberId: number): Promise<void> {
  const res = await fetchAuth(`${BASE}/instituicao/membros/${memberId}`, {
    method: 'DELETE',
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao remover membro')
}

export async function getRelatorio() {
  const res = await fetchAuth(`${BASE}/instituicao/relatorio`, {
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw new Error('Erro ao carregar relatório')
  return res.json()
}

export async function createCheckoutSession(plan: string, couponCode?: string): Promise<{ url: string }> {
  const body: Record<string, string> = { plan }
  if (couponCode?.trim()) body.coupon_code = couponCode.trim().toUpperCase()
  const res = await fetchAuth(`${BASE}/billing/checkout`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  }, {
    timeoutMs: BILLING_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A abertura do pagamento demorou demais. Tente novamente; nenhuma cobrança foi repetida.',
  })
  if (!res.ok) throw await readError(res, 'Erro ao iniciar assinatura')
  return res.json()
}

export interface BillingSyncResponse {
  synced: boolean
  plan: string
  billing_status?: string | null
}

export async function syncBillingSubscription(): Promise<BillingSyncResponse> {
  const res = await fetchAuth(`${BASE}/billing/sync`, {
    method: 'POST',
    headers: authBearerHeaders(),
    credentials: 'include',
  }, {
    timeoutMs: BILLING_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A confirmação do pagamento demorou demais. Seu plano será atualizado automaticamente.',
  })
  if (!res.ok) throw await readError(res, 'Erro ao confirmar a ativação da assinatura')
  return res.json()
}

export async function openBillingPortal(): Promise<{ url: string }> {
  const res = await fetchAuth(`${BASE}/billing/portal`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  }, {
    timeoutMs: BILLING_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A abertura do portal demorou demais. Verifique sua conexão e tente novamente.',
  })
  if (!res.ok) throw await readError(res, 'Erro ao abrir portal de assinatura')
  return res.json()
}

export interface PixSubscriptionRequest {
  reference_code: string
  plan: string
  plan_name: string
  amount_cents: number
  amount_label: string
  status: string
  recipient_name: string
  recipient_bank: string
  pix_key: string
  pix_payload?: string | null
  created_at: string
}

export async function getPixSubscriptionRequest(ref: string): Promise<PixSubscriptionRequest> {
  const res = await fetchAuth(`${BASE}/billing/pix/${encodeURIComponent(ref)}`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readError(res, 'Assinatura Pix não encontrada')
  return res.json()
}
