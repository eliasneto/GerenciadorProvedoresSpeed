# Guia de Uso — Criação de Logins no IXC
_Última atualização: 2026-07-10_

## O que é esta automação

Esta automação cria, de uma só vez, os **logins de internet** (usuário e senha que o cliente usa para navegar) de vários clientes dentro do sistema IXC. Ela evita que a equipe precise cadastrar cada login manualmente, tela por tela, dentro do IXC.

Você preenche uma planilha com os dados de cada cliente e o sistema cria o login de cada um automaticamente no IXC.

**Importante:** esta automação **não cadastra o cliente**. Ela só cria o login de um cliente e de um contrato que **já existem** no IXC. Se o cliente ainda não estiver cadastrado no IXC, use primeiro o card **"Clientes IXC" / Cadastro de Cliente**, na mesma tela, e depois volte aqui com o `Cliente_ID` e o `Login_Contrato_ID` gerados.

## Quem pode usar

Esta ferramenta é restrita à equipe do **Backoffice**. Usuários que não fazem parte desse grupo não conseguem acessar a tela.

## Onde encontrar

1. Acesse **Central de Automações** (menu do Backoffice).
2. Localize o card **"Logins IXC" / Criação de Login** (primeiro card da tela).

## Passo a passo

1. **Baixe a planilha modelo**, clicando em "Baixar Planilha Modelo" no card de Logins IXC.
2. **Preencha uma linha para cada cliente** que precisa de um login novo, seguindo a tabela de campos abaixo.
3. **Envie a planilha preenchida** no botão "Planilha" e clique em **"Gerar Logins"**.
4. Aguarde o processamento (o sistema mostra "Criando Logins...").
5. Ao final, um **relatório em Excel** é baixado automaticamente no seu computador, mostrando o resultado linha a linha (sucesso ou erro).

Não é preciso preencher todas as linhas da planilha na mesma hora — o sistema ignora qualquer linha em que o campo de login estiver vazio.

## Campos da planilha

| Campo | O que colocar | Obrigatório? |
|---|---|---|
| `Cliente_ID` | ID do cliente no IXC (ex.: 55) | Sim |
| `Login_Contrato_ID` | ID do contrato do cliente no IXC (ex.: 1151) | Sim |
| `Plano_ID` | ID do plano de velocidade no IXC (ex.: 4) | Sim |
| `Login_Login` | Nome de usuário do login (ex.: joao_silva) | Sim |
| `Login_Senha_Cliente` | Senha do login | Sim |
| `End_CEP` | CEP sem traço (ex.: 60346165) | Sim |
| `End_Bairro` | Nome do bairro | Sim |
| `End_Cidade_ID_IXC` | ID numérico da cidade no IXC (ex.: 948). **Não** usar o nome da cidade | Sim |
| `End_Logradouro` | Rua/Avenida | Sim |
| `End_Numero` | Número da residência | Sim |
| `End_Referencia` | Ponto de referência | Não |
| `Obs_Cliente` | Observação adicional, se houver | Não |
| `VELOCIDADE` | Velocidade contratada do endereço (ex.: 500 Mbps) | Não |
| `TIPO DE ACESSO` | Tipo de acesso do endereço (ex.: Fibra, Rádio, MPLS) | Não |
| `BLOCO IP` | Bloco de IP do endereço (ex.: /30, /29) | Não |
| `DUPLA ABORDAGEM` | Sim ou Não | Não |
| `ENTREGA RB` | Sim ou Não | Não |

**Dica:** os IDs (`Cliente_ID`, `Login_Contrato_ID`, `Plano_ID`, `End_Cidade_ID_IXC`) precisam ser o número usado dentro do próprio IXC, não o nome. Se não souber o número, consulte o cadastro do cliente no IXC antes de preencher a planilha.

## O que a automação ajusta sozinha (não precisa se preocupar)

- **Nome de usuário:** espaços, acentos e símbolos são removidos automaticamente do campo `Login_Login`. Por exemplo, "João Silva" vira "JoaoSilva".
- **CEP:** é formatado automaticamente com o traço no formato `00000-000`.
- **Tipo de conexão:** todo login criado é configurado como conexão por **Fibra**, autenticado por **login e senha**, permitindo **apenas 1 acesso simultâneo** por login.

## O que é criado no IXC

Para cada linha válida da planilha, a automação cria um **login de internet (radusuário)** no IXC, já vinculado:

- ao **cliente** (`Cliente_ID`);
- ao **contrato** (`Login_Contrato_ID`);
- ao **plano de velocidade** (`Plano_ID`);
- ao **endereço** informado (CEP, bairro, rua, número, referência, cidade).

O login é criado **ativo** e pronto para uso pelo cliente assim que a linha for processada com sucesso.

Se os campos opcionais de informações técnicas (`VELOCIDADE`, `TIPO DE ACESSO`, `BLOCO IP`, `DUPLA ABORDAGEM`, `ENTREGA RB`) forem preenchidos, eles são registrados como observação no cadastro do login dentro do IXC e também ficam salvos no endereço do cliente dentro do próprio sistema, para consulta futura.

## O relatório de resultado

O arquivo baixado ao final (`Relatorio_Importacao_Logins_IXC.xlsx`) traz, para cada linha:

- **Status_Importacao:** `SUCESSO` ou `ERRO`;
- **Mensagem_Importacao:** detalhe do que aconteceu;
- **ID_IXC:** número do login criado no IXC, quando der certo.

## Erros mais comuns

| Mensagem | O que significa |
|---|---|
| `Campo End_Cidade_ID_IXC invalido...` | O ID da cidade não foi preenchido com número. Confira o valor no IXC. |
| `IXC Negou: [mensagem do IXC]` | O IXC recusou o cadastro (ex.: contrato ou plano inexistente, login já usado por outro cliente). Revise os IDs informados. |
| `Erro HTTP ...` | Falha de comunicação com o IXC. Tente novamente; se persistir, acione o suporte técnico. |
| `Erro Técnico: ...` | Falha inesperada ao processar a linha. Acione o suporte técnico informando a mensagem completa. |

Se uma linha falhar, as demais linhas da planilha continuam sendo processadas normalmente — um erro não impede a criação dos outros logins.

## Acompanhamento

Toda execução (quem importou, quantos logins foram criados com sucesso, quantos falharam e quando) fica registrada e pode ser consultada na tela de **Central de Automações**, na lista de execuções abaixo dos cards, com filtro por usuário e por mês.

## Cuidados importantes

- A planilha contém a **senha do cliente em texto visível**. Trate o arquivo com o mesmo cuidado que trataria qualquer dado sensível: não compartilhe por canais inseguros e apague o arquivo do computador após o uso.
- Sempre confira os IDs (cliente, contrato, plano, cidade) antes de importar — IDs errados criam o login vinculado ao cliente ou contrato errado.
- Diferente do cadastro de cliente, esta automação **não pede uma confirmação extra** antes de criar o login — basta a linha estar preenchida com `Login_Login` para ser processada. Revise a planilha com atenção antes de clicar em "Gerar Logins".
