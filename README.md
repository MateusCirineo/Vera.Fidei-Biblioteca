# Vera.Fidei Biblioteca

> **Copyright (c) 2024–2026 Mateus Cirineo — Todos os direitos reservados.**
> Uso comercial, redistribuição e venda são expressamente proibidos. Veja [LICENSE](LICENSE).

Plataforma católica de verificação e consulta de fontes patrísticas e teológicas. Reúne obras dos Padres da Igreja (Patrologia Latina e Graeca de Migne), textos conciliares e teológicos, com sistema de busca semântica e verificação de citações com IA.

## Estrutura do Projeto

```
vera_fidei_starter/
├── backend/        # API Python (FastAPI) + PostgreSQL + Elasticsearch + ChromaDB
├── frontend/       # Aplicação web (Next.js / TypeScript) — PWA
├── mobile/         # App mobile (Flutter)
└── nginx/          # Configuração de proxy reverso

codex-playwright-tests/   # Testes E2E (Playwright)
LOGO VF/                  # Ícones e splash screens
docs/                     # Documentação, planos e assets
scripts/                  # Scripts utilitários de execução
```

## Componentes

### Backend (FastAPI)
- Busca semântica via **ChromaDB** (embeddings) e **Elasticsearch** (full-text)
- Banco relacional **PostgreSQL** com obras indexadas
- Pipeline de verificação de citações com múltiplos agentes de IA
- Ingestão de PDFs via Poppler

### Frontend (Next.js — PWA)
- Biblioteca com obras dos Padres (PL/PG de Migne)
- Seção de santos e orações
- Verificador de citações patrísticas
- Modo offline (PWA)

### Mobile (Flutter)
- App Android/iOS com as mesmas funcionalidades do frontend
- APK disponível em [Releases](../../releases)

## Como Rodar Localmente

```bash
# Backend
cd vera_fidei_starter/backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd vera_fidei_starter/frontend
npm install
npm run dev
```

Ou use os scripts na pasta `scripts/`:
- `scripts/run_backend.cmd`
- `scripts/run_frontend.cmd`

## Deploy

Consulte [docs/DEPLOY_ORACLE_CLOUD.md](docs/DEPLOY_ORACLE_CLOUD.md) para instruções de deploy na Oracle Cloud.

Para publicar nas lojas, veja [docs/BUILD_LOJAS.md](docs/BUILD_LOJAS.md).

## Documentação

- [Documento completo do projeto](docs/Vera.fidei%20-%20Documento%20Completo.md)
- [Deploy Oracle Cloud](docs/DEPLOY_ORACLE_CLOUD.md)
- [Build para lojas](docs/BUILD_LOJAS.md)
- [Plano de storage / acervo Migne](docs/PLANO_STORAGE_ACERVO_MIGNE.md)
