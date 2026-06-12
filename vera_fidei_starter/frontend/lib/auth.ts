const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface UserInfo {
  id: number
  name: string
  email: string
  plan: string
  is_active: boolean
}

function setToken(token: string): void {
  document.cookie = `vf_token=${token}; path=/; SameSite=Strict; Max-Age=${60 * 60 * 24 * 7}`
}

export function getToken(): string {
  if (typeof document === 'undefined') return ''
  const match = document.cookie.match(/(?:^|; )vf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export function clearToken(): void {
  document.cookie = 'vf_token=; path=/; Max-Age=0'
}

export function authBearerHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken()
  const apiKey = process.env.NEXT_PUBLIC_API_KEY ?? ''
  const headers: Record<string, string> = { ...extra }
  if (apiKey) headers['X-API-Key'] = apiKey
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

export async function register(name: string, email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Erro ao cadastrar' }))
    throw new Error(err.detail ?? 'Erro ao cadastrar')
  }
  const data = await res.json()
  setToken(data.access_token)
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Credenciais inválidas' }))
    throw new Error(err.detail ?? 'Credenciais inválidas')
  }
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
