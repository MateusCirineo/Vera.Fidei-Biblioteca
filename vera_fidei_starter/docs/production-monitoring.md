# Monitoramento de produção

O monitor do Vera.Fidei é executado a cada cinco minutos e verifica:

- disponibilidade HTTPS da apresentação pública;
- execução de PostgreSQL, Elasticsearch, backend, frontend e Nginx;
- estado saudável do backend;
- ocupação do disco, com alerta a partir de 80%;
- existência, idade máxima de 36 horas e checksum do backup PostgreSQL mais recente.

Uma falha gera e-mail para o endereço de suporte configurado no backend. O
e-mail é enviado apenas na transição de saudável para falha, evitando alertas
repetidos a cada cinco minutos. A recuperação também é notificada.

## Instalação

```sh
install -m 0750 ops/monitor_production.sh /opt/vera_fidei/ops/monitor_production.sh
install -m 0644 ops/systemd/vera-fidei-monitor.service /etc/systemd/system/
install -m 0644 ops/systemd/vera-fidei-monitor.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vera-fidei-monitor.timer
systemctl start vera-fidei-monitor.service
```

## Verificação

```sh
systemctl status vera-fidei-monitor.timer
systemctl list-timers vera-fidei-monitor.timer
journalctl -u vera-fidei-monitor.service --since today
```

O estado da última execução fica em `/var/lib/vera-fidei-monitor/status`. O
script não modifica banco, PDFs, índice ou backups.
