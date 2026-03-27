#!/bin/bash

# ==========================================
# ⚙️ CONFIGURAÇÕES (PREENCHA AQUI)
# ==========================================
# Dados do Windows
WIN_SHARE="//192.168.90.53/d$/Publica/Elias"
WIN_USER="howbe/elias.neto"
WIN_PASS="Gustavo@1027"

# Dados do Linux
PROJECT_DIR="/caminho/exato/da/sua/pasta/gerenciadorProvedores" 
MOUNT_POINT="/mnt/backup_ageis"
BACKUP_TMP="/tmp/backups_speed"

# Formato da Data (Ex: 2026-03-26_02-00)
DATA=$(date +%Y-%m-%d_%H-%M)
ARQUIVO_ZIP="backup_speed_$DATA.zip"

echo "🚀 Iniciando rotina de Backup da Ageis Sistemas..."

# 1. Prepara as pastas temporárias
mkdir -p $BACKUP_TMP
mkdir -p $MOUNT_POINT

# 2. Faz o Dump do Banco de Dados (Direto do Container Docker)
echo "📦 Extraindo Banco de Dados MySQL..."
docker exec speed_mysql mysqldump -u root -proot_super_password speed_banco > $BACKUP_TMP/banco_$DATA.sql

# 3. Compacta o Banco de Dados + Pasta Media (Os Anexos)
echo "🗜️ Compactando arquivos (ZIP)..."
cd $PROJECT_DIR
zip -r $BACKUP_TMP/$ARQUIVO_ZIP media/ $BACKUP_TMP/banco_$DATA.sql > /dev/null

# 4. Conecta na pasta do Windows de forma silenciosa e copia
echo "🔗 Conectando ao servidor Windows ($WIN_SHARE)..."
mount -t cifs "$WIN_SHARE" $MOUNT_POINT -o username=$WIN_USER,password=$WIN_PASS,vers=3.0,iocharset=utf8

echo "💾 Transferindo Backup para o Windows..."
cp $BACKUP_TMP/$ARQUIVO_ZIP $MOUNT_POINT/

# 5. Faxina Inteligente: Apaga backups com mais de 10 dias no Windows para não lotar o HD
echo "🧹 Limpando backups antigos no Windows (Mais de 10 dias)..."
find $MOUNT_POINT -name "backup_speed_*.zip" -type f -mtime +10 -delete

# 6. Desconecta do Windows e limpa o Linux
echo "🔒 Desconectando do Windows e limpando arquivos temporários..."
umount $MOUNT_POINT
rm -rf $BACKUP_TMP

echo "✅ BACKUP FINALIZADO COM SUCESSO: $ARQUIVO_ZIP"