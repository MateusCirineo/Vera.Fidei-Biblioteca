# Build e Publicação nas Lojas — Vera.Fidei

Este guia explica como gerar o app para Android e iOS e publicar na Play Store e App Store, usando o **EAS (Expo Application Services)** — o serviço de build em nuvem da Expo.

---

## O que é o EAS?

O EAS compila seu app React Native nos servidores da Expo.  
Você **não precisa de Mac** para gerar o build do iOS — o EAS faz isso remotamente.  
O plano gratuito permite alguns builds por mês, suficiente para começar.

---

## Pré-requisitos

- Conta gratuita em [expo.dev](https://expo.dev)
- Node.js instalado
- Servidor Oracle Cloud configurado (ver `DEPLOY_ORACLE_CLOUD.md`)

---

## Passo 1 — Instalar o EAS CLI

Abra o terminal na pasta do projeto mobile:

```bash
cd vera_fidei_starter/mobile
npm install -g eas-cli
```

---

## Passo 2 — Fazer login na Expo

```bash
eas login
```

Vai pedir email e senha da sua conta expo.dev.

---

## Passo 3 — Vincular o projeto ao EAS

```bash
eas init
```

Esse comando cria um projeto no painel expo.dev e preenche o `projectId` automaticamente no `app.config.js`.

---

## Passo 4 — Configurar a URL do servidor antes do build

No arquivo `mobile/.env`, coloque o IP do seu servidor Oracle:

```env
EXPO_PUBLIC_API_URL=http://SEU_IP_ORACLE:8000
EXPO_PUBLIC_API_KEY=SUA_API_KEY_DE_PRODUCAO
```

Ou, se tiver domínio com HTTPS:

```env
EXPO_PUBLIC_API_URL=https://seudominio.com
EXPO_PUBLIC_API_KEY=SUA_API_KEY_DE_PRODUCAO
```

---

## Passo 5 — Build de teste interno (Preview)

Antes de ir para as lojas, gere um `.apk` para testar no celular:

```bash
# Android — gera APK para instalar direto no celular
eas build --platform android --profile preview

# Quando terminar, o EAS mostra um link para baixar o .apk
# Envie o .apk para o celular e instale (permitir instalação de fontes desconhecidas)
```

---

## Passo 6 — Build de produção para as lojas

### Android (Google Play Store)

```bash
eas build --platform android --profile production
```

Gera um `.aab` (Android App Bundle) — o formato exigido pela Play Store.

**Para publicar:**
1. Acesse [play.google.com/console](https://play.google.com/console)
2. Crie uma conta de desenvolvedor (taxa única de $25)
3. Crie um novo app → "Vera.Fidei"
4. Faça upload do `.aab` gerado
5. Preencha descrição, capturas de tela, classificação etária
6. Publique para "Teste interno" primeiro, depois "Produção"

---

### iOS (Apple App Store)

```bash
eas build --platform ios --profile production
```

Gera um `.ipa` para o App Store.

**Para publicar:**
1. Acesse [appstoreconnect.apple.com](https://appstoreconnect.apple.com)
2. Conta Apple Developer ($99/ano)
3. Crie um novo app → "Vera.Fidei"
4. Use `eas submit --platform ios` para enviar automaticamente, ou faça upload manual via Transporter

---

## Passo 7 — Envio automático para as lojas (opcional)

Após o build, o EAS pode enviar diretamente:

```bash
# Enviar para Play Store (precisa configurar google-play-key.json)
eas submit --platform android

# Enviar para App Store
eas submit --platform ios
```

---

## Resumo rápido

| O que fazer | Comando |
|---|---|
| Instalar EAS CLI | `npm install -g eas-cli` |
| Login | `eas login` |
| Vincular projeto | `eas init` |
| Build teste Android | `eas build --platform android --profile preview` |
| Build Play Store | `eas build --platform android --profile production` |
| Build App Store | `eas build --platform ios --profile production` |
| Ver status dos builds | `eas build:list` |

---

## Perfis de build (`eas.json`)

| Perfil | Para quê | Distribuição |
|---|---|---|
| `development` | Desenvolvimento local com Expo Go | Interno |
| `preview` | Testes em dispositivos reais (APK direto) | Interno |
| `production` | Publicar nas lojas | Play Store / App Store |

---

## Importante antes de publicar

- [ ] Servidor Oracle Cloud rodando e acessível
- [ ] API Key de produção configurada (diferente da de desenvolvimento)
- [ ] HTTPS configurado no servidor (obrigatório para App Store)
- [ ] Ícone e splash screen finais em `mobile/assets/`
- [ ] `version` e `versionCode`/`buildNumber` incrementados no `app.config.js`
- [ ] Descrição do app escrita (máx. 4000 caracteres para as lojas)
- [ ] Capturas de tela do app (mínimo 2 por plataforma)

---

## Atualizações após o lançamento

### Atualização normal (nova versão na loja)

Para cada nova versão com funcionalidades novas ou mudanças nativas:

```bash
# 1. Incrementar versão no app.config.js
#    version: '1.2.0' → '1.3.0'
#    versionCode: 1 → 2      (Android)
#    buildNumber: '1' → '2'  (iOS)

# 2. Gerar o build
eas build --platform android --profile production
eas build --platform ios --profile production

# 3. Submeter para as lojas
eas submit --platform android
eas submit --platform ios
```

Os usuários recebem a atualização automaticamente pela loja, igual qualquer outro app.

---

### EAS Update — atualização instantânea sem passar pela loja

Mudanças apenas em JavaScript/TypeScript (telas, textos, lógica, cores, correções de bug) podem ser enviadas **diretamente aos usuários sem aprovação da loja** e sem gerar um novo build:

```bash
# Instalar suporte a updates no app.config.js (já configurado)
# Publicar uma atualização instantânea
eas update --branch production --message "Corrige bug no verificador"
```

Os usuários recebem na próxima vez que abrirem o app — sem precisar atualizar pela loja.

> **Quando usar EAS Update:** correções de bug, ajustes de texto, melhorias visuais, novas telas em JavaScript.  
> **Quando precisa de build novo:** adicionar biblioteca nativa, mudar ícone/splash, alterar permissões, mudanças no `app.config.js`.

---

## Estratégia de lançamento em fases (Beta → Produção)

O Vera.Fidei pode ser lançado gradualmente, sem pressa. Sequência recomendada:

```
Fase 0 — Hoje
  → Testando no Expo Go (você mesmo, Wi-Fi local)

Fase 1 — Servidor no ar (Oracle Cloud)
  → eas build --profile preview
  → APK enviado por link para amigos e seguidores testarem
  → Sem precisar de conta nas lojas

Fase 2 — Teste nas lojas (Beta fechado)
  → Play Store: "Teste Interno" (até 100 pessoas por email)
  → App Store: TestFlight (convite por email, até 10.000 pessoas)
  → Coleta feedback, corrige problemas

Fase 3 — Beta aberto
  → Play Store: "Open Testing" (qualquer pessoa pode entrar)
  → Continua no TestFlight
  → Divulga nas redes (TikTok, Instagram, YouTube)

Lançamento — Produção
  → Play Store: mover para "Produção" (todos os usuários)
  → App Store: submeter para revisão da Apple (1–3 dias)

Pós-lançamento
  → EAS Update para correções rápidas (sem passar pela loja)
  → Builds novos para funcionalidades grandes (novos volumes, novas seções)
  → Incrementa versão a cada release significativo
```

---

### Beta no Google Play (passo a passo)

1. No Google Play Console, crie o app "Vera.Fidei"
2. Vá em **Teste → Teste interno** → adicione emails dos testadores
3. Faça upload do `.aab` gerado pelo EAS
4. Os testadores recebem um link para instalar pela Play Store normalmente
5. Quando estiver pronto: **Teste interno → Closed Testing → Open Testing → Produção**

### Beta no iOS com TestFlight (passo a passo)

1. No App Store Connect, crie o app "Vera.Fidei"
2. Use `eas submit --platform ios` para enviar o build
3. No App Store Connect → **TestFlight** → adicione testadores por email
4. Eles recebem convite para instalar o app TestFlight e testar
5. Quando estiver pronto: clique em "Submit for Review" → Apple aprova em 1–3 dias
