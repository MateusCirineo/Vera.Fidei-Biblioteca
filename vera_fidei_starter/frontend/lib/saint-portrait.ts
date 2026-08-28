export type DailySaintPortrait = {
  src: string
  alt: string
  sourceLabel: 'Canção Nova' | 'Vatican News'
  sourceUrl: string
}

type HtmlAttributes = Record<string, string>

const GENERIC_SAINT_WORDS = new Set([
  'beata',
  'beato',
  'bispo',
  'companheiros',
  'doutor',
  'igreja',
  'martir',
  'martires',
  'memoria',
  'monge',
  'padre',
  'papa',
  'presbitero',
  'santa',
  'santas',
  'santo',
  'santos',
  'sao',
  'virgem',
])

export function decodeHtmlAttribute(value: string): string {
  return value.replace(/&(#x?[0-9a-f]+|amp|apos|gt|lt|quot);/gi, (_entity, code: string) => {
    const normalized = code.toLowerCase()
    if (normalized === 'amp') return '&'
    if (normalized === 'apos') return "'"
    if (normalized === 'gt') return '>'
    if (normalized === 'lt') return '<'
    if (normalized === 'quot') return '"'
    if (normalized.startsWith('#x')) {
      return String.fromCodePoint(Number.parseInt(normalized.slice(2), 16))
    }
    return String.fromCodePoint(Number.parseInt(normalized.slice(1), 10))
  })
}

function attributesFromTag(tag: string): HtmlAttributes {
  const attributes: HtmlAttributes = {}
  const pattern = /([:\w-]+)\s*=\s*(["'])([\s\S]*?)\2/g
  let match: RegExpExecArray | null

  while ((match = pattern.exec(tag)) !== null) {
    attributes[match[1].toLowerCase()] = decodeHtmlAttribute(match[3].trim())
  }

  return attributes
}

export function htmlMetaContent(html: string, key: string): string | null {
  const normalizedKey = key.toLowerCase()
  const tags = html.match(/<meta\s+[^>]*>/gi) ?? []

  for (const tag of tags) {
    const attributes = attributesFromTag(tag)
    const attributeKey = (attributes.property ?? attributes.name ?? '').toLowerCase()
    if (attributeKey === normalizedKey && attributes.content) return attributes.content
  }

  return null
}

export function htmlCanonicalUrl(html: string): string | null {
  const tags = html.match(/<link\s+[^>]*>/gi) ?? []
  for (const tag of tags) {
    const attributes = attributesFromTag(tag)
    if ((attributes.rel ?? '').toLowerCase() === 'canonical' && attributes.href) {
      return attributes.href
    }
  }
  return null
}

export function normalizeSaintIdentity(value: string): string[] {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .split(/\s+/)
    .filter(word => word.length > 2 && !GENERIC_SAINT_WORDS.has(word))
}

export function sourceTitleMatchesSaint(title: string, names: string[]): boolean {
  const candidate = new Set(normalizeSaintIdentity(title))
  if (candidate.size === 0) return false

  return names.some((name) => {
    const expected = normalizeSaintIdentity(name)
    return expected.length > 0 && expected.every(word => candidate.has(word))
  })
}

export function allowedSaintPortraitUrl(value: string): boolean {
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return false

    if (url.hostname === 'img.cancaonova.com') {
      return url.pathname.startsWith('/cnimages/canais/uploads/sites/')
    }

    if (url.hostname === 'www.vaticannews.va') {
      return url.pathname.startsWith('/content/dam/vaticannews/')
    }
  } catch {
    return false
  }

  return false
}

export function allowedSaintSourceUrl(value: string): boolean {
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return false
    return (
      url.hostname === 'santo.cancaonova.com'
      || (
        url.hostname === 'www.vaticannews.va'
        && url.pathname.startsWith('/pt/santo-do-dia/')
      )
    )
  } catch {
    return false
  }
}

export function vaticanDetailUrls(html: string, month: string, day: string): string[] {
  const links = html.match(/href\s*=\s*(["'])(.*?)\1/gi) ?? []
  const expectedPrefix = `/pt/santo-do-dia/${month}/${day}/`
  const urls = new Set<string>()

  for (const link of links) {
    const attributes = attributesFromTag(`<a ${link}>`)
    const href = attributes.href
    if (!href) continue

    try {
      const url = new URL(href, 'https://www.vaticannews.va')
      if (
        url.protocol === 'https:'
        && url.hostname === 'www.vaticannews.va'
        && url.pathname.startsWith(expectedPrefix)
        && url.pathname.endsWith('.html')
      ) {
        urls.add(url.toString())
      }
    } catch {
      // A origem externa pode publicar links incompletos; eles são ignorados.
    }
  }

  return [...urls].slice(0, 8)
}
