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
  is_owner?: boolean
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

export async function register(name: string, email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/web-register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name, email, password }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao cadastrar')
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/web-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw await readError(res, 'Credenciais inválidas')
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  }).catch(() => undefined)
}

export async function forgotPassword(email: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao solicitar redefinição de senha')
}

export async function resetPassword(token: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao redefinir senha')
}

export async function verifyEmail(token: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/verify-email/${encodeURIComponent(token)}`, {
    method: 'POST',
  })
  if (!res.ok) throw await readError(res, 'Erro ao verificar e-mail')
}

export async function resendVerification(): Promise<void> {
  const res = await fetch(`${BASE}/auth/resend-verification`, {
    method: 'POST',
    headers: authBearerHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw await readError(res, 'Erro ao reenviar verificação')
}

export async function getUser(): Promise<UserInfo | null> {
  try {
    const res = await fetch(`${BASE}/auth/me`, {
      credentials: 'include',
      cache: 'no-store',
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function downloadPersonalData(): Promise<Blob> {
  const res = await fetch(`${BASE}/auth/data-export`, {
    credentials: 'include',
  })
  if (!res.ok) throw await readError(res, 'Erro ao exportar seus dados')
  return res.blob()
}

export async function deleteAccount(password: string, confirmation: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/account`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ password, confirmation }),
  })
  if (!res.ok) throw await readError(res, 'Erro ao excluir a conta')
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
  if (!res.ok) throw await readError(res, 'Erro ao exportar histórico')
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

export interface BillingSyncResponse {
  synced: boolean
  plan: string
  billing_status?: string | null
}

export async function syncBillingSubscription(): Promise<BillingSyncResponse> {
  const res = await fetch(`${BASE}/billing/sync`, {
    method: 'POST',
    headers: authBearerHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw await readError(res, 'Erro ao confirmar a ativação da assinatura')
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
