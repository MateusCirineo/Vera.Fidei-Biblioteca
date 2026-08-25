# Manifesto da release 1.2.0

Este documento é o registro verificável do corte da versão. Um campo
`PENDENTE` impede que a versão seja tratada como release final reproduzível.

## Identidade

| Campo | Valor |
| --- | --- |
| Versão | `1.2.0` |
| Commit da release | `PENDENTE` — preencher após o commit consolidado |
| Tag assinada/anotada | `PENDENTE` — criar somente após os testes em produção |
| Commit implantado | `PENDENTE` — deve ser igual ao commit da release |
| Data da implantação | `PENDENTE` |
| Digest da imagem backend | `PENDENTE` — registrar `RepoDigest` após o build |
| Digest da imagem frontend | `PENDENTE` — registrar `RepoDigest` após o build |

As versões declaradas do backend FastAPI, frontend, aplicativo mobile e
configuração Expo são `1.2.0`.

## Entradas imutáveis do build

As imagens-base abaixo foram confirmadas no registry em 2026-08-25 e estão
fixadas nos Dockerfiles e no Compose por digest:

| Componente | Referência fixada |
| --- | --- |
| Python | `python:3.11-slim@sha256:3c1dfceb3f1267d4d378e7883cddf35c58757bab98d70bba30b6e02e808fa21d` |
| Node.js | `node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` |
| PostgreSQL | `postgres:15@sha256:29342cb52157b098821961d2c14eec3c019071f56a5d559e990cf07cf541ea9b` |
| Elasticsearch | `elasticsearch:8.13.0@sha256:9d1cd1491778aceca4490de7ec9f205c3633a277df15473e1ea507d13a5270c6` |
| Nginx | `nginx:alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de` |

Os digests de PostgreSQL, Elasticsearch e Nginx correspondem às imagens que já
estavam em execução na produção durante o corte; isso evita introduzir uma
atualização implícita de banco ou proxy apenas porque a tag mudou no registry.
Os pacotes Debian adicionados ao backend são resolvidos no snapshot imutável
`20260824T000000Z`, o mesmo dia-base informado pela imagem Python. Os índices
`debian` e `debian-security` desse snapshot e todos os nove pacotes solicitados
pelo Dockerfile foram confirmados antes do corte.

Os pacotes do backend são instalados de `backend/requirements.lock` com
`--require-hashes`. O wheel CPU do PyTorch usa URL direta oficial e SHA-256,
sem tornar o repositório PyTorch um índice global capaz de sombrear pacotes do
PyPI. O Dockerfile não atualiza `pip` por uma faixa mutável: usa o instalador
que já pertence à imagem Python fixada por digest; `setuptools` é então
instalado na versão e nos hashes definidos pelo próprio lock.

Comando canônico para atualizar o lock deliberadamente:

```bash
uv pip compile backend/requirements.txt \
  --python-version 3.11 \
  --python-platform x86_64-manylinux_2_28 \
  --generate-hashes \
  --emit-index-annotation \
  --upgrade \
  --output-file backend/requirements.lock
```

O lock é específico para Python 3.11, Linux x86_64. Uma alteração nele exige
novo teste de instalação e nova auditoria antes da release.

## Evidência do lock Python

Validação executada em 2026-08-25 no WSL2 Ubuntu x86_64, Python 3.11.15 e pip
26.2.1:

- 109 pacotes instalados com `pip install --require-hashes`;
- `pip check`: `No broken requirements found`;
- imports confirmados: FastAPI 0.141.1, PyTorch 2.13.0+cpu, Transformers
  5.15.1, Sentence Transformers 6.0.0 e Stripe 15.5.1;
- `pip-audit` no ambiente instalado: nenhuma vulnerabilidade conhecida nos
  pacotes que constam do PyPI;
- o `pip-audit` não reconhece a versão local `torch==2.13.0+cpu`; a consulta
  complementar à API OSV para `PyPI/torch` 2.13.0 retornou zero vulnerabilidades
  conhecidas na data da validação.

## Portões para finalizar

| Portão | Estado |
| --- | --- |
| Lock Python instala com hashes no alvo Linux x86_64 | PASSOU |
| Dependências Python sem vulnerabilidade conhecida | PASSOU em 2026-08-25 |
| Versões dos componentes alinhadas em 1.2.0 | PASSOU |
| Imagens-base fixadas por digest | PASSOU |
| Repositório dos pacotes Debian fixado por snapshot | PASSOU |
| Suíte completa após a consolidação final | PENDENTE |
| Builds backend, frontend e mobile a partir do commit final | PENDENTE |
| Digests das imagens construídas registrados acima | PENDENTE |
| Implantação do mesmo commit e migrações sem erro | PENDENTE |
| Smoke test autenticado no navegador e no fluxo mobile | PENDENTE |
| Webhook Stripe real entregue após a correção | PENDENTE |
| Auditoria final dos 1.839 PDFs | PENDENTE |
| Backup pré-implantação e restauração verificável | PENDENTE |

## Fechamento

Antes da tag, substituir todos os campos `PENDENTE` por valores observados,
confirmar que o commit implantado é idêntico ao commit da release e anexar ao
registro operacional as saídas dos testes. Não editar o manifesto depois da
tag; qualquer correção posterior exige uma nova versão.
