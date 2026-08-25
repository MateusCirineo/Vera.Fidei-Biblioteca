# Histórico de alterações

As mudanças relevantes do Vera Fidei são registradas neste arquivo. A
identidade exata de cada entrega e as evidências dos testes ficam no manifesto
da respectiva versão.

## [1.2.0] - 2026-08-25

### Adicionado

- Aplicativo Expo com autenticação, perfil, pesquisa paginada, biblioteca,
  verificador, planos, santos e orações.
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
