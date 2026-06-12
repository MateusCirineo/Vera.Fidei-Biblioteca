const { test, expect } = require('@playwright/test');

const BASE = process.env.VERA_BASE_URL || 'https://verafidei.oialfred.com';
const API_KEY = process.env.VERA_API_KEY || '';

const citationCases = [
  {
    name: 'Clemente real',
    quote: 'Cristo está entre os humildes, e não entre aqueles que se sobrepõem ao seu rebanho.',
    attributed_to: 'São Clemente de Roma',
    language: 'Português',
    expected: ['CONFIRMADA_EXATA', 'CORRESPONDENCIA_FORTE'],
  },
  {
    name: 'Irineu real',
    quote: 'Lêem coisas que não foram escritas e, como se costuma dizer, trançando cordas com areia.',
    attributed_to: 'Santo Irineu de Lião',
    language: 'Português',
    expected: ['CONFIRMADA_EXATA', 'CORRESPONDENCIA_FORTE'],
  },
  {
    name: 'Justino real',
    quote: 'não só os lemos intrepidamente, mas também, como vedes, nós vô-los oferecemos, para que os examineis',
    attributed_to: 'São Justino Mártir',
    language: 'Português',
    expected: ['CONFIRMADA_EXATA', 'CORRESPONDENCIA_FORTE'],
  },
  {
    name: 'Lumen Fidei real',
    quote: 'A fé nasce no encontro com o Deus vivo, que nos chama e revela o seu amor.',
    attributed_to: 'Papa Francisco',
    language: 'Português',
    expected: ['CONFIRMADA_EXATA', 'CORRESPONDENCIA_FORTE'],
  },
  {
    name: 'Moderna falsa',
    quote: 'Cada comunidade participa ativamente na construção viva da tradição por meio de releituras paradigmáticas.',
    attributed_to: 'Santo Irineu de Lião',
    language: 'Português',
    expected: ['NAO_ENCONTRADA'],
  },
];

test.describe.configure({ mode: 'serial' });
test.setTimeout(600_000);

test('public routes and library PDF flow', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/apresentacao$/);
  await expect(page.getByRole('heading', { name: 'Vera.Fidei', exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-apresentacao.png', fullPage: true });

  await page.goto(`${BASE}/biblioteca`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: 'Biblioteca Patrística' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Obras dos Padres' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Documentos da Igreja' })).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-biblioteca.png', fullPage: true });

  await page.goto(`${BASE}/biblioteca/9`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Patrística Vol. 1 — Padres Apostólicos' })).toBeVisible();
  await expect(page.getByText('Arquivos / Edições')).toBeVisible();
  const readPdf = page.getByRole('link', { name: 'Ler PDF' });
  await expect(readPdf).toHaveCount(1);
  await readPdf.click();
  await expect(page).toHaveURL(/\/visualizar\/6/);
  const frame = page.locator('iframe[title="Visualizador de PDF"]');
  await expect(frame).toBeVisible({ timeout: 30_000 });
  await expect(frame).toHaveAttribute('src', /\/api\/pdfs\/6/);
  await page.screenshot({ path: 'test-artifacts/verafidei-pdf-viewer.png', fullPage: true });

  expect(consoleErrors.filter((line) => !line.includes('favicon')).slice(0, 5)).toEqual([]);
});

test('citation verifier UI handles real and false citations', async ({ page }) => {
  await page.goto(`${BASE}/verificador`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('heading', { name: 'Verificador' })).toBeVisible();

  async function submitCitation(testCase, expectedText) {
    const quote = page.locator('#quote');
    const attributed = page.locator('#attributed');
    const language = page.locator('#language');
    const submit = page.getByRole('button', { name: 'Verificar citação' });
    await expect(quote).toBeEditable();
    await quote.fill(testCase.quote);
    await attributed.fill(testCase.attributed_to);
    await language.fill(testCase.language);
    await expect(quote).toHaveValue(testCase.quote);
    await expect(attributed).toHaveValue(testCase.attributed_to);
    await expect(submit).toBeEnabled({ timeout: 10_000 });
    await submit.click();
    await expect(page.getByText(expectedText, { exact: false })).toBeVisible({ timeout: 120_000 });
  }

  await submitCitation(citationCases[0], 'Confirmada');
  await expect(page.getByText('São Clemente de Roma', { exact: false })).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-citation-confirmed.png', fullPage: true });

  await submitCitation(citationCases[4], 'Não encontrada');
  await page.screenshot({ path: 'test-artifacts/verafidei-citation-not-found.png', fullPage: true });
});

test('citation API and PDF byte-range checks through Playwright request', async ({ request }) => {
  expect(API_KEY, 'VERA_API_KEY must be provided for API checks').not.toBe('');

  for (const testCase of citationCases) {
    const response = await request.post(`${BASE}/api/citations/verify-citation`, {
      headers: { 'X-API-Key': API_KEY },
      data: {
        quote: testCase.quote,
        attributed_to: testCase.attributed_to,
        language: testCase.language,
      },
      timeout: 120_000,
    });
    expect(response.ok(), `${testCase.name} HTTP ${response.status()}`).toBeTruthy();
    const payload = await response.json();
    expect(testCase.expected, `${testCase.name} status ${payload.status_code}`).toContain(payload.status_code);
  }

  for (const fileId of [6, 5, 7, 399, 28]) {
    const response = await request.get(`${BASE}/api/pdfs/${fileId}?api_key=${encodeURIComponent(API_KEY)}`, {
      headers: { Range: 'bytes=0-63' },
      timeout: 60_000,
    });
    expect(response.status(), `PDF ${fileId}`).toBe(206);
    expect(response.headers()['content-type']).toContain('application/pdf');
    expect(response.headers()['content-range']).toMatch(/^bytes 0-63\//);
  }
});
