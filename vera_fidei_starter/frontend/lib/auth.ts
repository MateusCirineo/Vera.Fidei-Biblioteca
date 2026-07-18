const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api'

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
}

function setToken(token: string): void {
  const secure = window.location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `vf_token=${encodeURIComponent(token)}; Path=/; SameSite=Lax; Max-Age=${60 * 60 * 24 * 7}${secure}`
}

export function getToken(): string {
  if (typeof document === 'undefined') return ''
  const match = document.cookie.match(/(?:^|; )vf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export function clearToken(): void {
  const secure = typeof window !== 'undefined' && window.location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `vf_token=; Path=/; SameSite=Lax; Max-Age=0${secure}`
}

export function authBearerHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken()
  const apiKey = process.env.NEXT_PUBLIC_API_KEY ?? ''
  const headers: Record<string, string> = { ...extra }
  if (apiKey) headers['X-API-Key'] = apiKey
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function readError(res: Response, fallback: string): Promise<Error> {
  const err = await res.json().catch(() => ({ detail: fallback }))
  return new Error(err.detail ?? fallback)
}

export async function register(name: string, email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao cadastrar')
  const data = await res.json()
  setToken(data.access_token)
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw await readError(res, 'Credenciais inválidas')
  const data = await res.json()
  setToken(data.access_token)
}

export function logout(): void {
  clearToken()
}

export async function getUser(): Promise<UserInfo | null> {
  const token = getToken()
  if (!token) return null
  try {
    const res = await fetch(`${BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      clearToken()
      return null
    }
    return res.json()
  } catch {
    return null
  }
}

export async function getHistorico(page = 1, perPage = 20) {
  const res = await fetch(`${BASE}/citations/historico?page=${page}&per_page=${perPage}`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw new Error('Erro ao carregar histórico')
  return res.json()
}

export async function deleteHistoricoEntry(id: number): Promise<void> {
  const res = await fetch(`${BASE}/citations/historico/${id}`, {
    method: 'DELETE',
    headers: authBearerHeaders(),
  })
  if (!res.ok) throw new Error('Erro ao remover entrada')
}

export async function downloadHistoricoLaudo(id: number): Promise<Blob> {
  const res = await fetch(`${BASE}/citations/historico/${id}/laudo`, {
    headers: authBearerHeaders(),
  })
  if (!res.ok) throw await readError(res, 'Erro ao baixar laudo')
  return res.blob()
}

export async function exportHistoricoExcel(): Promise<Blob> {
  const res = await fetch(`${BASE}/citations/historico/export.xlsx`, {
    headers: authBearerHeaders(),
  })
  if (!res.ok) throw await readError(res, 'Erro ao exportar histÃ³rico')
  return res.blob()
}

export const exportHistoricoCsv = exportHistoricoExcel

export async function getApiKeys() {
  const res = await fetch(`${BASE}/api-keys`, { headers: authBearerHeaders() })
  if (!res.ok) throw new Error('Erro ao listar API keys')
  return res.json()
}

export async function createApiKey(label: string): Promise<{ key: string }> {
  const res = await fetch(`${BASE}/api-keys`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ label }),
  })
  if (!res.ok) throw new Error('Erro ao gerar API key')
  return res.json()
}

export async function revokeApiKey(id: number): Promise<void> {
  const res = await fetch(`${BASE}/api-keys/${id}`, {
    method: 'DELETE',
    headers: authBearerHeaders(),
  })
  if (!res.ok) throw new Error('Erro ao revogar API key')
}

export async function getInstituicao() {
  const res = await fetch(`${BASE}/instituicao`, {
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw new Error('Sem instituicao')
  return res.json()
}

export async function getMembrosInstituicao() {
  const res = await fetch(`${BASE}/instituicao/membros`, {
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw new Error('Erro ao carregar membros')
  return res.json()
}

export async function criarInstituicao(name: string) {
  const res = await fetch(`${BASE}/instituicao`, {
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
  const res = await fetch(`${BASE}/instituicao/convidar`, {
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
  const res = await fetch(`${BASE}/instituicao/membros/${memberId}`, {
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
  const res = await fetch(`${BASE}/instituicao/membros/${memberId}`, {
    method: 'DELETE',
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao remover membro')
}

export async function getRelatorio() {
  const res = await fetch(`${BASE}/instituicao/relatorio`, {
    headers: authBearerHeaders({ 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '' }),
  })
  if (!res.ok) throw new Error('Erro ao carregar relatório')
  return res.json()
}

export async function createCheckoutSession(plan: string, couponCode?: string): Promise<{ url: string }> {
  const body: Record<string, string> = { plan }
  if (couponCode?.trim()) body.coupon_code = couponCode.trim().toUpperCase()
  const res = await fetch(`${BASE}/billing/checkout`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await readError(res, 'Erro ao iniciar assinatura')
  return res.json()
}

export async function openBillingPortal(): Promise<{ url: string }> {
  const res = await fetch(`${BASE}/billing/portal`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
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
  const res = await fetch(`${BASE}/billing/pix/${encodeURIComponent(ref)}`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readError(res, 'Assinatura Pix não encontrada')
  return res.json()
}
