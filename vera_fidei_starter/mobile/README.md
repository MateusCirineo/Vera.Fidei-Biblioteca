# Vera.Fidei Mobile

## Modos de distribuição

- `preview` usa o modo `direct` e mantém o fluxo Stripe do canal direto.
- `production` permanece no modo `reader`, sem compra ou link externo de cobrança.
- `production-play` usa o modo `play` e oferece assinaturas Android exclusivamente pelo Google Play Billing.

Comandos explícitos:

```powershell
npm run build:android:preview
npm run build:android:reader
npm run build:android:play
```

O Google Play Billing usa código nativo e não funciona no Expo Go. Neste projeto, o teste real de compra, restauração e troca de plano deve usar a build `production-play`, com o pacote `com.verafidei.app`, instalada por uma faixa de teste do Google Play. Uma development build só serve para IAP se for configurada com o mesmo pacote e os mesmos produtos do Play Console. O acesso pago só deve ser considerado ativo após a validação autoritativa do backend.
