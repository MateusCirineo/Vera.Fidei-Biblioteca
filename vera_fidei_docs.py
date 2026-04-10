"""
================================================================================
VERA.FIDEI
Plataforma Católica de Consulta e Verificação de Fontes Primárias
================================================================================
Autor  : Mateus Gustavo Cirineo Valim
Ano    : 2026
Versão : 1.0 (Planejamento / MVP)
================================================================================
"""

# ==============================================================================
# 1. METADADOS DO PROJETO
# ==============================================================================

PROJETO = {
    "nome": "Vera.fidei",
    "descricao": (
        "Plataforma digital (web + mobile) para organização, consulta e "
        "verificação de fontes primárias da tradição católica."
    ),
    "autor": "Mateus Gustavo Cirineo Valim",
    "ano": 2026,
    "versao_atual": "MVP — Verificador de Citações",
    "plataformas": ["Web (Next.js)", "Mobile (React Native / Expo)"],
}


# ==============================================================================
# 2. CONTEXTO E JUSTIFICATIVA
# ==============================================================================

CONTEXTO = """
O projeto Vera.fidei resolve três problemas reais na comunidade católica:

1. FRAGMENTAÇÃO
   Fontes patrísticas e documentos da Igreja estão espalhados em diferentes
   repositórios (Archive.org, Google Books, Vatican.va) sem organização
   centralizada, sem busca integrada e sem referenciamento padronizado.

2. FALSIFICAÇÃO
   Citações apócrifas atribuídas a Padres da Igreja, papas e teólogos circulam
   amplamente — muitas vezes de boa-fé, por quem as recebeu sem verificar.

3. ALUCINAÇÃO DE INTELIGÊNCIA ARTIFICIAL
   ChatGPT, Gemini e outros LLMs rotineiramente:
   - Inventam trechos de obras que existem, mas com conteúdo fabricado
   - Criam capítulos inexistentes de obras de São Tomás de Aquino
   - Atribuem erroneamente citações patrísticas a autores que nunca as escreveram
   - Geram frases em latim clássico gramaticalmente corretas, mas sem base real
   - Produzem referências bibliográficas falsas com perfeita confiança

   Essas citações PARECEM autorizadas. Elas NÃO são.
"""

PERGUNTA_CENTRAL = (
    "Como garantir a autenticidade de citações teológicas em um ambiente onde "
    "há grande circulação de informações falsas e dificuldade de acesso às "
    "fontes originais?"
)


# ==============================================================================
# 3. STACK TECNOLÓGICA
# ==============================================================================

STACK = {
    "backend_api": {
        "tecnologia": "Python + FastAPI",
        "papel": "Servidor principal — endpoints REST",
    },
    "banco_relacional": {
        "tecnologia": "PostgreSQL",
        "papel": "Metadados estruturados: livros, volumes, capítulos, chunks, autores",
    },
    "busca_textual": {
        "tecnologia": "Elasticsearch / OpenSearch",
        "papel": "Busca exata por termos — eficaz para latim, grego, morfologia complexa (BM25)",
    },
    "embeddings": {
        "tecnologia": "bge-m3 (MVP recomendado)",
        "papel": "Busca semântica multilíngue — paráfrases, variações de tradução",
        "alternativas": ["multilingual-e5", "LaBSE", "paraphrase-multilingual-mpnet"],
    },
    "vector_store": {
        "tecnologia": "ChromaDB",
        "papel": "Armazenamento dos vetores gerados pelo bge-m3 (local/dev)",
    },
    "ocr": {
        "tecnologia": "pdfplumber + pytesseract + pdf2image",
        "papel": "Extração de texto de PDFs escaneados (Migne séc. XIX)",
    },
    "llm_auxiliar": {
        "tecnologia": "Qwen / Llama / Mistral / Gemma",
        "papel": "Explicação do resultado ao usuário em linguagem natural",
        "aviso": "NÃO é fonte de verdade. NÃO decide. Apenas comunica.",
    },
    "frontend_web": {
        "tecnologia": "Next.js (TypeScript)",
        "papel": "Interface web da plataforma",
    },
    "mobile": {
        "tecnologia": "React Native / Expo",
        "papel": "App mobile (pós-MVP)",
    },
    "armazenamento_pdfs": {
        "dev": "Google Drive (gratuito, 15 GB — uso pessoal e grupo pequeno)",
        "producao": "Cloudflare R2 (10 GB gratuito, sem taxa de saída)",
    },
    "fontes_externas": {
        "vatican_va": "Encíclicas, documentos oficiais, concílios",
        "new_advent": "Patrística, enciclopédia católica",
        "nota": "Integração via conectores estruturados, não scraping bruto",
    },
}


# ==============================================================================
# 4. SISTEMA DE CONFIANÇA — ARQUITETURA HÍBRIDA EM 4 CAMADAS
# ==============================================================================

PRINCIPIO_FUNDAMENTAL = (
    "O LLM não é o juiz. É o explicador. "
    "A autoridade final vem das fontes primárias indexadas "
    "e das regras de validação determinísticas."
)

ARQUITETURA_SISTEMA_CONFIANCA = {
    "camada_1": {
        "nome": "Busca & Recuperação",
        "componentes": {
            "elasticsearch": "Busca exata por termos (latim, grego, termos técnicos teológicos)",
            "chromadb_bge_m3": "Busca semântica (paráfrases, mesmo sentido em idioma diferente)",
        },
    },
    "camada_2": {
        "nome": "Comparação & Score",
        "componentes": {
            "bm25": "Score de relevância textual (Elasticsearch)",
            "cosine_similarity": "Similaridade vetorial (bge-m3 / ChromaDB)",
            "regras_negocio": "Thresholds e regras fixas de validação",
        },
        "saida": "Score combinado por candidato encontrado",
    },
    "camada_3": {
        "nome": "Sistema de Confiança (O JUIZ FINAL)",
        "descricao": (
            "Classificação determinística baseada em score + contexto + regras. "
            "Não depende de IA generativa. "
            "Baseia-se exclusivamente nas fontes primárias indexadas."
        ),
    },
    "camada_4": {
        "nome": "Explicação (LLM auxiliar)",
        "descricao": (
            "Qwen / Llama / Mistral recebe o resultado da Camada 3 e gera "
            "uma explicação em linguagem natural para o usuário. "
            "NÃO decide. NÃO é fonte de verdade. Apenas comunica."
        ),
    },
}

FLUXO_VERIFICACAO = """
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
│  BM25 score + Cosine similarity              │
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
│  Gera texto explicando o resultado           │
│  NÃO decide. Apenas comunica.                │
└─────────────────────┬────────────────────────┘
                      ↓
                Resultado final ao usuário
"""


# ==============================================================================
# 5. CLASSIFICAÇÕES DO SISTEMA DE CONFIANÇA
# ==============================================================================

CLASSIFICACOES = {
    "CONFIRMADA_EXATA": {
        "emoji": "✅",
        "label": "Confirmada (exata)",
        "criterio": "Match literal encontrado na fonte primária",
        "confianca": "Alta",
    },
    "CONFIRMADA_TRADUCAO": {
        "emoji": "🟡",
        "label": "Confirmada (tradução diferente)",
        "criterio": (
            "Mesmo sentido encontrado, mas a tradução varia entre versões. "
            "Trecho localizado no original latino ou grego."
        ),
        "confianca": "Alta",
    },
    "PARAFREASE_PLAUSIVEL": {
        "emoji": "🟠",
        "label": "Paráfrase plausível",
        "criterio": (
            "Ideia correta, palavras diferentes. "
            "Comum em resumos, catecismos e citações de memória."
        ),
        "confianca": "Média",
    },
    "FORA_DE_CONTEXTO": {
        "emoji": "🔶",
        "label": "Fora de contexto",
        "criterio": (
            "Trecho existe na fonte primária, mas foi recortado de forma "
            "que distorce o significado original."
        ),
        "confianca": "Baixa",
    },
    "ATRIBUICAO_DUVIDOSA": {
        "emoji": "🔴",
        "label": "Atribuição duvidosa",
        "criterio": (
            "Texto existe, mas o autor atribuído está errado. "
            "Citação real mal-atribuída."
        ),
        "confianca": "Baixa",
    },
    "NAO_ENCONTRADA": {
        "emoji": "❌",
        "label": "Não encontrada",
        "criterio": (
            "Sem correspondência em nenhuma fonte confiável indexada "
            "nem nas fontes externas (Vatican.va, NewAdvent)."
        ),
        "confianca": "Nenhuma",
    },
    "PROVAVELMENTE_FALSA": {
        "emoji": "🚫",
        "label": "Provavelmente falsa / alucinação de IA",
        "criterio": (
            "Padrão linguístico típico de texto gerado por LLM. "
            "Estrutura que imita autoridade patrística sem base real."
        ),
        "confianca": "Nenhuma",
    },
}


# ==============================================================================
# 6. EXEMPLO REAL DE USO
# ==============================================================================

EXEMPLO_VERIFICACAO = {
    "entrada": {
        "citacao": "Quem não tem a Igreja por mãe não pode ter Deus por Pai",
        "atribuido_a": "São Cipriano de Cartago",
    },
    "saida": {
        "status": "✅ Confirmada (tradução diferente)",
        "autor": "São Cipriano de Cartago",
        "obra": "De Unitate Ecclesiae",
        "referencia": "PL 4, col. 503 — Cap. 6",
        "idioma_original": "Latim",
        "trecho_original": (
            '"Habere non potest Deum patrem '
            'qui Ecclesiam non habet matrem."'
        ),
        "confianca": "Alta",
        "acao": "[📖 Abrir no trecho exato →]",
    },
}


# ==============================================================================
# 7. FONTES DE DADOS
# ==============================================================================

FONTES_DE_DADOS = {
    "patrologia_latina": {
        "sigla": "PL",
        "autor_colecao": "Jacques Paul Migne",
        "volumes": 221,
        "idioma_principal": "Latim",
        "periodo": "Séculos II–XIII",
        "fontes_obtencao": ["Archive.org", "Google Books"],
        "referenciamento": "Por colunas — ex: PL 4, col. 503",
    },
    "patrologia_graeca": {
        "sigla": "PG",
        "autor_colecao": "Jacques Paul Migne",
        "volumes": 166,
        "idioma_principal": "Grego / Latim",
        "periodo": "Séculos I–XV",
        "fontes_obtencao": ["Archive.org"],
        "referenciamento": "Por colunas — ex: PG 7, col. 1208",
    },
    "patrologia_orientalis": {
        "sigla": "PO",
        "volumes": "~50",
        "idiomas": ["Siríaco", "Copta", "Árabe", "Etíope", "Armênio"],
        "fontes_obtencao": ["Archive.org"],
        "referenciamento": "Por colunas",
    },
    "enciclicas_papais": {
        "cobertura": "Todos os séculos",
        "idioma": "Multilíngue",
        "fonte": "Vatican.va",
    },
    "cartas_concilios": {
        "exemplos": [
            "Niceia (325)",
            "Roma (382)",
            "Hipona",
            "Cartago (397)",
        ],
        "idiomas": ["Latim", "Grego"],
        "fontes": ["Vatican.va", "NewAdvent"],
    },
    "documentos_oficiais": {
        "fonte": "Vatican.va",
        "idioma": "Multilíngue",
    },
}

PADRAO_REFERENCIA_MIGNE = """
IMPORTANTE: A Patrologia Migne (PL, PG, PO) utiliza COLUNAS, não páginas.

Formato padrão de referência:
  PL [volume], col. [número]
  PG [volume], col. [número]
  PO [volume], col. [número]

Exemplo: PL 4, col. 503

Mapeamento feito na ingestão (não em tempo real):
  coluna → página PDF → posição visual no documento

Armazenado como metadado estruturado em cada chunk indexado.
"""


# ==============================================================================
# 8. PIPELINE DE INGESTÃO (passo a passo)
# ==============================================================================

PIPELINE_INGESTAO = [
    {
        "etapa": 1,
        "nome": "download_pdf",
        "descricao": "Baixar o PDF da fonte (Archive.org, Google Books, Google Drive)",
        "ferramentas": ["requests", "gdown (Google Drive)"],
    },
    {
        "etapa": 2,
        "nome": "extracao_texto",
        "descricao": "Tentar extrair texto digital diretamente do PDF",
        "ferramentas": ["pdfplumber"],
        "nota": "Se o PDF for imagem escaneada, o texto retorna vazio → vai para OCR",
    },
    {
        "etapa": 3,
        "nome": "ocr",
        "descricao": "Converter páginas do PDF em imagem e aplicar OCR para extrair texto",
        "ferramentas": ["pdf2image", "pytesseract"],
        "nota": "Aplicado apenas quando a extração direta falha (PDFs escaneados Migne séc. XIX)",
    },
    {
        "etapa": 4,
        "nome": "limpeza",
        "descricao": "Normalizar o texto: remover artefatos de OCR, hifenizações, caracteres estranhos",
        "ferramentas": ["regex", "unicodedata"],
    },
    {
        "etapa": 5,
        "nome": "chunking",
        "descricao": (
            "Dividir o texto em chunks menores, respeitando a estrutura da obra "
            "(capítulos, seções, colunas Migne). Cada chunk vira uma unidade indexável."
        ),
        "ferramentas": ["lógica própria baseada em padrões de capítulo/coluna"],
    },
    {
        "etapa": 6,
        "nome": "embeddings",
        "descricao": "Gerar vetor semântico de cada chunk usando bge-m3",
        "ferramentas": ["sentence-transformers", "bge-m3"],
    },
    {
        "etapa": 7,
        "nome": "indexacao",
        "descricao": (
            "Indexar o chunk no Elasticsearch (busca exata) "
            "e no ChromaDB (busca semântica vetorial)"
        ),
        "ferramentas": ["elasticsearch-py", "chromadb"],
    },
    {
        "etapa": 8,
        "nome": "salvamento_metadados",
        "descricao": (
            "Salvar no PostgreSQL todos os metadados estruturados do chunk: "
            "coleção, sigla, volume, coluna, capítulo, autor, obra, idioma, "
            "página PDF, offset de caractere, versão/edição, fonte"
        ),
        "ferramentas": ["SQLAlchemy", "PostgreSQL"],
    },
]


# ==============================================================================
# 9. METADADOS POR CHUNK INDEXADO
# ==============================================================================

METADADOS_CHUNK = {
    "colecao": "ex: Patrologia Latina",
    "sigla": "ex: PL",
    "volume": "ex: 4",
    "coluna_inicial": "ex: 503",
    "coluna_final": "ex: 504",
    "capitulo_secao": "ex: Cap. 6",
    "autor": "ex: São Cipriano de Cartago",
    "obra": "ex: De Unitate Ecclesiae",
    "idioma": "ex: Latim",
    "pagina_pdf": "ex: 87",
    "offset_caractere_inicio": "ex: 1240",
    "offset_caractere_fim": "ex: 1380",
    "versao_edicao": "ex: Migne 1844 / PL edição crítica",
    "fonte_obtencao": "ex: Archive.org",
}


# ==============================================================================
# 9. TRATAMENTO DE MÚLTIPLAS VERSÕES
# ==============================================================================

MULTIPLAS_VERSOES = """
O sistema manterá versões distintas da mesma obra indexadas separadamente.

Cada versão possuirá seus próprios metadados:
  - idioma
  - edição
  - fonte
  - tradutor (quando aplicável)

Ao retornar um resultado, o sistema informará explicitamente ao usuário
qual versão foi utilizada na correspondência encontrada, evitando
ambiguidades entre traduções e edições diferentes.

Isso é crítico para:
  - Obras com múltiplas traduções (latim → português, inglês, etc.)
  - Edições críticas modernas x edição original Migne
  - Variantes textuais entre manuscritos
"""


# ==============================================================================
# 10. IDIOMAS SUPORTADOS
# ==============================================================================

IDIOMAS_SUPORTADOS = [
    "Latim",
    "Grego",
    "Hebraico",
    "Português",
    "Inglês",
    "Alemão",
    "Francês",
    "Siríaco",
    "Copta",
    "Árabe",
    "Espanhol",
    "Italiano",
]


# ==============================================================================
# 11. ESTRUTURA DE PASTAS DO PROJETO
# ==============================================================================

ESTRUTURA_PROJETO = """
vera-fidei/
├── backend/
│   ├── main.py                         # FastAPI entrypoint
│   ├── api/
│   │   └── routes/
│   │       ├── citations.py            # POST /verify-citation
│   │       └── library.py              # GET /books, /books/{id}/pdf
│   ├── ingestion/
│   │   ├── pdf_extractor.py            # Extração de texto (pdfplumber + OCR)
│   │   ├── chunker.py                  # Divisão em chunks por capítulo/coluna
│   │   └── indexer.py                  # Embeddings + indexação (ES + ChromaDB)
│   ├── search/
│   │   ├── elasticsearch_search.py     # Busca exata por termos
│   │   ├── vector_search.py            # Busca semântica (ChromaDB + bge-m3)
│   │   ├── citation_verifier.py        # Pipeline principal (camadas 1-3)
│   │   └── external_sources.py         # Conectores: Vatican.va, NewAdvent
│   ├── confidence/
│   │   ├── scorer.py                   # Combinação BM25 + cosine similarity
│   │   ├── classifier.py               # Sistema de Confiança (camada 3)
│   │   └── explainer.py                # LLM auxiliar — explicação (camada 4)
│   ├── models/
│   │   └── database.py                 # SQLAlchemy: Book, Volume, Chapter, Chunk
│   └── core/
│       ├── config.py
│       └── llm_client.py               # Wrapper LLM auxiliar (Qwen/Llama/Mistral)
├── frontend/
│   └── web/                            # Next.js app
│       ├── app/
│       │   ├── page.tsx                # Home
│       │   ├── verify/                 # Verificador de citações
│       │   └── library/                # Biblioteca (fase 2)
│       └── components/
│           ├── CitationInput.tsx
│           ├── VerificationResult.tsx
│           └── PdfViewer.tsx           # Leitor com navegação para trecho exato
└── data/
    ├── pdfs/
    │   ├── patrologia-latina/
    │   ├── patrologia-graeca/
    │   ├── patrologia-orientalis/
    │   ├── enciclicas/
    │   └── concilios/
    └── processed/                      # Texto extraído + metadados JSON
"""


# ==============================================================================
# 12. FASES DE DESENVOLVIMENTO
# ==============================================================================

FASES = {
    "fase_1_mvp": {
        "nome": "MVP — Verificador de Citações (backend)",
        "objetivo": "Verificador funcionando para uso pessoal e grupo pequeno",
        "tarefas": [
            "Setup: FastAPI + PostgreSQL + Elasticsearch + ChromaDB",
            "Pipeline de ingestão: OCR → limpeza → chunking → embedding (bge-m3) → indexação",
            "Indexar volumes iniciais: De Unitate Ecclesiae (Cipriano) + PL vol. 1-5",
            "Endpoint POST /verify-citation com todas as 4 camadas",
            "Conectores: Vatican.va + NewAdvent",
            "LLM auxiliar para geração da explicação ao usuário",
        ],
    },
    "fase_2_frontend": {
        "nome": "Frontend Web (Next.js)",
        "tarefas": [
            "Interface do verificador: campo de entrada + exibição completa do resultado",
            "Leitor de PDF inline com navegação para o trecho exato (coluna/página)",
            "Exibição do contexto antes e depois do trecho",
        ],
    },
    "fase_3_biblioteca": {
        "nome": "Biblioteca completa",
        "tarefas": [
            "Pipeline para todos os PDFs disponíveis (PL, PG, PO, encíclicas, concílios)",
            "Browser da biblioteca: filtro por coleção, autor, período histórico, idioma",
            "Busca avançada dentro dos documentos",
        ],
    },
    "fase_4_producao": {
        "nome": "Hospedagem pública + Mobile",
        "tarefas": [
            "Deploy: Railway/Render (backend) + Vercel (frontend)",
            "Migração PDFs: Google Drive → Cloudflare R2",
            "App React Native / Expo com o verificador",
            "Fine-tuning do classificador — versão avançada do Sistema de Confiança",
        ],
    },
}


# ==============================================================================
# 13. RISCOS TÉCNICOS E JURÍDICOS
# ==============================================================================

RISCOS = {
    "ocr_qualidade": {
        "descricao": (
            "PDFs Migne são digitalizações do século XIX — qualidade de OCR pode "
            "ser baixa em alguns volumes, especialmente nos caracteres gregos."
        ),
        "mitigacao": "Revisão manual de amostras + métricas de qualidade por volume",
    },
    "multiplas_versoes": {
        "descricao": (
            "A mesma obra pode existir em diferentes edições, traduções e variantes "
            "textuais — risco de falsos negativos na verificação."
        ),
        "mitigacao": "Indexar versões separadamente com metadados distintos",
    },
    "direitos_autorais": {
        "descricao": (
            "A Patrologia Migne original (séc. XIX) é domínio público. "
            "Porém, algumas edições críticas modernas podem ter proteção autoral."
        ),
        "mitigacao": "Priorizar edições Migne originais e fontes com licença aberta",
    },
    "diferencas_traducao": {
        "descricao": (
            "Variações entre traduções podem fazer o sistema classificar como "
            "'não encontrada' uma citação que existe, mas em tradução diferente."
        ),
        "mitigacao": "Busca semântica com bge-m3 + informar versão encontrada ao usuário",
    },
}


# ==============================================================================
# 14. DIFERENCIAL DO PROJETO
# ==============================================================================

DIFERENCIAIS = [
    "Verificação baseada 100% em fontes primárias reais — não em IA como fonte de verdade",
    "Combate direto e documentado a alucinações de IA, pseudo-patrística e falsas atribuições",
    "Localização exata do trecho: coleção → volume → coluna → capítulo → contexto → PDF",
    "Busca multilíngue: Latim, Grego, Hebraico, Português, Inglês, Alemão e outros",
    "Arquitetura híbrida: Elasticsearch (exata) + bge-m3/ChromaDB (semântica) + Sistema de Confiança determinístico",
    "LLM usado apenas como explicador — nunca como juiz",
    "Acervo centralizado: Migne completo + encíclicas + concílios + documentos da Igreja",
    "Navegação direta ao ponto exato no PDF original",
    "Sete níveis de classificação cobrindo todos os tipos de problema com citações",
    "Tratamento explícito de múltiplas versões e edições da mesma obra",
]


# ==============================================================================
# 15. ENDPOINT PRINCIPAL (REFERÊNCIA)
# ==============================================================================

# POST /verify-citation
#
# Request body:
# {
#     "quote": "Quem não tem a Igreja por mãe não pode ter Deus por Pai",
#     "attributed_to": "São Cipriano de Cartago",
#     "language": "pt"  (opcional — detectado automaticamente)
# }
#
# Response:
# {
#     "status": "CONFIRMADA_TRADUCAO",
#     "label": "✅ Confirmada (tradução diferente)",
#     "confianca": "Alta",
#     "autor": "São Cipriano de Cartago",
#     "obra": "De Unitate Ecclesiae",
#     "referencia": "PL 4, col. 503 — Cap. 6",
#     "idioma_original": "Latim",
#     "trecho_original": "Habere non potest Deum patrem qui Ecclesiam non habet matrem.",
#     "contexto_antes": "...",
#     "contexto_depois": "...",
#     "versao_utilizada": "Migne PL — edição 1844",
#     "pdf_pagina": 87,
#     "pdf_coluna": 503,
#     "pdf_link": "/library/patrologia-latina/vol-4/page/87#col503",
#     "explicacao": "A citação foi confirmada na obra original de São Cipriano..."
# }
