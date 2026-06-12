const LANGUAGE_LABELS: Record<string, string> = {
  la: 'latim', lat: 'latim', latin: 'latim', latim: 'latim',
  grc: 'grego', el: 'grego', greek: 'grego', grego: 'grego', 'grego antigo': 'grego',
  pt: 'português', por: 'português', portuguese: 'português', português: 'português',
  es: 'espanhol', spanish: 'espanhol', espanhol: 'espanhol',
  en: 'inglês', eng: 'inglês', english: 'inglês', inglês: 'inglês',
  fr: 'francês', french: 'francês', francês: 'francês',
  it: 'italiano', italian: 'italiano', italiano: 'italiano',
  de: 'alemão', german: 'alemão', alemão: 'alemão',
  he: 'hebraico', hebrew: 'hebraico', hebraico: 'hebraico',
  syc: 'siríaco', syriac: 'siríaco', siríaco: 'siríaco',
  multi: 'multilingue', multilingue: 'multilingue',
}

export function formatLanguage(language: string | null | undefined): string {
  if (!language) return ''
  const normalized = language.trim().toLowerCase()
  if (!normalized) return ''
  const direct = LANGUAGE_LABELS[normalized]
  if (direct) return direct
  const parts = normalized
    .replace(/\s+e\s+/g, '/')
    .split(/[+/;,|]/)
    .map((p) => p.trim())
    .filter(Boolean)
  if (parts.length > 1) {
    const labels = parts.map((p) => LANGUAGE_LABELS[p] ?? p)
    return [...new Set(labels)].join('/')
  }
  return language
}
