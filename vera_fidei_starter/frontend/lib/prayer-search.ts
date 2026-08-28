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
  normalizedVersions: string[],
  query: string,
  tokens: string[],
): number {
  if (normalizedTitle === query) return 0
  if (normalizedTitle.startsWith(query)) return 10
  if (normalizedTitle.includes(query)) return 20
  if (includesEveryToken(normalizedTitle, tokens)) return 25
  if (normalizedVersions.some(version => version.includes(query))) return 30
  if (normalizedVersions.some(version => includesEveryToken(version, tokens))) return 35
  return 40
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
    group.items.forEach(item => {
      const normalizedTitle = normalizePrayerSearch(item.title)
      const normalizedVersions = item.versions.map(version => ({
        ...version,
        normalized: normalizePrayerSearch(version.text),
      }))
      const matchedVersions = normalizedVersions.filter(version =>
        version.normalized.includes(query) || includesEveryToken(version.normalized, tokens)
      )
      const titleMatches = normalizedTitle.includes(query) || includesEveryToken(normalizedTitle, tokens)

      // All query terms must occur in the title or together inside one real version.
      // Never join metadata or separate translations to manufacture a match.
      if (!titleMatches && matchedVersions.length === 0) return

      const excerptVersion = matchedVersions.find(version =>
        normalizePrayerSearch(version.text).includes(query)
      ) ?? matchedVersions.find(version =>
        tokens.some(token => normalizePrayerSearch(version.text).includes(token))
      )

      const excerpt = excerptVersion
        ? excerptAroundMatch(excerptVersion.text, query, tokens)
        : undefined

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
          normalizedVersions.map(version => version.normalized),
          query,
          tokens,
        ),
      })
    })
  })

  // Modern JavaScript sort is stable, preserving catalogue order for equal scores.
  const rankedResults = results.sort((left, right) => left.score - right.score)
  const titleResults = rankedResults.filter(result => result.score < 30)

  // A name search must not be polluted by other prayers that only mention that name.
  // Search inside the prayer text only when no title itself matches the query.
  return titleResults.length > 0 ? titleResults : rankedResults
}
