# ADR-016 - Visao por Setor das atividades de RE e RI

## Status

`Aprovado`

> **Emenda (2026-08-07):** o grid proprio (Tipo/Escola/Status/Parceiro)
> descrito abaixo foi substituido pela ADR-017 — a tela de Setor passou a
> reaproveitar o mesmo grid de Enderecos Lastmile (Escola + RE/RI),
> trazendo de volta INEP/Estado/Municipio/Endereco. A decisao de
> "somente leitura" tambem foi revogada: a edicao de Setor/Status (RN-026)
> agora fica disponivel na tela de Setor tambem.

## Contexto

RN-026/ADR-015 tornaram `Setor` (e `Status`) editaveis em `RedeExterna`/
`RedeInterna`, direto no grid de Enderecos Lastmile. O usuario agora quer
que cada Setor (ex.: "Suprimentos") tenha sua propria tela, mostrando as
atividades (RE e RI) que estao atualmente com aquele Setor — para que quem
trabalha em "Suprimentos" veja so o que e dele, sem abrir a lista completa
de escolas.

Pedido, verbatim: "cada setor tem que ter usa propria visão, então se um
RE ou RI estiver no setor Suprimentos, suprimentos precisa ter um
ambiente onde o grid dele tenha a visão das atividades que estão com ele.
Precisamos criar uma aba no MENU chamado setor e criar uma visão para
cada setor existente, inicialmente você precisa apenas mostrar um grid
com as RE e Ri que estiver com cada setor."

Contexto tecnico relevante: `Setor` (PO-050) e cadastrado **por Processo**
(unico por `processo+nome`) — hoje existem 2 Processos ("Rede Externa
(RE)" e "Rede Interna (RI)"), cada um com os mesmos 5 nomes de Setor
(Lastmile, Suprimentos, Implantacao, Pos venda, Suporte), deliberadamente
espelhados (PO-050) exatamente para que RE e RI pudessem compartilhar o
mesmo vocabulario de Setor. Ou seja, hoje existem **duas linhas de
`Setor`** chamadas "Suprimentos" no banco (uma do Processo de RE, outra do
Processo de RI) — sao registros diferentes, mesmo nome.

## Decisao

Uma tela por **nome de Setor** (nao por linha de `Setor`), agrupando as
atividades de `RedeExterna` e `RedeInterna` que estejam vinculadas a
qualquer `Setor` com aquele nome, atraves de qualquer Processo. Nova secao
"Setores" no menu lateral, com um link por nome de Setor cadastrado.

**Suposicao registrada** (decisao tecnica reversivel, corrigir e simples
se estiver errada): "Suprimentos" e o mesmo lugar de trabalho
independente de ter vindo do processo de RE ou de RI — e por isso o
agrupamento e por nome, cruzando os dois Processos. Foi assim que a PO-050
foi desenhada (mesmos 5 nomes nos dois Processos, a pedido do proprio
usuario). Se a intencao for, na verdade, duas visoes separadas
("Suprimentos (RE)" e "Suprimentos (RI)"), e ajuste pontual na consulta,
sem mudanca de modelo.

## Decisao detalhada

### Rota e agrupamento

- `GET /prospeccao/setores/` — lista os nomes de Setor cadastrados
  (distintos, `Setor.objects.values_list('nome', flat=True).distinct()`);
- `GET /prospeccao/setores/<str:nome>/` — grid com todo `RedeExterna` e
  `RedeInterna` cujo `setor__nome` seja igual a `nome` (em qualquer
  Processo), com paginacao no mesmo padrao das demais telas do projeto;
- nome do Setor usado direto na URL (sem slug dedicado — nao ha caracteres
  ambiguos nos nomes cadastrados hoje; se isso mudar, adicionar slug e
  mudanca aditiva).

### Conteudo do grid (MVP — somente visualizacao)

Por linha: tipo (RE/RI), Escola (INEP + nome), Status atual, Parceiro
(quando houver). **Somente leitura nesta entrega** — usuario pediu
explicitamente "inicialmente ... apenas mostrar um grid"; editar
Setor/Status a partir desta tela fica para decisao futura.

### Menu

Nova secao "Setores" no sidebar (`core/base.html`), no mesmo padrao das
secoes existentes (Backoffice, Gestao, Administracao — cabecalho +
sublinks). Os sublinks (um por nome de Setor) sao dinamicos — vem do
banco, nao de uma lista fixa no template. Implementar via context
processor (mesmo padrao ja usado em
`apps.core_admin.context_processors.automacoes_realocadas`), disponivel em
toda pagina, para o sidebar renderizar sem cada view precisar repassar a
lista manualmente.

### Onde vive o codigo

Views/URLs/templates em `apps.leads` (mesmo app de `enderecos_lastmile`,
que ja mostra RE/RI) — nao um app novo. Nenhum model novo.

### Permissao

Mesma que ja protege Enderecos Lastmile hoje (`grupo_LastMile_required`,
grupo `LastMile` ou superuser). Nenhuma permissao por Setor especifico
(ex.: usuario do time Suprimentos ver so a tela de Suprimentos) foi pedida
nesta entrega — todo usuario com acesso a esta area ve todas as telas de
Setor. Se precisar restringir por time, e decisao futura (exigiria
vincular usuario a Setor, conceito que nao existe hoje).

## Consequencias positivas

- cada time ve so o que e dele, sem filtrar manualmente a lista completa;
- reaproveita 100% o que ja existe (`Setor`, `RedeExterna`/`RedeInterna`,
  RN-023/RN-026) — nenhum model novo;
- menu dinamico: cadastrar um Setor novo na tela de Processos (PO-050) faz
  a visao aparecer automaticamente, sem deploy.

## Consequencias negativas / riscos

- suposicao de agrupamento por nome (cruzando Processos) pode nao ser o
  que o usuario imaginava — risco mitigado por ser ajuste simples na
  consulta, nao no modelo;
- sem edicao nesta versao — quem usa a tela do Setor ainda precisa voltar
  para Enderecos Lastmile para mudar Setor/Status (aceitavel, o usuario
  pediu "apenas mostrar" por agora).

## Alternativas consideradas

### Uma visao por linha de Setor (Processo+nome), nao por nome

Rejeitada por agora — ver "Suposicao registrada" acima. O pedido do
usuario ("se um RE ou RI estiver no setor Suprimentos") trata Suprimentos
como um lugar so, nao dois.

### Pagina unica com filtro de Setor (em vez de uma URL por Setor)

Rejeitada. Usuario pediu explicitamente "criar uma visão para cada setor
existente" e "uma aba no MENU" — leitura mais direta e uma tela dedicada
por Setor, acessivel pelo menu, nao um filtro dentro de uma tela generica.

## Pendencias

- decisao futura: editar Setor/Status direto na tela do Setor (hoje so
  Enderecos Lastmile permite, RN-026);
- ~~decisao futura: restringir cada tela de Setor a um grupo/time
  especifico de usuarios~~ — **resolvida pela ADR-028 (2026-08-13):** grupo
  dedicado `Setor` (visibilidade do modulo) mais concessao individual por
  nome de Setor (RN-054/RN-055);
- confirmar com o usuario, apos a primeira entrega, se o agrupamento por
  nome (cruzando RE/RI) bateu com a expectativa.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
