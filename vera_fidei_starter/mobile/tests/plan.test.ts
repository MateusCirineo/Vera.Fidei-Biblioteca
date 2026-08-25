import assert from 'node:assert/strict'
import test from 'node:test'

import { canOpenLibraryPdf, normalizedPlan, planLabel } from '../lib/plan'

test('normaliza planos desconhecidos para Fiel', () => {
  assert.equal(normalizedPlan(' DESCONHECIDO '), 'fiel')
  assert.equal(planLabel(null), 'Fiel')
})

test('libera PDF somente a partir do Apologeta', () => {
  assert.equal(canOpenLibraryPdf('fiel'), false)
  assert.equal(canOpenLibraryPdf('catequista'), false)
  assert.equal(canOpenLibraryPdf('apologeta'), true)
  assert.equal(canOpenLibraryPdf('patristico'), true)
  assert.equal(canOpenLibraryPdf('magisterio'), true)
})
