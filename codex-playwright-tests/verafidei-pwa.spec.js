const { test, expect } = require('@playwright/test')

const BASE_URL = 'https://verafidei.oialfred.com'

test('Vera.Fidei exposes installable PWA metadata and service worker', async ({ page }) => {
  test.setTimeout(60_000)

  await page.goto(`${BASE_URL}/apresentacao`, { waitUntil: 'domcontentloaded' })

  const manifestHref = await page.locator('link[rel="manifest"]').getAttribute('href')
  expect(manifestHref).toBe('/manifest.webmanifest')

  const manifestResponse = await page.request.get(`${BASE_URL}/manifest.webmanifest`)
  expect(manifestResponse.ok()).toBeTruthy()
  const manifest = await manifestResponse.json()
  expect(manifest.short_name).toBe('Vera.Fidei')
  expect(manifest.display).toBe('standalone')
  expect(manifest.start_url).toBe('/apresentacao')
  expect(manifest.icons.some((icon) => icon.purpose === 'maskable')).toBeTruthy()

  const serviceWorkerResponse = await page.request.get(`${BASE_URL}/sw.js`)
  expect(serviceWorkerResponse.ok()).toBeTruthy()
  expect(serviceWorkerResponse.headers()['content-type']).toContain('javascript')

  await page.waitForFunction(async () => {
    if (!('serviceWorker' in navigator)) {
      return false
    }

    const registrations = await navigator.serviceWorker.getRegistrations()
    return registrations.some((registration) =>
      [registration.active, registration.installing, registration.waiting].some((worker) =>
        worker?.scriptURL.endsWith('/sw.js'),
      ),
    )
  })

  const activeWorker = await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.ready
    return registration.active?.scriptURL
  })

  expect(activeWorker).toBe(`${BASE_URL}/sw.js`)
})
