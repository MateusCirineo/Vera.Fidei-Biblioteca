const { test, expect } = require('@playwright/test');

const BASE = process.env.VERA_BASE_URL || 'https://verafidei.oialfred.com';

test.describe.configure({ mode: 'serial' });
test.setTimeout(180_000);

test('Orações opens as the fifth Vera.Fidei tab with the preserved dark identity', async ({ page }) => {
  await page.goto(`${BASE}/oracoes`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('heading', { name: 'Orações' })).toBeVisible();
  await expect(page.getByText('Ora et stude', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: /Roteiro de Orações Diárias/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Orações Marianas/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Salve-Rainha/ })).toHaveCount(0);

  await page.getByRole('button', { name: /Orações Marianas/ }).first().click();
  await expect(page.getByText('Voltar para categorias')).toBeVisible();
  await page.getByRole('button', { name: /Salve-Rainha/ }).click();
  await expect(page.getByRole('button', { name: 'Português' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Latim' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Inglês' })).toBeVisible();
  await page.getByRole('button', { name: 'Latim' }).click();
  await expect(page.getByText('Salve Regina', { exact: false })).toBeVisible();

  await expect(page.getByRole('link', { name: 'Orações', exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-oracoes-producao.png', fullPage: true });
});

test('Santos has Santo do dia and Santos e obras linked to existing library books', async ({ page }) => {
  await page.goto(`${BASE}/santos`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await expect(page.getByRole('heading', { name: 'Santos', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Santo do dia/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Santos e obras/ })).toBeVisible();
  await expect(page.getByText('Obras ligadas ao santo de hoje')).toBeVisible();

  await page.getByRole('button', { name: /Santos e obras/ }).click();
  await expect(page.getByRole('button', { name: /Santo Agostinho de Hipona/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('PL 32-46')).toBeVisible();
  await page.getByRole('button', { name: /Santo Agostinho de Hipona/ }).click();
  await expect(page.getByText('Patrística Vol. 10', { exact: false })).toBeVisible();
  await expect(page.locator('a[href^="/biblioteca/"]').first()).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-santos-obras-producao.png', fullPage: true });
});
