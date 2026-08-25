# Estado da preparação para o Google Play

## Foi implementado

- Perfil `production-play` para gerar AAB da loja.
- Pacote oficial `com.verafidei.app`.
- Assinaturas Catequista, Apologeta, Patrístico e Magistério.
- Compra, restauração, renovação, cancelamento, upgrade, downgrade, reembolso e revogação.
- Verificação autoritativa no backend antes de liberar o plano.
- Confirmação automática da compra, RTDN e reconciliador.
- Proteção contra cobrança simultânea pelo Stripe e Google Play.
- Nenhum checkout Stripe ou link externo no aplicativo da Play, conforme a [política do Google Play](https://support.google.com/googleplay/android-developer/answer/10281818?hl=pt-BR).
- Tokens de compra criptografados e tratamento seguro de pagamentos pendentes.
- Google Play permanece desativado por padrão para não afetar a PWA nem a produção atual.

## Validação concluída

- Backend: **315 testes aprovados**, 3 integrações externas ignoradas e 143 subtestes aprovados.
- Mobile: **35/35 testes aprovados**.
- Expo Doctor: **21/21 verificações aprovadas**.
- Bundle Android: **985 módulos**, gerado corretamente.
- Frontend: lint aprovado, build das **31 rotas** e nenhuma vulnerabilidade de produção encontrada.
- Auditoria independente: nenhum bloqueador interno.
- Commit local: `977dec7` — `feat: prepare Google Play billing`.
- Repositório limpo. Nada foi enviado ou implantado em produção.

## O que continuará necessário no dia do lançamento

1. Criar os quatro produtos e planos-base no Play Console.
2. Configurar conta de serviço, permissões e notificações RTDN.
3. Preencher ficha da loja, segurança de dados e assinatura do aplicativo.
4. Gerar o AAB assinado e enviá-lo para uma faixa interna.
5. Testar com comprador licenciado: compra, pendência, restauração, troca de plano, cancelamento, renovação e reembolso. O próprio Google exige esses testes em ambiente da loja; compras nativas também não funcionam pelo Expo Go. Consulte os [testes do Google Play Billing](https://developer.android.com/google/play/billing/test) e o [guia Expo para compras](https://docs.expo.dev/guides/in-app-purchases/).
6. Somente depois habilitar `GOOGLE_PLAY_ENABLED=true`.
