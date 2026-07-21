# GerenciadorProvedoresSpeed

## Acesso externo ao banco de dados

Se você quiser visualizar as tabelas brutas, criar relatórios ou fazer backups manuais, pode usar uma ferramenta como DBeaver, MySQL Workbench ou HeidiSQL na sua máquina e conectar usando host, porta, banco, usuário e senha configurados no `.env` do ambiente (arquivo não versionado). Não há credencial real registrada neste documento.

## Observações sobre custo de Google Places

Como o projeto usa duas chamadas (`places` + `place_details`), o custo fica um pouco maior, mas ainda pode ficar coberto pelos US$ 200 de crédito gratuito.

- `Text Search`: aproximadamente US$ 32,00 por 1.000 buscas
- `Place Details`: aproximadamente US$ 17,00 por 1.000 buscas

Com o crédito de US$ 200, é possível pesquisar e detalhar cerca de 4.000 a 5.000 fornecedores por mês sem custo adicional, dependendo do volume e do padrão de uso.

## Comandos úteis

```bash
docker exec -it speed_sistema python scripts/integracoes/ixc_api.py
docker exec -it speed_sistema python scripts/integracoes/ixc_faxina.py
```

## Referências

- API IXC: https://wikiapiprovedor.ixcsoft.com.br/
- Painel Google Billing: https://console.cloud.google.com/project/_/billing/enable

## Compatibilidade de banco legado

Se um volume antigo do MySQL foi criado antes da troca de credenciais para o padrão novo, ele pode continuar usando um banco, usuário e senha diferentes dos atuais. Os valores reais (atuais e legados) não ficam neste arquivo — consulte o `.env` do ambiente ou o cofre de segredos do projeto.

### Como identificar um volume legado

Se o container web ficar em loop com `Access denied for user` para o usuário configurado no `.env` atual, teste o acesso no MySQL com a credencial de root do ambiente:

```bash
docker compose exec speed_db mysql -uroot -p
```

Se o acesso com a senha de root **legada** funcionar (e não a atual), o volume foi inicializado com as credenciais antigas.

### Como promover um volume legado sem apagar dados

Entre no MySQL usando o root legado e crie o usuário novo para o banco antigo, substituindo os placeholders pelos valores reais do `.env`/cofre de segredos (nunca cole a senha real neste arquivo):

```sql
CREATE USER IF NOT EXISTS '<DB_USER_ATUAL>'@'%' IDENTIFIED BY '<DB_PASSWORD_ATUAL>';
ALTER USER '<DB_USER_ATUAL>'@'%' IDENTIFIED BY '<DB_PASSWORD_ATUAL>';
GRANT ALL PRIVILEGES ON speed_banco.* TO '<DB_USER_ATUAL>'@'%';
FLUSH PRIVILEGES;
```

Depois disso, ajuste o `.env` do ambiente para `DB_NAME=speed_banco`, mantendo o usuário e a senha atuais.

Esse caminho preserva o volume antigo e evita recriação do banco em ambientes mais sensíveis, como produção.
