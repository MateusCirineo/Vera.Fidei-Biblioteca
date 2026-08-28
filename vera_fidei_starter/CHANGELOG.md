# Histórico de alterações

As mudanças relevantes do Vera Fidei são registradas neste arquivo. A
identidade exata de cada entrega e as evidências dos testes ficam no manifesto
da respectiva versão.

## [1.3.0] - 2026-08-28

Este corte atualiza somente a PWA e a API. O aplicativo Expo/Android não recebe
nova versão nem novos artefatos nesta release; a publicação na Play Store
continua condicionada ao runbook e à homologação descritos na documentação.

### Adicionado

- Preparação do Google Play Billing com validação autoritativa no backend,
  confirmação de compras, RTDN, reconciliação, troca de plano e proteção contra
  cobrança simultânea pelo Stripe e pela loja. A integração permanece
  desabilitada por padrão até a homologação externa.
- Nova apresentação pública, imagens de fontes primárias e retratos dos santos
  com proveniência controlada.
- Artes fornecidas para as categorias de orações, busca própria e testes de
  correspondência de título e texto.
- Sincronização persistente do avatar entre dispositivos e atualização dos
  cabeçalhos quando a autenticação ou a imagem do perfil muda.

### Alterado

- A busca de orações passou a considerar somente o nome e o corpo da oração,
  sem produzir resultados por referências ou notas associadas.
- A citação diária passou a rejeitar bibliografias, prefácios, notas editoriais
  e outros trechos que não constituem citação do santo.
- O login passou a confirmar a sessão com o backend antes da navegação, a
  comunicar sucesso e a concluir a entrada por navegação integral.
- A política de acesso a PDFs passou a permitir a biblioteca completa também
  para contas do plano gratuito Fiel.
- A apresentação, as páginas de santos e orações e o perfil foram refinados
  para uso responsivo na PWA.
- As dependências do projeto Expo foram alinhadas aos patches atuais do SDK 57.
  O bundle Android foi validado, mas nenhum novo APK/AAB faz parte deste corte.

### Corrigido

- Requisições de cadastro, login, recuperação de conta, avatar,
  verificador, pesquisa, administração e assinatura agora encerram por sucesso,
  erro, cancelamento ou tempo excedido, inclusive quando o corpo HTTP deixa de
  responder depois dos cabeçalhos.
- Abertura, renderização e busca em PDFs possuem prazo, cancelamento, mensagem
  recuperável e nova tentativa, preservando o streaming dos arquivos grandes.
- O armazenamento offline trata IndexedDB bloqueado, abortado ou sem resposta
  sem retornar gravação parcial nem manter a interface em carregamento infinito.

## [1.2.0] - 2026-08-25

### Adicionado

- Aplicativo Expo com autenticação, perfil, pesquisa paginada, biblioteca,
  verificador, planos, santos e orações.
- Distribuições Android separadas: APK direto com assinatura e AAB leitor para
  lojas, sem checkout ou atalhos externos de compra dentro do aplicativo.
- Exportação dos dados pessoais e exclusão de conta diretamente no aplicativo
  móvel, além de identidade visual oficial para ícone, splash e ícone adaptável.
- Métricas administrativas de contas, assinaturas e acessos com acesso restrito
  ao proprietário.
- Rotinas de backup local e externo, teste de restauração e monitoramento de
  disponibilidade, disco e falhas operacionais.

### Alterado

- Abertura de PDFs passou a usar entrega parcial e resolução das cópias no
  Google Drive, inclusive para arquivos grandes.
- Pesquisa patrística e verificador voltaram a priorizar texto de edição
  confiável, mantendo OCR não conferido bloqueado como citação literal.
- Fluxos de cobrança passaram a reconciliar o estado atual da assinatura e a
  processar eventos Stripe de forma idempotente.
- Componentes backend, frontend, PWA e mobile foram alinhados na versão 1.2.0.
- Builds móveis passaram a usar numeração remota e incremento automático do
  EAS; o arquivo de envio foi reduzido ao código e aos recursos necessários.
- O backup externo passou a renovar o token do Google Drive em uma cópia
  privada e gravável da configuração, preservando a configuração original.
- Dependências Python de produção foram congeladas com hashes para Linux x86_64
  e as imagens-base do ambiente Docker foram fixadas por digest; pacotes Debian
  do backend passaram a usar um snapshot datado.

### Segurança e privacidade

- Redefinição de senha passou a invalidar sessões anteriores.
- Exclusão de conta passou a impedir assinaturas Stripe órfãs e a falhar de
  forma segura quando o estado da cobrança não pode ser confirmado.
- Exportação de dados pessoais passou a proibir armazenamento em cache.
- Senha mínima elevada para oito caracteres.
- Documentação da API desativada em produção, cabeçalhos de segurança reforçados
  e contexto Docker protegido contra inclusão de segredos e dados gerados.
