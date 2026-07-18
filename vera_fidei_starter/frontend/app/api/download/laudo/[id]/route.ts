import { NextRequest, NextResponse } from 'next/server'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ id: string }> },
) {
  const token = readToken(_request)
  if (!token) {
    return NextResponse.json({ detail: 'Sessao expirada. Entre novamente.' }, { status: 401 })
  }

  const { id } = await context.params
  if (!/^\d+$/.test(id)) {
    return NextResponse.json({ detail: 'Laudo invalido.' }, { status: 400 })
  }

  const res = await fetch(`${BASE}/citations/historico/${id}/laudo`, {
    headers: {
      'X-API-Key': API_KEY,
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  })

  if (!res.ok) {
    const detail = await res.text().catch(() => 'Erro ao baixar laudo.')
    return new NextResponse(detail, { status: res.status })
  }

  const body = await res.arrayBuffer()
  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': res.headers.get('content-type') ?? 'application/pdf',
      'Content-Disposition': `attachment; filename="laudo_verafidei_${id}.pdf"`,
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
