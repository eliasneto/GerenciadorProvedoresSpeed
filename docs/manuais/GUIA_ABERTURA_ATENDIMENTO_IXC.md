# Guia de Uso — Abertura de Atendimento (OS) no IXC
_Última atualização: 2026-07-10_

## O que é esta automação

Esta automação abre **atendimentos (tickets/O.S.)** para vários clientes de uma só vez dentro do IXC. Ela evita que a equipe precise abrir cada atendimento manualmente, tela por tela, dentro do IXC.

Você preenche uma planilha com os dados de cada atendimento e o sistema abre o atendimento de cada um automaticamente no IXC.

**Importante:** esta automação **não cadastra cliente nem cria login**. O cliente, o login e o contrato informados na planilha precisam **já existir** no IXC. Se o cliente ainda não estiver cadastrado, use primeiro o card **"Clientes IXC" / Cadastro de Cliente** e, se precisar de um login novo, o card **"Logins IXC" / Criação de Login** (ver os guias correspondentes).

## Quem pode usar

Esta ferramenta é restrita à equipe do **Backoffice**. Usuários que não fazem parte desse grupo não conseguem acessar a tela.

## Onde encontrar

1. Acesse **Central de Automações** (menu do Backoffice).
2. Localize o card **"Atendimento IXC" / Abertura de OS em Massa** (segundo card da tela).

## Passo a passo

1. **Baixe a planilha modelo**, clicando em "Baixar Planilha Modelo" no card de Atendimento IXC.
2. **Preencha uma linha para cada atendimento** que precisa ser aberto, seguindo a tabela de campos abaixo.
3. **Envie a planilha preenchida** no botão "Planilha" e clique em **"Gerar Atendimentos"**.
4. Aguarde o processamento (o sistema mostra "Abrindo OS...").
5. Ao final, um **relatório em Excel** (`Relatorio_OS_IXC.xlsx`) é baixado automaticamente, mostrando o resultado linha a linha.

Não é preciso preencher todas as linhas da planilha na mesma hora — o sistema ignora qualquer linha em que o campo `Cliente_ID` estiver vazio.

## Campos da planilha

Todos os campos que terminam em `_ID` aceitam **apenas o número do IXC** — não use nome, endereço ou qualquer outro texto.

| Campo | O que colocar | Obrigatório? |
|---|---|---|
| `Cliente_ID` | ID numérico do cliente no IXC (ex.: 1234) | Sim |
| `Login_ID` | ID numérico do login do cliente no IXC (ex.: 5678) | Sim |
| `Contrato_ID` | ID numérico do contrato no IXC | Sim |
| `Filial_ID` | ID numérico da filial do IXC responsável pelo atendimento (ex.: 1) | Sim |
| `Assunto_ID` | ID numérico do assunto do ticket, cadastrado no IXC (consulte em Suporte > Assuntos) | Sim |
| `Departamento_ID` | ID numérico do departamento/setor do IXC que vai receber o atendimento (consulte em Suporte > Departamentos) | Sim |
| `Tipo_Processo` | `Avulso`, `Cotacao Parceiro` ou `Outro` — ver regra abaixo | Sim |
| `Workflow_ID` | ID numérico do workflow acionado ao abrir o atendimento — ver regra abaixo | Depende do `Tipo_Processo` |
| `Assunto_Descricao` | Título do atendimento, exibido no IXC | Sim |
| `Descricao` | Texto da primeira mensagem do atendimento | Sim |

### Regra do `Tipo_Processo` e `Workflow_ID`

| Tipo_Processo | O que fazer no Workflow_ID | O que acontece no IXC |
|---|---|---|
| `Avulso` | Deixe **vazio** | Abre o atendimento sem acionar nenhum workflow; nenhuma O.S. é gerada automaticamente. |
| `Cotacao Parceiro` | Informe exatamente **18** | Aciona o workflow de cotação de parceiro, que gera automaticamente uma O.S. de instalação. |
| `Outro` | Informe o **ID do workflow desejado** | Aciona o workflow informado. |

**Atenção:** se qualquer linha da planilha tiver uma combinação inválida de `Tipo_Processo`/`Workflow_ID`, **a planilha inteira é bloqueada** — nenhum atendimento é aberto, nem os das linhas corretas. Você recebe de volta o mesmo relatório apontando qual linha tem o erro e quais ficaram "não enviadas" por causa dele. Corrija e reimporte.

## O que a automação ajusta sozinha (não precisa se preocupar)

- O sistema acrescenta automaticamente, ao final da `Descricao`, o nome do usuário que fez a importação e a data/hora.
- O atendimento é criado **aberto**; esta automação nunca finaliza o atendimento (`finalizar_atendimento = Não`).

## O que é criado no IXC

Para cada linha válida da planilha, a automação cria um **atendimento (ticket) do tipo Cliente** no IXC, já vinculado:

- ao **cliente** (`Cliente_ID`);
- ao **login** (`Login_ID`);
- ao **contrato** (`Contrato_ID`);
- à **filial** (`Filial_ID`);
- ao **assunto** (`Assunto_ID`) e **departamento** (`Departamento_ID`) informados;
- ao **workflow**, quando aplicável (`Workflow_ID`), que pode gerar automaticamente uma O.S. de instalação (caso `Cotacao Parceiro`).

O título do atendimento é o `Assunto_Descricao` e a primeira mensagem é a `Descricao` informada (com a identificação de quem importou anexada ao final).

## O relatório de resultado

O arquivo baixado ao final (`Relatorio_OS_IXC.xlsx`) traz, para cada linha:

- **Status_Importacao:** `SUCESSO`, `ERRO`, `ERRO_VALIDACAO` ou `NAO_ENVIADO`;
- **Mensagem_Importacao:** detalhe do que aconteceu.

## Erros mais comuns

| Mensagem | O que significa |
|---|---|
| `{Campo}_ID deve conter apenas o ID numerico do IXC...` | Algum campo `_ID` foi preenchido com texto, endereço ou nome em vez do número. |
| `Tipo_Processo invalido: '...'` | O valor não é exatamente `Avulso`, `Cotacao Parceiro` ou `Outro`. |
| `Tipo_Processo 'Avulso' exige Workflow_ID vazio...` | Há um número em `Workflow_ID` numa linha marcada como `Avulso`. Apague o valor. |
| `Tipo_Processo 'Cotacao Parceiro' exige Workflow_ID=18...` | O `Workflow_ID` está vazio ou diferente de 18 numa linha `Cotacao Parceiro`. |
| `Tipo_Processo 'Outro' exige Workflow_ID preenchido.` | Falta informar o número do workflow numa linha `Outro`. |
| `Login_ID invalido para cliente ...` | O `Login_ID` está vazio ou não é numérico. |
| `Assunto_Descricao vazio` / `Descricao vazia` | Um dos campos de texto obrigatórios não foi preenchido. |
| `Erro 401: token invalido ou sem permissao` | Falha de autenticação com o IXC. Acione o suporte técnico. |
| `IXC negou o ticket: [mensagem do IXC]` | O IXC recusou a abertura (ex.: assunto ou departamento inexistente). Revise os IDs informados. |
| `Ticket criado sem ID retornado pela API` | O IXC processou mas não confirmou o número do ticket. Confira diretamente no IXC. |
| `Erro Tecnico: ...` | Falha inesperada. Acione o suporte técnico informando a mensagem completa. |

Se **nenhuma** linha tiver erro de `Tipo_Processo`/`Workflow_ID`, o processamento segue normalmente linha a linha: um erro de uma linha (ex.: IXC negou o ticket) não impede a abertura dos atendimentos das demais linhas.

## Acompanhamento

Toda execução (quem importou, quantos atendimentos foram abertos com sucesso, quantos falharam e quando) fica registrada e pode ser consultada na tela de **Central de Automações**, na lista de execuções abaixo dos cards, com filtro por usuário e por mês.

## Cuidados importantes

- Sempre confira os IDs (cliente, login, contrato, filial, assunto, departamento, workflow) antes de importar — IDs errados abrem o atendimento vinculado ao cliente, setor ou processo errado.
- Preste atenção especial à combinação `Tipo_Processo`/`Workflow_ID`: um erro nesse campo bloqueia a planilha inteira, mesmo que as demais linhas estejam corretas.
