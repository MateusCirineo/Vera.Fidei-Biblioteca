# Publicação futura no Google Play

Este documento é o runbook operacional do perfil EAS `production-play`. Ele
descreve o estado que precisa existir antes de vender assinaturas pelo Google
Play, mas **não comprova que o Play Console, o Google Cloud ou a produção já
estejam configurados**.

Enquanto todos os portões deste documento não tiverem evidência registrada:

- mantenha `GOOGLE_PLAY_ENABLED=false`;
- não distribua `production-play` fora de testes internos;
- mantenha `production` como o AAB leitor atual;
- mantenha `preview` como o APK de distribuição direta com Stripe.

O perfil `production-play` é exclusivamente para a loja e deve usar a cobrança
nativa do Google Play. Ele não pode abrir checkout, portal Stripe nem link
externo de compra.

## Identidade do aplicativo e catálogo

O package name esperado pelo backend é `com.verafidei.app`. Antes do primeiro
AAB, confirme que esse mesmo identificador está explícito na configuração Expo,
no artefato assinado e no aplicativo criado no Play Console. Divergência de
package name impede a validação das compras.

O catálogo fixo é:

| Plano do Vera Fidei | Product ID do Google Play | Base plan ID | Renovação |
| --- | --- | --- | --- |
| Catequista | `vf.sub.catequista` | `monthly` | mensal automática |
| Apologeta | `vf.sub.apologeta` | `monthly` | mensal automática |
| Patrístico | `vf.sub.patristico` | `monthly` | mensal automática |
| Magistério | `vf.sub.magisterio` | `monthly` | mensal automática |

Trate product IDs e base plan IDs como imutáveis. Revise grafia, package name e
plano associado antes de ativá-los; não use IDs temporários. O preço e a moeda
mostrados no aplicativo devem vir de `ProductDetails` do Google Play, nunca de
um valor localizado escrito no código.

No Play Console, crie os quatro produtos de assinatura, adicione a cada um o
plano-base `monthly`, configure preços, países e impostos e só então ative os
planos-base. O JSON esperado pelo backend é:

```json
{
  "catequista": {
    "product_id": "vf.sub.catequista",
    "base_plan_id": "monthly"
  },
  "apologeta": {
    "product_id": "vf.sub.apologeta",
    "base_plan_id": "monthly"
  },
  "patristico": {
    "product_id": "vf.sub.patristico",
    "base_plan_id": "monthly"
  },
  "magisterio": {
    "product_id": "vf.sub.magisterio",
    "base_plan_id": "monthly"
  }
}
```

## Separação dos perfis EAS

| Perfil | Distribuição | Cobrança permitida | Situação |
| --- | --- | --- | --- |
| `preview` | APK interno/direto | Stripe | permanece como está |
| `production` | AAB da loja em modo `reader` | nenhuma no app | permanece como está |
| `production-play` | AAB da loja em modo `play` | Google Play Billing | futuro; bloqueado até homologação |

Nunca transforme `production` em atalho para `production-play`. A separação
permite retirar a compra nativa sem reintroduzir links de cobrança externa no
binário leitor.

## Contas de serviço e privilégios mínimos

Use duas contas de serviço próprias e duas identidades gerenciadas pelo Google:

1. **Android Publisher:** uma conta exclusiva para o backend consultar e
   confirmar assinaturas. Habilite a Google Play Developer API, convide/vincule
   a conta no Play Console e limite o acesso somente ao aplicativo Vera Fidei.
   Conceda apenas as permissões do Play Console necessárias para visualizar
   dados financeiros/pedidos/cancelamentos e gerenciar pedidos e assinaturas.
2. **Push OIDC:** uma conta exclusiva, por exemplo
   `vera-fidei-rtdn-push@PROJECT_ID.iam.gserviceaccount.com`, usada pelo Pub/Sub
   para assinar o token OIDC do push. Ela não precisa da chave JSON do Android
   Publisher e não deve receber permissões do Play Console.
3. **Publicador do Google Play:** conceda
   `roles/pubsub.publisher` no tópico RTDN para
   `google-play-developer-notifications@system.gserviceaccount.com`.
4. **Agente do Pub/Sub:** para emitir o token OIDC, conceda
   `roles/iam.serviceAccountTokenCreator` ao agente
   `service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com`. Para a fila
   de mensagens mortas, ele também precisa de `roles/pubsub.publisher` no
   tópico de dead-letter e `roles/pubsub.subscriber` na assinatura RTDN.

O operador que cria ou altera a assinatura push precisa poder atuar como a
conta Push OIDC (`iam.serviceAccounts.actAs`). Não dê essa permissão ao runtime
do Vera Fidei.

Revise essas permissões no IAM e no Play Console depois da configuração. Não
conceda Owner, Editor ou acesso global a todos os aplicativos por conveniência.

## Credencial e segredos fora do Git

A chave JSON do Android Publisher é somente para leitura no backend. Ela não
pode entrar no Git, `.env`, EAS, imagem Docker, backup de código, artefato de
build ou logs. Guarde-a em um diretório de segredos do servidor e monte-a no
container como `read_only`.

No Compose atual, copie a credencial para o host em:

```text
backend/secrets/google-play-service-account.json
```

A pasta `backend/secrets` inteira é montada somente para leitura em
`/run/secrets/vera-fidei`. Portanto, o caminho visível dentro do container é:

```text
/run/secrets/vera-fidei/google-play-service-account.json
```

No host, use proprietário/grupo compatíveis com o UID do processo do backend e
modo `0400` ou `0440`. Valide de dentro do container que o arquivo é legível,
mas nunca use `cat`, não copie seu conteúdo para o terminal e não o inclua em
diagnósticos.

Gere a chave Fernet e o segredo HMAC diretamente em um arquivo novo com modo
`0600`. Execute com o Python do backend, onde `cryptography` já está instalado:

```bash
sudo install -d -o root -g root -m 0700 /etc/vera-fidei/google-play
sudo env VF_PLAY_SECRET_FILE=/etc/vera-fidei/google-play/runtime.env python3 - <<'PY'
import os
import secrets
from cryptography.fernet import Fernet

path = os.environ["VF_PLAY_SECRET_FILE"]
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="ascii", newline="\n") as target:
    target.write(
        "GOOGLE_PLAY_TOKEN_ENCRYPTION_KEY="
        + Fernet.generate_key().decode("ascii")
        + "\n"
    )
    target.write(
        "GOOGLE_PLAY_ACCOUNT_HMAC_SECRET="
        + secrets.token_urlsafe(48)
        + "\n"
    )
PY
```

O comando não imprime os valores e falha se o arquivo já existir. Injete-os no
gerenciador de segredos ou no ambiente de implantação sem abrir o conteúdo em
saída de CI. A chave Fernet cifra tokens de compra armazenados e o HMAC deriva a
identidade ofuscada do usuário; o código atual não possui chaveiro para rotação.
Não troque nenhum dos dois segredos sem uma migração testada dos dados antigos.

## Variáveis do backend

Prepare a flag de ativação e as 14 variáveis de configuração abaixo com
`GOOGLE_PLAY_ENABLED=false`. Valores entre `<...>` são referências
operacionais, não valores literais:

```dotenv
GOOGLE_PLAY_ENABLED=false
GOOGLE_PLAY_PACKAGE_NAME=com.verafidei.app
GOOGLE_PLAY_PRODUCTS_JSON={"catequista":{"product_id":"vf.sub.catequista","base_plan_id":"monthly"},"apologeta":{"product_id":"vf.sub.apologeta","base_plan_id":"monthly"},"patristico":{"product_id":"vf.sub.patristico","base_plan_id":"monthly"},"magisterio":{"product_id":"vf.sub.magisterio","base_plan_id":"monthly"}}
GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=/run/secrets/vera-fidei/google-play-service-account.json
GOOGLE_PLAY_TOKEN_ENCRYPTION_KEY=<segredo-fernet>
GOOGLE_PLAY_ACCOUNT_HMAC_SECRET=<segredo-hmac>
GOOGLE_PLAY_REQUIRE_OBFUSCATED_ACCOUNT_ID=true
GOOGLE_PLAY_PUBSUB_AUDIENCE=https://verafidei.com.br/api/billing/google-play/rtdn
GOOGLE_PLAY_PUBSUB_SERVICE_ACCOUNT_EMAIL=vera-fidei-rtdn-push@<PROJECT_ID>.iam.gserviceaccount.com
GOOGLE_PLAY_PUBSUB_SUBSCRIPTION=projects/<PROJECT_ID>/subscriptions/<RTDN_SUBSCRIPTION_ID>
GOOGLE_PLAY_HTTP_TIMEOUT_SECONDS=15
GOOGLE_PLAY_RECONCILE_STALE_HOURS=6
GOOGLE_PLAY_RECONCILE_BATCH_SIZE=200
GOOGLE_PLAY_SYNC_RATE_LIMIT=20
GOOGLE_PLAY_SYNC_RATE_WINDOW_SECONDS=60
```

Esses são os nomes lidos por `backend/core/config.py`. O caminho em
`GOOGLE_PLAY_SERVICE_ACCOUNT_FILE` é o caminho **dentro** do container. A
audience precisa ser exatamente a mesma usada no token OIDC da assinatura
push. `GOOGLE_PLAY_PUBSUB_SUBSCRIPTION` precisa ser o nome completo que chega no
envelope Pub/Sub. Os valores `15`, `6`, `200`, `20` e `60` são os padrões
atuais. O limite de sincronização conta tokens de compra, compartilhado entre
`sync` e `restore`, por conta e por janela; alterá-los exige teste de timeout,
carga, quota da Developer API e tempo máximo de convergência do reconciliador.

## Contrato de preflight

Antes de iniciar uma compra, o aplicativo deve consultar `GET /billing/status`.
A resposta inclui `current_period_end`, em ISO 8601 ou `null`, proveniente do
item/assinatura selecionado pelo resolvedor do backend. Uma assinatura
`canceled` continua válida somente enquanto essa data estiver no futuro. Um
checkout Stripe vencido é devolvido como `checkout_expired`, nunca como
`checkout_pending` recuperável.

A conta proprietária recebe `plan=magisterio`, `billing_status=owner` e
`current_period_end=null`. Para ela, o catálogo Google Play responde
`enabled=false`, sem produtos nem identificador ofuscado, e `sync`/`restore`
recusam qualquer token. A conta proprietária não deve ser usada em testes de
licença ou compra.

## Google Play Developer API

- [ ] Habilitar a Google Play Developer API no projeto Google Cloud correto.
- [ ] Vincular o projeto Cloud ao Play Console correto.
- [ ] Criar a conta Android Publisher sem papéis amplos no projeto.
- [ ] Dar acesso somente ao package `com.verafidei.app` no Play Console.
- [ ] Conceder apenas visualização dos dados de pedidos necessários e gestão de
      pedidos/assinaturas.
- [ ] Montar a chave JSON somente no backend e confirmar que não aparece em
      `docker inspect`, artefatos, backups de código ou EAS.
- [ ] Com `GOOGLE_PLAY_ENABLED=false`, fazer um teste isolado da credencial em
      ambiente de homologação e registrar apenas sucesso/erro, nunca tokens.

Uma RTDN não é a fonte final do estado da assinatura. Ela informa que algo
mudou; o backend deve consultar `purchases.subscriptionsv2.get` e decidir o
direito com a resposta autenticada da Developer API, como o código atual faz.

## RTDN, Pub/Sub, OIDC e dead-letter

Topologia recomendada:

```text
Google Play -> tópico RTDN -> assinatura push autenticada -> backend
                              \
                               -> tópico dead-letter -> assinatura de inspeção
```

Nomes sugeridos:

```bash
PROJECT_ID=<projeto-cloud>
PROJECT_NUMBER=<numero-do-projeto>
RTDN_TOPIC=vera-fidei-google-play-rtdn
RTDN_SUB=vera-fidei-google-play-rtdn-push
RTDN_DLQ_TOPIC=vera-fidei-google-play-rtdn-dlq
RTDN_DLQ_SUB=vera-fidei-google-play-rtdn-dlq-inspect
PUSH_SA=vera-fidei-rtdn-push@${PROJECT_ID}.iam.gserviceaccount.com
PUSH_ENDPOINT=https://verafidei.com.br/api/billing/google-play/rtdn
```

Crie os recursos e aplique as permissões com o projeto explicitamente
selecionado. Revise cada variável antes de executar:

```bash
gcloud services enable androidpublisher.googleapis.com pubsub.googleapis.com \
  --project="${PROJECT_ID}"

gcloud pubsub topics create "${RTDN_TOPIC}" --project="${PROJECT_ID}"
gcloud pubsub topics create "${RTDN_DLQ_TOPIC}" --project="${PROJECT_ID}"

gcloud pubsub topics add-iam-policy-binding "${RTDN_TOPIC}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:google-play-developer-notifications@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

gcloud iam service-accounts add-iam-policy-binding "${PUSH_SA}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"

gcloud pubsub subscriptions create "${RTDN_SUB}" \
  --project="${PROJECT_ID}" \
  --topic="${RTDN_TOPIC}" \
  --push-endpoint="${PUSH_ENDPOINT}" \
  --push-auth-service-account="${PUSH_SA}" \
  --push-auth-token-audience="${PUSH_ENDPOINT}" \
  --min-retry-delay=10s \
  --max-retry-delay=600s \
  --message-retention-duration=7d

gcloud pubsub topics add-iam-policy-binding "${RTDN_DLQ_TOPIC}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

gcloud pubsub subscriptions add-iam-policy-binding "${RTDN_SUB}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

gcloud pubsub subscriptions update "${RTDN_SUB}" \
  --project="${PROJECT_ID}" \
  --dead-letter-topic="${RTDN_DLQ_TOPIC}" \
  --max-delivery-attempts=10

gcloud pubsub subscriptions create "${RTDN_DLQ_SUB}" \
  --project="${PROJECT_ID}" \
  --topic="${RTDN_DLQ_TOPIC}" \
  --message-retention-duration=7d
```

No Play Console, associe o tópico completo
`projects/PROJECT_ID/topics/vera-fidei-google-play-rtdn` e envie a mensagem de
teste. Não habilite payload unwrapping: o endpoint atual exige o envelope
Pub/Sub com `message` e `subscription`. O backend também exige:

- assinatura válida do token OIDC;
- `aud` exatamente igual a `GOOGLE_PLAY_PUBSUB_AUDIENCE`;
- e-mail verificado exatamente igual a
  `GOOGLE_PLAY_PUBSUB_SERVICE_ACCOUNT_EMAIL`;
- nome completo da assinatura exatamente igual a
  `GOOGLE_PLAY_PUBSUB_SUBSCRIPTION`;
- package name exatamente igual a `GOOGLE_PLAY_PACKAGE_NAME`.

Crie alerta para mensagens na dead-letter, tentativas repetidas, respostas não
2xx e atraso entre o evento do Play e o processamento. Uma mensagem na DLQ não
pode ser descartada antes da reconciliação do estado pela Developer API.

## Checklist do Play Console

Nada nesta lista deve ser marcado sem conferência direta no Console.

### Aplicativo e políticas

- [ ] Criar/confirmar o app Android com package `com.verafidei.app`.
- [ ] Confirmar que o AAB final tem `targetSdkVersion` 36; a exigência para
      novos apps e atualizações passa a API 36 em 31 de agosto de 2026.
- [ ] Ativar Play App Signing, proteger a upload key e registrar responsáveis e
      procedimento de recuperação.
- [ ] Preencher **App content** e todas as declarações aplicáveis com dados
      reais: anúncios, público-alvo, acesso ao app, permissões, conteúdo de
      saúde/notícias e demais formulários que o Console apresentar.
- [ ] Preencher **Data safety** de acordo com a telemetria, autenticação,
      suporte, cobrança e SDKs efetivamente presentes no AAB; não copiar uma
      declaração genérica.
- [ ] Publicar e informar a política de privacidade em
      `https://verafidei.com.br/privacidade`, depois testar a URL fora de
      uma sessão autenticada.
- [ ] Informar uma URL de exclusão de conta que leve diretamente ao fluxo web.
      O Vera Fidei possui exclusão autenticada em `/perfil`, mas a URL declarada
      ao Google só pode ser usada depois de validar, fora do app, que cumpre o
      requisito de iniciar a exclusão e explica os dados apagados ou retidos.
- [ ] Concluir o questionário de classificação indicativa e conferir o
      resultado antes de publicar.
- [ ] Fornecer instruções e uma conta de revisão funcional se qualquer conteúdo
      exigir login; nunca usar conta pessoal do proprietário.

### Página da loja e comercial

- [ ] Preparar nome, descrição curta, descrição completa, categoria, contato e
      traduções da página da loja.
- [ ] Enviar ícone de alta resolução de 512 x 512, feature graphic de
      1024 x 500 e capturas reais do aplicativo nos formatos exigidos; não usar
      telas que prometam recursos ainda bloqueados.
- [ ] Conferir países/regiões, disponibilidade de cada assinatura, moedas,
      preços localizados, períodos, eventuais ofertas e datas de vigência.
- [ ] Conferir perfil de pagamentos, dados fiscais, tributos e conta bancária.
- [ ] Ativar os quatro produtos e o base plan `monthly` apenas depois de revisar
      a associação entre product ID e plano do Vera Fidei.

### Trilhas e lançamento

- [ ] Enviar primeiro o AAB `production-play` à trilha interna.
- [ ] Adicionar testadores de licença e contas separadas para cada cenário.
- [ ] Executar pré-lançamento e corrigir falhas, ANRs, crashes e problemas de
      acessibilidade relevantes.
- [ ] Promover para teste fechado somente depois da matriz deste documento.
- [ ] Fazer nova revisão de políticas, Data safety, preços e artefato antes da
      produção.
- [ ] Para a primeira publicação em produção, lembrar que staged rollout não se
      aplica como proteção equivalente a atualizações. Em atualizações futuras,
      usar porcentagem inicial pequena, monitorar e ampliar gradualmente.

## Testes obrigatórios de cobrança

Use **Internal testing**, testadores de licença e **Play Billing Lab**. Instale
sempre pela página da trilha do Google Play com a mesma conta testadora; um APK
local não reproduz todo o comportamento da loja. Registre o product ID, estado
retornado pela Developer API, entitlement no backend, tela observada e horário.

| Cenário | Resultado obrigatório |
| --- | --- |
| Compra aprovada | Backend valida o token, vincula à conta ofuscada, reconhece a compra e libera exatamente o plano comprado. |
| Compra pendente | Nenhum entitlement pago até o Play confirmar o pagamento; UI informa pendência sem loop infinito. |
| Renovação | RTDN é idempotente, consulta o estado atual e estende o período sem duplicar assinatura. |
| Período de carência | Mantém o acesso conforme a política definida e mostra estado de cobrança recuperável. |
| Account hold | Retira o acesso pago e o restaura somente após confirmação do Play. |
| Cancelamento | Mantém o acesso apenas até a expiração confirmada; não trata cancelamento como reembolso imediato. |
| Expiração | Retira o entitlement e recalcula o plano do usuário. |
| Pausa e retomada | Pausa não libera acesso; retomada só libera após estado ativo confirmado. |
| Restaurar compra | Após reinstalação e novo login, a compra da mesma conta é reencontrada e sincronizada sem cobrar novamente. |
| Reembolso | O estado consultado/RTDN remove o entitlement quando aplicável e não deixa plano pago órfão. |
| Revogação/voided purchase | Remove imediatamente o entitlement, conserva trilha de auditoria e não aceita replay conflitante. |
| Upgrade | Usa o token vinculado retornado pelo Play, substitui o plano anterior e não deixa dois direitos concorrentes. |
| Downgrade | Respeita o momento efetivo configurado no Play e troca o plano apenas quando o estado confirmado exigir. |
| Compra de outra conta | `obfuscatedExternalAccountId` divergente é recusado sem transferir a assinatura. |
| RTDN duplicada | Retorna sucesso idempotente e não duplica evento, assinatura ou item. |
| RTDN fora de ordem | O estado atual da Developer API prevalece; evento antigo não reativa direito revogado ou expirado. |
| OIDC ausente/inválido | Endpoint rejeita sem consultar ou alterar assinatura. |
| Audience/e-mail/subscription divergente | Endpoint rejeita sem persistir direito. |
| Falha temporária da Developer API | Pub/Sub tenta novamente; após o limite, a mensagem chega à DLQ e gera alerta. |
| Stripe já existente | A regra de entitlement escolhe um resultado determinístico, sem downgrade indevido nem cobrança cruzada. |
| Exclusão de conta | Assinatura Play é tratada conforme a política antes de apagar o usuário; não fica cobrança órfã. |

Também valide troca de rede, fechamento do app durante o pagamento, toque duplo,
retorno após autenticação expirada, restauração em outro aparelho e preço/moeda
vindos do Play. Nenhum teste pode usar credenciais ou conta do proprietário em
gravações, logs ou capturas compartilhadas.

## Portões de ativação

Execute na ordem:

1. Confirmar package name, target API 36, Play Billing Library suportada e AAB
   assinado do perfil `production-play`.
2. Rodar em `mobile/`: `npm ci`, `npm run typecheck`, `npm run lint`, `npm test`,
   `npm audit --omit=dev` e `npx expo-doctor`.
3. Rodar a suíte do backend, incluindo configuração, catálogo, sincronização,
   restauração, RTDN, idempotência, reembolso/revogação e entitlements.
4. Verificar que o artefato EAS não contém `.env`, PDFs, dados do backend,
   credenciais, tokens ou histórico Git.
5. Configurar Play Console, Developer API, Pub/Sub, OIDC, dead-letter, alertas e
   as 14 variáveis de configuração mantendo `GOOGLE_PLAY_ENABLED=false` na
   produção pública.
6. Implantar o backend com o arquivo JSON montado somente para leitura e validar
   que a inicialização falha fechada diante de qualquer configuração ausente.
7. Enviar o AAB à trilha interna e cadastrar testadores de licença. Somente
   depois dos testes automatizados e de segurança anteriores, abrir uma janela
   controlada de homologação com `GOOGLE_PLAY_ENABLED=true`, ainda sem acesso
   público ao perfil `production-play`.
8. Enviar a mensagem RTDN de teste pelo Play Console e executar integralmente a
   matriz de cobrança, inclusive DLQ, reconciliação, restore, refund, revoke,
   upgrade, downgrade e exclusão de conta. Se qualquer caso falhar, voltar a
   flag para `false` e corrigir antes de repetir.
9. Manter observação sem erro no período definido pela equipe e conferir backup
   e restauração do banco antes da ativação.
10. Somente com todas as evidências end-to-end aprovadas, manter
    `GOOGLE_PLAY_ENABLED=true` pelo processo normal de secrets/deploy, reiniciar
    apenas o backend necessário e repetir smoke tests de produção.
11. Liberar `production-play` primeiro no teste fechado. Produção exige uma
    decisão separada baseada nos resultados, políticas e monitoramento.

Ativar o backend não autoriza publicar o AAB, e publicar um AAB interno não
autoriza ativar o backend. Os dois portões são independentes.

## Rollback

Em incidente de compra ou validação:

1. interrompa a ampliação da trilha e pause a nova versão no Play Console;
2. volte os usuários para o binário `production` leitor quando aplicável;
3. em emergência, defina `GOOGLE_PLAY_ENABLED=false` pelo deploy normal para
   impedir novas sincronizações, ciente de que isso também pausa RTDN e restore;
4. não apague produtos, base plans, tokens cifrados, eventos, assinaturas ou
   tópicos Pub/Sub;
5. preserve a DLQ e reconcilie cada assinatura com a Developer API antes de
   reativar;
6. documente impacto, janela, eventos afetados e resultado da reconciliação.

Um rollback não deve revogar manualmente usuários cuja compra continua válida.

## Registro de evidências

Para cada homologação, registre em local protegido:

- data, operador e ambiente;
- commit/tag, versão, EAS build ID, `versionCode` e hash do AAB;
- package name, product ID/base plan e país da conta testadora;
- casos executados e resultado esperado/observado;
- IDs de evento e order ID mascarados, nunca purchase token;
- resposta HTTP e latência do RTDN sem corpo sensível;
- profundidade da assinatura e da DLQ;
- confirmação de backup/restauração;
- links internos para capturas e aprovação final.

## Fontes oficiais

- [Preparação do Google Play Billing](https://developer.android.com/google/play/billing/getting-ready)
- [Google Play Developer API: primeiros passos](https://developers.google.com/android-publisher/getting_started)
- [Referência de Real-time Developer Notifications](https://developer.android.com/google/play/billing/rtdn-reference)
- [Autenticação de push do Pub/Sub](https://docs.cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
- [Dead-letter topics do Pub/Sub](https://docs.cloud.google.com/pubsub/docs/dead-letter-topics)
- [Teste do Google Play Billing](https://developer.android.com/google/play/billing/test)
- [Prazos da Play Billing Library](https://developer.android.com/google/play/billing/deprecation-faq)
- [Requisitos de target API](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Exclusão de conta](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Classificação indicativa](https://support.google.com/googleplay/android-developer/answer/9859655)
- [Recursos da página da loja](https://support.google.com/googleplay/android-developer/answer/9866151)
- [Assinaturas, base plans, países e preços](https://support.google.com/googleplay/android-developer/answer/140504)
- [Impostos e compliance](https://support.google.com/googleplay/android-developer/answer/10463498)
- [Play App Signing](https://developer.android.com/studio/publish/app-signing)
- [Preparar e lançar uma versão](https://support.google.com/googleplay/android-developer/answer/9859348)
- [Staged rollout](https://support.google.com/googleplay/android-developer/answer/6346149)
