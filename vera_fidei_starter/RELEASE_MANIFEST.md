# Manifesto da release 1.3.0

Este documento registra o corte reproduzível do Vera.Fidei 1.3.0. A identidade
canônica da release é a tag anotada `v1.3.0`; o commit exato é obtido por:

```bash
git rev-list -n 1 v1.3.0
```

## Identidade e escopo

| Campo | Valor |
| --- | --- |
| Versão | `1.3.0` |
| Tag canônica | `v1.3.0` anotada |
| Commit da release | commit apontado por `v1.3.0` |
| Commit do runtime implantado | `c6d7515d3e0d1b743d2ae8e812ba9ffec89c541e` |
| Data do corte | `2026-08-28`, `America/Sao_Paulo` |
| Escopo desta entrega | backend, frontend e PWA |
| Mobile | código validado; versão pública permanece `1.2.0` |
| Google Play | integração preparada e desativada; nenhum novo AAB faz parte deste corte |

A release reúne nove commits depois de `v1.2.0`. Ela inclui as páginas públicas
responsivas, santos, orações, avatar sincronizado, login confirmado, biblioteca
com PDFs para o plano Fiel, preparação do Google Play Billing e a eliminação de
carregamentos indefinidos nas operações de rede e de armazenamento local.

O manifesto anterior foi preservado sem alteração em
`docs/releases/v1.2.0.md`; ele continua sendo a fonte canônica dos APK/AAB
assinados da versão 1.2.0.

## Correção de carregamentos indefinidos

O frontend passou a usar uma única implementação de requisição com prazo total,
inclusive durante a leitura do corpo da resposta. Foram cobertos:

- cadastro, login, recuperação e redefinição de senha;
- verificador, pesquisa, histórico, favoritos e administração;
- avatar, perfil, exportação e exclusão de conta;
- assinatura, checkout, portal, Pix e consulta de situação do plano;
- abertura, renderização, extração textual e nova tentativa de páginas PDF;
- IndexedDB bloqueado, abortado ou sem resposta;
- proxy de PDF, downloads, service worker e telemetria.

As telas encerram o estado de carregamento em sucesso, erro, cancelamento ou
tempo excedido. O streaming normal de PDFs grandes permanece sem limite total:
somente a espera pelos cabeçalhos e os corpos de erro possuem prazo.

## Proveniência e reprodução

Os objetos Git dos componentes no commit do runtime e na tag são:

| Componente | Objeto Git |
| --- | --- |
| Backend | `3e10ec82128f0b31d57e2d4f79726509a87a93fe` |
| Frontend | `682477682a195850fcdbecbc25b6cce2c547a2fe` |
| Mobile | `02fcf1db42152df6fe38f70b916a5cd82c74edb7` |

Reprodução local:

```bash
git clone https://github.com/MateusCirineo/Vera.Fidei-Biblioteca.git
cd Vera.Fidei-Biblioteca
git checkout v1.3.0
cd vera_fidei_starter
docker compose build backend frontend
```

O backend instala `requirements.lock` com hashes em Python 3.11/Linux x86_64.
Frontend e mobile usam os respectivos `package-lock.json`. As imagens-base
continuam fixadas por digest conforme os Dockerfiles e o Compose versionados.

## Imagens implantadas e rollback

| Componente | Image ID 1.3.0 |
| --- | --- |
| Backend | `sha256:826f87ffb633c209b323706d42a3f22e40c934b09b4346617a92d92ac1da4876` |
| Frontend | `sha256:ff64385dbaa8bfb17d1421843d908ce07c7a52251d2afb70cc0d89f5e4dbc026` |

Antes da troca, o código de produção foi salvo em
`/var/backups/vera-fidei/code/pre-v1.3.0-20260828T233308Z/code.tar.gz`, com
SHA-256 `6a3cb51a29e404569000669735241171ce35d32cc2d979b85d722f1d82e4fb2a`.
As imagens anteriores foram preservadas como:

- `vera_fidei-backend:pre-v1.3.0-c6d7515`;
- `vera_fidei-frontend:pre-v1.3.0-c6d7515`.

O deploy foi seletivo, sem `--delete`, preservando `.env`, PDFs, banco,
índices, modelos, configuração do rclone, dados e segredos. Não houve migração
destrutiva nem reinicialização do PostgreSQL ou Elasticsearch.

## Evidências automatizadas

| Portão | Resultado no código da release |
| --- | --- |
| Backend | `332 passed`, `3 skipped`, `158 subtests passed` |
| Lock Python | `pip-audit`: 0 vulnerabilidades; OSV para `torch 2.13.0`: 0 |
| Análise Python | Bandit: 0 achados médios ou altos |
| Imagem Linux | `python -m pip check`: nenhuma dependência quebrada |
| Frontend | `36/36` testes, lint e TypeScript aprovados |
| Build Next.js | aprovado, 31 páginas geradas |
| Auditoria frontend | 0 vulnerabilidades, inclusive dependências de desenvolvimento |
| Mobile | `35/35` testes, lint e TypeScript aprovados |
| Expo Doctor | `21/21` verificações aprovadas |
| Bundle Android local | 985 módulos e exportação concluída; não é AAB assinado desta release |
| Auditoria mobile | 0 vulnerabilidades |
| Higiene Git | `git diff --check` aprovado e árvore limpa no corte |

Os três testes ignorados do backend são integrações que exigem instâncias
externas reais de PostgreSQL/Elasticsearch; produção foi validada separadamente.
O `.venv` histórico do computador contém pacotes antigos que não pertencem ao
lock. O gate autoritativo foi executado na nova imagem Linux de produção.

## Smoke real em produção

Executado depois da troca dos containers, em `2026-08-28`:

| Cenário | Resultado observado |
| --- | --- |
| Containers | backend saudável; frontend, Nginx, PostgreSQL e Elasticsearch em execução |
| Rotas públicas | apresentação, login, cadastro, biblioteca, orações e santos responderam 200 |
| Segurança | HSTS, CSP, `nosniff`, `DENY`, política de referência e permissões presentes |
| Documentação interna | `/api/docs` respondeu 404 |
| PWA | manifest e service worker responderam 200; cache `vera-fidei-pwa-v14` |
| Ícones PWA | 192, 512, 1024 e maskable responderam 200 |
| Cadastro e sessão | conta temporária criada; plano `fiel`; logout e novo login aprovados |
| Biblioteca gratuita | conta Fiel abriu a obra canário PG001 (`book_id=32`, `file_id=28`) |
| PDF grande | 211.280.137 bytes; HTTP 206; somente bytes `0-65535` transferidos |
| Verificador | citação de Agostinho: `CONFIRMADA_EXATA`, confiança alta, histórico criado |
| Limpeza do smoke | conta e histórico temporários excluídos; 0 contas de smoke restantes |
| Logs | nenhuma ocorrência 5xx, traceback ou exceção depois do deploy |

A sessão de navegador gráfico integrada ao ambiente de desenvolvimento não
estava disponível. Por isso, a evidência desta release é formada por testes de
componentes, build, chamadas HTTPS autenticadas e o smoke público acima; ela não
é apresentada como inspeção visual em um aparelho físico novo.

## Dados e operações

| Item | Situação no corte |
| --- | --- |
| Acervo | 632 obras, 1.839 registros de PDF e 117.337 trechos |
| Backup PostgreSQL | dump de 115.215.845 bytes com SHA, criado em `2026-08-28T06:19:05Z` |
| Backup externo | monitor confirmou cópia externa saudável depois do deploy |
| Monitor | execução manual e timer de cinco minutos aprovados |
| Stripe | reconciliador executado após o deploy: 3 verificados, 0 alterações, 0 erros |
| Timers | backup local, backup externo, monitor e reconciliador ativos |
| Disco | 72 GB usados de 150 GB, 50% de ocupação |
| Serviços Vera.Fidei falhos | 0 |

O OCR Oriental já havia concluído as oito obras em `2026-08-14` com
`ok=8, failed=0`. O serviço histórico de execução única tentou repetir o lote
antes do Elasticsearch subir no reboot de `2026-08-19`; ele foi desabilitado e
seu estado de falha foi limpo, sem apagar textos ou PDFs.

## PWA e Google Play

O produto distribuível desta release é a PWA 1.3.0. A recomendação de lançamento
é publicar e divulgar primeiro a PWA, acompanhar erros e conversões reais e usar
o mesmo backend durante a homologação Android.

O código `production-play` e o Google Play Billing estão preparados, mas
`GOOGLE_PLAY_ENABLED` permanece desativado. A publicação na Play Store exige,
fora deste repositório:

1. criar produtos e planos-base no Play Console;
2. configurar conta de serviço, permissões e RTDN;
3. preencher ficha da loja, política de dados e assinatura do aplicativo;
4. gerar e enviar um AAB assinado para a faixa interna;
5. testar compra, pendência, restauração, troca, cancelamento, renovação,
   reembolso e revogação com comprador licenciado;
6. habilitar `GOOGLE_PLAY_ENABLED=true` somente depois da homologação.

Portanto, esta release não afirma que o aplicativo já foi publicado ou aprovado
pela Play Store. Lançamento simultâneo adicionaria risco sem benefício técnico;
PWA primeiro e Play depois da faixa interna é o corte recomendado.

## Limites editoriais declarados

- Existem 37.783 trechos de OCR ainda não conferidos nas coleções PG/PL/PO:
  9.235 PG, 17.862 PL e 10.686 PO.
- Há 102 trechos visuais marcados como verificados, 2 passagens verificadas e
  69 revisões de página registradas.
- OCR não conferido permanece bloqueado como citação literal e só pode fornecer
  localização no PDF. Não se afirma revisão palavra por palavra do acervo.
- A revisão editorial pode continuar depois do lançamento sem bloquear a PWA,
  pois o comportamento público é fail-closed.
- A validação dos artefatos móveis da versão 1.2.0 continua documentada no
  manifesto anterior; nenhum novo APK, AAB ou IPA foi assinado neste corte.

## Decisão de lançamento

O corte PWA/API 1.3.0 está aprovado tecnicamente para divulgação, dentro dos
limites explicitados acima. Google Play permanece uma entrega posterior e só
deve ser anunciada depois da homologação externa e dos testes de compra na loja.
