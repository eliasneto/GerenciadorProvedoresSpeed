-- Script de compatibilidade para promover um volume MySQL antigo
-- para o padrao novo do projeto, sem precisar alterar o .env atual.
--
-- Motivo deste arquivo:
-- As primeiras versoes do ambiente Docker criavam o banco com:
--   Banco: speed_banco
--   Usuario app: speed_user
--   Senha app: speed_password
--   Root: root_super_password
--
-- O projeto atual usa no .env:
--   Banco: speed_prod
--   Usuario app: speed_app
--   Senha app: SpeedApp!2026#Prod
--   Root: SpeedRoot!2026#Prod
--
-- Quando um volume legado e reutilizado, mudar o .env nao altera os usuarios
-- e bancos ja gravados dentro do MySQL. Nesses casos, o sistema pode falhar com:
--   Access denied for user 'speed_app'
--
-- Este script promove o ambiente legado para o padrao novo, preservando o banco
-- antigo e permitindo que o .env atual continue sendo usado sem ajustes.
--
-- O que este script faz:
-- 1. Garante a existencia do banco novo speed_prod
-- 2. Cria ou atualiza o usuario speed_app com a senha nova
-- 3. Concede acesso do speed_app aos bancos speed_prod e speed_banco
-- 4. Altera a senha do root local para o padrao novo
--
-- Uso esperado:
-- 1. Entrar no MySQL com o root legado:
--      docker compose exec speed_db mysql -uroot -proot_super_password
-- 2. Dentro do MySQL:
--      SOURCE /tmp/migrar_credenciais_mysql_legado.sql;
--    ou copiar e colar o conteudo manualmente.
--
-- Observacao:
-- Se o banco legado speed_banco continuar sendo o banco real com dados,
-- o sistema ainda pode precisar de migracao/logica de dados para usar speed_prod.
-- Este script cuida das credenciais e acessos, nao copia dados entre bancos.

CREATE DATABASE IF NOT EXISTS speed_banco;
CREATE DATABASE IF NOT EXISTS speed_prod;

CREATE USER IF NOT EXISTS 'speed_app'@'%' IDENTIFIED BY 'SpeedApp!2026#Prod';
ALTER USER 'speed_app'@'%' IDENTIFIED BY 'SpeedApp!2026#Prod';

GRANT ALL PRIVILEGES ON speed_banco.* TO 'speed_app'@'%';
GRANT ALL PRIVILEGES ON speed_prod.* TO 'speed_app'@'%';

ALTER USER 'root'@'localhost' IDENTIFIED BY 'SpeedRoot!2026#Prod';

FLUSH PRIVILEGES;

SELECT 'Migracao de credenciais concluida: speed_app e root agora seguem o padrao novo do .env.' AS resultado;
