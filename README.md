# GerenciadorProvedoresSpeed

## Acesso externo ao banco de dados

Se você quiser visualizar as tabelas brutas, criar relatórios ou fazer backups manuais, pode usar uma ferramenta como DBeaver, MySQL Workbench ou HeidiSQL na sua máquina e conectar com estes dados:

- Host / IP: `localhost` ou `127.0.0.1`
- Porta: `3309`
- Banco de dados: `speed_banco`
- Usuário: `speed_user` ou `root`
- Senha: `speed_password` ou `root_super_password`, se usar `root`

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

Se um volume antigo do MySQL foi criado antes da troca de credenciais para o padrão novo, ele pode continuar usando estes dados:

- Banco legado: `speed_banco`
- Usuário legado: `speed_user`
- Senha legada: `speed_password`
- Root legado: `root_super_password`

O padrão atual do projeto é:

- Banco atual: `speed_prod`
- Usuário atual: `speed_app`
- Senha atual: `SpeedApp!2026#Prod`
- Root atual: `SpeedRoot!2026#Prod`

### Como identificar um volume legado

Se o container web ficar em loop com `Access denied for user 'speed_app'`, teste o acesso no MySQL:

```bash
docker compose exec speed_db mysql -uroot -proot_super_password
```

Se esse acesso funcionar, o volume foi inicializado com as credenciais antigas.

### Como promover um volume legado sem apagar dados

Entre no MySQL usando o root legado e crie o usuário novo para o banco antigo:

```sql
CREATE USER IF NOT EXISTS 'speed_app'@'%' IDENTIFIED BY 'SpeedApp!2026#Prod';
ALTER USER 'speed_app'@'%' IDENTIFIED BY 'SpeedApp!2026#Prod';
GRANT ALL PRIVILEGES ON speed_banco.* TO 'speed_app'@'%';
FLUSH PRIVILEGES;
```

Depois disso, você pode usar temporariamente:

```env
DB_NAME=speed_banco
DB_USER=speed_app
DB_PASSWORD=SpeedApp!2026#Prod
```

Esse caminho preserva o volume antigo e evita recriação do banco em ambientes mais sensíveis, como produção.
