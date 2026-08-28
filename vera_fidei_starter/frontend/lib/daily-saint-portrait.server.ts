import 'server-only'

import type { CalendarSaint } from '@/lib/roman-calendar'
import {
  allowedSaintPortraitUrl,
  allowedSaintSourceUrl,
  htmlCanonicalUrl,
  htmlMetaContent,
  sourceTitleMatchesSaint,
  type DailySaintPortrait,
  vaticanDetailUrls,
} from '@/lib/saint-portrait'

const CANCAO_NOVA_DAILY_URL = 'https://santo.cancaonova.com/'
const VATICAN_NEWS_ORIGIN = 'https://www.vaticannews.va'
const FETCH_TIMEOUT_MS = 4_000
const PORTRAIT_REVALIDATE_SECONDS = 6 * 60 * 60

async function fetchHtml(url: string, providerSignal?: AbortSignal): Promise<string | null> {
  try {
    const requestSignal = providerSignal
      ? AbortSignal.any([providerSignal, AbortSignal.timeout(FETCH_TIMEOUT_MS)])
      : AbortSignal.timeout(FETCH_TIMEOUT_MS)
    const response = await fetch(url, {
      headers: {
        Accept: 'text/html,application/xhtml+xml',
        'User-Agent': 'VeraFidei/1.0 (contato: vera.fidei661@gmail.com)',
      },
      next: { revalidate: PORTRAIT_REVALIDATE_SECONDS },
      signal: requestSignal,
    })
    if (!response.ok) return null

    const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
    if (!contentType.includes('text/html')) return null
    return await response.text()
  } catch {
    return null
  }
}

function portraitFromHtml(
  html: string,
  saint: CalendarSaint,
  sourceLabel: DailySaintPortrait['sourceLabel'],
  fallbackSourceUrl: string,
): DailySaintPortrait | null {
  const title = htmlMetaContent(html, 'og:title') ?? htmlMetaContent(html, 'twitter:title')
  const src = htmlMetaContent(html, 'og:image') ?? htmlMetaContent(html, 'twitter:image')
  const canonical = htmlCanonicalUrl(html) ?? fallbackSourceUrl
  const names = [saint.name, ...saint.aliases]

  if (
    !title
    || !src
    || !sourceTitleMatchesSaint(title, names)
    || !allowedSaintPortraitUrl(src)
    || !allowedSaintSourceUrl(canonical)
  ) {
    return null
  }

  return {
    src,
    alt: `${saint.name} — imagem publicada por ${sourceLabel}`,
    sourceLabel,
    sourceUrl: canonical,
  }
}

async function fromCancaoNova(
  saint: CalendarSaint,
  providerSignal?: AbortSignal,
): Promise<DailySaintPortrait | null> {
  const html = await fetchHtml(CANCAO_NOVA_DAILY_URL, providerSignal)
  return html
    ? portraitFromHtml(html, saint, 'Canção Nova', CANCAO_NOVA_DAILY_URL)
    : null
}

async function fromVaticanNews(
  saint: CalendarSaint,
  providerSignal?: AbortSignal,
): Promise<DailySaintPortrait | null> {
  const [month, day] = saint.key.split('-')
  if (!month || !day) return null

  const indexUrl = `${VATICAN_NEWS_ORIGIN}/pt/santo-do-dia/${month}/${day}.html`
  const indexHtml = await fetchHtml(indexUrl, providerSignal)
  if (!indexHtml) return null

  const detailUrls = vaticanDetailUrls(indexHtml, month, day)
  for (const detailUrl of detailUrls) {
    const detailHtml = await fetchHtml(detailUrl, providerSignal)
    if (!detailHtml) continue
    const portrait = portraitFromHtml(detailHtml, saint, 'Vatican News', detailUrl)
    if (portrait) return portrait
  }

  return null
}

export async function getDailySaintPortrait(
  saint: CalendarSaint,
): Promise<DailySaintPortrait | null> {
  const vaticanController = new AbortController()
  const vaticanSignal = AbortSignal.any([
    vaticanController.signal,
    AbortSignal.timeout(FETCH_TIMEOUT_MS),
  ])
  const vaticanPromise = fromVaticanNews(saint, vaticanSignal)

  const cancaoNova = await fromCancaoNova(
    saint,
    AbortSignal.timeout(FETCH_TIMEOUT_MS),
  )
  if (cancaoNova) {
    vaticanController.abort()
    return cancaoNova
  }

  return await vaticanPromise
}
