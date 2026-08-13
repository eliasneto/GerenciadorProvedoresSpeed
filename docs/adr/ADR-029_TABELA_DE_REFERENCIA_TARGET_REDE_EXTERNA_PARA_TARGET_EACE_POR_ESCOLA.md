# ADR-029 - Tabela de referencia propria para TARGET EACE (UF x Velocidade), espelhando `target_rede_externa`

## Status

`Aprovado` — decisao de negocio/arquitetura do usuario. Nome exato do
model/app, mecanismo de importacao e tratamento do mismatch de tipo
(`int`/`decimal`) ficam a criterio tecnico do Dev (ver Pendencias) — esta
ADR nao fecha esses pontos.

## Contexto

A RN-057/PO-076 (2026-08-13) identificou que o "TARGET EACE" mencionado
pelo usuario para uma escola nao e um dado por escola: e um valor de
referencia por UF e velocidade contratada, hoje mantido pelo DashboardEACE
numa tabela `target_rede_externa`, do banco de origem `eace_jira`
(confirmada por inspecao estrutural de um backup real fornecido pelo
usuario, `eace_jira_backup_20260813.sql.gz` — ver ADR-010, emenda
2026-08-13; **somente estrutura foi inspecionada, nenhuma linha de dado
real foi lida ou copiada para a documentacao**). Essa tabela nao e exposta
por nenhum endpoint documentado em `API_EXTERNA.md` — o SGP so tem acesso a
ela porque o usuario forneceu o backup manualmente.

Questionado sobre como o TARGET EACE de uma escola deveria ser obtido, o
usuario respondeu, em 2026-08-13, com as palavras exatas: "essa tabela:
'target_rede_externa' informa o valor da rede externa que o cliente EACE
disponibilizada para nós, esse é o TARGET EACE. preciso dessa tabela toda
no nosso sistema, vamos usar para pegar os valores das velocidades por
estado e colocar na escola."

## Decisao

Replicar a tabela de referencia inteira no SGP, como um catalogo proprio
(UF + velocidade -> valor) — **nao** como campo individual gravado em
`Escola`. O TARGET EACE de uma escola especifica passa a ser **derivado por
consulta** (UF da escola + velocidade minima da escola) contra esse
catalogo, no mesmo espirito das propriedades somente-leitura ja existentes
em `Escola` (`referencia_rede_externa`/`referencia_rede_interna`/
`referencia_mapa_calor`, ADR-013) — nunca um valor copiado/armazenado na
linha da Escola.

## Decisao detalhada

### Estrutura confirmada na origem (`eace_jira.target_rede_externa`)

| Coluna | Tipo | Papel |
|---|---|---|
| `uf` | `varchar(2)` | Estado |
| `velocidade_mbps` | `int` | velocidade contratada — **match exato**, nao faixa (`UNIQUE KEY (uf, velocidade_mbps)` na origem) |
| `valor` | `decimal(10,2)` | valor de referencia (TARGET EACE) para aquele UF + velocidade |

A origem tinha `AUTO_INCREMENT=79` no backup inspecionado — tabela pequena
(por volta de 78 combinacoes), compativel com "preciso dessa tabela toda no
nosso sistema".

### O que fica para o Dev decidir (tecnico, reversivel, baixo risco)

- nome exato do model/app — este documento e a RN-057/PO-076 usam
  `TargetRedeExterna` apenas como **nome de trabalho** para as tres
  documentacoes conseguirem se referenciar de forma consistente, no mesmo
  vocabulario em portugues ja usado por `Escola`/`RedeExterna`/
  `RedeInterna`/`Processo`/`Setor`/`Campo` (`apps.escolas`) — **nao** e uma
  decisao final de nomenclatura; CLAUDE.md secao 8 pede codigo em ingles, o
  que hoje ja diverge do padrao Portugues predominante nesses models
  existentes. O Dev segue a convencao ja estabelecida no app ou traz a
  divergencia ao Orquestrador antes de nomear, sem que esta ADR imponha
  uma ou outra;
- app dono: o candidato natural e `apps.escolas` (mesmo app de `Escola` e
  dos demais catalogos ligados a Rede Externa/Interna), mas a confirmacao
  fica com o Dev/Orquestrador no momento da implementacao;
- mecanismo de importacao/atualizacao dos dados: nao ha endpoint de API
  para isso — a origem e o backup fornecido manualmente pelo usuario.
  Importacao inicial via management command (mesmo padrao de
  `apps/clientes/management/commands/importar_planilha.py`) ou cadastro via
  Django Admin, a criterio do Dev;
- como tratar o cruzamento de tipo `velocidade_mbps` (`int` na origem)
  contra `Escola.velocidade_dl_minima` (`decimal`, RN-057/PO-076 Parte 1)
  no lookup — precisa de arredondamento/cast cuidadoso, para nao falhar
  silenciosamente quando a velocidade da escola nao for um inteiro exato.

### Como se relaciona com Escola

- **nao ha FK de `Escola` para essa tabela** — a leitura e por **UF +
  velocidade** (mesma chave unica da origem), nunca por uma linha
  especifica vinculada;
- quando `Escola` ganhar a coluna tipada de Velocidade Minima (RN-057/
  PO-076 Parte 1), uma propriedade somente-leitura calcula o TARGET EACE
  daquela escola buscando `uf=Escola.uf` e `velocidade_mbps`
  correspondente nesse catalogo; sem correspondencia exata, o valor fica
  vazio — nunca inventado ou aproximado (mesmo principio da RN-051);
- exibicao dentro da area de Campos vinculada a Atividade Principal
  (Escola), RN-037/038, sempre somente leitura, junto com Velocidade
  Minima e Kit Inicial (RN-057).

## Consequencias positivas

- tabela pequena (~78 linhas), simples de importar e manter por completo,
  exatamente como pedido pelo usuario;
- reaproveita o padrao ja existente de "referencia somente-leitura
  calculada" (ADR-013), sem introduzir mecanismo novo de exibicao;
- independe de o DashboardEACE algum dia expor essa tabela via API — o SGP
  passa a ter sua propria copia de referencia, sob seu controle.

## Consequencias negativas / riscos

- a copia "congela" o valor no momento da importacao; se o EACE atualizar
  os valores de referencia no DashboardEACE, o SGP so reflete a mudanca com
  uma nova importacao manual — nao ha sincronizacao automatica (mesma
  limitacao ja aceita para os catalogos Setor/Processo/Campo, hoje mantidos
  manualmente);
- mismatch de tipo (`int` vs `decimal`) no cruzamento de velocidade pode
  deixar o TARGET EACE vazio para escolas com velocidade fracionaria, se
  nao tratado com cuidado pelo Dev;
- sem mecanismo de atualizacao definido ainda, o catalogo pode ficar
  desatualizado sem que ninguem perceba — mitigar com uma tela/rotina de
  reimportacao explicita, a criterio do Dev.

## Alternativas consideradas

### Confiar em campo calculado devolvido pela API do DashboardEACE (`EscolaOut`)

Rejeitada pelo usuario. Alem disso, nenhum endpoint documentado em
`API_EXTERNA.md` sugere que esse valor exista hoje na resposta de
`/escolas` — dependeria do DashboardEACE expor algo novo, fora do controle
do SGP.

### Guardar o TARGET EACE como valor copiado por escola (coluna em `Escola`, preenchida no momento da sincronizacao)

Rejeitada pelo usuario: "os valores das velocidades por estado" devem virar
uma tabela propria, e o valor por escola e derivado dela — nao um dado
individual gravado na escola.

## Pendencias

- nome definitivo do model/app e mecanismo de importacao — decisao tecnica
  do Dev;
- tratamento do mismatch de tipo `int`/`decimal` na chave de velocidade —
  decisao tecnica do Dev;
- forma de manter o catalogo atualizado no futuro (reimportacao manual,
  tela de administracao) — nao decidida; aceitavel por ora, no mesmo padrao
  dos demais catalogos do sistema (Setor/Processo/Campo);
- confirmar `kit_wifi` como "Kit Inicial" (RN-057, Parte 2) — pendencia
  separada, nao bloqueia esta ADR;
- avaliar se `valor_kit` (catalogo de preco por tipo de kit, tambem
  presente no backup) merece tratamento equivalente — fora do escopo desta
  ADR, nao pedido pelo usuario.

## Gatilho de regeneracao

Nenhum diagrama documenta esta ADR ainda. Quando o model for implementado,
atualizar o diagrama `03 · Modelo de dominio` (e `05 · Modulos e
dependencias`, se a nova tabela ficar em `apps.escolas`) para incluir a
nova entidade de referencia e sua relacao de lookup (sem FK) com `Escola`.
