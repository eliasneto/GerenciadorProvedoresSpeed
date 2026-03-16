# GerenciadorProvedoresSpeed

Como você acessa esse banco de dados por fora?
Se você quiser ver as tabelas cruas, criar relatórios ou fazer backups manuais, você pode baixar um programa como o DBeaver, MySQL Workbench ou HeidiSQL na sua máquina e conectar usando exatamente estes dados:

Host / IP: localhost (ou 127.0.0.1)
Porta: 3309 (Aquela porta segura que abrimos para fora)
Banco de Dados: speed_banco
Usuário: speed_user (ou root)
Senha: speed_password (ou root_super_password se usar o root)


API google: AIzaSyCtz9rsDfujX9NhIvm1rW1hfkKCsxE3GHk


Pontos importantes sobre o custo:
Como agora estamos usando duas chamadas (places + place_details), o custo é um pouco maior, mas ainda coberto pelos US$ 200 grátis:

Text Search: Custa aprox. US$ 32,00 por 1.000 buscas.

Place Details: Custa aprox. US$ 17,00 por 1.000 buscas.

Com o crédito de US$ 200, você consegue pesquisar e detalhar cerca de 4.000 a 5.000 fornecedores por mês totalmente de graça.


docker exec -it speed_sistema python scripts/integracoes/ixc_api.py
docker exec -it speed_sistema python scripts/integracoes/ixc_faxina.py