# Monitoramento de produção

O monitor do Vera.Fidei é executado a cada cinco minutos e verifica:

- disponibilidade HTTPS da apresentação pública;
- execução de PostgreSQL, Elasticsearch, backend, frontend e Nginx;
- estado saudável do backend;
- ocupação do disco, com alerta a partir de 80%;
- existência, idade máxima de 36 horas e checksum do backup PostgreSQL mais recente;
- confirmação de backup externo criptografado com no máximo 36 horas;
- sucesso da última reconciliação automática de assinaturas Stripe.

Uma falha tenta enviar e-mail ao endereço de suporte configurado no backend. O
envio é tentado apenas na transição de saudável para falha, evitando alertas
repetidos a cada cinco minutos; a recuperação também tenta gerar uma
notificação. O erro permanece no journal mesmo se o serviço de e-mail estiver
indisponível.

## Instalação

```sh
install -m 0750 ops/monitor_production.sh /opt/vera_fidei/ops/monitor_production.sh
install -m 0750 ops/backup_postgres.sh /opt/vera_fidei/ops/backup_postgres.sh
install -m 0750 ops/backup_postgres_offsite.sh /opt/vera_fidei/ops/backup_postgres_offsite.sh
install -m 0644 ops/systemd/vera-fidei-monitor.service /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-monitor.timer /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-db-backup.service /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-db-backup.timer /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-db-offsite.service /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-db-offsite.timer /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-billing-reconcile.service /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-billing-reconcile.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now \
  vera-fidei-db-backup.timer \
  vera-fidei-db-offsite.timer \
  vera-fidei-billing-reconcile.timer \
  vera-fidei-monitor.timer
systemctl start vera-fidei-monitor.service
```

## Verificação

```sh
systemctl status vera-fidei-monitor.timer
systemctl list-timers \
  vera-fidei-db-backup.timer \
  vera-fidei-db-offsite.timer \
  vera-fidei-billing-reconcile.timer \
  vera-fidei-monitor.timer
journalctl -u vera-fidei-monitor.service --since today
```

O estado da última execução fica em `/var/lib/vera-fidei-monitor/status`. O
script não modifica banco, PDFs, índice ou backups.

## Backup externo

O `vera-fidei-db-offsite.timer` criptografa o dump mais recente com `age`, envia
o arquivo e seu SHA-256 ao Google Drive, baixa novamente os dois objetos e
confere o SHA-256 do conteúdo cifrado. A configuração original do rclone permanece somente leitura em
`/root/.config/rclone/rclone.conf`; o serviço cria uma cópia privada e gravável
em `/var/lib/vera-fidei/rclone/rclone.conf` para permitir renovação segura do
token sem liberar escrita no diretório pessoal do administrador.

O marcador `/var/lib/vera-fidei/offsite-backup-success` só é atualizado depois
da verificação remota. O monitor trata como falha um marcador ausente ou com
mais de 36 horas.
