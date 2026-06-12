const { test, expect } = require('@playwright/test');

const BASE = process.env.VERA_BASE_URL || 'https://verafidei.oialfred.com';
const API_KEY = process.env.VERA_API_KEY || '';

const requestedBooks = [
  { id: 2000, fileId: 3964, title: 'Cerimonial dos Bispos', type: 'liturgia', section: null, collection: 'LIT-CER' },
  { id: 2001, fileId: 3965, title: 'Código de Direito Canônico - 27 de novembro de 1983', type: 'direito_canonico', section: null, collection: 'CDC' },
  { id: 2002, fileId: 3966, title: 'Casa da Iniciação Cristã: Eucaristia 2 - Jesus Cristo', type: 'catequese', section: null, collection: 'CATEQ-IC' },
  { id: 2003, fileId: 3967, title: 'Casa da Iniciação Cristã: Eucaristia 1 - A História da Salvação', type: 'catequese', section: null, collection: 'CATEQ-IC' },
  { id: 2004, fileId: 3968, title: 'Gramática de Grego Koiné', type: 'linguas_biblicas', section: null, collection: 'GRC-KOINE' },
  { id: 2005, fileId: 3969, title: 'Maria, Toda de Deus e Tão Humana', type: 'teologia', section: null, collection: 'TEO-MARI' },
  { id: 2006, fileId: 3970, title: 'Didaquê Bilíngue Grego-Português - Instrução dos Doze Apóstolos', type: null, section: 'patristica', tradition: 'portuguesa', collection: 'DIDAQUE', edition: 'Editora Familia', language: 'grc+pt' },
  { id: 2007, fileId: 3971, title: 'Psychomachia', type: 'literatura_crista', section: null, collection: 'LITCR-POESIA' },
  { id: 2008, fileId: 3972, title: 'Alfabeto Hebraico', type: 'linguas_biblicas', section: null, collection: 'HEB-ALFABETO' },
  { id: 2009, fileId: 3973, title: 'Demonographia', type: 'teologia', section: null, collection: 'TEO-DEMON' },
  { id: 2010, fileId: 3974, title: 'Curso de Latim', type: 'linguas_biblicas', section: null, collection: 'LAT' },
  { id: 2011, fileId: 3975, title: 'Missal Romano de Paulo V', type: 'liturgia', section: null, collection: 'LIT-MISSAL' },
  { id: 2012, fileId: 3976, title: 'Ritual de Exorcismos', type: 'liturgia', section: null, collection: 'LIT-EXOR' },
  { id: 2013, fileId: 3977, title: 'Patrística Vol. 12 — A Graça (I): O Espírito e a Letra; A Natureza e a Graça; A Graça de Cristo e o Pecado Original', type: null, section: 'patristica', collection: 'PT' },
  { id: 2014, fileId: 3978, title: 'Patrística Vol. 13 — A Graça (II): A Graça e a Liberdade; A Correção e a Graça; O Dom da Esperança', type: null, section: 'patristica', collection: 'PT' },
  { id: 2015, fileId: 3979, title: 'Patrística Vol. 14 — Homilia sobre Lucas 12; Homilias sobre o Espírito Santo', type: null, section: 'patristica', collection: 'PT' },
  { id: 2016, fileId: 3980, title: 'Patrística Vol. 15 — História Eclesiástica', type: null, section: 'patristica', collection: 'PT' },
  { id: 2017, fileId: 3981, title: 'Patrística Vol. 16 — Dos Bens do Matrimônio; A Santa Virgindade; Dos Bens da Viuvez', type: null, section: 'patristica', collection: 'PT' },
  { id: 2018, fileId: 3982, title: 'Patrística Vol. 17 — A Doutrina Cristã', type: null, section: 'patristica', collection: 'PT' },
  { id: 2019, fileId: 3983, title: 'Patrística Vol. 18 — Contra os Pagãos; A Encarnação do Verbo; Vida e Conduta de Santo Antão', type: null, section: 'patristica', collection: 'PT' },
  { id: 2020, fileId: 3984, title: 'Patrística Vol. 19 — A Verdadeira Religião; O Cuidado Devido aos Mortos', type: null, section: 'patristica', collection: 'PT' },
  { id: 2021, fileId: 3985, title: 'Patrística Vol. 20 — Contra Celso', type: null, section: 'patristica', collection: 'PT' },
  { id: 2022, fileId: 3986, title: 'Patrística Vol. 21 — Comentário ao Gênesis', type: null, section: 'patristica', collection: 'PT' },
  { id: 2023, fileId: 3987, title: 'Patrística Vol. 22 — Tratado sobre a Santíssima Trindade', type: null, section: 'patristica', collection: 'PT' },
  { id: 2024, fileId: 3988, title: 'Patrística Vol. 23 — Da Incompreensibilidade de Deus; Da Providência de Deus; Cartas a Olímpia', type: null, section: 'patristica', collection: 'PT' },
  { id: 2025, fileId: 3989, title: 'Patrística Vol. 24 — Contra os Acadêmicos; A Ordem; A Grandeza da Alma; O Mestre', type: null, section: 'patristica', collection: 'PT' },
  { id: 2026, fileId: 3990, title: 'Patrística Vol. 25 — Explicação das Cartas', type: null, section: 'patristica', collection: 'PT' },
  { id: 2027, fileId: 3991, title: 'Patrística Vol. 26 — Examerão', type: null, section: 'patristica', collection: 'PT' },
  { id: 2028, fileId: 3992, title: 'Patrística Vol. 27_1 — Comentário às Cartas de São Paulo I', type: null, section: 'patristica', collection: 'PT' },
  { id: 2029, fileId: 3993, title: 'Patrística Vol. 27_2 — Comentário às Cartas de São Paulo II', type: null, section: 'patristica', collection: 'PT' },
  { id: 2030, fileId: 3994, title: 'Patrística Vol. 27_3 — Comentário às Cartas de São Paulo III', type: null, section: 'patristica', collection: 'PT' },
  { id: 2031, fileId: 3995, title: 'Patrística Vol. 28 — Regra Pastoral', type: null, section: 'patristica', collection: 'PT' },
  { id: 2032, fileId: 3996, title: 'Patrística Vol. 29 — Gregório de Nissa', type: null, section: 'patristica', collection: 'PT' },
  { id: 2033, fileId: 3997, title: 'Patrística Vol. 30 — Tratado sobre os Princípios', type: null, section: 'patristica', collection: 'PT' },
  { id: 2034, fileId: 3998, title: 'Patrística Vol. 31 — Apologia contra os Livros de Rufino', type: null, section: 'patristica', collection: 'PT' },
  { id: 2035, fileId: 3999, title: 'Patrística Vol. 32 — A Fé e o Símbolo; A Disciplina Cristã; A Continência', type: null, section: 'patristica', collection: 'PT' },
  { id: 2036, fileId: 4000, title: 'Patrística Vol. 33 — Demonstração da Pregação Apostólica', type: null, section: 'patristica', collection: 'PT' },
  { id: 2037, fileId: 4001, title: 'Patrística Vol. 34 — Homilias sobre o Evangelho de Lucas', type: null, section: 'patristica', collection: 'PT' },
  { id: 2038, fileId: 4002, title: 'Patrística Vol. 35_1 — Obras Completas I', type: null, section: 'patristica', collection: 'PT' },
  { id: 2039, fileId: 4003, title: 'Patrística Vol. 36 — O Sermão da Montanha e Escritos sobre a Fé', type: null, section: 'patristica', collection: 'PT' },
  { id: 2040, fileId: 4004, title: 'Patrística Vol. 37 — A Trindade; Escritos Éticos; Cartas', type: null, section: 'patristica', collection: 'PT' },
  { id: 2041, fileId: 4005, title: 'Patrística Vol. 38 — Orígenes', type: null, section: 'patristica', collection: 'PT' },
  { id: 2042, fileId: 4006, title: 'Patrística Vol. 39 — A Mentira', type: null, section: 'patristica', collection: 'PT' },
  { id: 2043, fileId: 4007, title: 'Patrística Vol. 40 — A Natureza do Bem; O Castigo e Perdão dos Pecados; O Batismo das Crianças', type: null, section: 'patristica', collection: 'PT' },
  { id: 2044, fileId: 4008, title: 'Patrística Vol. 41 — A Simpliciano; Réplica à Carta de Parmeniano', type: null, section: 'patristica', collection: 'PT' },
  { id: 2045, fileId: 4009, title: 'Patrística Vol. 42 — Tratado sobre o Batismo', type: null, section: 'patristica', collection: 'PT' },
  { id: 2046, fileId: 4010, title: 'Patrística Vol. 43 — Retratações', type: null, section: 'patristica', collection: 'PT' },
  { id: 2047, fileId: 4011, title: 'Patrística Vol. 44 — Comentário ao Evangelho de Mateus', type: null, section: 'patristica', collection: 'PT' },
  { id: 2048, fileId: 4012, title: 'Patrística Vol. 45 — Sobre a Música', type: null, section: 'patristica', collection: 'PT' },
  { id: 2049, fileId: 4013, title: 'Patrística Vol. 46 — Apologia', type: null, section: 'patristica', collection: 'PT' },
  { id: 2050, fileId: 4014, title: 'Patrística Vol. 47_1 — Comentários a São João I', type: null, section: 'patristica', collection: 'PT' },
  { id: 2051, fileId: 4015, title: 'Patrística Vol. 47_2 — Comentários a São João II', type: null, section: 'patristica', collection: 'PT' },
  { id: 2052, fileId: 4016, title: 'Patrística Vol. 47_3 — Comentários a São João III', type: null, section: 'patristica', collection: 'PT' },
  { id: 2053, fileId: 4017, title: 'Patrística Vol. 52 — Registro Epistolar', type: null, section: 'patristica', collection: 'PT' },
  { id: 2054, fileId: 4018, title: 'Sobre a Vida de Moisés', type: null, section: 'patristica', collection: 'PT' },
];

test.describe.configure({ mode: 'serial' });
test.setTimeout(600_000);

test('all requested books are indexed with working public PDF byte ranges', async ({ request }) => {
  expect(API_KEY, 'VERA_API_KEY must be provided for API checks').not.toBe('');
  const api = await request.get(`${BASE}/api/books`, {
    headers: { 'X-API-Key': API_KEY },
    timeout: 120_000,
  });
  expect(api.ok(), `/api/books HTTP ${api.status()}`).toBeTruthy();
  const books = await api.json();
  const byId = new Map(books.map((book) => [book.id, book]));

  for (const expected of requestedBooks) {
    const book = byId.get(expected.id);
    expect(book, `book ${expected.id} missing`).toBeTruthy();
    expect(book.title, `book ${expected.id} title`).toBe(expected.title);
    expect(book.ingest_status, `book ${expected.id} ingest_status`).toBe('done');
    expect(book.chunk_count, `book ${expected.id} chunk_count`).toBeGreaterThan(0);
    expect(book.collection, `book ${expected.id} collection`).toBe(expected.collection);

    if (expected.section) {
      expect(book.library_section, `book ${expected.id} library_section`).toBe(expected.section);
      expect(book.patristic_tradition, `book ${expected.id} patristic_tradition`).toBe(expected.tradition || 'portuguesa');
      expect(book.edition_label, `book ${expected.id} edition_label`).toBe(expected.edition || 'Paulus');
      expect(book.language, `book ${expected.id} language`).toBe(expected.language || 'pt');
    } else {
      expect(book.document_type, `book ${expected.id} document_type`).toBe(expected.type);
    }

    const pdf = await request.get(`${BASE}/api/pdfs/${expected.fileId}?api_key=${encodeURIComponent(API_KEY)}`, {
      headers: { Range: 'bytes=0-63' },
      timeout: 60_000,
    });
    expect([200, 206], `PDF ${expected.fileId} HTTP ${pdf.status()}`).toContain(pdf.status());
    expect(pdf.headers()['content-type'], `PDF ${expected.fileId} content-type`).toContain('application/pdf');
    const body = await pdf.body();
    expect(body.subarray(0, 4).toString('ascii'), `PDF ${expected.fileId} signature`).toBe('%PDF');
  }
});

test('requested books are visible in the expected library tabs and open in the PDF viewer', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.goto(`${BASE}/biblioteca`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: 'Biblioteca Patrística' }).click();
  await page.getByRole('button', { name: 'em Português' }).click();
  await expect(page.getByRole('button', { name: /Paulus/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('button', { name: /Editora Família/ })).toBeVisible();
  await expect(page.getByText('Patrística Vol. 12', { exact: false })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Patrística Vol. 47_3', { exact: false })).toBeVisible();
  await expect(page.getByText('Sobre a Vida de Moisés', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Editora Família/ }).click();
  await expect(page.getByText('Didaquê Bilíngue Grego-Português - Instrução dos Doze Apóstolos', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-patristica-portugues-paulus.png', fullPage: true });

  await page.getByRole('button', { name: 'Patrística Grega' }).click();
  await expect(page.getByText('Didaquê Bilíngue Grego-Português - Instrução dos Doze Apóstolos', { exact: true })).toBeVisible();

  await page.goto(`${BASE}/biblioteca/2013`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Patrística Vol. 12 — A Graça (I): O Espírito e a Letra; A Natureza e a Graça; A Graça de Cristo e o Pecado Original' })).toBeVisible();
  await page.getByRole('link', { name: 'Ler PDF' }).click();
  await expect(page).toHaveURL(/\/visualizar\/3977/);
  await expect(page.locator('iframe[title="Visualizador de PDF"]')).toHaveAttribute('src', /\/api\/pdfs\/3977/);
  await page.screenshot({ path: 'test-artifacts/verafidei-patristica-viewer.png', fullPage: true });

  await page.goto(`${BASE}/biblioteca`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle');
  await page.getByRole('button', { name: 'Documentos da Igreja' }).click();
  await expect(page.getByRole('button', { name: 'Catequese' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Liturgia' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Direito Canônico' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Teologia' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Línguas Bíblicas' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Literatura Cristã' })).toBeVisible();

  await page.getByRole('button', { name: 'Catequese' }).click();
  await page.getByRole('button', { name: 'Iniciação Cristã' }).click();
  await expect(page.getByText('Casa da Iniciação Cristã: Eucaristia 2 - Jesus Cristo', { exact: true })).toBeVisible();
  await expect(page.getByText('Casa da Iniciação Cristã: Eucaristia 1 - A História da Salvação', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Cursos' }).click();
  await expect(page.getByText('Curso Elementar de Catequese I', { exact: true })).toBeVisible();
  await expect(page.getByText('Curso Elementar de Catequese II', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Liturgia' }).click();
  await page.getByRole('button', { name: 'Missais' }).click();
  await expect(page.getByText('Missal Romano de Paulo V', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Rituais' }).click();
  await expect(page.getByText('Ritual de Exorcismos', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Cerimoniais' }).click();
  await expect(page.getByText('Cerimonial dos Bispos', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Direito Canônico' }).click();
  await expect(page.getByText('Código de Direito Canônico - 27 de novembro de 1983', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Teologia' }).click();
  await page.getByRole('button', { name: 'Mariologia' }).click();
  await expect(page.getByText('Maria, Toda de Deus e Tão Humana', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Demonologia' }).click();
  await expect(page.getByText('Demonographia', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Línguas Bíblicas' }).click();
  await page.getByRole('button', { name: 'Grego' }).click();
  await expect(page.getByText('Gramática de Grego Koiné', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Hebraico' }).click();
  await expect(page.getByText('Alfabeto Hebraico', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Latim' }).click();
  await expect(page.getByText('Curso de Latim', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Literatura Cristã' }).click();
  await page.getByRole('button', { name: 'Poesia' }).click();
  await expect(page.getByText('Psychomachia', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-artifacts/verafidei-documentos-subabas.png', fullPage: true });

  await page.goto(`${BASE}/biblioteca/2009`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Demonographia' })).toBeVisible();
  await page.getByRole('link', { name: 'Ler PDF' }).click();
  await expect(page).toHaveURL(/\/visualizar\/3973/);
  await expect(page.locator('iframe[title="Visualizador de PDF"]')).toHaveAttribute('src', /\/api\/pdfs\/3973/);
  await page.screenshot({ path: 'test-artifacts/verafidei-demonographia-viewer.png', fullPage: true });

  expect(consoleErrors.filter((line) => !line.includes('favicon')).slice(0, 5)).toEqual([]);
});

test('mobile PDF.js viewer renders a requested PDF page canvas', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/visualizar/3973`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('link', { name: 'Abrir PDF' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('link', { name: 'Abrir PDF' }).click();
  await expect(page).toHaveURL(/\/viewer\/pdf/);
  const canvases = page.locator('canvas');
  await expect(canvases.first()).toBeVisible({ timeout: 120_000 });
  await expect(canvases).toHaveCount(2);
  await page.screenshot({ path: 'test-artifacts/verafidei-mobile-pdfjs-demonographia.png', fullPage: true });

  const relevantErrors = consoleErrors.filter((line) => (
    !line.includes('favicon') &&
    !line.includes('Failed to load resource: the server responded with a status of 404')
  ));
  expect(relevantErrors.slice(0, 5)).toEqual([]);
});

test('Vera Fidei and sibling domains stay online', async ({ request }) => {
  for (const url of [
    'https://verafidei.oialfred.com/biblioteca',
    'https://oialfredtech.com',
    'https://easiercise.oialfredtech.com',
  ]) {
    const response = await request.get(url, { timeout: 60_000 });
    expect(response.status(), `${url} status`).toBe(200);
  }
});
