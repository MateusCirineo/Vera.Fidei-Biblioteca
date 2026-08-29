import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const viewer = readFileSync(
  new URL('../app/viewer/pdf/page.tsx', import.meta.url),
  'utf8',
)

test('centraliza a pagina renderizada sem deslocar a camada de destaques', () => {
  const renderedPage = viewer.match(
    /<div className="relative mx-auto w-fit">([\s\S]*?)<\/div>/,
  )?.[1] ?? ''

  assert.ok(renderedPage, 'o canvas deve estar dentro do contêiner centralizado')
  assert.match(renderedPage, /<canvas ref=\{canvasRef\} className="block"/)
  assert.match(renderedPage, /<div ref=\{overlayRef\} className="pointer-events-none absolute left-0 top-0"/)
})

test('preserva a largura rolavel e o comportamento responsivo do visualizador', () => {
  assert.match(viewer, /ref=\{wrapRef\}\s+className="relative w-full"/)
  assert.match(viewer, /style=\{\{ height: placeholderHeight, width: placeholderWidth \}\}/)
  assert.match(viewer, /placeholderWidth=\{placeholderWidthForPage\(pageNum\)\}/)
  assert.match(viewer, /className=\{isMobile \? 'px-0 py-0' : 'flex justify-center px-2 py-3'\}/)
  assert.match(viewer, /className="flex-1 overflow-auto"/)
  assert.match(viewer, /touchAction: 'pan-x pan-y'/)
})
