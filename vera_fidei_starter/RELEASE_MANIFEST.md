# Manifesto da release 1.2.0

Este documento registra o corte verificável do Vera.Fidei 1.2.0. A identidade
canônica é a tag anotada `v1.2.0`; o commit exato é obtido sem ambiguidade por:

```bash
git rev-list -n 1 v1.2.0
```

## Identidade e escopo

| Campo | Valor |
| --- | --- |
| Versão | `1.2.0` |
| Tag canônica | `v1.2.0` anotada |
| Commit da release | commit apontado por `v1.2.0` |
| Marcador implantado | `/opt/vera_fidei/.deployed_git_commit`, igual ao commit da tag |
| Data do corte | `2026-08-25`, `America/Sao_Paulo` |
| Escopo público | API, frontend/PWA e artefatos Android assinados |
| iOS | código e bundles locais validados; IPA assinado não faz parte deste corte |

O runtime web foi construído e implantado a partir de `1fabfdd`. Os diretórios
`backend/` e `frontend/` não mudaram entre esse commit e a tag: seus objetos Git
são, respectivamente, `0d2dd5207715c1d2e96be2e9128a77eaeb1c7838` e
`84859662b081f1185eb400fd7033fd2250e91ae1`. As mudanças posteriores pertencem
ao empacotamento móvel, operações e documentação.

## Proveniência das mudanças

| Entrega | Commit |
| --- | --- |
| Consolidação funcional e de segurança | `6814b22` |
| Runtime web e arquivos de implantação com LF | `1fabfdd` |
| Arquivo mínimo enviado ao EAS | `978da2a` |
| Identidade visual e empacotamento nativo | `85759f4` |
| Distribuições mobile `direct` e `reader` | `0d92a5e` |
| Persistência privada do token do backup externo | `32bc0f7` |
| Numeração remota e automática dos builds EAS | `f31f060` |
| Verificação SHA-256 remota e documentação final | commit apontado por `v1.2.0` |

## Imagens do runtime web

As imagens são locais ao servidor e, portanto, a evidência correta é o
`Image ID`, não um `RepoDigest` de registry:

| Componente | Image ID |
| --- | --- |
| Backend | `sha256:68530b2662aa56b026392398c7ba5567301dc4bc6ae3f6c90019fa62d9a89e6e` |
| Frontend | `sha256:21ade86b61f357bed1caa5a4d2b8dae5a6704c8e6cd77f0f5c4002201acf7fd7` |

As entradas imutáveis usadas pelos Dockerfiles e pelo Compose são:

| Componente | Referência fixada |
| --- | --- |
| Python | `python:3.11-slim@sha256:3c1dfceb3f1267d4d378e7883cddf35c58757bab98d70bba30b6e02e808fa21d` |
| Node.js | `node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` |
| PostgreSQL | `postgres:15@sha256:29342cb52157b098821961d2c14eec3c019071f56a5d559e990cf07cf541ea9b` |
| Elasticsearch | `elasticsearch:8.13.0@sha256:9d1cd1491778aceca4490de7ec9f205c3633a277df15473e1ea507d13a5270c6` |
| Nginx | `nginx:alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de` |

Os pacotes Debian usam o snapshot `20260824T000000Z`. O backend instala
`backend/requirements.lock` com `--require-hashes`; o lock é específico para
Python 3.11 em Linux x86_64.

## Artefatos Android assinados

| Artefato | Perfil e modo | Build EAS | Versão | Bytes | SHA-256 |
| --- | --- | --- | --- | ---: | --- |
| `vera-fidei-android-direct-v1.2.0-code3.apk` | `preview`, `direct` | `c167eacb-362c-4ba9-a208-397abeadf395` | `1.2.0 (3)` | 84.632.710 | `49c38fba6adda083ca57e5bd6a5481c60307e39a4612033ca0d8f8252f71f048` |
| `vera-fidei-android-reader-v1.2.0-code4.aab` | `production`, `reader` | `8a3f371f-9834-4f07-9f9e-cada2de37ca8` | `1.2.0 (4)` | 58.888.311 | `16577193749b0a009e73385566f62e9b0c84df49795e208b28adf08e484e19ef` |

O APK passou `zipalign` e validação de assinatura APK v2. O AAB passou
`bundletool validate` 1.18.3 e `jarsigner`. Ambos usam
`com.verafidei.app`; a inspeção dos arquivos encontrou zero entradas de
`.env`, Git, backend, PDFs, rclone ou chaves.

O perfil `direct` inclui o gerenciamento de assinatura. O perfil de loja
`reader` remove checkout, portal e atalhos externos de compra, mantendo
autenticação, pesquisa, biblioteca, verificador, PDF, perfil, exportação e
exclusão de conta.

## Evidências executadas em 2026-08-25

| Portão | Resultado observado |
| --- | --- |
| Backend | 279 coletados; 276 aprovados, 3 ignorados, 0 falhas |
| Auditoria Python | 0 vulnerabilidades no lock; OSV `torch 2.13.0`: 0; Bandit: 0 médio/alto |
| Frontend | lint e build aprovados; 31 páginas geradas; 0 vulnerabilidades de produção |
| Mobile | typecheck, lint, 12/12 testes, auditoria 0 e Expo Doctor 21/21 |
| Bundles locais | Android `direct`/`reader` e iOS `direct`/`reader` exportados com sucesso |
| Produção | backend saudável; frontend, Nginx, PostgreSQL e Elasticsearch em execução sem reinício inesperado |
| Segurança pública | HTTPS, HSTS, CSP sem `unsafe-eval`; documentação interna da API retorna 404 |
| PWA | manifest, service worker e quatro ícones retornam 200 |
| Stripe | evento real `customer.subscription.updated` entregue em modo live com HTTP 200; 0 eventos antigos pendentes |
| PDFs | 1.839 de 1.839 caminhos resolvidos; 0 ausentes e 0 referências redundantes |
| PDF grande | PG001 com 211.280.137 bytes respondeu HTTP 206 com somente 65.536 bytes |
| Backup local | dump de 115.214.446 bytes com SHA e catálogo válidos |
| Restauração | 632 obras, 117.337 trechos e 11 usuários restaurados em banco temporário |
| Backup externo | upload cifrado, re-download e SHA-256 remoto aprovados às `2026-08-25T07:44:37Z` |
| Monitoramento | timers de backup local/externo, reconciliação e monitor ativos; disco em 40% |

A instalação limpa do lock Linux incluiu 109 pacotes e passou `pip check`. O
`.venv` histórico do computador de desenvolvimento contém pacotes extras do
Chroma que não pertencem ao lock; ele não é usado na imagem nem constitui uma
dependência da release.

## Limites declarados

- Existem 37.783 trechos de OCR das coleções PG/PL/PO ainda sem revisão humana
  palavra por palavra. Eles permanecem bloqueados como transcrição literal e
  só podem fornecer localização no PDF; a revisão editorial continua depois
  do lançamento.
- A integração autenticada da PWA/API foi testada, mas a instalação dos
  artefatos em um aparelho físico não pôde ser executada neste ambiente. O APK
  e o AAB foram validados e assinados, sem substituir esse smoke físico.
- Publicação em Google Play ou App Store depende das contas, metadados e
  revisão externa das lojas. Esta release não contém um IPA assinado.

Esses limites não são apresentados como trabalho já concluído. Eles delimitam
o que pode ser anunciado: a PWA/API 1.2.0 e os artefatos Android aqui
identificados, sem alegar revisão integral do OCR ou aprovação prévia das lojas.
