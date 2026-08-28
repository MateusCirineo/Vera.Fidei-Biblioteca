# Vera.Fidei

O Vera.Fidei é uma plataforma de pesquisa patrística e verificação de citações,
entregue como PWA, API e aplicativo Expo. O acervo preserva edição, tradutor,
página e ligação ao PDF; OCR não conferido falha fechado e não é apresentado
como transcrição literal.

## Componentes

- `backend/`: API FastAPI, PostgreSQL, Elasticsearch, ingestão, pesquisa,
  verificador, autenticação e cobrança;
- `frontend/`: PWA Next.js;
- `mobile/`: aplicativo Expo/React Native;
- `nginx/`: proxy e entrega parcial de PDFs;
- `ops/`: backup, restauração, reconciliação Stripe e monitoramento.

## Desenvolvimento local

Backend:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Mobile:

```bash
cd mobile
npm ci
npx expo start
```

`requirements.txt` é a entrada editável para desenvolvimento. A imagem de
produção usa o lock de Python 3.11 para Linux x86_64 e exige todos os hashes:

```bash
cd backend
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
```

O comando de regeneração e os portões obrigatórios da entrega estão em
`RELEASE_MANIFEST.md`.

## Produção e reprodução da release

Parta da tag anotada da versão e crie os arquivos de ambiente apenas no
servidor. Eles não pertencem ao Git:

```bash
git checkout v1.3.0
cp deployment.env.example .env
# configurar .env e backend/.env.production com os valores reais
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Os testes obrigatórios, IDs imutáveis das imagens e builds móveis estão em
`RELEASE_MANIFEST.md`. Para voltar à versão anterior, extraia o código da tag
anterior sem apagar diretórios de dados e reconstrua somente os serviços
alterados. Restaure banco apenas pelo procedimento controlado de recuperação,
quando uma migração realmente exigir isso. Nunca sobrescreva `.env`, `backend/pdfs`,
`backend/chroma_db`, `backend/model_cache` ou os volumes PostgreSQL e
Elasticsearch durante implantação ou rollback.

## Aplicativo móvel

O projeto Expo fica em `mobile/` e possui três perfis de distribuição
deliberadamente diferentes:

- `preview`: APK de distribuição direta, com gerenciamento de assinatura pelo
  Stripe;
- `production`: AAB em modo leitor, sem checkout, portal de cobrança ou links
  externos de compra dentro do aplicativo;
- `production-play`: futuro AAB da loja com Google Play Billing nativo, ainda
  bloqueado até a configuração e a homologação completas.

O perfil `production` continua falhando fechado como `reader`, e `preview`
continua sendo o único perfil com cobrança Stripe direta. O modo `play` não
deve ser habilitado nem publicado antes de cumprir o runbook em
[`docs/google-play-release.md`](docs/google-play-release.md). Os perfis de
release usam versionamento remoto do EAS e incremento automático do
`versionCode`.

Antes de um build remoto, execute `npm run typecheck`, `npm run lint`,
`npm test`, `npm audit --omit=dev` e `npx expo-doctor`. O arquivo enviado ao
EAS deve ser inspecionado para confirmar que não contém `.env`, PDFs, dados do
backend, credenciais ou o histórico Git.
