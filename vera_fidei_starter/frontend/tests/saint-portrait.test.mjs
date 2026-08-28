import assert from 'node:assert/strict'
import test from 'node:test'
import {
  allowedSaintPortraitUrl,
  allowedSaintSourceUrl,
  htmlCanonicalUrl,
  htmlMetaContent,
  sourceTitleMatchesSaint,
  vaticanDetailUrls,
} from '../lib/saint-portrait.ts'

test('lê metadados independentemente da ordem dos atributos', () => {
  const html = `
    <meta content="Santo Agostinho, doutor da Igreja" property="og:title">
    <meta property='og:image' content='https://img.cancaonova.com/cnimages/canais/uploads/sites/2/2022/08/agostinho.jpg'>
    <link href="https://santo.cancaonova.com/santo/santo-agostinho/" rel="canonical">
  `

  assert.equal(htmlMetaContent(html, 'og:title'), 'Santo Agostinho, doutor da Igreja')
  assert.equal(
    htmlMetaContent(html, 'og:image'),
    'https://img.cancaonova.com/cnimages/canais/uploads/sites/2/2022/08/agostinho.jpg',
  )
  assert.equal(
    htmlCanonicalUrl(html),
    'https://santo.cancaonova.com/santo/santo-agostinho/',
  )
})

test('confere a identidade do santo antes de aceitar o retrato', () => {
  assert.equal(
    sourceTitleMatchesSaint('Santo Agostinho, bispo e doutor da Igreja', ['Santo Agostinho']),
    true,
  )
  assert.equal(
    sourceTitleMatchesSaint('Santa Mônica, viúva', ['Santo Agostinho']),
    false,
  )
})

test('aceita somente imagens e páginas das fontes previstas', () => {
  assert.equal(
    allowedSaintPortraitUrl('https://img.cancaonova.com/cnimages/canais/uploads/sites/2/2022/08/agostinho.jpg'),
    true,
  )
  assert.equal(
    allowedSaintPortraitUrl('https://www.vaticannews.va/content/dam/vaticannews/santi/agostinho.jpg'),
    true,
  )
  assert.equal(allowedSaintPortraitUrl('https://example.com/agostinho.jpg'), false)
  assert.equal(allowedSaintPortraitUrl('http://img.cancaonova.com/cnimages/agostinho.jpg'), false)
  assert.equal(allowedSaintSourceUrl('https://santo.cancaonova.com/santo/santo-agostinho/'), true)
  assert.equal(
    allowedSaintSourceUrl('https://www.vaticannews.va/pt/santo-do-dia/08/28/s--agostinho.html'),
    true,
  )
  assert.equal(allowedSaintSourceUrl('https://www.vaticannews.va/en/saints/agostinho.html'), false)
})

test('extrai somente páginas do dia no Vatican News', () => {
  const html = `
    <a href="/pt/santo-do-dia/08/28/s--agostinho.html">Agostinho</a>
    <a href="https://www.vaticannews.va/pt/santo-do-dia/08/28/s--hermes.html">Hermes</a>
    <a href="/pt/santo-do-dia/08/27/santa-monica.html">Mônica</a>
  `

  assert.deepEqual(vaticanDetailUrls(html, '08', '28'), [
    'https://www.vaticannews.va/pt/santo-do-dia/08/28/s--agostinho.html',
    'https://www.vaticannews.va/pt/santo-do-dia/08/28/s--hermes.html',
  ])
})
