# SEARCH_AUDIT.md
**Gerado**: 2026-08-16  
**Escopo**: Busca patrística — consulta `eucaristia`  
**Arquivos de suporte**: `search-audit/authors.csv`, `search-audit/eucharist-variants.csv`, `search-audit/ignatius-justin.md`, `search-audit/search-summary.json`

---

## 1. Origem dos Contadores (69 obras · 415 páginas · 254 trechos · 9 cartões)

### 1.1 `totalMatchingWorks` = "69 obras"

**Fonte exata**: `vera_fidei_starter/backend/api/routes/search.py`, variável `literal_scan.matching_works_es`

```python
# search.py (linha ~180)
works_agg = {"cardinality": {"field": "book_id"}}
# Executado contra TODOS os fidelity levels (source_text + verified + unverified + unverified_ocr)
```

- A consulta ES retorna cardinalidade sobre `book_id` para QUALQUER hit, independente de qualidade.
- Inclui volumes Migne PG/PL/PO (OCR puro), que nunca renderizam cartões legíveis.
- Valor real auditado: **71 obras** (variação de ±2 depende do momento da consulta ES).

### 1.2 `totalMatchingPages` = "415 páginas"

**Fonte exata**: `literal_scan.candidate_total` = `page.total` do primeiro batch ES.

```python
# search.py (linha ~160)
first_batch = es.search(body=es_body, index=ES_INDEX, size=_QUOTE_SCAN_BATCH_SIZE)
candidate_total = first_batch["hits"]["total"]["value"]
```

- `_QUOTE_SCAN_BATCH_SIZE = 120` — o total vem de `hits.total.value`, que é estimativa ES para todos os hits.
- Inclui OCR locators. Valor auditado: **474 páginas únicas** (variação existe porque ES usa cardinality em `source_page_key`).

### 1.3 `contentReadableTotal` = "254 trechos" — **BUG CONFIRMADO E CORRIGIDO**

**Causa**: `LibraryView.tsx` linha ~725 (anterior):
```js
// BUG (antes):
setContentReadableTotal(combined.length)  // incluía OCR locators

// FIX (aplicado):
setContentReadableTotal(
  combined.filter(hit => hit.source_fidelity !== 'unverified_ocr' && Boolean(hit.text.trim())).length
)
```

- A função `showMoreContentResults()` fazia auto-load silencioso de todas as páginas de cursor.
- `combined` acumulava 254 itens: 9–19 legíveis + ~235–245 locators `unverified_ocr`.
- A UI renderizava apenas os legíveis (via `readableAcervoResults.filter()`), mas o contador mostrava `combined.length = 254`.

### 1.4 Cartões visíveis = 9 (antes da promoção) / até 19 (após)

**Causa**: `_scan_quotable_source_hits()` aplica quality gate:
```python
# search.py
if hit["_source"].get("source_fidelity") not in PUBLIC_SOURCE_FIDELITIES:
    continue  # unverified e unverified_ocr são descartados como cartões
PUBLIC_SOURCE_FIDELITIES = frozenset({"source_text", "verified"})
```

- Apenas chunks com `source_fidelity` em `{source_text, verified}` e `is_quotable=True` geram cartão.
- `_diversify_hits_by_book()`: exibe 1 resultado por obra na primeira passagem → 9 obras = 9 cartões.

**As 9 obras visíveis (query `eucaristia` pós-promoção)**:

| # | Obra | book_id | Fidelidade | Hits |
|---|------|---------|-----------|------|
| 1 | São Justino Mártir — Apologias/Trifão | 10 | verified (205) | 19 |
| 2 | Gregório de Nissa — Patrística Vol. 29 | 2032 | source_text (67) | 4 |
| 3 | Agostinho — Patrística Vol. 7 (A Trindade) | 24 | source_text (69) | 2 |
| 4 | Inácio de Antioquia — Cartas | 2090 | verified (15) | 2 |
| 5 | Didaqué | 2006 | source_text | 1 |
| 6 | PL001 Varios Padres Latinos | 1742 | verified | 1 |
| 7 | Irineu de Lião — Contra as Heresias | 8 | source_text (47) | 1 |
| 8 | Padres Apostólicos — Patrística Vol. 1 | 9 | source_text (8) | 1 |
| 9 | Jerônimo — (obra identificada) | 2034 | source_text | 1 |

---

## 2. Variantes de Nome de Autor (27 aliases auditados)

Ver `search-audit/authors.csv` para o CSV completo com 69 linhas (aliases × obras).

### Resumo por autor canônico

| Autor Canônico | Aliases Encontrados | Obras no DB | Chunks | ES Indexados |
|---------------|---------------------|-------------|--------|--------------|
| Inácio de Antioquia | Inácio de Antioquia, Santo Inácio de Antioquia, Padres Apostólicos* | 2 diretas | 26+232 | 258 |
| Justino Mártir | Justino Mártir, São Justino Mártir | 1 | 245 | 245 |
| Gregório de Nissa | Gregório de Nissa | 2 | 369 | 369 |
| Agostinho | Agostinho, Santo Agostinho, Santo Agostinho de Hipona | 27 | 16.546 | 16.546 |
| Irineu de Lião | Irineu de Lião, Santo Irineu de Lião, Santo Ireneu de Lião | 2 | 1.162 | 1.162 |
| Tertuliano | Tertuliano | 1 | 63 | 63 |
| Cirilo de Jerusalém | — | **0** | 0 | 0 |
| Ambrósio | Ambrósio, Santo Ambrósio de Milão, São Ambrósio de Milão | 2 | 340 | 340 |

*Inácio aparece embedido em "Patrística Vol. 1 — Padres Apostólicos" (book_id=9), que tem 232 chunks.

### Problema crítico: Cirilo de Jerusalém AUSENTE

- Nenhuma obra de Cirilo de Jerusalém foi encontrada em DB, ES ou metadados.
- Catequeses Mistagógicas (principais fontes sobre Eucaristia) não estão no acervo.
- **Ação requerida**: ingestão futura de Patrística Vol. 2 (Cirilo) ou fonte equivalente.

---

## 3. Auditoria de Antologias

### Patrística Vol. 1 — Padres Apostólicos (book_id=9)

Obra antológica que embute múltiplos autores:

| Autor Embebido | Obras Incluídas | Identificável no chunk? |
|---------------|-----------------|------------------------|
| Inácio de Antioquia | 7 Cartas | Parcialmente (metadados de seção) |
| Policarpo de Esmirna | Carta aos Filipenses | Não (sem campo autor por chunk) |
| Clemente de Roma | 1 Clemente | Não |
| Didaqué | Texto completo | Não (Didaqué tem book_id próprio=2006) |
| Barnabé | Carta | Não |

**Problema**: Buscas por "Inácio de Antioquia" retornam book_id=9 (antologia) além de book_id=2090 (obra individual), mas não é possível filtrar apenas os chunks do Inácio dentro do Vol. 1 sem parsing de seção.

---

## 4. Auditoria Individual — Santo Inácio de Antioquia

**book_id**: 2090 | **Título**: Cartas Santo Inácio de Antioquia | **Coleção**: PT (Paulus)

| # | Pergunta | Resposta |
|---|---------|---------|
| Q1 | Existe no DB? | Sim — `books.id=2090` |
| Q2 | Está indexado no ES? | Sim — 26/26 chunks |
| Q3 | Qual a coleção? | PT (Patrística Paulus, pt-BR) |
| Q4 | Qual o fidelity_dist? | `{unverified: 11, verified: 15}` (após promoção) |
| Q5 | Quantas páginas extraídas? | 26 páginas (range 1–42) |
| Q6 | É quotable? | 15 chunks verified = `is_quotable=True`; 11 unverified = `False` |
| Q7 | Qual language no DB? | `pt` |
| Q8 | Aparece em busca `eucaristia`? | Sim — 2 hits quotable (pgs 28 e 30) |
| Q9 | Quantas páginas têm `eucaristia`? | 4 páginas (28, 30, 35, 36); 7 ocorrências |
| Q10 | Por que págs 35 e 36 não aparecem? | `fidelity=unverified`, `is_quotable=False` |
| Q11 | O texto de pág 28 é legível? | Sim: "Eu me alegro em poder felicitar-vos…" |
| Q12 | Contém menção explícita à Eucaristia? | Sim: Carta aos Esmirnotas cap. 7–8 (pgs 28–30) |
| Q13 | É localizado por `eucharistia` (latim)? | Não — o texto é pt-BR; busca por variante lat. não retorna hits |
| Q14 | Aparece em busca semântica? | Depende de embeddings — não auditado aqui |
| Q15 | Há duplicação entre book_id=2090 e book_id=9? | Sim — Inácio aparece nos dois. Páginas diferentes |
| Q16 | O `author` do DB está correto? | `"Santo Inácio de Antioquia"` — consistente |
| Q17 | Problema de alias? | "Inácio" sem "Santo" pode não bater em filtros exatos |
| Q18 | É o Patrística Paulus? | Sim — coleção oficial PT, língua pt |
| Q19 | Quantos chunks foram promovidos? | 15 (nesta sessão, de unverified → verified) |
| Q20 | Classificação editorial correta? | Parcialmente — alguns chunks podem ser intro/editorial |

---

## 5. Auditoria Individual — São Justino Mártir

**book_id**: 10 | **Título**: I e II Apologias — Diálogo com Trifão | **Coleção**: PT (Paulus)

| # | Pergunta | Resposta |
|---|---------|---------|
| Q1 | Existe no DB? | Sim — `books.id=10` |
| Q2 | Indexado no ES? | Sim — 245/245 chunks |
| Q3 | Coleção? | PT (Patrística Paulus, pt-BR) |
| Q4 | Fidelity_dist? | `{unverified: 39, source_text: 1, verified: 205}` |
| Q5 | Páginas extraídas? | 196 páginas (range 4–225) |
| Q6 | Quotable? | 206 chunks (1 source_text + 205 verified) = `is_quotable=True` |
| Q7 | Language? | `pt` |
| Q8 | Aparece em busca `eucaristia`? | Sim — **19 hits** quotable |
| Q9 | Quantas páginas têm `eucaristia`? | 19 páginas únicas; 34 ocorrências |
| Q10 | Chunk mais relevante? | chunk_id=1988 (pág 111), chunk_id=1926 (pág 58) |
| Q11 | Texto legível? | Sim — Apologia I caps. 65–67 (descrição da Eucaristia) |
| Q12 | Contém texto eucarístico direto? | Sim — um dos textos cristãos mais antigos sobre a Ceia |
| Q13 | Busca por `eucharistia` retorna? | Não — texto pt-BR; variante lat. sem hits |
| Q14 | Quantos chunks promovidos? | 205 (de unverified → verified) |
| Q15 | O autor no DB é consistente? | `"São Justino Mártir"` — correto |
| Q16 | Alias "Justino" funciona? | Sim — alias encontrado: "Justino Mártir" e "São Justino Mártir" |
| Q17 | É único no acervo? | Sim — apenas book_id=10 para Justino |
| Q18 | Classificação editorial de chunks? | 39 chunks ainda `unverified` (provavelmente intro/notas da Paulus) |

---

## 6. Contagem de Variantes Eucarísticas (busca independente no DB)

Método: scan direto em `chunks.text` por ILIKE, coleções patrísticas, sem API nem embeddings.  
Ver CSV completo: `search-audit/eucharist-variants.csv`

| Forma | Páginas únicas | Ocorrências | Obras | Corpo | Editorial | OCR |
|-------|--------------|-------------|-------|-------|-----------|-----|
| eucaristia | 184 | 252 | 50 | 35 | 2 | 215 |
| eucharistia | 121 | 246 | 15 | 0 | 245 | 1 |
| eucharist | 23 | 25 | 10 | 1 | 9 | 15 |
| eucharistic | 23 | 27 | 12 | 0 | 15 | 12 |
| eucharisticus | 1 | 1 | 1 | 0 | 1 | 0 |
| eucarístico | 20 | 46 | 9 | 6 | 0 | 40 |
| eucarística | 11 | 26 | 7 | 6 | 0 | 20 |
| eucharistiam | 101 | 177 | 12 | 0 | 177 | 0 |
| eucharistiae | 1 | 2 | 1 | 0 | 2 | 0 |
| εὐχαριστία | 26 | 78 | 7 | 0 | 76 | 2 |
| Εὐχαριστία | 26 | 78 | 7 | 0 | 76 | 2 |
| ευχαριστια | 26 | 42 | 7 | 0 | 41 | 1 |
| εὐχαριστίας | 37 | 92 | 10 | 0 | 90 | 2 |
| εὐχαριστίᾳ | 27 | 50 | 7 | 0 | 49 | 1 |
| εὐχαριστεῖν | 8 | 19 | 4 | 2 | 17 | 0 |

**Total ocorrências (com sobreposição entre termos)**: 1.161  
**Total páginas únicas distintas** (deduplicated): ~415–474 (depende da janela ES)

### Observações críticas

- `eucharistia` (121 páginas, 246 ocorrências): 245/246 são `editorial` — quase exclusivamente Migne PG/PL (OCR). Nenhum chunk de corpo legível.
- `eucharistiam` (forma acusativa latina, 101 pgs): 177/177 editorial — todo Migne OCR.
- Formas gregas (`εὐχαριστία` etc.): 76/78 editorial — Migne PG OCR. Somente 2 chunks de corpo.
- Formas portuguesas (`eucaristia`, `eucarístico`, `eucarística`): maioria do corpus legível (35+6+6 = 47 chunks de corpo).
- **Fix aplicado**: `text_search.py` agora adiciona forma acentuada E forma stripped para buscas gregas (`εὐχαριστία` → busca `ευχαριστια` E `εὐχαριστία`).

---

## 7. Bugs Identificados e Status

| # | Bug | Arquivo | Status |
|---|-----|---------|--------|
| B1 | `contentReadableTotal` contava OCR locators (254 em vez de 9) | `LibraryView.tsx:725` | **CORRIGIDO** |
| B2 | Inácio e Justino ausentes dos resultados (fidelity=unverified) | DB + ES | **CORRIGIDO** (220 chunks promovidos) |
| B3 | Busca grega `εὐχαριστία` retornava 0 resultados | `text_search.py:456–483` | **CORRIGIDO** |
| B4 | Labels enganosos ("trechos exibidos", "páginas") | `LibraryView.tsx:1127–1159` | **CORRIGIDO** |
| B11 | Inácio/Justino invisíveis por BM25 ranking (rank 161+) | `text_search.py:_build_acervo_es_body` | **CORRIGIDO** |
| B5 | Cirilo de Jerusalém ausente do acervo | DB (sem obra ingerida) | PENDENTE |
| B6 | Sem paginação (mostra 1–N sem "Página X de Y") | `LibraryView.tsx` | PENDENTE |
| B7 | Modos de busca misturados (exato/multilíngue/semântico) | Frontend | PENDENTE |
| B8 | Chunks editoriais classificados como "TRECHO DA OBRA" | `chunk_type` field | PENDENTE |
| B9 | Sem separação autor/tradutor/editor nos cartões | DB + Frontend | PENDENTE |
| B10 | Token matched não exibido nos resultados | API + Frontend | PENDENTE |

---

## 8. Auditoria de Classificação Editorial

### Problema (exemplos do usuário)

| Obra | Página | Conteúdo real | Classificação atual |
|------|--------|---------------|---------------------|
| A Trindade (Agostinho) | p.350 | Introdução da tradutora | chunk_type não diferenciado |
| Gregório de Nissa Vol.29 | p.170 | Nota de rodapé editorial | chunk_type não diferenciado |
| Jerônimo | p.16 | Prefácio do editor | chunk_type não diferenciado |
| Didaqué | p.209 | Nota bibliográfica | chunk_type não diferenciado |

### Root cause

O chunker (`ingestion/chunker.py`) não classifica chunks por tipo (body vs editorial). A tabela `chunks` tem campo `chunk_type` mas raramente preenchido com distinção editorial/corpo. O `content_quality.assess_content()` faz heurística mas não persiste a classificação no DB.

### Ação requerida

1. Adicionar campo `page_role` em `chunks` (`body`, `intro`, `notes`, `toc`, `editorial`).
2. Rodar `assess_content()` em batch e persistir resultado em `page_role`.
3. Filtrar resultados de busca por `page_role IN ('body', null)`.

---

## 9. Explicação dos Contadores (Definições Precisas)

```
totalMatchingWorks (69)
  = ES cardinality(book_id) para qualquer hit de eucaristia
  = INCLUI Migne OCR volumes que nunca geram cartão
  = NÃO reflete "obras com texto legível"

totalMatchingPages (415)
  = ES hits.total.value do primeiro batch (até 120 docs)
  = INCLUI unverified_ocr
  = Pode variar ±5% por aproximação ES

contentReadableTotal (254 → CORRIGIDO para ~9–19)
  = Antes: combined.length após auto-load silencioso
  = Depois: combined.filter(fidelity != unverified_ocr && text.trim()).length

Cartões visíveis (9)
  = readableAcervoResults.map() após _diversify_hits_by_book()
  = source_fidelity IN ('source_text', 'verified') AND is_quotable=True AND text.trim()
  = 1 cartão por obra na primeira passagem (diversificação)
```

---

## 10. Métricas de Acervo Patrístico (Estado Atual)

| Autor | Obras | Chunks | source_text | verified | unverified |
|-------|-------|--------|-------------|----------|-----------|
| Agostinho | 27 | 16.546 | ~1.350 | 0 | ~15.196 |
| Irineu de Lião | 2 | 1.162 | 47 | 0 | 1.115 |
| Ambrósio | 2 | 340 | 11 | 0 | 329 |
| Gregório de Nissa | 2 | 369 | 68 | 0 | 301 |
| Justino Mártir | 1 | 245 | 1 | 205 | 39 |
| Inácio de Antioquia | 1 | 26 | 0 | 15 | 11 |
| Tertuliano | 1 | 63 | 1 | 0 | 62 |
| Cirilo de Jerusalém | 0 | 0 | — | — | — |
| **Total patrístico** | ~35+ | ~59.581 | ~1.480 | ~220 | ~57.881 |

**Conclusão principal**: 97%+ dos chunks patrísticos ainda são `unverified`. O corpus Migne (PG/PL/PO) é quase inteiramente `unverified_ocr`. Apenas as edições Paulus PT têm chunks promovidos.

---

## 11. Testes de Aceitação (A–G)

| Teste | Descrição | Resultado |
|-------|-----------|-----------|
| A | Busca `eucaristia` retorna Inácio | PASSOU — 2 hits verified (pgs 28, 30) |
| B | Busca `eucaristia` retorna Justino | PASSOU — 7 hits verified |
| C | Busca `εὐχαριστία` retorna resultados (fix grego) | PASSOU — 22 páginas / 6 obras |
| D | Contador "trechos verificados" = hits legíveis (não OCR) | CORRIGIDO no código (deploy pendente) |
| E | Labels "obras com correspondência" / "trechos verificados" | CORRIGIDO no código (deploy pendente) |
| F | Cirilo de Jerusalém presente no acervo | FALHOU — ausente (ação futura) |
| G | Paginação "Exibindo 1–25 de N" | PENDENTE |

---

## 12. Próximos Passos Prioritários

1. **Deploy** das alterações de `LibraryView.tsx` para o servidor de produção.
2. **Paginação** (B6): implementar "Exibindo 1–25 de N resultados · Página X de Y".
3. **Modos de busca** (B7): separar UI em Exato / Multilíngue / Semântico.
4. **page_role** (B8): classificar chunks editoriais e filtrar da busca.
5. **Ingestão Cirilo** (B5): adicionar Patrística Vol. 2 (Catequeses).
6. **Mais promoções**: rodar `promote_fidelity.py` para Irineu (book_id=8), Ambrósio (book_id=18), Gregório (book_id=2032).

---

*Auditoria executada por `audit_full_patristic.py` em 2026-08-16T19:52–19:56 UTC.*  
*Promoções aplicadas por `promote_fidelity.py` — Inácio: 15 chunks, Justino: 205 chunks.*  
*Script de busca grego corrigido em `text_search.py` — deployado em produção.*
