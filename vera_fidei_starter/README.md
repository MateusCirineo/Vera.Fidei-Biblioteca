# Vera.fidei — Starter alinhado ao planejamento

Este starter implementa a base do MVP do **Verificador de Citações Teológicas** conforme o documento do projeto:

- FastAPI no backend
- PostgreSQL via SQLAlchemy
- endpoint `POST /verify-citation`
- estrutura para OCR / ingestão / busca / sistema de confiança
- suporte a metadados Migne (`colecao`, `volume`, `coluna`, `pagina_pdf`, `offsets`)
- tratamento de múltiplas versões da mesma obra
- LLM apenas como explicador (stub, não decide)

## Rodar

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

`requirements.txt` é a entrada editável para desenvolvimento. A imagem de
produção usa o lock de Python 3.11 para Linux x86_64 e exige todos os hashes:

```bash
cd backend
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
```

O comando de regeneração e os portões obrigatórios da entrega estão em
`RELEASE_MANIFEST.md`.
