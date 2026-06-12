const { test, expect } = require('@playwright/test');

const BASE = process.env.VERA_BASE_URL || 'https://verafidei.oialfred.com';
const API_KEY = process.env.VERA_API_KEY || '';

test.setTimeout(180_000);

test('new Vera.Fidei books are categorized and PDFs open', async ({ page, request }) => {
  const api = await request.get(`${BASE}/api/books`, {
    headers: { 'X-API-Key': API_KEY },
    timeout: 60_000,
  });
  expect(api.ok()).toBeTruthy();
  const books = await api.json();
  const byId = new Map(books.filter((book) => book.id >= 1989 && book.id <= 1999).map((book) => [book.id, book]));

  expect(byId.get(1989).document_type).toBe('liturgia');
  expect(byId.get(1990).document_type).toBe('liturgia');
  expect(byId.get(1991).document_type).toBe('liturgia');
  expect(byId.get(1992).document_type).toBe('doutrina_social');
  for (const id of [1993, 1996, 1997, 1998, 1999]) {
    expect(byId.get(id).document_type).toBe('catecismo');
    expect(byId.get(id).ingest_status).toBe('done');
    expect(byId.get(id).chunk_count).toBeGreaterThan(0);
  }
  for (const id of [1994, 1995]) {
    expect(byId.get(id).document_type).toBe('catequese');
    expect(byId.get(id).ingest_status).toBe('done');
    expect(byId.get(id).chunk_count).toBeGreaterThan(0);
  }

  await page.goto(`${BASE}/biblioteca`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Documentos da Igreja' }).click();

  await expect(page.getByRole('button', { name: /Catecismo/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Catequese/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Liturgia/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Doutrina Social/ })).toBeVisible();

  await page.getByRole('button', { name: /Liturgia/ }).click();
  await expect(page.getByText('Missal Romano (Brasil) 2023')).toBeVisible();
  await expect(page.getByText('Livro de Celebração de Bênçãos')).toBeVisible();
  await expect(page.getByText('Manual das Indulgências - Normas e Concessões')).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-liturgia-books.png', fullPage: true });

  await page.getByRole('button', { name: /Doutrina Social/ }).click();
  await expect(page.getByText('Compêndio da Doutrina Social da Igreja')).toBeVisible();

  await page.getByRole('button', { name: /Catecismo/ }).click();
  await expect(page.getByText('Catecismo São Pio X')).toBeVisible();
  await expect(page.getByText('Catecismo Romano São Pio V')).toBeVisible();
  await expect(page.locator('a[href="/biblioteca/1999"]')).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-catecismo-books.png', fullPage: true });

  await page.getByRole('button', { name: /Catequese/ }).click();
  await expect(page.getByText('Curso Elementar de Catequese I')).toBeVisible();
  await expect(page.getByText('Curso Elementar de Catequese II')).toBeVisible();

  await page.goto(`${BASE}/biblioteca/1990`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Missal Romano (Brasil) 2023' })).toBeVisible();
  await page.getByRole('link', { name: 'Ler PDF' }).click();
  await expect(page).toHaveURL(/\/visualizar\/3954/);
  await expect(page.locator('iframe[title="Visualizador de PDF"]')).toHaveAttribute('src', /\/api\/pdfs\/3954/);
  await page.screenshot({ path: 'test-artifacts/verafidei-missal-viewer.png', fullPage: true });
});
