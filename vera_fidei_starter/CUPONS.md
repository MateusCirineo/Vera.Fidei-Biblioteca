# Cupons de Desconto â€” Vera.Fidei

## Como funciona

Cada aluno ou parceiro recebe um cÃ³digo Ãºnico (ex: `COLEGIO2024A`). Quando digita o cÃ³digo no campo "Cupom de desconto" na pÃ¡gina `/planos` e clica em "Assinar mensalmente", o backend valida o cÃ³digo via Stripe API e aplica o desconto diretamente no checkout â€” o aluno jÃ¡ vÃª o preÃ§o reduzido antes de confirmar o pagamento.

Os cÃ³digos sÃ£o **de uso Ãºnico**: apÃ³s a primeira assinatura confirmada, o cÃ³digo Ã© marcado como esgotado automaticamente pelo Stripe.

---

## Criar cupons no Stripe Dashboard (passo a passo)

### 1. Criar o Coupon (template de desconto)

1. Acesse [dashboard.stripe.com](https://dashboard.stripe.com) â†’ **Products** â†’ **Coupons**
2. Clique em **+ New**
3. Configure o desconto:
   - **Percent off**: ex. `30` (30% de desconto) â€” recomendado para facilitar
   - **Duration**: `Forever` (aplica em todas as mensalidades enquanto a assinatura continuar ativa)
   - **Name**: ex. `ColÃ©gio PatrÃ­stico â€” 30%`
4. Salve. VocÃª acabou de criar um **Coupon** reutilizÃ¡vel (template).

### 2. Criar Promotion Codes individuais (uso Ãºnico por aluno)

1. Ainda em **Coupons**, clique no coupon que acabou de criar
2. Clique em **Add promotion code**
3. Em **Code**, digitar o cÃ³digo desejado (ex: `COLEGIO2024A`) ou deixar em branco para gerar automaticamente
4. Em **Redemption limits**, marcar **Limit to one use** âœ“
5. Clique em **Save**
6. Repita o passo 2â€“5 para cada aluno, gerando um cÃ³digo diferente por pessoa

> **Dica:** O mesmo Coupon (template de desconto) pode ter dezenas de Promotion Codes diferentes, cada um de uso Ãºnico.

---

## Gerar mÃºltiplos cÃ³digos em lote via Stripe CLI

Se precisar gerar muitos cÃ³digos de uma vez:

```bash
# Instalar Stripe CLI (se ainda nÃ£o tiver)
# https://stripe.com/docs/stripe-cli

# Login
stripe login

# Substitua coupon_ID pelo ID do coupon criado acima (ex: M5d3kQ3R)
# Este comando cria 30 cÃ³digos Ãºnicos com max_redemptions=1
for i in $(seq 1 30); do
  stripe promotion_codes create \
    --coupon=coupon_ID \
    --code="COLEGIO$(printf '%02d' $i)25" \
    --max-redemptions=1
done
```

Os cÃ³digos gerados serÃ£o: `COLEGIO0125`, `COLEGIO0225`, ..., `COLEGIO3025`.

---

## Fluxo tÃ©cnico

```
UsuÃ¡rio digita cÃ³digo em /planos
        â†“
Frontend â†’ POST /billing/checkout { plan, coupon_code }
        â†“
Backend: stripe.PromotionCode.list(code=CODE, active=True)
        â†“
  NÃ£o encontrado â†’ HTTP 422 "Cupom invÃ¡lido ou jÃ¡ utilizado"
  Encontrado    â†’ cria checkout session com discounts=[{promotion_code: ID}]
        â†“
UsuÃ¡rio Ã© redirecionado ao Stripe com desconto prÃ©-aplicado
        â†“
ApÃ³s pagamento: webhook atualiza plano do usuÃ¡rio normalmente
```

Quando nÃ£o hÃ¡ cupom, o campo de promoÃ§Ã£o nativo do Stripe ainda aparece no checkout (comportamento padrÃ£o).

---

## Exemplo â€” ColÃ©gio PatrÃ­stico

Acordo: 30% de desconto recorrente no plano MagistÃ©rio (R$ 99,99/mÃªs â†’ R$ 69,99/mÃªs enquanto a assinatura continuar ativa) para alunos do curso.

1. Criar coupon `ColÃ©gio PatrÃ­stico â€” 30% off` no Stripe Dashboard
2. Gerar um Promotion Code unico por aluno. Para muitos alunos, use --count no script; por padrao os codigos sao aleatorios e nao previsiveis:

```bash
python create_test_coupons.py sk_test_SUACHAVE --prefix COLEGIO --percent 30 --forever --count 100
```

Esse exemplo cria 100 codigos aleatorios, como `COLEGIO-A7K3Q9PL`, cada um com uso unico e desconto recorrente enquanto a assinatura continuar ativa.
O script tambem salva uma planilha CSV em `coupons/`, por exemplo:

```text
coupons/coupons_colegio_20260718_140000.csv
```

Esse arquivo e a lista que voce usa para enviar um codigo individual para cada aluno. A pasta `coupons/` fica fora do Git para nao publicar os codigos.

Para producao, troque `sk_test_SUACHAVE` por `sk_live_SUACHAVE` quando tiver certeza que quer criar os codigos reais.

3. Enviar cada codigo individualmente para o respectivo aluno
4. O aluno acessa Vera.Fidei -> Planos -> digita o cupom -> assina com desconto

ApÃ³s a assinatura, o cÃ³digo Ã© automaticamente desativado. Tentativas de reuso retornam erro na pÃ¡gina.
