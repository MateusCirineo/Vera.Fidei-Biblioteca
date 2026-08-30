import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(
  new URL('../components/admin/AdminMetrics.tsx', import.meta.url),
  'utf8',
)

test('admin analytics presents the same explicit daily, 7-day and 30-day windows', () => {
  assert.match(source, />Hoje</)
  assert.match(source, />Últimos 7 dias</)
  assert.match(source, />Últimos 30 dias</)
  assert.match(source, /data\.registrations/)
  assert.match(source, /data\.visitors/)
  assert.match(source, /data\.page_views/)
  assert.match(source, /data\.searches/)
  assert.match(source, /data\.verifications/)
  assert.match(source, /period\?\.today/)
  assert.match(source, /period\?\.last_7_days/)
  assert.match(source, /period\?\.last_30_days/)
  assert.match(source, /Number\.isFinite/)
})

test('admin analytics identifies the measurement baseline and Brazilian timezone', () => {
  assert.match(source, /Medição desta base iniciada em/)
  assert.match(source, /America\/Sao_Paulo/)
  assert.match(source, /horário de Brasília/)
  assert.match(source, /Os períodos de 7 e 30 dias incluem hoje/)
})

test('admin analytics defines unique visitors without claiming personal identification', () => {
  assert.match(source, /Visitantes únicos desde o início desta medição/)
  assert.match(source, /Nenhum IP ou identificação pessoal é guardado/)
})
