import { NextRequest, NextResponse } from 'next/server'
import { LONG_REQUEST_TIMEOUT_MS, fetchWithTimeout } from '@/lib/http'
import { getServerApiBase } from '@/lib/api-base'

const BASE = getServerApiBase()
const API_KEY = process.env.INTERNAL_API_KEY ?? process.env.NEXT_PUBLIC_API_KEY ?? ''

export async function GET(request: NextRequest) {
  const token = readToken(request)
  if (!token) {
    return NextResponse.json({ detail: 'Sessao expirada. Entre novamente.' }, { status: 401 })
  }

  const res = await fetchWithTimeout(`${BASE}/citations/historico/export.xlsx`, {
    headers: {
      'X-API-Key': API_KEY,
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  }, { timeoutMs: LONG_REQUEST_TIMEOUT_MS })

  if (!res.ok) {
    const detail = await res.text().catch(() => 'Erro ao exportar Excel.')
    return new NextResponse(detail, { status: res.status })
  }

  const body = await res.arrayBuffer()
  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': res.headers.get('content-type')
        ?? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'Content-Disposition': 'attachment; filename="historico_verafidei.xlsx"',
      'Cache-Control': 'no-store',
    },
  })
}

function readToken(request: NextRequest): string {
  const cookieValue = request.cookies.get('vf_token')?.value
  if (!cookieValue) return ''
  try {
    return decodeURIComponent(cookieValue)
  } catch {
    return cookieValue
  }
}
