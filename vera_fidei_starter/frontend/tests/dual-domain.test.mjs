import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { getPublicApiBase, getServerApiBase } from '../lib/api-base.ts'

test('browser API defaults to the current origin while server API stays private', () => {
  const previousPublic = process.env.NEXT_PUBLIC_API_URL
  const previousInternal = process.env.INTERNAL_API_URL
  const previousBuild = process.env.SERVER_BUILD_API_URL
  delete process.env.NEXT_PUBLIC_API_URL
  delete process.env.INTERNAL_API_URL
  delete process.env.SERVER_BUILD_API_URL

  try {
    assert.equal(getPublicApiBase(), '/api')
    assert.equal(getServerApiBase(), 'http://backend:8000')
  } finally {
    if (previousPublic === undefined) delete process.env.NEXT_PUBLIC_API_URL
    else process.env.NEXT_PUBLIC_API_URL = previousPublic
    if (previousInternal === undefined) delete process.env.INTERNAL_API_URL
    else process.env.INTERNAL_API_URL = previousInternal
    if (previousBuild === undefined) delete process.env.SERVER_BUILD_API_URL
    else process.env.SERVER_BUILD_API_URL = previousBuild
  }
})

test('explicit public and internal API bases are normalized', () => {
  const previousPublic = process.env.NEXT_PUBLIC_API_URL
  const previousInternal = process.env.INTERNAL_API_URL
  const previousBuild = process.env.SERVER_BUILD_API_URL
  process.env.NEXT_PUBLIC_API_URL = 'https://verafidei.com.br/api///'
  process.env.INTERNAL_API_URL = 'http://backend:8000///'
  process.env.SERVER_BUILD_API_URL = 'https://verafidei.oialfred.com/api///'

  try {
    assert.equal(getPublicApiBase(), 'https://verafidei.com.br/api')
    assert.equal(getServerApiBase(), 'http://backend:8000')
  } finally {
    if (previousPublic === undefined) delete process.env.NEXT_PUBLIC_API_URL
    else process.env.NEXT_PUBLIC_API_URL = previousPublic
    if (previousInternal === undefined) delete process.env.INTERNAL_API_URL
    else process.env.INTERNAL_API_URL = previousInternal
    if (previousBuild === undefined) delete process.env.SERVER_BUILD_API_URL
    else process.env.SERVER_BUILD_API_URL = previousBuild
  }
})

test('server-only build fallback does not change the same-origin browser base', () => {
  const previousBuild = process.env.SERVER_BUILD_API_URL
  const previousInternal = process.env.INTERNAL_API_URL
  const previousPublic = process.env.NEXT_PUBLIC_API_URL
  process.env.SERVER_BUILD_API_URL = 'https://verafidei.oialfred.com/api/'
  delete process.env.INTERNAL_API_URL
  delete process.env.NEXT_PUBLIC_API_URL

  try {
    assert.equal(getServerApiBase(), 'https://verafidei.oialfred.com/api')
    assert.equal(getPublicApiBase(), '/api')
  } finally {
    if (previousBuild === undefined) delete process.env.SERVER_BUILD_API_URL
    else process.env.SERVER_BUILD_API_URL = previousBuild
    if (previousInternal === undefined) delete process.env.INTERNAL_API_URL
    else process.env.INTERNAL_API_URL = previousInternal
    if (previousPublic === undefined) delete process.env.NEXT_PUBLIC_API_URL
    else process.env.NEXT_PUBLIC_API_URL = previousPublic
  }
})

test('deployment configuration serves and permits both production domains', () => {
  const nginx = readFileSync(new URL('../../nginx/default.conf', import.meta.url), 'utf8')
  const viewer = readFileSync(new URL('../public/pdf-viewer.html', import.meta.url), 'utf8')
  const compose = readFileSync(new URL('../../docker-compose.yml', import.meta.url), 'utf8')

  for (const domain of ['verafidei.com.br', 'verafidei.oialfred.com']) {
    assert.match(nginx, new RegExp(domain.replaceAll('.', '\\.')))
    assert.match(viewer, new RegExp(domain.replaceAll('.', '\\.')))
  }
  assert.match(compose, /NEXT_PUBLIC_API_URL:\s*\/api/)
  assert.match(compose, /NEXT_PUBLIC_SITE_URL:\s*https:\/\/verafidei\.com\.br/)
})
