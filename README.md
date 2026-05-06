# GerenciadorProvedoresSpeed

Como você acessa esse banco de dados por fora?
Se você quiser ver as tabelas cruas, criar relatórios ou fazer backups manuais, você pode baixar um programa como o DBeaver, MySQL Workbench ou HeidiSQL na sua máquina e conectar usando exatamente estes dados:

Host / IP: localhost (ou 127.0.0.1)
Porta: 3309 (Aquela porta segura que abrimos para fora)
Banco de Dados: speed_banco
Usuário: speed_user (ou root)
Senha: speed_password (ou root_super_password se usar o root)



Pontos importantes sobre o custo:
Como agora estamos usando duas chamadas (places + place_details), o custo é um pouco maior, mas ainda coberto pelos US$ 200 grátis:

Text Search: Custa aprox. US$ 32,00 por 1.000 buscas.

Place Details: Custa aprox. US$ 17,00 por 1.000 buscas.

Com o crédito de US$ 200, você consegue pesquisar e detalhar cerca de 4.000 a 5.000 fornecedores por mês totalmente de graça.


docker exec -it speed_sistema python scripts/integracoes/ixc_api.py
docker exec -it speed_sistema python scripts/integracoes/ixc_faxina.py

API IXC: https://wikiapiprovedor.ixcsoft.com.br/

PAinel Google: https://console.cloud.google.com/project/_/billing/enable

## Compatibilidade de Banco Legado

Se um volume antigo do MySQL foi criado antes da troca de credenciais para o padrao novo, ele pode continuar usando estes dados:

- Banco legado: `speed_banco`
- Usuario legado: `speed_user`
- Senha legada: `speed_password`
- Root legado: `root_super_password`

O padrao novo do projeto hoje e:

- Banco atual: `speed_prod`
- Usuario atual: `speed_app`
- Senha atual: `SpeedApp!2026#Prod`
- Root atual: `SpeedRoot!2026#Prod`

### Como identificar um volume legado

Se o container web ficar em loop com `Access denied for user 'speed_app'`, teste no MySQL:

```bash
docker compose exec speed_db mysql -uroot -proot_super_password
```

Se esse acesso funcionar, o volume foi inicializado com as credenciais antigas.

### Como promover um volume legado sem apagar dados

Entre no MySQL usando o root legado e crie o usuario novo para o banco antigo:

```sql
CREATE USER IF NOT EXISTS 'speed_app'@'%' IDENTIFIED BY 'SpeedApp!2026#Prod';
ALTER USER 'speed_app'@'%' IDENTIFIED BY 'SpeedApp!2026#Prod';
GRANT ALL PRIVILEGES ON speed_banco.* TO 'speed_app'@'%';
FLUSH PRIVILEGES;
```

Depois disso, voce pode usar temporariamente:

```env
DB_NAME=speed_banco
DB_USER=speed_app
DB_PASSWORD=SpeedApp!2026#Prod
```

Esse caminho preserva o volume antigo e evita recriacao do banco em ambientes mais sensiveis, como producao.
