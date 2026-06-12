# Deploy — Oracle Cloud Always Free (ARM)

Guia completo para migrar o Vera.Fidei do PC local para produção no Oracle Cloud, com o backend acessível pelo app mobile.

---

## 1. Criar conta e VM no Oracle Cloud

1. Acesse [cloud.oracle.com](https://cloud.oracle.com) e crie uma conta gratuita
2. Vá em **Compute → Instances → Create Instance**
3. Configurações obrigatórias:
   - **Image:** Ubuntu 22.04 (ARM)
   - **Shape:** `VM.Standard.A1.Flex` — **Always Free**
   - **OCPUs:** 4 | **RAM:** 24 GB
   - **Boot volume:** 100 GB
4. Crie ou importe uma **SSH key** (guarde o arquivo `.key`)
5. Em **Networking:** crie uma VCN nova ou use a padrão — anote o **IP público** da VM

---

## 2. Abrir portas no firewall da Oracle

No console Oracle, vá em **Networking → Virtual Cloud Networks → sua VCN → Security Lists → Default**:

Adicione regra de entrada (Ingress):
- **Source:** `0.0.0.0/0`
- **Protocol:** TCP
- **Destination Port:** `8000`

Depois, **na própria VM**, libere a porta no firewall interno:

```bash
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

---

## 3. Configurar o servidor (rodar na VM via SSH)

```bash
# Conectar na VM
ssh -i seu_arquivo.key ubuntu@SEU_IP_PUBLICO

# Instalar dependências do sistema
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    build-essential git poppler-utils rsync

# Criar pasta do projeto
mkdir -p ~/vera_fidei/backend
mkdir -p ~/vera_fidei/pdfs
```

---

## 4. Transferir os dados do PC para o servidor

Rodar **no seu PC Windows** (Git Bash ou WSL):

```bash
# Variáveis — ajuste o IP e o caminho
SERVER_IP="SEU_IP_PUBLICO"
SSH_KEY="caminho/para/seu_arquivo.key"
BACKEND="c:/Users/Kryptonian-PC/Desktop/PROGRAMACAO VS/C PROGRAMATION/Scripts Python/GIT - RANDOMS MATT/Projeto pessoal/Vera.Fidei-Biblioteca/vera_fidei_starter/backend"

# 1. Enviar código do backend
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' \
  -e "ssh -i $SSH_KEY" \
  "$BACKEND/" \
  ubuntu@$SERVER_IP:~/vera_fidei/backend/

# 2. Enviar ChromaDB (embeddings — pode ser grande, ~2–5 GB)
rsync -avz --progress \
  -e "ssh -i $SSH_KEY" \
  "$BACKEND/chroma_db/" \
  ubuntu@$SERVER_IP:~/vera_fidei/backend/chroma_db/

# 3. Enviar banco SQLite (metadados dos livros)
rsync -avz \
  -e "ssh -i $SSH_KEY" \
  "$BACKEND/db.sqlite3" \
  ubuntu@$SERVER_IP:~/vera_fidei/backend/db.sqlite3

# 4. Enviar PDFs (se houver — pode ser muito grande)
# Se os PDFs estiverem em pasta separada, ajuste o caminho:
rsync -avz --progress \
  -e "ssh -i $SSH_KEY" \
  "$BACKEND/pdfs/" \
  ubuntu@$SERVER_IP:~/vera_fidei/pdfs/
```

---

## 5. Instalar dependências Python na VM

```bash
# Na VM
cd ~/vera_fidei/backend

# Criar ambiente virtual
python3.11 -m venv .venv
source .venv/bin/activate

# Instalar dependências (CPU only — sem CUDA no servidor)
pip install --upgrade pip
pip install -r requirements.txt

# O modelo bge-m3 será baixado automaticamente na primeira execução (~1.5 GB)
# Para pré-baixar:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

---

## 6. Criar arquivo .env de produção na VM

```bash
# Na VM
cat > ~/vera_fidei/backend/.env << 'EOF'
DATABASE_URL=sqlite:////home/ubuntu/vera_fidei/backend/db.sqlite3
CHROMA_PATH=/home/ubuntu/vera_fidei/backend/chroma_db
PDF_STORAGE_PATH=/home/ubuntu/vera_fidei/pdfs
VERA_EMBEDDING_DEVICE=cpu
API_KEY=UmGKwx6a-aGLzA-_PsakG-u7lSbB1qhlmgD7eUWUWRc
EOF
```

> **Importante:** Gere uma nova API_KEY para produção. Use: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

## 7. Criar serviço systemd (backend roda automaticamente)

```bash
# Na VM
sudo tee /etc/systemd/system/vera-fidei.service << 'EOF'
[Unit]
Description=Vera.Fidei Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/vera_fidei/backend
Environment="PATH=/home/ubuntu/vera_fidei/backend/.venv/bin"
EnvironmentFile=/home/ubuntu/vera_fidei/backend/.env
ExecStart=/home/ubuntu/vera_fidei/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vera-fidei
sudo systemctl start vera-fidei

# Verificar se está rodando
sudo systemctl status vera-fidei
```

---

## 8. Testar o backend

```bash
# Do seu PC
curl -H "X-API-Key: SUA_API_KEY" http://SEU_IP_PUBLICO:8000/books | head -100
curl -H "X-API-Key: SUA_API_KEY" http://SEU_IP_PUBLICO:8000/health
```

---

## 9. Atualizar o app mobile para apontar para o servidor

No arquivo `vera_fidei_starter/mobile/.env`, troque:

```env
# Antes (local)
EXPO_PUBLIC_API_URL=http://192.168.0.3:8000

# Depois (produção)
EXPO_PUBLIC_API_URL=http://SEU_IP_PUBLICO:8000
EXPO_PUBLIC_API_KEY=SUA_API_KEY_DE_PRODUCAO
```

---

## 10. (Opcional) HTTPS com domínio próprio

Se quiser HTTPS (necessário para publicar na App Store):

```bash
# Instalar nginx + certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Configurar nginx como proxy reverso
sudo tee /etc/nginx/sites-available/vera-fidei << 'EOF'
server {
    server_name seudominio.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/vera-fidei /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Obter certificado SSL gratuito (Let's Encrypt)
sudo certbot --nginx -d seudominio.com
```

---

## Resumo rápido

| Etapa | Comando principal |
|---|---|
| Conectar na VM | `ssh -i chave.key ubuntu@IP` |
| Enviar código | `rsync -avz --exclude .venv backend/ ubuntu@IP:~/vera_fidei/backend/` |
| Enviar ChromaDB | `rsync -avz chroma_db/ ubuntu@IP:~/vera_fidei/backend/chroma_db/` |
| Instalar deps | `python3.11 -m venv .venv && pip install -r requirements.txt` |
| Iniciar serviço | `sudo systemctl start vera-fidei` |
| Ver logs | `sudo journalctl -u vera-fidei -f` |
| Reiniciar | `sudo systemctl restart vera-fidei` |

---

## Dados a migrar

- `backend/db.sqlite3` — banco de metadados dos livros
- `backend/chroma_db/` — embeddings (ChromaDB)
- `backend/pdfs/` — arquivos PDF (se armazenados localmente)
- `backend/.env` — variáveis de ambiente (criar novo no servidor)
- `backend/requirements.txt` — dependências Python
- Todo o código `backend/` exceto `.venv` e `__pycache__`
