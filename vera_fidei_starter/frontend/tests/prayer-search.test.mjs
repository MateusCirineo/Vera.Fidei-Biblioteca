import assert from 'node:assert/strict'
import test from 'node:test'
import {
  normalizePrayerSearch,
  searchPrayerGroups,
} from '../lib/prayer-search.ts'

const groups = [
  {
    code: 'MARIA',
    title: 'Orações Marianas',
    description: 'Devoções a Nossa Senhora, rosário e invocações marianas.',
    items: [
      {
        id: 'ave-maria-1',
        title: 'Ave Maria',
        source: 'Canção Nova - Liturgia Diária',
        versions: [
          { lang: 'Português', text: 'Ave Maria, cheia de graça, o Senhor é convosco.' },
          { lang: 'Latim', text: 'Ave Maria, gratia plena, Dominus tecum.' },
          { lang: 'Inglês', text: 'Hail Mary, full of grace, the Lord is with thee.' },
        ],
      },
      {
        id: 'ave-maria-2',
        title: 'Ave Maria — versão 2',
        source: 'Canção Nova - Liturgia Diária',
        versions: [
          { lang: 'Português', text: 'Ave, Maria, cheia de graça.' },
        ],
      },
    ],
  },
  {
    code: 'ESP',
    title: 'Orações ao Espírito Santo',
    description: 'Pentecostes, discernimento, dons e súplicas ao Paráclito.',
    items: [
      {
        id: 'veni-creator',
        title: 'Veni Creator Spiritus',
        source: 'Vera.Fidei',
        note: 'Hino tradicional',
        versions: [
          { lang: 'Latim', text: 'Veni, Creator Spiritus, mentes tuorum visita.' },
          { lang: 'Português', text: 'Vinde, Espírito Criador, visitai as nossas almas.' },
        ],
      },
    ],
  },
  {
    code: 'BASE',
    title: 'Principais Orações Diárias',
    description: 'Orações fundamentais e fórmulas comuns da vida católica.',
    items: [
      {
        id: 'pai-nosso',
        title: 'Pai Nosso',
        source: 'Vera.Fidei',
        versions: [
          {
            lang: 'Português',
            text: 'Pai nosso, que estais nos céus, santificado seja o vosso nome.',
          },
        ],
      },
      {
        id: 'oracao-manha-referenciada',
        title: 'Oração da manhã',
        source: 'Referência editorial: Pai Nosso, edição de estudo',
        note: 'Ver também Pai Nosso na página anterior.',
        url: 'https://example.test/referencias/pai-nosso',
        versions: [
          {
            lang: 'Português',
            text: 'Eu vos adoro, meu Deus, e vos ofereço todas as ações deste dia. Ao final, reze um Pai Nosso.',
          },
        ],
      },
    ],
  },
]

test('normaliza acentos, caixa, espaços e apóstrofos', () => {
  assert.equal(normalizePrayerSearch('  Orações d’ÁLMAS  '), 'oracoes dalmas')
})

test('pesquisa título sem acento e mantém itens reais distintos', () => {
  const results = searchPrayerGroups(groups, 'ave maria')

  assert.deepEqual(results.map(result => result.itemId), ['ave-maria-1', 'ave-maria-2'])
})

test('não duplica uma oração quando várias versões correspondem', () => {
  const results = searchPrayerGroups(groups, 'ave')

  assert.equal(results.filter(result => result.itemId === 'ave-maria-1').length, 1)
  assert.deepEqual(
    results.find(result => result.itemId === 'ave-maria-1').matchedLanguages,
    ['Português', 'Latim'],
  )
})

test('pesquisa somente título e texto próprio das versões', () => {
  assert.deepEqual(searchPrayerGroups(groups, 'gratia plena').map(result => result.itemId), ['ave-maria-1'])
  assert.deepEqual(searchPrayerGroups(groups, 'espirito criador').map(result => result.itemId), ['veni-creator'])
  assert.match(searchPrayerGroups(groups, 'espirito criador')[0].excerpt, /Espírito Criador/)
})

test('ignora categoria, descrição, idioma, fonte, nota e URL', () => {
  for (const metadataOnlyQuery of [
    'oracoes marianas',
    'paraclito',
    'ingles',
    'cancao nova',
    'hino tradicional',
    'example test referencias',
  ]) {
    assert.deepEqual(
      searchPrayerGroups(groups, metadataOnlyQuery),
      [],
      `não deveria casar metadado: ${metadataOnlyQuery}`,
    )
  }
})

test('Pai Nosso retorna a oração real, não item cuja referência contém o nome', () => {
  const results = searchPrayerGroups(groups, 'Pai Nosso')

  assert.deepEqual(results.map(result => result.itemId), ['pai-nosso'])
  assert.equal(results.some(result => result.itemId === 'oracao-manha-referenciada'), false)
})

test('uma correspondência de título prevalece sobre menções no texto de outras orações', () => {
  assert.deepEqual(
    searchPrayerGroups(groups, 'oracao da manha').map(result => result.itemId),
    ['oracao-manha-referenciada'],
  )
})

test('preserva pesquisa acentuada ou sem acento e por trecho do texto', () => {
  assert.deepEqual(searchPrayerGroups(groups, 'Espírito').map(result => result.itemId), ['veni-creator'])
  assert.deepEqual(searchPrayerGroups(groups, 'espirito').map(result => result.itemId), ['veni-creator'])
  assert.deepEqual(
    searchPrayerGroups(groups, 'santificado seja o vosso nome').map(result => result.itemId),
    ['pai-nosso'],
  )
})

test('não mistura termos do título, metadados ou traduções diferentes', () => {
  assert.deepEqual(searchPrayerGroups(groups, 'creator almas'), [])
  assert.deepEqual(searchPrayerGroups(groups, 'gratia lord'), [])
})

test('retorna vazio para consulta vazia ou inexistente', () => {
  assert.deepEqual(searchPrayerGroups(groups, '   '), [])
  assert.deepEqual(searchPrayerGroups(groups, 'termo inexistente'), [])
})
