# Rollback — Vera.Fidei

## Ponto de segurança: pré-merge de 12/06/2026 às 19:49

| Campo | Valor |
|---|---|
| Hash | `3eb286e46189bf0863f6fbc2df41e144fe84259e` |
| Tag | `backup-pre-auth-2026-06-12-1949` |
| Branch | `main` |
| Data | 12/06/2026 às 19:49 |
| Motivo do ponto | Antes do merge de auth, histórico, laudos, planos e API keys |

---

## O que foi adicionado no merge (o que será revertido)

- Autenticação JWT (registro, login, `/auth/*`)
- Histórico de verificações por usuário
- Exportação de laudos em PDF (plano Catequista+)
- Contexto patrístico e tradução (plano Apologeta+)
- Painel de gestão institucional (plano Patrístico+)
- API Keys comerciais e `/v1/verificar` (plano Magistério)
- Páginas: `/login`, `/cadastro`, `/historico`, `/planos`, `/perfil`, `/painel`

---

## Como executar o rollback

### 1. No repositório local

```bash
git checkout main
git reset --hard 3eb286e46189bf0863f6fbc2df41e144fe84259e
git push origin main --force-with-lease
```

### 2. No servidor (após o push)

```bash
git pull origin main
docker compose build backend frontend
docker compose up -d
```

### 3. Banco de dados

As tabelas novas (`users`, `verification_history`, `institutions`, `institution_members`, `api_keys`) podem permanecer no banco — a versão antiga do backend simplesmente não as usa.

Não é necessário dropar nada. Se quiser limpar manualmente:

```sql
DROP TABLE IF EXISTS api_keys;
DROP TABLE IF EXISTS institution_members;
DROP TABLE IF EXISTS institutions;
DROP TABLE IF EXISTS verification_history;
DROP TABLE IF EXISTS users;
```

---

## Alternativa via tag (sem precisar do hash)

```bash
git checkout main
git reset --hard backup-pre-auth-2026-06-12-1949
git push origin main --force-with-lease
```
