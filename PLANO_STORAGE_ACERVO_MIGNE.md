# Plano de Storage para Acervo Grande do Vera.Fidei

Data: 2026-06-03

## Objetivo

Permitir que o Vera.Fidei cresca para receber a Patrologia do Migne, novas obras patrísticas, documentos da Igreja, livros de catequese, liturgia e outros acervos sem depender do disco principal do servidor Hetzner e sem quebrar o app, o PWA, o APK, o verificador de citações ou a experiencia atual do usuario.

## Situacao atual

Hoje o Vera.Fidei guarda os PDFs fisicos no servidor em:

```text
/opt/vera_fidei/backend/pdfs
```

O cadastro das obras fica no PostgreSQL, principalmente nas tabelas:

```text
books
book_files
chunks
translations
```

Os indices ficam separados:

```text
/opt/vera_fidei/backend/chroma_db
Docker volume: vera_fidei_es_data
```

Na medicao feita em 2026-06-03, a producao estava aproximadamente assim:

```text
PDFs:             1.7 GB
ChromaDB:         1.5 GB
PostgreSQL:       197 MB
Elasticsearch:    225 MB
Disco livre:      43 GB de 150 GB
```

Isso ainda esta funcionando bem, mas o Hetzner tambem sera usado para outros apps. Portanto, ele nao deve virar o deposito principal de todos os PDFs do Vera.Fidei.

## Problema

Subir toda a Patrologia do Migne diretamente no disco do Hetzner nao e uma boa estrategia.

O risco nao esta apenas no tamanho dos PDFs. Cada obra adicionada tambem pode gerar:

- texto extraido para `chunks`;
- metadados no PostgreSQL;
- embeddings no ChromaDB;
- indice textual no Elasticsearch;
- cache temporario para verificacao de citacoes;
- processamento pesado se o PDF for escaneado ou tiver OCR ruim.

Ou seja: 1 GB de PDF pode gerar mais consumo em banco, indice, cache e processamento. Com a Migne completa, isso pode crescer rapido.

## Recomendacao

A melhor solucao e mover os PDFs para um storage externo S3-compatible, mantendo o backend do Vera.Fidei como intermediario.

Recomendacao principal:

```text
Cloudflare R2
```

Alternativas viaveis:

```text
Backblaze B2
Hetzner Object Storage
AWS S3
Wasabi
```

Nao recomendo Google Drive como storage principal de producao. Ele pode servir como backup ou pasta temporaria de entrada, mas nao como base oficial do aplicativo, pois pode gerar problemas de permissao, limite, link quebrado, bloqueio de trafego e lentidao.

## Arquitetura proposta

O usuario continuaria acessando o app exatamente como hoje.

O frontend, PWA e APK continuariam chamando:

```text
/api/pdfs/{file_id}
```

Mas, por tras, o backend buscaria o arquivo no storage externo.

Fluxo recomendado:

```text
Usuario
  -> Vera.Fidei frontend/PWA/APK
  -> /api/pdfs/{file_id}
  -> backend consulta book_files
  -> backend localiza objeto no R2
  -> backend redireciona ou transmite PDF
```

Para o verificador:

```text
Usuario verifica citacao
  -> backend encontra chunk
  -> backend consulta book_file
  -> se precisar escanear pagina real:
       baixa PDF do R2 para cache temporario
       procura pagina correta
       retorna file_id + pdf_page
  -> app abre o PDF no trecho correto
```

## O que muda no codigo

Mudancas pequenas e controladas:

1. Criar um adaptador de storage no backend.

```text
storage/local.py
storage/s3.py
storage/service.py
```

2. Adicionar variaveis de ambiente.

```text
PDF_STORAGE=local ou s3
S3_ENDPOINT_URL=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_PUBLIC_BASE_URL=
PDF_CACHE_DIR=/tmp/vera_fidei_pdf_cache
PDF_CACHE_MAX_GB=5
```

3. Alterar a rota de PDFs.

Arquivo principal:

```text
backend/api/routes/pdfs.py
```

Hoje ela resolve arquivo local e usa `X-Accel-Redirect`.

No novo modelo, ela deve:

- manter compatibilidade com arquivo local;
- se `PDF_STORAGE=s3`, gerar URL assinada ou fazer streaming pelo backend;
- preservar `Content-Type: application/pdf`;
- preservar `Content-Disposition`;
- continuar funcionando com `file_id`.

4. Alterar o verificador de citacoes.

Arquivo principal:

```text
backend/services/verification_service.py
```

Hoje ele precisa resolver caminho local do PDF para encontrar a pagina real. No novo modelo, ele deve:

- tentar cache local primeiro;
- se nao existir, baixar do storage;
- escanear o PDF;
- guardar em cache temporario;
- apagar/rotacionar cache antigo para nao pesar o servidor.

5. Ajustar ingestao.

Ao subir uma obra nova:

- salvar PDF no R2;
- registrar `book_files.stored_path` com a chave do objeto;
- extrair texto para chunks;
- indexar Chroma/Elasticsearch;
- remover arquivo temporario local depois da ingestao.

## O que nao deve mudar

Nao deve mudar:

- design;
- cores;
- fonte;
- navegacao;
- PWA;
- APK;
- rotas publicas usadas pelo frontend;
- estrutura visual da biblioteca;
- funcionamento do verificador;
- abertura por `file_id`;
- abertura por `pdf_page`;
- organizacao das abas.

O objetivo e trocar o armazenamento fisico dos PDFs sem o usuario perceber.

## Plano de migracao seguro

### Fase 1 - Preparar compatibilidade

- Criar adaptador de storage local/S3.
- Manter o modo atual como padrao.
- Adicionar testes para PDF local continuar abrindo.
- Adicionar testes para PDF remoto abrir via storage.

### Fase 2 - Criar bucket externo

- Criar bucket no Cloudflare R2.
- Criar credenciais S3 com permissao limitada.
- Definir estrutura de chaves.

Exemplo:

```text
pdfs/patristica/migne/pl/pl-004.pdf
pdfs/patristica/migne/pg/pg-001.pdf
pdfs/documentos/papas/leao-xiii/rerum-novarum-pt.pdf
```

### Fase 3 - Migrar PDFs existentes

- Enviar os PDFs atuais para o R2.
- Atualizar `book_files.stored_path` para apontar para a chave remota.
- Manter copia local temporaria por seguranca.
- Testar biblioteca, verificador e abertura direta dos PDFs.

### Fase 4 - Ativar producao

- Definir `PDF_STORAGE=s3`.
- Subir backend.
- Testar:
  - abrir PDF pela biblioteca;
  - abrir trecho no verificador;
  - abrir PDF no APK;
  - abrir PDF no PWA;
  - testar mobile.

### Fase 5 - Limpar Hetzner

So depois de validar tudo:

- remover PDFs locais antigos;
- manter apenas cache temporario;
- configurar limite de cache;
- manter backup externo.

## Como subir a Patrologia do Migne

Nao subir tudo de uma vez.

Ordem recomendada:

1. Criar estrutura no R2.
2. Subir um lote pequeno, por exemplo 5 a 10 volumes.
3. Ingerir e indexar.
4. Testar:
   - busca;
   - verificador;
   - pagina correta;
   - abertura no PDF;
   - performance mobile.
5. Depois subir por blocos maiores.

Separacao sugerida:

```text
Patrologia Migne
  - PL - Patrologia Latina
  - PG - Patrologia Grega
  - Indices e volumes auxiliares
```

Cada volume deve preservar:

- titulo;
- volume;
- idioma;
- PL/PG;
- colunas, quando aplicavel;
- pagina do PDF;
- autor canonico;
- obra ou secao;
- editora/fonte.

## Pontos de atencao

### OCR

Se os PDFs forem escaneados, a qualidade do OCR vai definir a qualidade da busca e do verificador.

PDF escaneado ruim pode causar:

- citacao nao encontrada;
- pagina errada;
- texto quebrado;
- lentidao na ingestao;
- necessidade de OCR externo.

### Cache

O backend deve usar cache temporario para PDFs remotos, mas com limite.

Exemplo:

```text
PDF_CACHE_MAX_GB=5
```

Assim o servidor nao volta a encher de PDFs permanentes.

### Banco e indices

Mesmo com PDFs fora do Hetzner, o banco e os indices ainda podem crescer.

Se o acervo ficar gigantesco, proximos passos possiveis:

- mover Elasticsearch para servidor separado;
- trocar Chroma local por banco vetorial externo;
- separar workers de ingestao;
- criar fila de processamento;
- usar servidor dedicado apenas para indexacao.

## Decisao recomendada

Sim, o Vera.Fidei pode receber toda a Patrologia do Migne e muitos outros livros, mas nao e prudente manter todos os PDFs no disco principal do Hetzner.

A decisao recomendada e:

```text
Cloudflare R2 para PDFs
Hetzner para backend, banco, API, PWA/APK e indices
Cache local temporario apenas quando necessario
```

Essa estrategia preserva o app, reduz o peso no servidor e deixa o Vera.Fidei preparado para crescer como uma biblioteca catolica digital seria.

## Implementacao adicionada ao projeto

Foi adicionada uma camada de storage compativel com o comportamento antigo:

```text
vera_fidei_starter/backend/storage/pdf_storage.py
```

Ela suporta:

- `PDF_STORAGE=local`: modo atual, usando `backend/pdfs`;
- `PDF_STORAGE=s3` ou `PDF_STORAGE=r2`: modo remoto S3-compatible;
- cache local temporario para verificacao e indexacao;
- abertura de PDF pela mesma rota `/api/pdfs/{file_id}`;
- migracao gradual sem mudar o frontend, PWA ou APK.

Tambem foi criado um script de migracao:

```text
vera_fidei_starter/backend/scripts/migrate_pdfs_to_s3.py
```

Uso seguro, sem alterar nada:

```bash
python scripts/migrate_pdfs_to_s3.py
```

Uso real, depois de configurar as credenciais:

```bash
python scripts/migrate_pdfs_to_s3.py --apply
```

Migrar apenas um lote pequeno:

```bash
python scripts/migrate_pdfs_to_s3.py --apply --limit 10
```

Migrar um livro especifico:

```bash
python scripts/migrate_pdfs_to_s3.py --apply --book-id 123
```

Nao usar `--delete-local` ate validar tudo em producao.

## Fontes uteis

- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Cloudflare R2 funcionamento: https://developers.cloudflare.com/r2/how-r2-works/
- Backblaze B2: https://www.backblaze.com/cloud-storage
- Hetzner Storage Box: https://docs.hetzner.com/storage/storage-box/
