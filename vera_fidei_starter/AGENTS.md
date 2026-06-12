# AGENTS.md — Sistema de Agentes do Vera.Fidei

Todos os agentes estão em `backend/app/agents/`. A classe base está em `base.py`.

---

## Estrutura base

**`base.py`** define três entidades centrais:

| Classe | Papel |
|---|---|
| `AgentResult` | Encapsula a saída de cada agente: `agent_name`, `status`, `data`, `notes`, `warnings` |
| `PipelineContext` | Estado compartilhado entre agentes: `user_task`, `execution_id`, `mission`, `findings`, `reports`, `handoffs`, `history` |
| `BaseAgent` | Classe abstrata com método `run(ctx: PipelineContext) -> AgentResult` |

O método `ctx.handoff(source, target, payload)` registra transferência de contexto com rastreabilidade completa por `execution_id`.

---

## Fluxos principais

O sistema possui três fluxos distintos, detectados automaticamente pelo Orchestrator:

| Fluxo | Palavras-chave detectadas | Agentes envolvidos |
|---|---|---|
| **Verificação de Citações** | cita, atribu, disse, escreveu | 10 agentes |
| **Ingestão de PDFs** | pdf, upload, ingest, importar, patrologia, pg, pl, concilio | 4 agentes |
| **Tarefa Geral** | qualquer outro input | 2 agentes |

---

## Os 13 Agentes

---

### 1. Orchestrator
**Arquivo:** `orchestrator.py` | **Nome:** `orchestrator`

Ponto de entrada de qualquer pipeline. Analisa a tarefa do usuário, determina o fluxo correto e cria a missão estruturada com: objetivo, escopo, agentes, ordem de execução, dependências, riscos e critério de conclusão. Também inicializa o `progress` com os campos `completed`, `in_progress`, `pending` e `next_steps`.

---

### 2. Planner
**Arquivo:** `planner.py` | **Nome:** `planner`

Recebe a missão criada pelo Orchestrator e elabora o plano operacional detalhado. Define subtarefas concretas, ordem de execução, dependências entre etapas, riscos específicos e a definição de "done". Sempre o segundo agente a rodar em qualquer fluxo.

---

### 3. Search Agent
**Arquivo:** `search_agent.py` | **Nome:** `search_agent`

Realiza busca híbrida no corpus:
- **Elasticsearch** — busca textual exata (BM25)
- **ChromaDB** — busca semântica vetorial (bge-m3)

Extrai citação e autor da tarefa do usuário (suporta múltiplos formatos de aspas e atribuição). Combina os resultados em score único: **65% textual + 35% semântico**. Retorna os top-5 candidatos ordenados. Rastreia a estratégia de match: `user_query`, `fallback_quote` ou `semantic`.

---

### 4. Source Finder
**Arquivo:** `source_finder.py` | **Nome:** `source_finder`

Recebe os candidatos do Search Agent e os enriquece com dados reais do banco (PostgreSQL):
- Recupera: chunk completo, livro, metadados (edição, coleção, volume, coluna, página PDF)
- Detecta autor canônico via heurísticas
- Valida correspondência entre autor detectado e autor atribuído pelo usuário
- Formata referência final: obra, vol., col., página

Ao final, registra handoffs para `citation_verifier`, `language_agent` e `edition_agent`.

---

### 5. Language Agent
**Arquivo:** `language_agent.py` | **Nome:** `language_agent`

Identifica o idioma do trecho localizado na fonte. Ordem de prioridade: script heurístico → heurístico específico de latim → `langdetect`. Suporta 16 idiomas e scripts:

`la` (Latim), `grc` (Grego Antigo), `el` (Grego Moderno), `pt` (Português), `es` (Espanhol), `en` (Inglês), `fr` (Francês), `it` (Italiano), `de` (Alemão), `he` (Hebraico), `syc` (Siríaco), `cop` (Copta), `ar` (Árabe), `hy` (Armênio), `ka` (Georgiano), `gez` (Ge'ez)

Retorna: código ISO, grau de certeza (0–1) e limitações. Detecta também o idioma da query do usuário para contexto multilíngue. Roda em paralelo com o Edition Agent após o Source Finder.

---

### 6. Edition Agent
**Arquivo:** `edition_agent.py` | **Nome:** `edition_agent`

Identifica a edição do corpus utilizada no trecho localizado. Mapeia 7 coleções suportadas:

| Sigla | Coleção |
|---|---|
| `PL` | Patrologia Latina (Migne) |
| `PG` | Patrologia Graeca (Migne) |
| `PO` | Patrologia Orientalis |
| `PT` | Coleção Patrística (Paulus) |
| `CONC` | Documentos Conciliares |
| `MAG` | Magistério |
| `NA` | New Advent |

Lista arquivos disponíveis com metadados (volume, editor, tradutor). Rastreia riscos, como edições Migne do século XIX versus edições críticas modernas. Roda em paralelo com o Language Agent.

---

### 7. Citation Verifier
**Arquivo:** `citation_verifier.py` | **Nome:** `citation_verifier`

O classificador central do sistema. Recebe o trecho localizado e executa avaliação determinística em quatro métricas:

1. **Similaridade textual normalizada** — via `SequenceMatcher` (sem acentos, sem pontuação)
2. **Lexical anchor** — fração de palavras significativas (≥4 chars) da query presentes no texto
3. **Intrusion score** — detecção de jargão acadêmico moderno (via `verification_service`)
4. **Score combinado** — `CombinedScorer`: 65% textual + 35% semântico + bônus por `author_match`

Classifica em **7 códigos internos**:

| Código | Descrição |
|---|---|
| `CONFIRMADA_EXATA` | Correspondência literal na fonte (similaridade ≥ 0.85) |
| `TRADUCAO_FIEL` | Mesmo conteúdo, tradução diferente |
| `CORRESPONDENCIA_FORTE` | Score alto, sem identidade literal |
| `ATRIBUICAO_DUVIDOSA` | Texto existe, autor incorreto |
| `TRADUCAO_IMPRECISA` | Tradução com desvios semânticos |
| `PARAFRASE_PLAUSIVEL` | Ideia correta, palavras diferentes |
| `NAO_ENCONTRADA` | Sem correspondência no corpus |

Depende de: Source Finder + Language Agent + Edition Agent.

---

### 8. Translation Agent
**Arquivo:** `translation_agent.py` | **Nome:** `translation_agent`

Avalia a fidelidade da tradução em três dimensões:
1. Correspondência entre o texto original encontrado e sua tradução
2. Preservação semântica entre a query do usuário e a tradução no banco
3. Ausência de acréscimos ou distorções

Emite veredito: `tradução fiel`, `aceitável`, `paráfrase` ou `imprecisa`. Depende de: Citation Verifier + Language Agent.

---

### 9. Context Agent
**Arquivo:** `context_agent.py` | **Nome:** `context_agent`

Recupera o contexto textual adjacente ao chunk localizado: busca `seq_index - 1` (anterior) e `seq_index + 1` (posterior) no mesmo livro. Calcula risco de uso fora de contexto detectando negações no entorno ("não", "nunca", "falso", "heresia"). Retorna: `central_excerpt`, `previous_context`, `next_context`, `out_of_context_risk`. Depende de: Citation Verifier.

---

### 10. Consistency Agent
**Arquivo:** `consistency_agent.py` | **Nome:** `consistency_agent`

Valida a coerência entre os resultados de todos os agentes anteriores. Verifica convergência de: autor, obra, tema, idioma, edição. Detecta conflitos entre relatórios. Define correções necessárias (ex.: confirmar edição crítica definitiva). Depende de todos os agentes do fluxo de verificação (Source Finder → Context Agent).

---

### 11. Safety Agent
**Arquivo:** `safety_agent.py` | **Nome:** `safety_agent`

Agente final do fluxo de verificação. Traduz os 7 códigos internos do Citation Verifier nos **4 vereditos públicos** com degradação conservadora:

| Código interno | Veredito público | Nível |
|---|---|---|
| `CONFIRMADA_EXATA` | confirmado | alto |
| `TRADUCAO_FIEL` | confirmado | médio-alto |
| `CORRESPONDENCIA_FORTE` | provável | médio |
| `ATRIBUICAO_DUVIDOSA` | inconclusivo | baixo |
| `TRADUCAO_IMPRECISA` | inconclusivo | baixo |
| `PARAFRASE_PLAUSIVEL` | inconclusivo | baixo |
| `NAO_ENCONTRADA` | não sustentado | crítico |

**Regra conservadora:** se `intrusion_score > 0.3` ou há conflitos detectados pelo Consistency Agent, o veredito desce um nível. Emite também: forças, fragilidades, risco de erro e recomendação de exibição ao usuário. Depende de: Consistency Agent.

---

### 12. PDF Ingestion Agent
**Arquivo:** `pdf_ingestion_agent.py` | **Nome:** `pdf_ingestion_agent`

Inventaria os PDFs-alvo para ingestão. Busca arquivos PG002–PG005 (Patrologia Graeca) e PL001–PL005 (Patrologia Latina). Verifica existência e tamanho de cada arquivo (identifica arquivos zerados). Recomenda o comando de importação com parâmetros batch, cooldown e cuda. Usa Chroma delta para embeddings. Depende de: Planner.

---

### 13. Ingestion Validation Agent
**Arquivo:** `ingestion_validation_agent.py` | **Nome:** `ingestion_validation_agent`

Valida se a ingestão dos PDFs foi concluída com sucesso no banco. Consulta o PostgreSQL para os 9 volumes esperados (PG002–PG005, PL001–PL005). Conta registros de `BookFile` e `Chunk` por volume. Retorna status por volume: `not_imported`, `in_progress` ou `done`. Rastreia progresso com contadores `done` e `remaining`. Depende de: PDF Ingestion Agent.

---

## Grafo de dependências — Fluxo de Verificação de Citações

```
orchestrator
     ↓
  planner
     ↓
 search_agent
     ↓
source_finder
   ↙       ↘
language   edition
  agent     agent
      ↘   ↙
  citation_verifier
     ↙         ↘
translation   context
  agent        agent
      ↘       ↙
   consistency_agent
          ↓
     safety_agent
```

---

## Grafo de dependências — Fluxo de Ingestão de PDFs

```
orchestrator
     ↓
  planner
     ↓
pdf_ingestion_agent
     ↓
ingestion_validation_agent
```

---

## Tabela resumo

| # | Agente | Arquivo | Fluxo |
|---|---|---|---|
| 1 | Orchestrator | `orchestrator.py` | Todos |
| 2 | Planner | `planner.py` | Todos |
| 3 | Search Agent | `search_agent.py` | Verificação |
| 4 | Source Finder | `source_finder.py` | Verificação |
| 5 | Language Agent | `language_agent.py` | Verificação |
| 6 | Edition Agent | `edition_agent.py` | Verificação |
| 7 | Citation Verifier | `citation_verifier.py` | Verificação |
| 8 | Translation Agent | `translation_agent.py` | Verificação |
| 9 | Context Agent | `context_agent.py` | Verificação |
| 10 | Consistency Agent | `consistency_agent.py` | Verificação |
| 11 | Safety Agent | `safety_agent.py` | Verificação |
| 12 | PDF Ingestion Agent | `pdf_ingestion_agent.py` | Ingestão |
| 13 | Ingestion Validation Agent | `ingestion_validation_agent.py` | Ingestão |
