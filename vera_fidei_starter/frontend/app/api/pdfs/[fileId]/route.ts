import { NextRequest, NextResponse } from 'next/server'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ fileId: string }> },
) {
  const token = readToken(request)
  if (!token) {
    return NextResponse.json({ detail: 'Sessao expirada. Entre novamente.' }, { status: 401 })
  }

  const { fileId } = await context.params
  if (!/^\d+$/.test(fileId)) {
    return NextResponse.json({ detail: 'Arquivo invalido.' }, { status: 400 })
  }

  const upstreamUrl = new URL(`${BASE}/pdfs/${fileId}`)
  if (request.nextUrl.searchParams.get('download')) {
    upstreamUrl.searchParams.set('download', '1')
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  }
  if (API_KEY) headers['X-API-Key'] = API_KEY
  const range = request.headers.get('range')
  if (range) headers.Range = range

  const res = await fetch(upstreamUrl.toString(), {
    headers,
    cache: 'no-store',
  })

  if (!res.ok && res.status !== 206) {
    const detail = await res.text().catch(() => 'Erro ao abrir PDF.')
    return new NextResponse(detail, {
      status: res.status,
      headers: {
        'Content-Type': res.headers.get('content-type') ?? 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    })
  }

  return new NextResponse(res.body, {
    status: res.status,
    headers: copyPdfHeaders(res.headers),
  })
}

function copyPdfHeaders(headers: Headers): Headers {
  const responseHeaders = new Headers()
  for (const key of [
    'accept-ranges',
    'content-disposition',
    'content-length',
    'content-range',
    'content-type',
    'etag',
    'last-modified',
  ]) {
    const value = headers.get(key)
    if (value) responseHeaders.set(key, value)
  }
  if (!responseHeaders.has('content-type')) {
    responseHeaders.set('content-type', 'application/pdf')
  }
  responseHeaders.set('cache-control', 'private, no-store')
  return responseHeaders
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
