# Planos E Assinaturas

## Visão Geral

O Vera.Fidei possui um plano gratuito e planos pagos mensais.

Os planos pagos existem para sustentar infraestrutura, processamento, armazenamento de PDFs, verificação de citações, manutenção e expansão do acervo.

## Planos

| Plano | Preço | Limite | Indicação |
|---|---:|---:|---|
| Fiel | Grátis | 10 verificações/mês | Uso pessoal |
| Catequista | R$ 9,90/mês | 25 verificações/mês | Aulas e grupos |
| Apologeta | R$ 29,99/mês | 50 verificações/mês | Pesquisa e defesa da fé |
| Patrístico | R$ 59,99/mês | 100 verificações/mês | Instituições pequenas |
| Magistério | R$ 99,99/mês | Ilimitado | Equipes e integrações |

## Plano Fiel

Inclui:

- verificação básica de citações;
- resultado com nível de confiança;
- histórico recente de verificações;
- acesso à biblioteca digital.

## Plano Catequista

Inclui:

- tudo do plano Fiel;
- laudos em PDF;
- referência exata da fonte;
- histórico completo da conta;
- uso indicado para catequese e grupos de estudo.

## Plano Apologeta

Inclui:

- tudo do plano Catequista;
- contexto patrístico mais completo;
- análise de tradução e variação textual;
- acesso a PDFs digitalizados;
- exportação do histórico em CSV.

## Plano Patrístico

Inclui:

- tudo do plano Apologeta;
- painel de gestão institucional;
- convite e gestão de membros;
- relatório mensal de uso;
- uso indicado para apostolados e equipes.

## Plano Magistério

Inclui:

- tudo do plano Patrístico;
- API dedicada;
- endpoint REST `/v1/verificar`;
- geração e revogação de chaves;
- integração com sistemas externos;
- prioridade para uso avançado.

## Assinatura

As assinaturas são mensais e processadas pela Stripe.

O Vera.Fidei não deve armazenar número completo de cartão. O pagamento e a gestão de cobrança ficam no ambiente seguro do provedor de pagamento.

## Cancelamento

O usuário pode cancelar a assinatura pelo portal de cobrança quando disponível.

Quando a Stripe confirma o cancelamento, o sistema atualiza o plano da conta conforme a situação da assinatura.

## Repasse

Os valores pagos por usuários são processados pela Stripe e seguem para a conta bancária configurada no painel Stripe.

O repasse bancário depende das regras, prazos, validações e configurações da própria Stripe.

## Observação Importante

Para confirmar recebimento efetivo em banco, é necessário verificar o painel da Stripe e o extrato da conta bancária cadastrada.
