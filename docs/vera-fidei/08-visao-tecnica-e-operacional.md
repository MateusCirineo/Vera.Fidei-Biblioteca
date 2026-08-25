# Visão Técnica E Operacional

## Arquitetura Geral

O Vera.Fidei é composto por:

- frontend em Next.js;
- backend em FastAPI;
- banco PostgreSQL;
- Elasticsearch para busca textual;
- ChromaDB para busca semântica;
- Nginx como proxy;
- Stripe para assinaturas;
- PWA para uso mobile.

## Backend

O backend fornece APIs para:

- autenticação;
- listagem de livros;
- autores e catálogo;
- PDFs;
- favoritos;
- histórico;
- verificação de citações;
- planos e cobrança;
- chaves de API;
- instituições.

## Frontend

O frontend fornece:

- página inicial;
- apresentação;
- cadastro;
- login;
- biblioteca;
- detalhe de obra;
- visualizador de PDF;
- verificador;
- santos;
- orações;
- perfil;
- planos;
- contato;
- termos;
- privacidade.

## Banco De Dados

O banco guarda:

- usuários;
- livros;
- arquivos PDF;
- trechos indexados;
- histórico de verificações;
- favoritos;
- assinaturas;
- chaves de API;
- dados institucionais.

## Indexação

A indexação transforma obras em trechos pesquisáveis.

Cada trecho pode guardar:

- texto;
- autor;
- obra;
- coleção;
- volume;
- página;
- coluna;
- idioma;
- edição;
- arquivo de origem.

## OCR

OCR é necessário para PDFs escaneados.

Sem OCR, o PDF pode abrir visualmente, mas a busca textual e o verificador podem não conseguir usar aquele conteúdo.

## Stripe

A integração com Stripe envolve:

- Price IDs dos planos;
- checkout de assinatura;
- portal de cobrança;
- webhook;
- atualização do plano do usuário;
- cancelamento;
- bloqueio ou downgrade conforme status da assinatura.

## Segurança

Pontos importantes:

- não expor chaves secretas no frontend;
- manter chaves Stripe apenas no backend/servidor;
- usar variável pública apenas para chave pública quando necessário;
- proteger endpoints com autenticação e API key quando aplicável;
- revogar chaves comprometidas;
- registrar erros sem expor dados sensíveis.

## Produção

Antes de divulgar amplamente, sempre verificar:

- backend saudável;
- frontend no ar;
- nginx ativo;
- banco ativo;
- Elasticsearch ativo;
- checkout Stripe funcionando;
- webhook funcionando;
- cadastro/login funcionando no mobile;
- PDF funcionando no PWA;
- limite do verificador funcionando;
- suporte e políticas publicados.
