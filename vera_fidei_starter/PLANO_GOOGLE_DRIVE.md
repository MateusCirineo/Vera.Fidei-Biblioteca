# Plano: Google Drive como Extensão de Armazenamento + Upload de Livros

## Contexto

O servidor Hetzner (`5.161.115.95`) já carrega:
- 1.4GB de PDFs em `backend/pdfs/`
- 1.2GB de embeddings ChromaDB em `backend/chroma_db/`

Com o acervo completo (Migne PL 221 vol + PG 166 vol + PO + outros), o volume de PDFs pode
chegar facilmente a 50GB+. Guardar tudo no servidor é inviável a longo prazo.

**Solução:** Google Drive como camada de armazenamento dos PDFs originais.
O servidor guarda apenas embeddings e metadados — não os PDFs brutos.

---

## Arquitetura Proposta

```
Google Drive (pasta Vera.Fidei)
        │
        │  1. Claude acessa Drive via MCP
        │  2. Baixa PDF temporariamente no servidor
        ▼
  Backend (servidor Hetzner)
        │
        │  3. Processa: OCR + embeddings + metadados
        │  4. Salva URL do Drive no banco (book_files)
        │  5. Deleta PDF local
        ▼
  ChromaDB + PostgreSQL
  (embeddings + metadados permanentes)
        │
        │  6. Usuário abre PDF no leitor
        ▼
  Redirect → Google Drive URL
  (PDF servido pelo Drive, não pelo servidor)
```

---

## O Que Muda no Código

### Compatível com tudo que já existe — nenhuma funcionalidade quebra.

#### `backend/models/database.py`
Adicionar campo `drive_url` na tabela `book_files`:
```sql
ALTER TABLE book_files ADD COLUMN drive_url TEXT;
```

#### `backend/api/routes/pdfs.py`
Modificar o endpoint `GET /pdfs/{file_id}`:
```python
# Lógica atual: serve arquivo local
# Nova lógica:
if arquivo_existe_local:
    serve arquivo local  # comportamento atual preservado
else:
    redirect 302 → book_file.drive_url  # novo: Google Drive
```

#### `backend/services/ingestion_service.py`
Adicionar suporte a ingestão via URL do Drive:
```python
# Novo fluxo opcional:
download_from_drive(drive_url) → caminho_temp
ingest(caminho_temp)
salvar drive_url no banco
deletar caminho_temp
```

---

## Workflow de Upload de Novos Livros

### Opção A — Claude faz o upload (recomendado)
1. Mateus coloca PDFs em pasta do Google Drive
2. Mateus avisa o Claude: "tem novos livros na pasta X"
3. Claude acessa Drive via MCP, lista os PDFs
4. Claude chama `POST /books/ingest-auto` para cada PDF
5. Servidor ingere, embeddings criados, PDF deletado do servidor
6. Drive URL salva no banco para visualização futura

### Opção B — Upload manual via admin
1. Mateus acessa `https://verafidei.oialfred.com/admin`
2. Faz upload direto pelo browser
3. PDF fica no servidor (comportamento atual)

---

## Estrutura de Pastas no Google Drive (Sugerida)

```
Vera.Fidei — Biblioteca/
├── PL — Patrologia Latina/
│   ├── PL001 — Tertuliano.pdf
│   ├── PL002 — Cipriano.pdf
│   └── ...
├── PG — Patrologia Graeca/
│   ├── PG001 — Clemente de Roma.pdf
│   └── ...
├── PO — Patrologia Orientalis/
│   └── ...
├── Patristicos — Paulus/
│   ├── Vol1 — Padres Apostolicos.pdf
│   └── ...
└── Documentos — Igreja/
    ├── Encíclicas/
    └── Concílios/
```

---

## Vantagens

| | Servidor sozinho | Com Google Drive |
|---|---|---|
| Custo de armazenamento | Cresce com acervo | Fixo (só embeddings) |
| Backup dos PDFs | Risco de perda | Drive sincroniza |
| Acesso aos PDFs | Rápido (local) | Redirect (mínimo delay) |
| Escalabilidade | Limitada | Ilimitada (Drive) |
| Complexidade | Simples | Mínima mudança |

---

## Estado Atual (2026-04-30)

- [x] Servidor no ar: `https://verafidei.oialfred.com`
- [x] 324 livros no PostgreSQL, 45.383 chunks
- [x] 1.4GB PDFs no servidor (volumes já ingeridos)
- [x] ChromaDB com embeddings (1.2GB)
- [ ] Integração Google Drive (a implementar)
- [ ] Campo `drive_url` no banco (a implementar)
- [ ] Redirect `/pdfs/{file_id}` → Drive (a implementar)
- [ ] Workflow de ingestão via Drive URL (a implementar)

---

## Próximos Passos

1. Mateus compartilha pasta do Google Drive com os PDFs
2. Claude implementa as mudanças no backend (campo + redirect)
3. Claude testa a ingestão via Drive com 1 volume piloto
4. Se OK: Claude processa os volumes restantes em lote
5. PDFs antigos no servidor: opcionalmente deletar após confirmar Drive URLs funcionando
