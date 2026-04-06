#!/bin/bash

set -euo pipefail

# Dados do Windows
WIN_SHARE="${BACKUP_LEGACY_WINDOWS_SHARE:-//${BACKUP_WINDOWS_HOST:-192.168.90.53}/${BACKUP_WINDOWS_SHARE:-Publica}}"
WIN_USER="${BACKUP_LEGACY_WINDOWS_USER:-${BACKUP_WINDOWS_DOMAIN:-HOWBE}/${BACKUP_WINDOWS_USER:-elias.neto}}"
WIN_PASS="${BACKUP_LEGACY_WINDOWS_PASSWORD:-${BACKUP_WINDOWS_PASSWORD:-}}"

# Dados do Linux
PROJECT_DIR="${PROJECT_DIR:-/caminho/exato/da/sua/pasta/gerenciadorProvedores}"
MOUNT_POINT="${MOUNT_POINT:-/mnt/backup_ageis}"
BACKUP_TMP="${BACKUP_TMP:-/tmp/backups_speed}"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-}"
MYSQL_DATABASE="${MYSQL_DATABASE:-speed_prod}"

# Formato da data
DATA=$(date +%Y-%m-%d_%H-%M)
ARQUIVO_ZIP="backup_speed_$DATA.zip"

echo "Iniciando rotina de backup..."

if [ -z "$WIN_PASS" ]; then
  echo "BACKUP_WINDOWS_PASSWORD/BACKUP_LEGACY_WINDOWS_PASSWORD nao configurado."
  exit 1
fi

if [ -z "$MYSQL_ROOT_PASSWORD" ]; then
  echo "MYSQL_ROOT_PASSWORD nao configurado."
  exit 1
fi

mkdir -p "$BACKUP_TMP"
mkdir -p "$MOUNT_POINT"

echo "Extraindo banco de dados MySQL..."
docker exec speed_mysql mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" > "$BACKUP_TMP/banco_$DATA.sql"

echo "Compactando arquivos..."
cd "$PROJECT_DIR"
zip -r "$BACKUP_TMP/$ARQUIVO_ZIP" media/ "$BACKUP_TMP/banco_$DATA.sql" > /dev/null

echo "Conectando ao compartilhamento Windows..."
mount -t cifs "$WIN_SHARE" "$MOUNT_POINT" -o "username=$WIN_USER,password=$WIN_PASS,vers=3.0,iocharset=utf8"

echo "Transferindo backup..."
cp "$BACKUP_TMP/$ARQUIVO_ZIP" "$MOUNT_POINT/"

echo "Limpando backups antigos..."
find "$MOUNT_POINT" -name "backup_speed_*.zip" -type f -mtime +10 -delete

echo "Finalizando limpeza local..."
umount "$MOUNT_POINT"
rm -rf "$BACKUP_TMP"

echo "BACKUP FINALIZADO COM SUCESSO: $ARQUIVO_ZIP"
