import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const profileSource = readFileSync(
  new URL('../app/perfil/page.tsx', import.meta.url),
  'utf8',
)
const tabsSource = readFileSync(
  new URL('../components/perfil/ProfileHistoryTabs.tsx', import.meta.url),
  'utf8',
)
const citationHistorySource = readFileSync(
  new URL('../components/perfil/ProfileHistory.tsx', import.meta.url),
  'utf8',
)
const readingHistorySource = readFileSync(
  new URL('../components/perfil/ProfileReadingHistory.tsx', import.meta.url),
  'utf8',
)

test('perfil agrupa os dois historicos em abas na secao existente', () => {
  assert.match(profileSource, /<ProfileHistoryTabs userId=\{user\.id\} userPlan=\{user\.plan\} \/>/)
  assert.doesNotMatch(profileSource, /<ProfileReadingHistory userId=/)
  assert.doesNotMatch(profileSource, /<ProfileHistory userPlan=/)
  assert.match(tabsSource, /id="historico"/)
  assert.match(tabsSource, /Obras e leituras/)
  assert.match(tabsSource, /Citações e verificações/)
  assert.match(tabsSource, /role="tablist"/)
  assert.match(tabsSource, /role="tabpanel"/)
})

test('aba de obras reutiliza o historico de leitura e suas acoes', () => {
  assert.match(tabsSource, /<ProfileReadingHistory userId=\{userId\} embedded \/>/)
  assert.match(readingHistorySource, /listReadingHistory/)
  assert.match(readingHistorySource, /Continuar lendo/)
  assert.match(readingHistorySource, /Recomeçar/)
})

test('aba de citacoes preserva historico, exportacao e laudos', () => {
  assert.match(tabsSource, /<ProfileHistory userPlan=\{userPlan\} embedded \/>/)
  assert.match(citationHistorySource, /getHistorico/)
  assert.match(citationHistorySource, /Exportar Excel/)
  assert.match(citationHistorySource, /Baixar laudo PDF/)
})
