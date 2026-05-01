const ROMAN_TABLE: [number, string][] = [
  [1000,'M'],[900,'CM'],[500,'D'],[400,'CD'],
  [100,'C'],[90,'XC'],[50,'L'],[40,'XL'],
  [10,'X'],[9,'IX'],[5,'V'],[4,'IV'],[1,'I'],
]

function toRoman(n: number): string {
  let result = ''
  for (const [val, sym] of ROMAN_TABLE) {
    while (n >= val) { result += sym; n -= val }
  }
  return result
}

export function toCentury(year: number): number {
  return Math.ceil(Math.abs(year) / 100)
}

export function centuryLabel(century: number): string {
  return `Século ${toRoman(century)}`
}

export function groupByCentury<T>(
  items: T[],
  getYear: (item: T) => number | null,
): { century: number | null; label: string; items: T[] }[] {
  const map = new Map<number | null, T[]>()
  for (const item of items) {
    const year = getYear(item)
    const century = year != null ? toCentury(year) : null
    if (!map.has(century)) map.set(century, [])
    map.get(century)!.push(item)
  }

  const result: { century: number | null; label: string; items: T[] }[] = []
  const known = ([...map.keys()] as (number | null)[])
    .filter((k): k is number => k !== null)
    .sort((a, b) => a - b)

  for (const c of known) {
    result.push({ century: c, label: centuryLabel(c), items: map.get(c)! })
  }
  if (map.has(null)) {
    result.push({ century: null, label: 'Século desconhecido', items: map.get(null)! })
  }
  return result
}

// Mapa de Padres da Igreja → ano de falecimento (aproximado)
// Nomes no formato exato retornado pelo catálogo da API /authors/catalog
export const FATHER_DEATH_YEARS: Record<string, number> = {
  // ── Século I ──────────────────────────────────────────────────────────────
  'Clemente de Roma': 99,
  'São Clemente de Roma': 99,
  'São Barnabé': 100,

  // ── Século II ─────────────────────────────────────────────────────────────
  'Papias de Hierápolis': 130,
  'Hermas': 150,
  'Aristides de Atenas': 134,
  'Santo Inácio de Antioquia': 107,
  'Inácio de Antioquia': 107,
  'São Policarpo de Esmirna': 155,
  'Policarpo de Esmirna': 155,
  'São Justino Mártir': 165,
  'Justino Mártir': 165,
  'Taciano, o Sírio': 185,
  'Atenágoras de Atenas': 177,
  'Teófilo de Antioquia': 185,
  'Melito de Sardes': 180,
  'São Melito de Sardes': 180,
  'Santo Ireneu de Lião': 180,
  'Santo Irineu de Lião': 180,
  'Santo Irineu de Lyon': 180,
  'Ireneu de Lyon': 180,
  'Ireneu de Lião': 180,
  'Irineu de Lyon': 180,
  'Irineu de Lião': 180,
  'Santo Ireneu': 180,
  'Santo Irineu': 180,

  // ── Século III ────────────────────────────────────────────────────────────
  'Tertuliano': 220,
  'Clemente de Alexandria': 215,
  'Orígenes': 254,
  'São Cipriano de Cartago': 258,
  'Cipriano de Cartago': 258,
  'São Cipriano': 258,
  'Novaciano': 258,
  'São Hipólito de Roma': 235,
  'Hipólito de Roma': 235,
  'Gregório Taumaturgo': 270,
  'São Gregório Taumaturgo': 270,
  'Dionísio de Alexandria': 265,
  'São Dionísio de Alexandria': 265,
  'Lactâncio': 325,

  // ── Século IV ─────────────────────────────────────────────────────────────
  'São Atanásio de Alexandria': 373,
  'Atanásio de Alexandria': 373,
  'São Hilário de Poitiers': 368,
  'Hilário de Poitiers': 368,
  'São Efrém Sírio': 373,
  'Efrém Sírio': 373,
  'São Basílio Magno': 379,
  'Basílio Magno': 379,
  'Basílio de Cesareia': 379,
  'São Gregório Nazianzeno': 390,
  'Gregório Nazianzeno': 390,
  'Gregório de Nazianzo': 390,
  'São Gregório de Nissa': 394,
  'Gregório de Nissa': 394,
  'São Ambrósio de Milão': 397,
  'Ambrósio de Milão': 397,
  'Ambrósio': 397,
  'São Cirilo de Jerusalém': 386,
  'Cirilo de Jerusalém': 386,
  'Epifânio de Salamina': 403,
  'São Epifânio de Salamina': 403,
  'Filastério de Bréscia': 397,

  // ── Século V ──────────────────────────────────────────────────────────────
  'São João Crisóstomo': 407,
  'João Crisóstomo': 407,
  'São Jerônimo': 420,
  'Jerônimo': 420,
  'Santo Agostinho de Hipona': 430,
  'Santo Agostinho': 430,
  'Agostinho de Hipona': 430,
  'Agostinho': 430,
  'São João Cassiano': 435,
  'João Cassiano': 435,
  'São Cirilo de Alexandria': 444,
  'Cirilo de Alexandria': 444,
  'São Vicente de Lérins': 450,
  'Vicente de Lérins': 450,
  'São Pedro Crisólogo': 450,
  'Pedro Crisólogo': 450,
  'Teodoreto de Ciro': 457,
  'São Leão Magno': 461,
  'Leão Magno': 461,
  'São Próspero de Aquitânia': 465,
  'Próspero de Aquitânia': 465,
  'São Isidoro de Pelúsio': 450,
  'Isidoro de Pelúsio': 450,
  'São Proclo de Constantinopla': 446,
  'Proclo de Constantinopla': 446,

  // ── Século VI ─────────────────────────────────────────────────────────────
  'Boécio': 524,
  'São Fulgêncio de Ruspe': 533,
  'Fulgêncio de Ruspe': 533,
  'São Cesário de Arles': 542,
  'Cesário de Arles': 542,
  'Cassiodoro': 580,
  'São Columbano': 597,
  'Columbano': 597,
  'São Bento de Núrsia': 547,
  'Bento de Núrsia': 547,
  'São Gaudêncio de Bréscia': 410,
  'São Cromácio de Aquileia': 407,
  'Cromácio de Aquileia': 407,

  // ── Século VII ────────────────────────────────────────────────────────────
  'São Gregório Magno': 604,
  'Gregório Magno': 604,
  'Santo Isidoro de Sevilha': 636,
  'Isidoro de Sevilha': 636,
  'São Máximo Confessor': 662,
  'Máximo Confessor': 662,
  'São Leandro de Sevilha': 600,
  'Leandro de Sevilha': 600,
  'São Ildefonso de Toledo': 667,
  'Santo Ildefonso de Toledo': 667,
  'São Sofrônio de Jerusalém': 638,
  'Sofrônio de Jerusalém': 638,

  // ── Século VIII ───────────────────────────────────────────────────────────
  'São Beda, o Venerável': 735,
  'Beda, o Venerável': 735,
  'Beda Venerável': 735,
  'São João Damasceno': 749,
  'João Damasceno': 749,
  'São Germano de Constantinopla': 740,
  'Germano de Constantinopla': 740,
  'São André de Creta': 740,
  'André de Creta': 740,

  // ── Século IX ─────────────────────────────────────────────────────────────
  'Alcuíno': 804,
  'João Escoto Erígena': 877,
  'São Martinho de Braga': 579,
  'Martinho de Braga': 579,

  // ── Século XII ────────────────────────────────────────────────────────────
  'São Bernardo de Claraval': 1153,
  'Bernardo de Claraval': 1153,

  // ── Século XIII ───────────────────────────────────────────────────────────
  'Santo Tomás de Aquino': 1274,
  'Tomás de Aquino': 1274,
  'São Boaventura': 1274,
  'Boaventura': 1274,
  'Alberto Magno': 1280,

  // ── Século XIV ────────────────────────────────────────────────────────────
  'Duns Escoto': 1308,

  // ── Autores sem obras ainda — prevenção futura ─────────────────────────────
  'Afraates, o Persa': 345,
  'Arnóbio de Sica': 330,
  'São Alexandre de Alexandria': 328,
  'Eusébio de Cesareia': 339,
  'Santo Antão do Egito': 356,
  'São Pacômio': 348,
  'São Macário do Egito': 390,
  'São Amfilóquio de Icônio': 403,
  'Evágrio Pôntico': 399,
  'Dídimo, o Cego': 398,
  'São Gregório de Tours': 594,
  'Minúcio Félix': 250,
  'Quodvultdeus': 454,
  'Rufino de Aquileia': 411,
  'Salviano de Marselha': 480,
  'São Hilário de Arles': 449,
  'São Máximo de Turim': 465,
  'São Paládio de Galácia': 430,
  'São Sulpício Severo': 425,
  'Teodoro de Mopsuéstia': 428,
  'Nilo de Âncira': 430,
  'Marco, o Monge': 430,
  'Hesíquio de Jerusalém': 450,
  'Filoxênio de Mabugue': 523,
  'São Tiago de Saruge': 521,
  'Ênodio de Pavia': 521,
  'Pseudo-Dionísio Areopagita': 510,
  'São Isaac de Nínive': 700,
}

export function getAuthorDeathYear(name: string): number | null {
  // Correspondência exata primeiro
  if (FATHER_DEATH_YEARS[name] != null) return FATHER_DEATH_YEARS[name]
  // Correspondência parcial (nome no lookup contém o nome buscado ou vice-versa)
  const lower = name.toLowerCase()
  for (const [key, year] of Object.entries(FATHER_DEATH_YEARS)) {
    const kl = key.toLowerCase()
    if (kl.includes(lower) || lower.includes(kl)) return year
  }
  return null
}
