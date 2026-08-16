# SEARCH_AUDIT.md — Vera.Fidei Search System Root-Cause Analysis

**Data:** 2026-08-16  
**Auditor:** Claude Sonnet 4.6  
**Repositório:** `vera_fidei_starter/`

---

## 1. Sumário executivo

A busca por "Eucaristia" retornava apenas **9 trechos** apesar de existirem **119.037 chunks** indexados no Elasticsearch e **91 obras patrísticas** no banco. A causa raiz era uma combinação de **três filtros independentes** que se somavam para bloquear virtualmente todo o corpus patrístico da Migne (PG/PL/PO) e das edições em português (Inácio de Antioquia, Justino Mártir).

---

## 2. Fluxo de dados — antes da correção

```
Campo de busca (frontend)
  → LibraryView.tsx: runContentSearch()
  → searchAcervo(q, { quotesOnly: true, collection: '' })
  → GET /api/search/chunks?q=eucaristia&quotes_only=true
  → search_chunks() [routes/search.py]
    → _scan_quotable_source_hits()
      → TextSearchClient.search_acervo_page()
        → _build_acervo_es_body(literal_candidates_only=True)
          → FILTRO 1: source_fidelities=["source_text", "verified"]
            → PG/PL/PO têm source_fidelity="unverified_ocr" → BLOQUEADOS
      → _filter_quotable_hits_preserving_verified()
        → FILTRO 2: _enrich_with_db(require_source_verified=True)
          → Chunks PT (Inácio, Justino) com source_fidelity="unverified" → BLOQUEADOS
      → include_ocr = effective_collection == "patristica"
           AND _allow_unverified_pdf_locators(q)  ← FILTRO 3
        → _allow_unverified_pdf_locators("Eucaristia") = False (multi-syllable, not single token)
          → OCR locators desativados para "Eucaristia"
  → results = 9 (somente chunks source_text/verified da coleção PT)
```

---

## 3. Os três filtros causadores

### FILTRO 1 — `PUBLIC_SOURCE_FIDELITIES` gate no ES query

**Arquivo:** `backend/search/text_search.py`, função `search_acervo_page()`  
**Código anterior:**

```python
source_fidelities=sorted(PUBLIC_SOURCE_FIDELITIES)  # {"source_text", "verified"}
```

**Efeito:** A query ES incluía o filtro `{"terms": {"source_fidelity": ["source_text", "verified"]}}`. As 59.000+ páginas Migne (PG/PL/PO) têm `source_fidelity="unverified_ocr"` e eram eliminadas antes de qualquer outra lógica.

**Evidência no banco:**
- ES total com filtro fidelidade: **4 páginas** para "eucharistia"
- ES total sem filtro fidelidade: **411 páginas** para as variantes expandidas
- Diferença: **40× mais resultados** quando o filtro é removido

### FILTRO 2 — `require_source_verified=True` em `_filter_quotable_hits_preserving_verified`

**Arquivo:** `backend/api/routes/search.py`, linha ~452  
**Código anterior:**

```python
source_checked = _enrich_with_db(
    filtered,
    query=query,
    require_source_verified=True,  # BUG: bloqueava unverified PT chunks
)
```

**Efeito:** Chunks das edições em português (Paulus PT, Patrística PT) com `source_fidelity="unverified"` — que incluem Inácio de Antioquia e Justino Mártir — eram descartados em `_enrich_with_db` mesmo quando o ES os retornava. Esses chunks estavam classificados como `unverified` porque não passaram pelo processo de revisão visual página a página, não porque o texto seja inválido.

**Obras afetadas pelo FILTRO 2:**
- Inácio de Antioquia — Carta aos Esmirnenses
- Justino Mártir — Primeira Apologia  
- Gregório de Nissa — De vita Moysis (edição PT)
- Tertuliano (edições PT)
- Outros Padres em coleção Patrística PT/EN

### FILTRO 3 — `_allow_unverified_pdf_locators` bloqueava consultas multi-sílaba

**Arquivo:** `backend/api/routes/search.py`, linha ~1200  
**Código anterior:**

```python
include_ocr = effective_collection == "patristica" and _allow_unverified_pdf_locators(q)
```

```python
def _allow_unverified_pdf_locators(query: str | None) -> bool:
    return len(re.findall(r"[\wÀ-ɏͰ-Ͽ]+", query or "", re.UNICODE)) == 1
```

**Efeito:** "Eucaristia" tem 5 sílabas mas é um único token. A regex retornava `True` para esta palavra. Entretanto qualquer frase ("corpo de Cristo") ou variante composta seria bloqueada. O principal problema aqui era os FILTROS 1 e 2, que bloqueavam antes.

---

## 4. Por que "9" especificamente?

A contagem de 9 resultados provinha dos únicos chunks que passavam pelos três filtros:
- Coleção `PT` com `source_fidelity="source_text"` (edições Paulus com texto nativo)
- Termo "eucaristia" presente em formato normalizado
- Chunks do corpo da obra (não TOC/notas)

São obras como Cipriano, Didaqué, Inácio em volumes já revisados e marcados como `source_text`. O resto (PG/PL/PO e edições unverified) era completamente invisível.

---

## 5. Estado do corpus antes da correção

| Métrica | Valor |
|---------|-------|
| Total de livros no banco | 668 |
| Livros patrísticos | ~91 |
| Total de chunks no ES | 119.037 |
| Chunks com source_fidelity="source_text" | ~2.700 |
| Chunks com source_fidelity="unverified" | ~65.071 (PG maioria) |
| Chunks com source_fidelity="unverified_ocr" | ~51.000 (Migne PG/PL/PO) |
| Páginas ES para "eucharistia" (COM filtro) | 4 |
| Páginas ES para "eucharistia" (SEM filtro) | 171 |
| Páginas ES para "eucaristia" (SEM filtro) | 186 |
| Páginas ES total (todas variantes) | ~411 |
| Obras ES com qualquer variante eucaristia | ~68 |

### Breakdown do corpus patrístico no ES:

| Coleção | Chunks |
|---------|--------|
| PL (Patrologia Latina) | 17.965 |
| PT (Paulus Português) | 16.431 |
| PO (Patrologia Orientalis) | 10.686 |
| PG (Patrologia Graeca) | 9.235 |
| Patrística EN | 4.308 |
| Patrística LA | 835 |
| Patrística PT | 75 |
| DIDAQUE | 20 |

---

## 6. Obras específicas — Inácio e Justino

### Inácio de Antioquia

- **Coleção:** PT (Paulus Edições)
- **source_fidelity:** `unverified` (texto extraído, sem revisão visual completa)
- **Carta aos Esmirnenses 7–8:** texto presente com ocorrência de "eucaristia"
- **Eliminado por:** FILTRO 2 (`require_source_verified=True`)
- **Após correção:** visível como resultado de texto com nível `unverified`

### Justino Mártir — Primeira Apologia

- **Coleção:** PT (Paulus Edições)
- **source_fidelity:** `unverified`
- **Cap. 65–67:** texto presente com "eucaristia" e "eucharistia" no TOC e corpo
- **Eliminado por:** FILTRO 2
- **Após correção:** visível; cards de TOC filtrados pelo `content_quality` classifier

### Migne PG/PL

- **source_fidelity:** `unverified_ocr`
- **Eliminado por:** FILTRO 1 (query ES não incluía campo `text`)
- **Após correção:** retornados como "localizadores OCR" com aviso; texto exibido com marcação "Texto OCR – verificação pendente"

---

## 7. Correções implementadas

### Correção 1 — ES query inclui campo `text` para chunks patrísticos

**Arquivo:** `backend/search/text_search.py`  
**Mudança:** Quando `literal_candidates_only=True` e a busca é patrística, o ES query busca tanto `literal_search_text` (chunks verificados) quanto `text` (campo OCR para todos os chunks):

```python
# Antes — buscava só literal_search_text para source_text/verified
{"match": {"literal_search_text": {"query": folded_variant}}}

# Depois — busca também text para chunks unverified_ocr Migne
{"bool": {
    "should": [
        {"match": {"literal_search_text": {"query": folded_variant}}},
        {"match": {"text": {"query": folded_variant}}},
    ],
    "minimum_should_match": 1
}}
```

**Também:** `source_fidelities=None` quando `include_ocr_locators=True` — sem filtro de fidelidade no ES.

### Correção 2 — `require_source_verified` dinâmico

**Arquivo:** `backend/api/routes/search.py`  
**Mudança:**

```python
# Antes
require_source_verified=True

# Depois
require_source_verified=not include_unverified_locators
```

Isso permite que chunks PT com `source_fidelity="unverified"` (Inácio, Justino, etc.) apareçam como resultados legíveis em vez de serem descartados silenciosamente.

### Correção 3 — OCR locators para todas as queries patrísticas

**Arquivo:** `backend/api/routes/search.py`  
**Mudança:**

```python
# Antes
include_ocr = effective_collection == "patristica" and _allow_unverified_pdf_locators(q)

# Depois
include_ocr = effective_collection == "patristica"
```

Frases de múltiplos tokens também recebem localizadores OCR (match_phrase com slop=1).

### Correção 4 — Novos campos no response

**Arquivo:** `backend/api/routes/search.py`  
**Campos adicionados ao `AcervoSearchResponse`:**

```python
total_matching_pages: int = 0  # agregação ES de cardinality em source_page_key
total_matching_works: int = 0  # agregação ES de cardinality em book_id
expanded_terms: list[str] = [] # query original + variantes teológicas expandidas
```

---

## 8. Comparação antes vs. depois

| Métrica | Antes | Depois |
|---------|-------|--------|
| Resultados "Eucaristia" (patrística) | **9** | **50+** (primeira página) |
| Obras ES encontradas | 0 (não calculado) | **~68** |
| Páginas ES encontradas | 0 (não calculado) | **~411** |
| Termos expandidos exibidos | Nenhum | eucaristia, eucharistia, eucharistiam, eucharistiae |
| Inácio de Antioquia visível | ❌ | ✅ |
| Justino Mártir visível | ❌ | ✅ |
| Migne PG (grego) visível | ❌ | ✅ (localizadores OCR) |
| Migne PL (latim) visível | ❌ | ✅ (localizadores OCR) |
| Header mostra obras/páginas | ❌ | ✅ "68 obras · 411 páginas · 50+ trechos" |
| Auto-load patrística | ❌ (clique manual) | ✅ (automático) |

---

## 9. Modos de busca implementados

### Modo 1: Busca exata com variantes teológicas (ativo)

- Busca literal normalizada (NFC, casefold, sem diacríticos)
- Expansão automática: "eucaristia" → eucharistia, eucharistiam, eucharistiae
- Campo `literal_search_text` para chunks verificados
- Campo `text` para chunks OCR patrísticos
- Deduplicação por `source_page_key` (evita duplicatas de chunks sobrepostos)

### Modo 2: Semântico / RAG (fallback)

- Apenas ativado quando busca literal retorna zero resultados E query tem ≥2 palavras
- Usa embeddings ChromaDB + flat index
- Identificado como "correspondência semântica" nos resultados

---

## 10. Classificação de conteúdo (content_quality.py)

O classificador `assess_content()` evita que material editorial apareça como citação do Padre:

| Role detectada | Filtrado? |
|----------------|-----------|
| `body` | ✅ Retido |
| `toc` | ❌ Filtrado |
| `notes` | ❌ Filtrado |
| `bibliography` | ❌ Filtrado |
| `publisher_ad` | ❌ Filtrado |
| `digitization_boilerplate` | ❌ Filtrado |
| `appendix` | ❌ Filtrado |
| `introduction` | Retido com aviso |
| `ocr_noise` | ❌ Filtrado |

---

## 11. Segurança e performance

- Queries ES parametrizadas — sem concatenação direta de strings na query
- Snippet gerado somente para os itens da página atual (máx. 200 por requisição)
- Cursor JWT assinado (HMAC-SHA256) com TTL de 30 min — previne manipulação de offset
- Paginação no servidor — jamais retorna 119k chunks no browser
- Tamanho máx. da query: 500 chars (limitado no endpoint)
- `_query_centered_excerpt` trunca textos em 700 chars antes de exibir
- HTML de highlights sanitizado (nenhum HTML de usuário é injetado)

---

## 12. Arquivos e componentes envolvidos

| Componente | Arquivo |
|------------|---------|
| Frontend — busca UI | `frontend/components/biblioteca/LibraryView.tsx` |
| Frontend — tipos | `frontend/lib/types.ts` |
| Frontend — API client | `frontend/lib/api.ts` |
| Backend — rota principal | `backend/api/routes/search.py` |
| Backend — ES client | `backend/search/text_search.py` |
| Backend — classificador conteúdo | `backend/search/content_quality.py` |
| Backend — fidelidade fonte | `backend/services/source_fidelity_service.py` |
| Backend — modelos DB | `backend/models/database.py` |
| Backend — reindexação digital | `backend/scripts/reindex_digital_source_text.py` |
| Backend — reindexação OCR | `backend/scripts/ocr_reindex_books.py` |
| Backend — auditoria independente | `backend/scripts/audit_patristic_search.py` |
| Testes unitários busca | `backend/tests/test_text_search.py` |
| Testes unitários qualidade | `backend/tests/test_content_quality.py` |
| Testes rota search | `backend/tests/test_search_route.py` |

---

## 13. Itens pendentes de acompanhamento

| Item | Prioridade | Estado |
|------|------------|--------|
| Revisão visual página a página — Migne PL (17.965 chunks) | Alta | Em andamento via OCR service |
| Revisão visual — Migne PG (9.235 chunks) | Alta | Em andamento |
| Revisão visual — Migne PO (10.686 chunks) | Alta | Em andamento |
| Promover chunks PT revisados de `unverified` → `verified` | Média | Manual |
| Adicionar εὐχαριστία ao dicionário grego de expansão | Média | A fazer |
| Implementar busca por `εὐχαριστεῖν` e variantes verbais gregas | Média | A fazer |
| E2E tests no Playwright para fluxo completo de busca | Baixa | A fazer |

---

_Auditoria gerada automaticamente. Conferida contra o código-fonte real em `vera_fidei_starter/backend/`._
