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

test('pesquisa descrição da categoria sem acento', () => {
  const results = searchPrayerGroups(groups, 'paraclito')

  assert.deepEqual(results.map(result => result.itemId), ['veni-creator'])
  assert.match(results[0].excerpt, /Paráclito/)
})

test('pesquisa conteúdo, idioma e fonte', () => {
  assert.deepEqual(searchPrayerGroups(groups, 'gratia plena').map(result => result.itemId), ['ave-maria-1'])
  assert.deepEqual(searchPrayerGroups(groups, 'ingles').map(result => result.itemId), ['ave-maria-1'])
  assert.deepEqual(
    searchPrayerGroups(groups, 'cancao nova').map(result => result.itemId),
    ['ave-maria-1', 'ave-maria-2'],
  )
})

test('aceita termos distribuídos entre título e idioma', () => {
  const results = searchPrayerGroups(groups, 'creator portugues')

  assert.deepEqual(results.map(result => result.itemId), ['veni-creator'])
})

test('retorna vazio para consulta vazia ou inexistente', () => {
  assert.deepEqual(searchPrayerGroups(groups, '   '), [])
  assert.deepEqual(searchPrayerGroups(groups, 'termo inexistente'), [])
})
