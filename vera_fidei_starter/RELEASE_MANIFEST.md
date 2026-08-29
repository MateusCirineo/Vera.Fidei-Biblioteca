# Manifesto da release 1.3.2

Este documento registra o corte reproduzível do Vera.Fidei 1.3.2. A identidade
canônica da release é a tag anotada `v1.3.2`; o commit exato é obtido por:

```bash
git rev-list -n 1 v1.3.2
```

O manifesto completo das funcionalidades da PWA 1.3.0 permanece disponível no
commit apontado pela tag `v1.3.0`. A versão 1.3.2 inclui a migração de domínio,
a robustez de sessão/PWA da 1.3.1 e o hotfix de centralização responsiva das
páginas do visualizador de PDF, sem migração destrutiva de dados.

## Identidade e escopo

| Campo | Valor |
| --- | --- |
| Versão da PWA | `1.3.2` |
| Tag canônica | `v1.3.2` anotada |
| Data do corte | `2026-08-29`, `America/Sao_Paulo` |
| Domínio canônico | `https://verafidei.com.br` |
| Domínio de transição | `https://verafidei.oialfred.com` |
| Escopo | backend, frontend, PWA, proxy e monitoramento |
| Mobile | código aponta ao domínio novo; versão pública continua `1.2.0` |
| Google Play | integração preparada e desativada até homologação externa |

## Migração de domínio

- O domínio raiz e `www` apontam para `5.161.115.95` por DNS autoritativo da
  Locaweb.
- `www.verafidei.com.br` redireciona permanentemente ao domínio raiz,
  preservando caminho e consulta.
- HTTP redireciona para HTTPS.
- O certificado Let's Encrypt cobre o domínio raiz e `www` e é válido até
  `2026-11-27`.
- O domínio antigo permanece funcional durante a transição e usa a mesma
  aplicação, banco, acervo, PDFs e assinaturas.
- O frontend usa `/api` na mesma origem; nenhuma URL privada do Docker é
  exposta ao navegador.
- O backend permite CORS apenas para o domínio novo, `www`, o domínio legado e
  as origens operacionais explicitamente configuradas. Origem não confiável é
  recusada.

## Sessão, cobrança e PWA

- Login web continua usando cookie de sessão `Secure` e `HttpOnly`, separado
  por host.
- Checkout, Pix e portal Stripe retornam ao host seguro onde o fluxo começou;
  `www` volta ao domínio raiz. Hosts desconhecidos caem no canônico e não podem
  produzir redirecionamento aberto.
- O service worker foi atualizado para o cache `vera-fidei-pwa-v15` e preserva
  respostas `opaqueredirect` sem tentar reconstruir o corpo.
- A rota `/` agora renderiza diretamente a mesma apresentação de
  `/apresentacao`, com HTTP 200 e sem redirecionamento. Isso também recupera
  instalações antigas ainda controladas pelo service worker anterior.

## Visualizador de PDF

- A página renderizada e sua camada de destaques compartilham um contêiner de
  largura real centralizado no espaço disponível.
- O espaço reservado da renderização progressiva acompanha a largura da página
  e o zoom, evitando deslocamento lateral durante o carregamento.
- Quando o zoom torna a página maior que a tela, a rolagem horizontal continua
  disponível; busca, navegação, destaques e carregamento parcial foram mantidos.

## Implantação e rollback

O deploy foi seletivo, sem `--delete`, preservando `.env`, segredos, PDFs,
banco PostgreSQL, Elasticsearch, índices, rclone, backups e arquivos do acervo.
PostgreSQL e Elasticsearch não foram recriados.

| Componente | Image ID 1.3.2 |
| --- | --- |
| Backend | `sha256:30724aa71bf804f04e4a792cdc4cafd86bd98b009d61111458f5d4cbf784fe31` |
| Frontend | `sha256:1f0a227be270c7dc84a5af1cf73d038a82d519f5a291f39f0089d82a0d1f6e47` |

O backup principal dos 32 destinos substituídos foi salvo em
`/opt/vera_fidei/backups/dual-domain-final-active-before-20260829T024216Z.tgz`,
com SHA-256
`d931fad81f436fdee54d5c302776efd5499015c0e85c3cb278e317f4cc675119`.
Também foram criados backups independentes antes da ativação TLS, do hotfix do
service worker, da raiz sem redirecionamento e do ajuste de versão do frontend.
O hotfix do visualizador possui ainda o backup
`/opt/vera_fidei/backups/pdf-center-before-20260829T003039.tgz`, com SHA-256
`90c8083711139b862f25b1bf22efea1a4a234c790578be6d0de48423d900719b`.

## Evidências automatizadas

| Portão | Resultado |
| --- | --- |
| Backend | `333 passed`, `3 skipped` |
| Domínio, Stripe/webhook e Google Play | `54/54` testes relevantes |
| Frontend | `44/44` testes e lint aprovados |
| Build Next.js | TypeScript aprovado e 31 rotas geradas |
| Dependências frontend | `npm ci`: 0 vulnerabilidades |
| Mobile | `36/36` testes, lint e TypeScript aprovados |
| Compose | configuração de produção válida |
| Higiene Git | `git diff --check` aprovado |

## Smoke real em produção

| Cenário | Resultado observado |
| --- | --- |
| Rotas públicas | raiz, apresentação, biblioteca, login, planos, orações e santos: HTTP 200 |
| Raiz da PWA | HTTP 200 sem `Location`; conteúdo visual equivalente a `/apresentacao` |
| Assets | CSS e JavaScript reais: HTTP 200 e tipos corretos |
| PWA | manifest HTTP 200; service worker `vera-fidei-pwa-v15` HTTP 200 |
| Segurança | HSTS, CSP, `nosniff`, `DENY`, política de referência e permissões presentes |
| CORS | novo domínio, `www` e legado aceitos exatamente; origem hostil recusada |
| Login novo | HTTP 200; sessão confirmada; cookie `Secure` e `HttpOnly` |
| Login legado | HTTP 200; sessão confirmada; cookie `Secure` e `HttpOnly` |
| Plano gratuito | conta temporária carregou plano `fiel` |
| PDF PG001 | HTTP 206; 65.536 bytes; `application/pdf` |
| Layout do PDF | bundle público contém o contrato de centralização e largura responsiva |
| Verificador | `CONFIRMADA_EXATA`, confiança `Alta` |
| Exclusão | conta removida e sessão do outro host invalidada |
| Limpeza | 0 contas e 0 históricos de smoke restantes |
| Containers | backend saudável; frontend, Nginx, PostgreSQL e Elasticsearch ativos |
| Monitor | execução manual aprovada; unidade success; timer habilitado e ativo |
| Logs após a troca | 0 marcadores de erro no backend/frontend e 0 respostas Nginx 5xx |
| Disco | 53% utilizado; 69 GB disponíveis |

A sessão gráfica integrada de navegador não estava disponível neste ambiente.
Por isso, a validação visual automatizada foi feita pela equivalência do HTML e
pelos assets reais; a validação funcional usou HTTPS e sessão autenticada de
produção. Isso não é apresentado como teste em um aparelho físico novo.

## Limites preservados

- A release não afirma revisão palavra por palavra de todo o OCR das coleções
  PG/PL/PO. Texto não conferido continua bloqueado como citação literal.
- Nenhuma compra real foi criada durante o smoke. O retorno por host da Stripe
  foi coberto por testes automatizados para não cobrar nem alterar assinaturas.
- O envio de e-mail continua usando o remetente já validado; ele não foi
  trocado para o domínio novo sem configuração SPF/DKIM/DMARC específica.
- Google Play permanece desativado até produtos, RTDN, AAB assinado e compras
  licenciadas serem homologados no Play Console.

## Reprodução

```bash
git clone https://github.com/MateusCirineo/Vera.Fidei-Biblioteca.git
cd Vera.Fidei-Biblioteca
git checkout v1.3.2
cd vera_fidei_starter
docker compose build backend frontend
```

## Decisão

A PWA/API 1.3.2 está aprovada tecnicamente para divulgação em
`https://verafidei.com.br`. O domínio antigo pode permanecer durante a transição
e depois ser redirecionado quando a base instalada tiver atualizado o service
worker.
