# ADR-025 - Generalizacao de subatividades e multiplas atividades principais (decisao adiada)

## Status

`Aprovado`

> Esta ADR registra uma decisao de **adiamento**. Nao desenha um alvo tecnico
> nem autoriza qualquer execucao de codigo agora — define apenas que a
> generalizacao descrita abaixo nao sera feita nesta rodada, e o que precisa
> acontecer para ela voltar a ser considerada.

## Contexto

Usuario pediu (2026-08-11) a capacidade de criar subatividades (hoje Rede
Externa/RE e Rede Interna/RI) sem precisar codificar cada uma: um cadastro no
Admin para criar quantas subatividades forem necessarias, escolhendo em qual
atividade principal cada uma aparece, ou aplicando a todas.

Investigacao do Orquestrador, antes de desenhar a feature, confirmou o estado
real do codigo:

- existe hoje **uma unica** atividade principal no sistema inteiro: `Escola`
  (`apps.escolas.Escola`). Nenhum outro app tem esse conceito;
- RE e RI **nao** sao linhas de um cadastro dinamico — sao dois Django models
  fixos e hardcoded (`RedeExterna`, `RedeInterna`, ADR-012), cada um com
  `OneToOneField` para `Escola`, tabela propria, e uma superficie grande de
  telas e regras de negocio escritas especificamente em termos de "RE" e "RI"
  (grid de Enderecos Lastmile, modal de Campos, modal de historico, modal de
  parceiro, visao por Setor, envio de e-mail) — RN-023 a RN-042 (20 regras).

Generalizar isso (catalogo administravel de tipos de subatividade + model de
instancia generico, e suporte a mais de uma atividade principal) e uma
refatoracao arquitetural de grande porte, na area mais ativa do sistema.

Apresentadas as alternativas, o usuario decidiu (2026-08-11): por ora, nao
fazer essa generalizacao. O pedido concreto imediato passou a ser criar mais
uma subatividade fixa, "Mapa Calor", no mesmo molde hardcoded de RE/RI —
implementada em codigo pelo Dev, nao cadastrada pelo usuario via Admin (ver
RN-043 e PO-067, `docs/BACKLOG.md`).

## Decisao

Adiar a generalizacao. Nenhum trabalho de codigo sera feito agora para
suportar:

- um catalogo administravel de tipos de subatividade (o usuario cadastrando
  novas subatividades pelo Admin, sem intervencao do Dev);
- mais de uma atividade principal alem de `Escola`.

A extensao imediata (subatividade "Mapa Calor", RN-043/PO-067) segue o padrao
hardcoded ja usado por `RedeExterna`/`RedeInterna` (ADR-012), reaproveitando a
classe abstrata `ProcessoRedeBase` ja existente — sem introduzir catalogo ou
abstracao nova de subatividade.

Registrado aqui, para nao bloquear silenciosamente o caminho futuro: ao
implementar Mapa Calor (e qualquer outra subatividade fixa que vier antes da
generalizacao), o Dev nao precisa adotar nenhuma medida extra de
"preparacao" para a generalizacao futura — nao ha exigencia formal nesta
ADR. A decisao de como generalizar (e o que fazer com os dados de RE/RI/Mapa
Calor ja existentes) fica inteiramente para quando o usuario decidir avancar.

## Consequencias positivas

- evita o risco de regressao nas 20 regras de negocio ja em producao
  (RN-023 a RN-042) ao mexer na area mais ativa do sistema;
- entrega o pedido concreto (mais uma subatividade, Mapa Calor) no padrao ja
  validado por RE/RI, sem esperar um redesenho maior;
- nao compromete nenhuma decisao de dado agora — a porta para generalizar
  depois continua aberta.

## Consequencias negativas / riscos

- o problema original do usuario ("nao digitar codigo toda vez que precisar
  de uma subatividade nova") **nao e resolvido agora**, apenas adiado;
- cada subatividade fixa nova (Mapa Calor, e qualquer outra antes da
  generalizacao) aumenta o numero de lugares no codigo que hoje enumeram RE/RI
  explicitamente (grid, modais, cascata Setor/Status, e-mail) — quanto mais
  subatividades hardcoded existirem quando a generalizacao for decidida, maior
  o esforco de migracao de dados e de codigo naquele momento;
- se, no futuro, surgir de fato uma segunda atividade principal antes da
  generalizacao ser decidida, o desenho atual (RE/RI/Mapa Calor amarrados
  especificamente a `Escola`) precisara ser revisto do zero para aquele caso.

## Alternativas consideradas

### Generalizar agora: catalogo administravel de tipos de subatividade + model de instancia generico

Rejeitada por decisao do usuario em 2026-08-11. Prioridade agora e a entrega
concreta (Mapa Calor); a generalizacao propriamente dita fica para uma versao
futura do sistema, sem data definida.

### Suportar multiplas atividades principais desde ja

Rejeitada por decisao do usuario. Hoje existe so `Escola`; nao ha necessidade
concreta de outra atividade principal no momento, e desenhar para uma
atividade principal hipotetica correria o risco de acertar a abstracao errada
sem um segundo caso real para validar contra.

### Hibrido: generalizar so RE/RI (sem tocar em "atividade principal"), mantendo Escola fixa

Nao chegou a ser proposta como alternativa formal ao usuario nesta rodada —
citada aqui porque pode ser o primeiro passo natural quando a generalizacao
for retomada (reduz o escopo de uma vez so). Sem decisao tomada sobre ela.

## Pendencias

- quando o usuario decidir avancar com a generalizacao, esta ADR deve ser
  substituida por uma nova, com o desenho completo: catalogo de tipos de
  subatividade, model de instancia generico, e um plano explicito de migracao
  de dados para o que existir de RE/RI/Mapa Calor (e de outras subatividades
  fixas eventualmente criadas ate la);
- se surgir uma segunda atividade principal real antes da generalizacao,
  trazer o caso concreto ao Orquestrador antes de generalizar — evita repetir
  o erro ja registrado na ADR-022 (desenhar em cima de um entendimento
  hipotetico em vez de um pedido real).

## Gatilho de regeneracao

Nao ha diagrama associado a esta ADR — e uma decisao de adiamento, sem
desenho tecnico. Verificado: `docs/diagrams/03 - modelo-dominio.html` (e o
JSON que o gera) nao tem hoje nenhum gatilho de regeneracao registrado
referente a este tema. Se uma ADR futura substituir esta com o desenho da
generalizacao, cabe a ela registrar ali o gatilho de regeneracao do diagrama
de dominio, refletindo o catalogo generico.
