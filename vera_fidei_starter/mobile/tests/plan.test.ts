import assert from 'node:assert/strict'
import test from 'node:test'

import { canOpenLibraryPdf, normalizedPlan, planLabel } from '../lib/plan'

test('normaliza planos desconhecidos para Fiel', () => {
  assert.equal(normalizedPlan(' DESCONHECIDO '), 'fiel')
  assert.equal(planLabel(null), 'Fiel')
})

test('libera PDF para todos os planos autenticados, inclusive Fiel', () => {
  assert.equal(canOpenLibraryPdf('fiel'), true)
  assert.equal(canOpenLibraryPdf('catequista'), true)
  assert.equal(canOpenLibraryPdf('apologeta'), true)
  assert.equal(canOpenLibraryPdf('patristico'), true)
  assert.equal(canOpenLibraryPdf('magisterio'), true)
  assert.equal(canOpenLibraryPdf(null), false)
  assert.equal(canOpenLibraryPdf('desconhecido'), false)
})
