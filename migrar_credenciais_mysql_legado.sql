-- Script de compatibilidade para promover um volume MySQL antigo
-- para o padrao novo do projeto, sem precisar alterar o .env atual.
--
-- Motivo deste arquivo:
-- As primeiras versoes do ambiente Docker criavam o banco com um usuario/senha
-- de desenvolvimento proprios (ver .env/cofre de segredos do ambiente para os
-- valores reais legados; nao ha senha real registrada neste arquivo).
--
-- O projeto atual usa no .env um usuario/senha proprios do ambiente
-- (nao registrados neste arquivo).
--
-- Quando um volume legado e reutilizado, mudar o .env nao altera os usuarios
-- e bancos ja gravados dentro do MySQL. Nesses casos, o sistema pode falhar com:
--   Access denied for user
--
-- Este script promove o ambiente legado para o padrao novo, preservando o banco
-- antigo e permitindo que o .env atual continue sendo usado sem ajustes.
--
-- O que este script faz:
-- 1. Garante a existencia do banco novo speed_prod
-- 2. Cria ou atualiza o usuario atual com a senha nova
-- 3. Concede acesso do usuario atual aos bancos speed_prod e speed_banco
-- 4. Altera a senha do root local para o padrao novo
--
-- Uso esperado:
-- 1. Substituir os placeholders <DB_USER_ATUAL>, <DB_PASSWORD_ATUAL> e
--    <ROOT_PASSWORD_ATUAL> pelos valores reais do .env/cofre de segredos do
--    ambiente antes de rodar este script. Nao versionar o arquivo com os
--    valores reais preenchidos.
-- 2. Entrar no MySQL com o root legado:
--      docker compose exec speed_db mysql -uroot -p
-- 3. Dentro do MySQL:
--      SOURCE /tmp/migrar_credenciais_mysql_legado.sql;
--    ou copiar e colar o conteudo manualmente.
--
-- Observacao:
-- Se o banco legado speed_banco continuar sendo o banco real com dados,
-- o sistema ainda pode precisar de migracao/logica de dados para usar speed_prod.
-- Este script cuida das credenciais e acessos, nao copia dados entre bancos.

CREATE DATABASE IF NOT EXISTS speed_banco;
CREATE DATABASE IF NOT EXISTS speed_prod;

CREATE USER IF NOT EXISTS '<DB_USER_ATUAL>'@'%' IDENTIFIED BY '<DB_PASSWORD_ATUAL>';
ALTER USER '<DB_USER_ATUAL>'@'%' IDENTIFIED BY '<DB_PASSWORD_ATUAL>';

GRANT ALL PRIVILEGES ON speed_banco.* TO '<DB_USER_ATUAL>'@'%';
GRANT ALL PRIVILEGES ON speed_prod.* TO '<DB_USER_ATUAL>'@'%';

ALTER USER 'root'@'localhost' IDENTIFIED BY '<ROOT_PASSWORD_ATUAL>';

FLUSH PRIVILEGES;

SELECT 'Migracao de credenciais concluida: speed_app e root agora seguem o padrao novo do .env.' AS resultado;
