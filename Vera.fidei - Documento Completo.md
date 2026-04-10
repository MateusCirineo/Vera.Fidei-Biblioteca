# VERA.FIDEI
## Plataforma Católica de Consulta e Verificação de Fontes Primárias
### Documento de Planejamento Completo

**Autor:** Mateus Gustavo Cirineo Valim
**Ano:** 2026

---

## 1. DELIMITAÇÃO DO TEMA

O presente projeto consiste no desenvolvimento de uma plataforma digital completa — disponível em versão web e mobile — voltada à organização, consulta, acesso e verificação de fontes primárias da tradição católica.

A plataforma recebe o nome de **Vera.fidei**, em referência à verdade da fé, e tem como propósito central oferecer à comunidade católica um ambiente confiável, estruturado e multilíngue para acesso às raízes doutrinárias e históricas da Igreja.

Nesse sistema serão disponibilizados, de forma organizada e acessível, todos os volumes em PDF da **Patrologia Latina** (Migne, 221 volumes), da **Patrologia Graeca** (Migne, 166 volumes) e da **Patrologia Orientalis** (aproximadamente 50 volumes, cobrindo textos em Siríaco, Copta, Árabe e outros idiomas). Além disso, estarão disponíveis encíclicas papais de todos os séculos, cartas dos grandes Concílios da Igreja — como Niceia (325), Roma (382), Hipona, Cartago (397) e outros — e documentos oficiais da Santa Sé.

Além da biblioteca digital, o sistema contará com uma funcionalidade central e inédita: o **Verificador de Citações Teológicas**, capaz de identificar a origem exata de frases atribuídas a Padres da Igreja, papas, concílios e reformadores — ou de denunciar quando tais citações não existem, foram distorcidas, foram mal-atribuídas ou foram geradas por sistemas de inteligência artificial.

O sistema funcionará de forma **multilíngue**, suportando Latim, Grego, Hebraico, Português, Inglês, Alemão e outros idiomas, sendo capaz de localizar a citação no idioma original e rastrear suas variações em diferentes traduções.

O diferencial central do projeto é levar o usuário até o **trecho exato dentro da obra original**, indicando com precisão:

- Coleção (PL — Patrologia Latina / PG — Patrologia Graeca / PO — Patrologia Orientalis)
- Volume
- Coluna (referência padrão Migne — que numera por colunas, não por páginas)
- Capítulo ou seção
- Localização textual exata (offset de caractere + página PDF + posição visual)
- Contexto completo antes e depois do trecho encontrado

---

## 2. JUSTIFICATIVA

### 2.1 O problema do acesso fragmentado

Atualmente, há uma grande dificuldade no acesso estruturado às fontes primárias católicas. Os volumes da Patrologia Migne, as encíclicas antigas e as cartas conciliares estão espalhados em diferentes repositórios digitais — Archive.org, Google Books, Vatican.va — sem organização centralizada, sem busca integrada e sem referenciamento padronizado. Estudantes de teologia, pesquisadores e fiéis precisam de horas de pesquisa para encontrar um único trecho em uma obra patrística.

### 2.2 O problema das citações falsas

Há uma circulação massiva de citações apócrifas atribuídas a grandes nomes da tradição católica. Frases que nunca foram escritas por Santo Agostinho, São Tomás de Aquino, São Cipriano ou outros Padres da Igreja circulam em redes sociais, livros, pregações e artigos — muitas vezes de boa-fé, por quem simplesmente encontrou aquela citação em outro lugar e a repassou sem verificar.

### 2.3 O problema das alucinações de inteligência artificial

Este é o problema mais urgente e crescente que o projeto busca combater. Ferramentas de IA como **ChatGPT**, **Gemini** e outras rotineiramente:

- Inventam trechos de obras que existem, mas com conteúdo fabricado
- Criam capítulos inexistentes de obras de São Tomás de Aquino
- Atribuem erroneamente citações patrísticas a autores que nunca as escreveram
- Geram frases em latim clássico com estrutura gramaticalmente correta, mas sem base em nenhuma fonte real
- Produzem referências bibliográficas falsas com perfeita confiança e aparência de autoridade

Essas citações **parecem autorizadas**. Elas não são. E o problema cresce à medida que o uso de IA se expande no estudo teológico e na evangelização digital.

### 2.4 O que o Vera.fidei resolve

| Problema | Solução |
|---|---|
| Fontes fragmentadas e de difícil acesso | Biblioteca centralizada com todos os volumes Migne + documentos da Igreja |
| Dificuldade de verificação manual | Verificador automático com busca em fontes primárias reais |
| Citações falsas e mal-atribuídas | Sistema de Confiança que classifica e denuncia o problema |
| Alucinações de IA | Verificação contra corpus real — não contra outra IA |
| Falta de referência exata | Localização com coleção + volume + coluna + capítulo + contexto + PDF |

---

## 3. OBJETIVOS

### 3.1 Objetivo Geral

Desenvolver uma plataforma digital completa — web e mobile — para consulta, acesso e verificação de fontes primárias da tradição católica, com foco em precisão, multilinguismo e combate à desinformação teológica.

### 3.2 Objetivos Específicos

- Disponibilizar todos os volumes da Patrologia Latina, Graeca e Orientalis (Migne) em formato PDF indexado e pesquisável
- Disponibilizar encíclicas papais, cartas conciliares e documentos oficiais da Igreja
- Implementar busca avançada por termo exato, busca semântica e busca multilíngue
- Criar o Verificador de Citações Teológicas com classificação automática de autenticidade
- Mostrar a localização exata da citação (coleção, volume, coluna, capítulo, contexto)
- Navegar o usuário diretamente ao trecho exato no PDF original
- Suportar múltiplos idiomas: Latim, Grego, Hebraico, Português, Inglês, Alemão e outros
- Detectar e classificar citações fabricadas por IA, pseudo-patrísticas e fora de contexto
- Integrar fontes externas verificadas: Vatican.va e NewAdvent

---

## 4. PROBLEMATIZAÇÃO

Como garantir a autenticidade de citações teológicas em um ambiente onde há grande circulação de informações falsas, dificuldade de acesso às fontes originais e crescente produção de conteúdo fabricado por sistemas de inteligência artificial?

---

## 5. METODOLOGIA

### 5.1 Etapa 1 — Coleta e organização do dataset

**Fontes patrísticas:**
- Patrologia Latina (Migne): 221 volumes — Archive.org, Google Books
- Patrologia Graeca (Migne): 166 volumes — Archive.org
- Patrologia Orientalis: ~50 volumes — Archive.org

**Fontes documentais da Igreja:**
- Encíclicas papais: Vatican.va
- Cartas de Concílios: Vatican.va, NewAdvent
- Documentos oficiais: Vatican.va

**Armazenamento dos PDFs:**
- Fase de desenvolvimento e grupo pequeno: **Google Drive** (gratuito, 15 GB)
- Fase de produção pública: **Cloudflare R2** (10 GB gratuito, sem taxa de saída)

**Status:** parte dos volumes já está em posse do autor; os demais serão mapeados e obtidos via fontes públicas.

---

### 5.2 Etapa 2 — Pipeline de processamento dos PDFs

Os PDFs da Patrologia Migne são em sua maioria digitalizações de obras do século XIX — imagens escaneadas, não texto digital. O processamento seguirá este fluxo:

```
PDF (imagem escaneada)
        ↓
OCR com pytesseract + pdf2image
        ↓
Extração e limpeza do texto (pdfplumber)
        ↓
Segmentação por capítulos e colunas
        ↓
Geração de chunks semânticos
        ↓
Geração de embeddings com bge-m3
        ↓
Indexação no Elasticsearch (busca exata por termos)
Indexação no ChromaDB (busca semântica vetorial)
        ↓
Metadados salvos no PostgreSQL
```

---

### 5.3 Etapa 3 — Referência Migne e mapeamento de localização

**Importante:** A Patrologia Migne (PL, PG, PO) utiliza **colunas**, não páginas, como unidade de referência. O padrão é: `PL [vol], col. [X]`.

O mapeamento `coluna → página PDF → posição visual` é feito **durante a fase de ingestão** e armazenado como metadado estruturado. Dessa forma, a localização do trecho é imediata no momento da consulta, sem nenhum cálculo em tempo real.

Cada chunk indexado armazena:

| Campo | Exemplo |
|---|---|
| Coleção / Sigla | Patrologia Latina / PL |
| Volume | 4 |
| Coluna inicial | 503 |
| Coluna final | 504 |
| Capítulo / Seção | Cap. 6 |
| Autor | São Cipriano de Cartago |
| Obra | De Unitate Ecclesiae |
| Idioma | Latim |
| Página no PDF | 87 |
| Offset de caractere | 1240–1380 |
| Versão / Edição | Migne PL — 1844 |

---

### 5.4 Etapa 4 — Tratamento de múltiplas versões

O sistema manterá versões distintas da mesma obra **indexadas separadamente**. Cada versão possuirá seus próprios metadados: idioma, edição, fonte e tradutor (quando aplicável).

Ao retornar um resultado, o sistema informará explicitamente ao usuário qual versão foi utilizada na correspondência encontrada, evitando ambiguidades entre traduções e edições diferentes.

Isso é crítico para:
- Obras com múltiplas traduções (latim → português, inglês, etc.)
- Edições críticas modernas versus a edição original Migne
- Variantes textuais entre manuscritos

---

### 5.5 Etapa 5 — Indexação

**Elasticsearch / OpenSearch:**
Responsável pela busca exata e busca por termos — especialmente eficaz para textos em latim e grego com morfologia complexa. Utiliza o algoritmo BM25.

**ChromaDB (vector store):**
Responsável pela busca semântica — utiliza os vetores gerados pelo `bge-m3` para encontrar trechos com o mesmo significado em idiomas diferentes, paráfrases e variações de tradução.

Os dois motores atuam em paralelo e seus resultados são combinados pela camada de score.

---

### 5.6 Etapa 6 — Backend

**Python + FastAPI** como servidor principal.

Endpoints principais:
- `POST /verify-citation` — verificador de citações (MVP)
- `GET /books` — lista da biblioteca
- `GET /books/{id}/pdf` — acesso ao PDF com navegação por trecho

---

### 5.7 Etapa 7 — Frontend

- **Web:** Next.js com TypeScript
- **Mobile:** React Native / Expo (fase posterior ao MVP)

---

### 5.8 Etapa 8 — Testes

- Citações reais com fonte conhecida
- Citações inventadas atribuídas a padres reais
- Citações reais com autor trocado
- Citações parafraseadas
- Citações fora de contexto
- Citações em diferentes idiomas (PT, EN, LA, GR)

---

## 6. FUNCIONAMENTO DO VERIFICADOR DE CITAÇÕES

### 6.1 Entrada

O usuário insere o texto da citação (em qualquer idioma) e o nome do autor atribuído.

**Exemplo:**
> Citação: "Quem não tem a Igreja por mãe não pode ter Deus por Pai"
> Atribuído a: São Cipriano de Cartago

---

### 6.2 Processamento — Arquitetura Híbrida em 4 Camadas

> **Princípio fundamental: o LLM não é o juiz. É o explicador.**
> A autoridade final sobre a veracidade de uma citação vem exclusivamente das fontes primárias indexadas e das regras de validação determinísticas.

```
Usuário envia: citação + autor atribuído
                      ↓
┌──────────────────────────────────────────────┐
│  CAMADA 1 — Busca & Recuperação              │
│  Elasticsearch: busca exata por termos       │
│  ChromaDB + bge-m3: busca semântica          │
└─────────────────────┬────────────────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│  CAMADA 2 — Comparação & Score               │
│  BM25 score (Elasticsearch)                  │
│  Cosine similarity (bge-m3 / ChromaDB)       │
│  Regras de negócio fixas                     │
│  → score combinado por candidato             │
└─────────────────────┬────────────────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│  CAMADA 3 — Sistema de Confiança (JUIZ)      │
│  score + contexto + regras → status final    │
│  Determinístico. Baseado em fontes primárias.│
└─────────────────────┬────────────────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│  CAMADA 4 — Explicação (LLM auxiliar)        │
│  Qwen / Llama / Mistral                      │
│  Gera texto explicando o resultado           │
│  NÃO decide. NÃO é fonte de verdade.         │
└─────────────────────┬────────────────────────┘
                      ↓
                Resultado final ao usuário
```

---

### 6.3 Saída — Sistema de Confiança (classificações)

| Status | Descrição | Quando ocorre |
|---|---|---|
| ✅ Confirmada (exata) | Match literal na fonte primária | Trecho idêntico encontrado |
| 🟡 Confirmada (tradução diferente) | Mesma ideia, tradução varia | Mesmo trecho no original, tradução difere |
| 🟠 Paráfrase plausível | Ideia correta, palavras diferentes | Resumos, catecismos, citações de memória |
| 🔶 Fora de contexto | Trecho existe, sentido distorcido | Trecho real recortado de forma enganosa |
| 🔴 Atribuição duvidosa | Texto existe, autor errado | Citação real, pessoa errada |
| ❌ Não encontrada | Sem correspondência em nenhuma fonte | Nenhum resultado em todo o corpus |
| 🚫 Provavelmente falsa / alucinação de IA | Padrão típico de LLM | Estrutura de IA sem base real |

---

### 6.4 Como funciona o "Abrir no trecho exato"

Quando o sistema encontra a citação, ele não apenas informa a referência — ele leva o usuário diretamente ao ponto exato no PDF.

Isso é possível porque, **na fase de ingestão**, cada trecho é indexado com:
- **Página no PDF** — número da página onde o trecho se encontra
- **Coluna Migne** — coluna exata dentro da página (padrão PL/PG/PO)
- **Offset de caractere** — posição exata de início e fim do trecho no texto extraído
- **Posição visual** — coordenada calculada para scroll automático no leitor

No momento da consulta, esses valores já estão salvos como metadado. O sistema apenas lê e usa — sem nenhum cálculo em tempo real.

**Saída ao usuário — exemplo completo:**

```
✅ Confirmada (tradução diferente)

Autor:      São Cipriano de Cartago
Obra:       De Unitate Ecclesiae
Referência: PL 4, col. 503 — Cap. 6
Idioma:     Latim (original)
Confiança:  Alta
Versão:     Migne PL — edição 1844

Trecho original (latim):
"Habere non potest Deum patrem
 qui Ecclesiam non habet matrem."

Contexto antes: [texto que antecede]
Contexto depois: [texto que sucede]

[📖 Abrir no trecho exato →]
```

O botão **"Abrir no trecho exato"** leva diretamente ao ponto correto no PDF — seja na Patrologia Latina, Graeca, Oriental, em uma encíclica ou em qualquer outro documento indexado.

---

## 7. ESTRUTURA DO SISTEMA

### 7.1 Componentes principais

**1. Biblioteca (PDF + texto indexado)**
Todos os documentos organizados por coleção, com metadados completos e acesso ao PDF com navegação por trecho exato.

**2. Motor de busca híbrido**
Elasticsearch para busca exata por termos + ChromaDB com bge-m3 para busca semântica.

**3. Verificador de Citações**
Pipeline de 4 camadas: busca → score → classificação → explicação.

**4. Sistema de Confiança**
O juiz final da plataforma. Determinístico, baseado em fontes primárias, não dependente de IA generativa como fonte de verdade.

---

## 8. TECNOLOGIAS

### Frontend
- **Web:** React / Next.js (TypeScript)
- **Mobile:** React Native / Expo (pós-MVP)

### Backend
- **Python** + **FastAPI**

### Banco de dados relacional
- **PostgreSQL** — metadados de livros, volumes, capítulos, trechos

### Busca textual
- **Elasticsearch / OpenSearch** — busca exata, termos latinos e gregos, BM25

### Busca semântica
- **ChromaDB** (vector store) + modelo **bge-m3** (embeddings multilíngues)

### Modelos de embedding

| Modelo | Característica |
|---|---|
| `bge-m3` **(MVP recomendado)** | Multilíngue, semântico, excelente para latim/grego e paráfrases |
| `multilingual-e5` | Alternativa sólida e bem documentada |
| `LaBSE` | Forte para alinhamento entre idiomas |
| `paraphrase-multilingual-mpnet` | Especializado em detecção de paráfrases |

### OCR e extração de texto
- **pdfplumber** — extração de PDFs digitais
- **pytesseract** + **pdf2image** — OCR para PDFs escaneados

### LLM auxiliar
- **Qwen / Llama / Mistral / Gemma**
- Papel: apenas explicar o resultado ao usuário em linguagem natural
- **Não é fonte de verdade. Não decide.**

### Armazenamento de PDFs
- **Google Drive** — desenvolvimento e grupo pequeno (gratuito, 15 GB)
- **Cloudflare R2** — produção pública (10 GB gratuito, sem taxa de saída)

### Fontes externas (conectores estruturados)
- **Vatican.va** — encíclicas, documentos oficiais, concílios
- **NewAdvent** — patrística, enciclopédia católica

---

## 9. FONTES DE DADOS

| Coleção | Volumes | Idioma principal | Fonte |
|---|---|---|---|
| Patrologia Latina — Migne (PL) | 221 | Latim | Archive.org, Google Books |
| Patrologia Graeca — Migne (PG) | 166 | Grego / Latim | Archive.org |
| Patrologia Orientalis (PO) | ~50 | Siríaco, Copta, Árabe, etc. | Archive.org |
| Encíclicas papais | todos os séculos | Multilíngue | Vatican.va |
| Cartas de Concílios | desde 325 | Latim / Grego | Vatican.va, NewAdvent |
| Documentos oficiais da Igreja | — | Multilíngue | Vatican.va |

---

## 10. RISCOS DO PROJETO

| Risco | Descrição | Mitigação |
|---|---|---|
| **OCR de baixa qualidade** | PDFs Migne são do século XIX — digitalização precária em vários volumes, especialmente nos caracteres gregos | Revisão amostral por volume + métricas de qualidade de OCR |
| **Múltiplas versões da mesma obra** | A mesma obra pode existir em edições, traduções e variantes textuais distintas — risco de falsos negativos | Indexar versões separadamente com metadados distintos + informar versão ao usuário |
| **Direitos autorais** | A Patrologia Migne original (séc. XIX) é domínio público, mas algumas edições críticas modernas podem ter proteção autoral | Priorizar edições Migne originais e fontes com licença aberta |
| **Diferenças entre traduções** | Variações entre traduções podem fazer o sistema classificar erroneamente uma citação real | Busca semântica com bge-m3 + exibir versão encontrada ao usuário |
| **PDFs inconsistentes** | Qualidade, resolução e estrutura dos arquivos variam entre volumes e fontes | Pipeline de validação na ingestão com relatório de erros por volume |
| **Idiomas mistos** | Alguns volumes Migne têm texto em latim e grego na mesma página | Detecção automática de idioma por chunk antes da indexação |

---

## 11. FASES DE DESENVOLVIMENTO

### Fase 1 — MVP: Verificador de Citações (backend)

Objetivo: verificador funcionando para uso pessoal e grupo pequeno.
Foco: **precisão antes de escala** — começar com autores selecionados (ex: São Cipriano) e obras específicas (ex: *De Unitate Ecclesiae*).

- Setup: FastAPI + PostgreSQL + Elasticsearch + ChromaDB
- Pipeline de ingestão completo: OCR → limpeza → chunking → embedding (bge-m3) → indexação com metadados
- Indexar volumes iniciais: *De Unitate Ecclesiae* (Cipriano) + PL volumes 1 a 5
- Endpoint `POST /verify-citation` com todas as 4 camadas
- Conectores estruturados: Vatican.va + NewAdvent
- LLM auxiliar para geração da explicação ao usuário

### Fase 2 — Frontend Web (Next.js)

- Interface do verificador: campo de entrada + exibição completa do resultado
- Leitor de PDF inline com navegação para o trecho exato (coluna/página/offset)
- Exibição do contexto antes e depois do trecho

### Fase 3 — Biblioteca completa

- Pipeline para todos os PDFs disponíveis (PL, PG, PO, encíclicas, concílios)
- Browser da biblioteca: filtro por coleção, autor, período histórico, idioma
- Busca avançada dentro dos documentos

### Fase 4 — Hospedagem pública + Mobile

- Deploy: Railway/Render (backend) + Vercel (frontend)
- Migração: Google Drive → Cloudflare R2
- App React Native / Expo com o verificador
- Fine-tuning do classificador — versão avançada do Sistema de Confiança

---

## 12. DIFERENCIAL DO PROJETO

- Verificação baseada **100% em fontes primárias reais** — não em IA como fonte de verdade
- Combate direto e documentado a alucinações de IA, pseudo-patrística e falsas atribuições
- Localização **exata** do trecho: coleção → volume → coluna → capítulo → offset → PDF
- Busca multilíngue: Latim, Grego, Hebraico, Português, Inglês, Alemão e outros
- Arquitetura híbrida: Elasticsearch (exata) + bge-m3/ChromaDB (semântica) + Sistema de Confiança determinístico + LLM apenas como explicador
- Acervo centralizado: Migne completo + encíclicas + concílios + documentos da Igreja
- Navegação direta ao ponto exato no PDF com mapeamento feito na ingestão
- Sete níveis de classificação cobrindo todos os tipos de problema com citações
- Tratamento explícito de múltiplas versões e edições da mesma obra

---

## 13. CONSIDERAÇÕES FINAIS

O Vera.fidei representa uma solução robusta, tecnicamente sólida e culturalmente relevante para um problema real e crescente na comunicação religiosa contemporânea.

A proliferação de ferramentas de inteligência artificial generativa tornou mais fácil do que nunca a produção de conteúdo teológico que parece autêntico mas não tem nenhuma base nas fontes primárias da tradição católica. O projeto propõe uma resposta direta a esse problema: não com outra IA, mas com as próprias fontes.

A plataforma une tecnologia moderna, critério histórico-patrístico e responsabilidade doutrinária, com potencial para se tornar referência no estudo e na evangelização fundamentada da tradição católica.
