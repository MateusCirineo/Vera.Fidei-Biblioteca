# Backup e restauração do Vera.Fidei

O servidor cria diariamente um arquivo PostgreSQL no formato custom em
`/var/backups/vera-fidei/postgres`. Cada execução verifica o catálogo do dump,
gera SHA-256 e conserva 14 dias. O diretório usa permissão `0700`.

## Verificação operacional

```sh
systemctl status vera-fidei-db-backup.timer
systemctl list-timers vera-fidei-db-backup.timer
journalctl -u vera-fidei-db-backup.service
```

## Teste real de restauração

O teste seleciona o dump mais recente pela data de modificação, valida seu
SHA-256, cria um banco temporário, restaura com `--exit-on-error`, conta obras,
trechos e usuários e remove o banco temporário ao terminar:

```sh
cd /opt/vera_fidei
./ops/verify_postgres_restore.sh
```

Um arquivo específico pode ser informado como primeiro argumento. O script
nunca sobrescreve o banco `vera_fidei` em uso.

Os PDFs, o índice do Elasticsearch e o índice semântico não fazem parte deste
dump. Eles permanecem nos volumes/diretórios de produção e devem ter cópia
externa própria antes de uma migração completa de servidor.

## Cópia externa criptografada

Depois do backup local, `vera-fidei-db-offsite.timer` criptografa o dump com
`age` para a chave SSH pública do proprietário e envia o arquivo cifrado e seu
SHA-256 para `vera_drive:vera-fidei/backups/postgres-encrypted`. A chave privada
não existe no servidor: ela permanece no computador do proprietário.

```sh
systemctl status vera-fidei-db-offsite.timer
systemctl list-timers vera-fidei-db-offsite.timer
journalctl -u vera-fidei-db-offsite.service
```

Para recuperar um backup em outro computador, baixe o arquivo `.age` e o
`.sha256`, valide o checksum e use a chave SSH privada correspondente:

```sh
sha256sum --check vera-fidei-AAAAmmddTHHMMSSZ.dump.age.sha256
age --decrypt --identity ~/.ssh/id_ed25519 \
  --output vera-fidei-restaurado.dump \
  vera-fidei-AAAAmmddTHHMMSSZ.dump.age
```

Em seguida, informe o dump descriptografado ao teste de restauração ou ao
procedimento controlado de recuperação. Nunca envie a chave privada ao servidor
ou ao armazenamento externo.
