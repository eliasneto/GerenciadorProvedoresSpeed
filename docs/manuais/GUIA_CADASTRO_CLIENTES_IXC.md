# Guia de Uso — Cadastro de Clientes no IXC
_Última atualização: 2026-07-10_

## O que é esta automação

Esta automação cadastra **clientes novos** (pessoa física ou jurídica) no IXC, vários de uma só vez. Ela evita que a equipe precise cadastrar cada cliente manualmente, tela por tela, dentro do IXC.

Você preenche uma planilha com os dados de cada cliente e o sistema cadastra cada um automaticamente no IXC.

**Importante:** esta automação **cria apenas o cadastro do cliente**. Ela não cria login nem contrato. Depois de cadastrar o cliente aqui e anotar o `Cliente_ID` retornado, use os cards **"Atendimento IXC"** e **"Logins IXC"** (ver os guias correspondentes) para abrir atendimento e criar o login desse cliente.

## Quem pode usar

Esta ferramenta é restrita à equipe do **Backoffice**. Usuários que não fazem parte desse grupo não conseguem acessar a tela.

## Onde encontrar

1. Acesse **Central de Automações** (menu do Backoffice).
2. Localize o card **"Clientes IXC" / Cadastro de Cliente** (terceiro card da tela).

## Passo a passo

1. **Baixe a planilha modelo**, clicando em "Baixar Planilha Modelo" no card de Clientes IXC. O arquivo já vem com uma linha de exemplo preenchida e uma aba **"Instrucoes_Ajuda"**, que traz a explicação de cada campo e, sempre que possível, a lista real de opções válidas de `Tipo_Cliente_ID` e `Filial_ID` já cadastradas no IXC.
2. **Preencha uma linha para cada cliente novo**, seguindo a tabela de campos abaixo.
3. **Envie a planilha preenchida** no botão "Planilha" e clique em **"Cadastrar Clientes"**.
4. Aguarde o processamento (o sistema mostra "Cadastrando Clientes...").
5. Ao final, um **relatório em Excel** é baixado automaticamente, mostrando o resultado linha a linha.

## Validação antes do envio (planilha "tudo ou nada")

Antes de cadastrar qualquer cliente, o sistema **revisa a planilha inteira**. Se **qualquer linha** tiver um erro de preenchimento, **nenhum cliente é cadastrado** — nem os das linhas corretas.

Nesse caso, você recebe de volta o arquivo `Validacao_Cadastro_Clientes_IXC.xlsx`, com uma coluna `Status_Validacao` (`OK` em verde ou `ERRO` em vermelho) e uma coluna `Erros_Validacao` explicando exatamente o que corrigir em cada linha. Corrija a planilha e importe novamente.

Só quando **todas** as linhas passarem na validação é que os clientes são de fato enviados ao IXC.

## Campos da planilha

| Campo | O que colocar | Obrigatório? |
|---|---|---|
| `Razao_Social` | Nome ou razão social do cliente (ex.: Cliente Teste LTDA) | Sim |
| `CNPJ_CPF` | CPF ou CNPJ, com ou sem máscara | Sim |
| `Nome_Fantasia` | Nome fantasia do cliente | Não |
| `Tipo_Pessoa` | `F`/`PF` (física) ou `J`/`PJ` (jurídica) | Não — se vazio, o sistema deduz pelo tamanho do documento |
| `IE_RG` | Inscrição estadual ou RG (pode usar "ISENTO") | Não |
| `Contribuinte_ICMS` | `S` (contribuinte), `N` (não contribuinte) ou `I` (isento) | Não — se vazio, o sistema deduz automaticamente |
| `Tipo_Cliente_Fiscal` | `01`=Comercial, `02`=Industrial, `03`=Serviços, `04`=Produtor Rural, `05`=Simples Nacional, `99`=Outros | Não — se vazio, usa `99` |
| `Tipo_Localidade` | `U` (Urbano) ou `R` (Rural) — não usar UF/estado aqui | Não — se vazio, usa `U` |
| `CEP` | CEP do endereço principal, com ou sem máscara | Sim |
| `Endereco` | Somente o nome da rua/avenida (ex.: RUA EXEMPLO) — **não** cole o endereço completo com CEP/cidade junto | Sim |
| `Numero` | Número do imóvel, só dígitos, ou `SN` para sem número | Não — se vazio, usa `SN` |
| `Bairro` | Bairro do endereço principal | Sim |
| `Cidade_ID_IXC` | ID numérico da cidade cadastrada no IXC (ex.: 887). Não usar nome da cidade | Sim |
| `Complemento` | Complemento do endereço (ex.: Sala 02) | Não |
| `Referencia` | Ponto de referência | Não |
| `Contato_Nome` | Nome do contato principal do cliente | Não |
| `Email` | E-mail principal do cliente | Sim |
| `Telefone` | Telefone principal, com ou sem máscara | Sim |
| `Tipo_Cliente_ID` | ID do tipo de cliente já cadastrado no IXC (ver aba Instrucoes_Ajuda) | Sim |
| `Tipo_Assinante_ID` | `1`=Comercial/Industrial, `2`=Poder Público, `3`=Residencial/PF, `4`=Público, `5`=Semi-Público, `6`=Outros | Não — se vazio, usa `3` |
| `Filial_ID` | ID da filial do IXC associada ao cliente (ver aba Instrucoes_Ajuda) | Sim |
| `Vendedor_ID` | ID do vendedor/responsável no IXC | Não |
| `Observacao` | Observação administrativa livre | Não |
| `Ativo` | `S` (ativo) ou `N` (inativo) | Não — se vazio, usa `S` |
| `Permitir_Duplicidade` | `Sim` para permitir cadastrar mesmo já existindo cliente com o mesmo documento/razão social | Não — se vazio, o sistema **bloqueia** duplicidade |
| `Prospeccao` | `Sim`/`Nao` — marca o cliente como prospecção no CRM do IXC | Não |
| `Confirmar_Cadastro` | Digite exatamente **SIM** | Sim |

## Regras importantes que a automação aplica

- **Confirmação obrigatória:** toda linha precisa ter `Confirmar_Cadastro = SIM`. Sem isso, a linha é recusada já na validação.
- **CPF/CNPJ é validado matematicamente** (dígitos verificadores), não só o tamanho. Um documento com número de dígitos certo mas verificador inválido é recusado antes de qualquer envio ao IXC.
- **Verificação de duplicidade:** por padrão, o sistema procura no IXC um cliente já existente com o mesmo CNPJ/CPF ou a mesma razão social. Se encontrar, **não cadastra de novo** — apenas informa o ID do cliente já existente. Para forçar o cadastro mesmo assim, preencha `Permitir_Duplicidade = Sim`.
- **Campo `Endereco` só aceita o logradouro.** Se você colar o endereço inteiro (com CEP, bairro, cidade), o sistema tenta cortar automaticamente a partir da primeira vírgula; se sobrar pouco texto, a linha é recusada pedindo para informar somente o nome da rua.
- **Campo `Numero`** só aceita dígitos ou `SN`; qualquer outro texto (ex.: "123 - Fundos") deve ser movido para `Complemento`.

## O que é criado no IXC

Para cada linha válida, a automação cria um **cadastro de cliente** (pessoa física ou jurídica) no IXC, com:

- dados cadastrais (razão social, documento, inscrição estadual/RG, contato, e-mail, telefone);
- endereço completo (CEP, logradouro, número, bairro, cidade, complemento, referência);
- vínculo com o **tipo de cliente** e a **filial** informados;
- classificação fiscal, tipo de localidade e tipo de assinante (usando os padrões descritos acima quando não informados);
- status ativo/inativo e marcação de prospecção, quando aplicável.

O sistema também acrescenta, ao campo de observação do cliente, a identificação de quem fez a importação e a data/hora.

## O relatório de resultado

O arquivo baixado ao final (`Relatorio_Cadastro_Clientes_IXC.xlsx`) traz, para cada linha:

- **Status_Importacao:** `SUCESSO` ou `ERRO`;
- **Mensagem_Importacao:** detalhe do que aconteceu;
- **ID_IXC:** número do cliente criado (ou já existente) no IXC.

## Erros mais comuns

| Mensagem | O que significa |
|---|---|
| `{Campo} e obrigatorio e nao foi informado.` | Um campo obrigatório da planilha ficou vazio. |
| `Confirmar_Cadastro deve ser preenchido com SIM...` | Faltou digitar `SIM` no campo de confirmação. |
| `CPF/CNPJ '...' invalido — digitos verificadores nao conferem.` | O documento tem o tamanho certo, mas os dígitos verificadores não batem — confira se foi digitado corretamente. |
| `CNPJ_CPF invalido: esperado 11 digitos (CPF) ou 14 digitos (CNPJ)...` | O documento não tem 11 nem 14 dígitos. |
| `Tipo_Cliente_ID '...' nao e uma opcao valida no IXC.` | O ID informado não existe entre os tipos de cliente cadastrados no IXC — confira a aba Instrucoes_Ajuda. |
| `Filial_ID '...' nao e uma opcao valida no IXC.` | Idem, para o ID de filial. |
| `Cidade_ID_IXC {id} nao encontrada no IXC.` | O ID de cidade informado não existe no IXC. |
| `Endereco '...' ficaria com apenas '...' apos remocao de CEP/cidade embutidos.` | O campo `Endereco` veio com o endereço completo colado; informe só o logradouro. |
| `Numero '...' invalido.` | O campo `Numero` tem texto além de dígitos ou `SN`. |
| `Cliente ja existente no IXC (ID ...). Nenhuma alteracao feita para {razao_social}.` | Já existe um cliente com o mesmo CNPJ/CPF ou razão social. Use `Permitir_Duplicidade = Sim` se o cadastro duplicado for intencional. |
| `Nao foi possivel cadastrar {razao_social} no IXC. [mensagem do IXC]` | O IXC recusou o cadastro por outro motivo. Revise a mensagem específica retornada. |

## Acompanhamento

Toda execução (quem importou, quantos clientes foram cadastrados com sucesso, quantos falharam e quando) fica registrada e pode ser consultada na tela de **Central de Automações**, na lista de execuções abaixo dos cards, com filtro por usuário e por mês.

## Cuidados importantes

- A planilha contém **dados pessoais do cliente** (CPF/CNPJ, e-mail, telefone, endereço). Trate o arquivo com o mesmo cuidado que trataria qualquer dado sensível: não compartilhe por canais inseguros e apague o arquivo do computador após o uso.
- Confira sempre `Tipo_Cliente_ID` e `Filial_ID` na aba **Instrucoes_Ajuda** da própria planilha modelo antes de preencher — os IDs corretos variam conforme o cadastro do IXC.
- Anote o `ID_IXC` retornado para cada cliente: ele é o `Cliente_ID` que você vai usar depois nas automações de Atendimento e de Criação de Login.
