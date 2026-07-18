import { NextRequest, NextResponse } from 'next/server'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

export async function GET(request: NextRequest) {
  const token = readToken(request)
  if (!token) {
    return NextResponse.json({ detail: 'Sessao expirada. Entre novamente.' }, { status: 401 })
  }

  const res = await fetch(`${BASE}/citations/historico/export.xlsx`, {
    headers: {
      'X-API-Key': API_KEY,
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  })

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
