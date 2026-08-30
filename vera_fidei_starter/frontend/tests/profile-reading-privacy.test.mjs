import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  clearLocalReadingProgress,
  localReadingProgressKey,
} from '../lib/readingProgress.ts'

const profileSource = readFileSync(
  new URL('../app/perfil/page.tsx', import.meta.url),
  'utf8',
)
const readingHistorySource = readFileSync(
  new URL('../components/perfil/ProfileReadingHistory.tsx', import.meta.url),
  'utf8',
)

function sourceBetween(startMarker, endMarker) {
  const start = profileSource.indexOf(startMarker)
  const end = profileSource.indexOf(endMarker, start + startMarker.length)
  assert.notEqual(start, -1, `Marcador inicial ausente: ${startMarker}`)
  assert.notEqual(end, -1, `Marcador final ausente: ${endMarker}`)
  return profileSource.slice(start, end)
}

function memoryStorage() {
  const values = new Map()
  return {
    get length() { return values.size },
    getItem(key) { return values.get(key) ?? null },
    setItem(key, value) { values.set(key, String(value)) },
    removeItem(key) { values.delete(key) },
    key(index) { return [...values.keys()][index] ?? null },
  }
}

test('limpeza local remove somente o historico da conta encerrada', () => {
  const previousWindow = globalThis.window
  const localStorage = memoryStorage()
  globalThis.window = { localStorage }
  try {
    const currentUserKey = localReadingProgressKey(10, 20, 30)
    const otherUserKey = localReadingProgressKey(11, 20, 30)
    localStorage.setItem(currentUserKey, 'progresso da conta encerrada')
    localStorage.setItem(otherUserKey, 'progresso de outra conta')
    localStorage.setItem('vera-fidei:preferencia', 'preservar')

    assert.equal(clearLocalReadingProgress(10), 1)
    assert.equal(localStorage.getItem(currentUserKey), null)
    assert.equal(localStorage.getItem(otherUserKey), 'progresso de outra conta')
    assert.equal(localStorage.getItem('vera-fidei:preferencia'), 'preservar')
  } finally {
    globalThis.window = previousWindow
  }
})

test('logout limpa o progresso local somente depois de encerrar a sessao', () => {
  const handler = sourceBetween(
    'async function handleLogout()',
    'async function handleExportData()',
  )

  const logoutPosition = handler.indexOf('await logout()')
  const clearPosition = handler.indexOf('clearLocalReadingProgress(user.id)')
  assert.ok(logoutPosition >= 0)
  assert.ok(clearPosition > logoutPosition)
})

test('exportacao tenta sincronizar o progresso antes de pedir o JSON', () => {
  const handler = sourceBetween(
    'async function handleExportData()',
    'async function handleDeleteAccount()',
  )

  const flushPosition = handler.indexOf('await flushPendingReadingProgress(user.id)')
  const downloadPosition = handler.indexOf('await downloadPersonalData()')
  assert.ok(flushPosition >= 0)
  assert.ok(downloadPosition > flushPosition)
  assert.match(handler, /catch \{[\s\S]*readingSyncIncomplete = true/)
})

test('exclusao bem-sucedida limpa o progresso local e informa esse dado', () => {
  const handler = sourceBetween(
    'async function handleDeleteAccount()',
    'if (loading)',
  )

  const deletionPosition = handler.indexOf('await deleteAccount(')
  const clearPosition = handler.indexOf('clearLocalReadingProgress(user.id)')
  assert.ok(deletionPosition >= 0)
  assert.ok(clearPosition > deletionPosition)
  assert.match(profileSource, /históricos de leitura e de verificações/)
})

test('historico nao inventa percentual usando o total fisico do PDF', () => {
  assert.doesNotMatch(readingHistorySource, /current_page\s*\/\s*item\.total_pages/)
  assert.match(readingHistorySource, /const hasMeasuredProgress = progress !== null/)
  assert.match(readingHistorySource, /\{hasMeasuredProgress && \(/)
})
