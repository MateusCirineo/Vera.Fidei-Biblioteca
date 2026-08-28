export interface SearchablePrayerVersion {
  lang: string
  text: string
}

export interface SearchablePrayerItem {
  id: string
  title: string
  source?: string
  note?: string
  versions: SearchablePrayerVersion[]
}

export interface SearchablePrayerGroup {
  code: string
  title: string
  description: string
  items: SearchablePrayerItem[]
}

export interface PrayerSearchResult {
  key: string
  groupCode: string
  groupTitle: string
  groupDescription: string
  itemId: string
  itemTitle: string
  source?: string
  languages: string[]
  matchedLanguages: string[]
  excerpt?: string
  score: number
}

export function normalizePrayerSearch(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’'`´]/g, '')
    .toLocaleLowerCase('pt-BR')
    .replace(/\s+/g, ' ')
    .trim()
}

function includesEveryToken(value: string, tokens: string[]): boolean {
  return tokens.every(token => value.includes(token))
}

function matchScore(
  normalizedTitle: string,
  normalizedCategory: string,
  normalizedBody: string,
  normalizedSource: string,
  query: string,
  tokens: string[],
): number {
  if (normalizedTitle === query) return 0
  if (normalizedTitle.startsWith(query)) return 10
  if (normalizedTitle.includes(query)) return 20
  if (includesEveryToken(normalizedTitle, tokens)) return 25
  if (normalizedCategory.includes(query)) return 30
  if (includesEveryToken(normalizedCategory, tokens)) return 35
  if (normalizedBody.includes(query)) return 40
  if (includesEveryToken(normalizedBody, tokens)) return 45
  if (normalizedSource.includes(query)) return 50
  return 55
}

function excerptAroundMatch(value: string, query: string, tokens: string[]): string | undefined {
  const collapsed = value.replace(/\s+/g, ' ').trim()
  if (!collapsed) return undefined

  const normalized = normalizePrayerSearch(collapsed)
  let matchAt = normalized.indexOf(query)
  if (matchAt < 0) {
    matchAt = tokens.reduce((earliest, token) => {
      const candidate = normalized.indexOf(token)
      if (candidate < 0) return earliest
      return earliest < 0 ? candidate : Math.min(earliest, candidate)
    }, -1)
  }
  if (matchAt < 0) return undefined

  const maximumLength = 180
  const contextBefore = 54
  let start = Math.max(0, matchAt - contextBefore)
  let end = Math.min(collapsed.length, start + maximumLength)

  if (start > 0) {
    const nextSpace = collapsed.indexOf(' ', start)
    if (nextSpace >= 0 && nextSpace < matchAt) start = nextSpace + 1
  }
  if (end < collapsed.length) {
    const previousSpace = collapsed.lastIndexOf(' ', end)
    if (previousSpace > matchAt) end = previousSpace
  }

  return `${start > 0 ? '…' : ''}${collapsed.slice(start, end)}${end < collapsed.length ? '…' : ''}`
}

/** Returns one result per real prayer item, never one duplicate per language. */
export function searchPrayerGroups(
  groups: SearchablePrayerGroup[],
  rawQuery: string,
): PrayerSearchResult[] {
  const query = normalizePrayerSearch(rawQuery)
  if (!query) return []
  const tokens = query.split(' ').filter(Boolean)
  const results: PrayerSearchResult[] = []

  groups.forEach(group => {
    const normalizedCategory = normalizePrayerSearch(`${group.title} ${group.description} ${group.code}`)

    group.items.forEach(item => {
      const normalizedTitle = normalizePrayerSearch(item.title)
      const normalizedSource = normalizePrayerSearch(`${item.source ?? ''} ${item.note ?? ''}`)
      const normalizedVersions = item.versions.map(version => ({
        ...version,
        normalized: normalizePrayerSearch(`${version.lang} ${version.text}`),
      }))
      const normalizedBody = normalizedVersions.map(version => version.normalized).join(' ')
      const searchable = [
        normalizedTitle,
        normalizedCategory,
        normalizedBody,
        normalizedSource,
      ].join(' ')

      if (!includesEveryToken(searchable, tokens)) return

      const matchedVersions = normalizedVersions.filter(version =>
        version.normalized.includes(query) || includesEveryToken(version.normalized, tokens)
      )
      const excerptVersion = matchedVersions.find(version =>
        normalizePrayerSearch(version.text).includes(query)
      ) ?? matchedVersions.find(version =>
        tokens.some(token => normalizePrayerSearch(version.text).includes(token))
      )

      let excerpt = excerptVersion
        ? excerptAroundMatch(excerptVersion.text, query, tokens)
        : undefined
      if (!excerpt && includesEveryToken(normalizedCategory, tokens)) {
        excerpt = excerptAroundMatch(group.description, query, tokens)
      }
      if (!excerpt && includesEveryToken(normalizedSource, tokens)) {
        excerpt = excerptAroundMatch(`${item.source ?? ''} ${item.note ?? ''}`, query, tokens)
      }

      results.push({
        key: `${group.code}:${item.id}`,
        groupCode: group.code,
        groupTitle: group.title,
        groupDescription: group.description,
        itemId: item.id,
        itemTitle: item.title,
        source: item.source,
        languages: [...new Set(item.versions.map(version => version.lang))],
        matchedLanguages: [...new Set(matchedVersions.map(version => version.lang))],
        excerpt,
        score: matchScore(
          normalizedTitle,
          normalizedCategory,
          normalizedBody,
          normalizedSource,
          query,
          tokens,
        ),
      })
    })
  })

  // Modern JavaScript sort is stable, preserving catalogue order for equal scores.
  return results.sort((left, right) => left.score - right.score)
}
