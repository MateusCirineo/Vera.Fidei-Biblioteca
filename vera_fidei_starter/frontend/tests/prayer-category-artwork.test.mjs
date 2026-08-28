import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const assetsDir = path.join(frontendRoot, 'assets', 'oracoes', 'categories')
const componentPath = path.join(frontendRoot, 'components', 'oracoes', 'PrayerCategoryIcon.tsx')

const artwork = {
  MARIA: 'marianas.webp',
  DIV: 'diversas.webp',
  JOSE: 'sao-jose.webp',
  EUCA: 'eucaristicas.webp',
  ESP: 'espirito-santo.webp',
  NOV: 'novenas.webp',
  VIACR: 'via-sacra.webp',
  SEQ: 'sequencias-liturgicas.webp',
  DOUT: 'doutores-da-igreja.webp',
  DIARIA: 'oracoes-diarias.webp',
  BIBLIA: 'para-ler-a-biblia.webp',
  BASE: 'principais-oracoes-diarias.webp',
  SANTOS: 'oracoes-aos-santos.webp',
  SANTAS: 'oracoes-as-santas.webp',
}

function webpDimensions(buffer) {
  assert.equal(buffer.subarray(0, 4).toString('ascii'), 'RIFF')
  assert.equal(buffer.subarray(8, 12).toString('ascii'), 'WEBP')
  assert.equal(buffer.subarray(12, 16).toString('ascii'), 'VP8 ')
  assert.deepEqual([...buffer.subarray(23, 26)], [0x9d, 0x01, 0x2a])

  return {
    width: buffer.readUInt16LE(26) & 0x3fff,
    height: buffer.readUInt16LE(28) & 0x3fff,
  }
}

test('prayer categories use exactly the fourteen supplied artworks', async () => {
  const files = (await readdir(assetsDir)).sort()
  assert.deepEqual(files, Object.values(artwork).sort())

  let totalBytes = 0
  for (const filename of files) {
    const buffer = await readFile(path.join(assetsDir, filename))
    totalBytes += buffer.length
    assert.deepEqual(webpDimensions(buffer), { width: 192, height: 192 })
    assert.ok(buffer.length <= 20_000, `${filename} is too large: ${buffer.length} bytes`)
  }
  assert.ok(totalBytes <= 200_000, `artwork bundle is too large: ${totalBytes} bytes`)
})

test('every prayer group code is mapped to its semantic artwork', async () => {
  const component = await readFile(componentPath, 'utf8')

  for (const [code, filename] of Object.entries(artwork)) {
    const importStem = filename.replace(/\.webp$/, '')
    assert.match(component, new RegExp(`from '@/assets/oracoes/categories/${importStem}\\.webp'`))
    assert.match(component, new RegExp(`\\b${code}:`))
  }

  assert.match(component, /alt=""/)
  assert.match(component, /aria-hidden="true"/)
  assert.match(component, /unoptimized/)
})
