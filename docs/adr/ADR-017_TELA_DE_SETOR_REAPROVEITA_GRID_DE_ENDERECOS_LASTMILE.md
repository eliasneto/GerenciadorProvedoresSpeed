# ADR-017 - Tela de Setor reaproveita o grid de Enderecos Lastmile (Escola + RE/RI), com edicao habilitada

## Status

`Aprovado`

## Contexto

ADR-016/PO-052 criaram a tela de Setor como uma lista simples e independente
(Tipo, Escola, Status, Parceiro), separada do grid de Enderecos Lastmile.
O usuario apontou uma perda real: essa lista simples nao mostra INEP,
Estado, Municipio, Endereco — informacao que so existe no grid de Escola
já construido (ADR-011/ADR-013). Pediu para "levar a visão da escola
também": a mesma tela que já existe hoje (Escola + subatividade RE/RI),
filtrada para mostrar so as escolas com atividade naquele Setor —
"a subatividade ... pode ser RE ou RI, ou as duas" (ou seja, mostrar so a
linha da subatividade que de fato esta naquele Setor, nao as duas sempre).

Perguntado se a edicao de Setor/Status (RN-026, disponivel no grid de
Enderecos Lastmile) deveria ficar disponivel tambem na tela de Setor —
ADR-016 havia decidido "somente leitura" — o usuario confirmou que **sim**,
deve ficar editavel tambem.

## Decisao

A tela de Setor deixa de ser uma lista propria (a da ADR-016/PO-052 e
descontinuada) e passa a **reaproveitar o mesmo grid de Enderecos
Lastmile** (mesmo template/partial), filtrado para mostrar somente as
`Escola` com `RedeExterna` ou `RedeInterna` vinculada a um `Setor` com o
nome da tela atual. A edicao de Setor/Status (RN-026) fica disponivel
tambem aqui — revogando a restricao "somente leitura" da ADR-016.

## Decisao detalhada

### Reaproveitamento em vez de duplicacao

`filtrar_escolas_lastmile` (`apps/leads/services.py`) ganha um parametro
opcional `setor_nome`. Quando informado, filtra
`Escola.objects.filter(Q(rede_externa__setor__nome=setor_nome) |
Q(rede_interna__setor__nome=setor_nome))`, mantendo os demais filtros
(busca, cidade, estado, ordenacao) como hoje.

`enderecos_lastmile.html` recebe variaveis de contexto para se adaptar:
titulo/subtitulo (ex.: "Setor / Suprimentos" em vez de "Enderecos /
Lastmile"), e o nome do Setor atual (`setor_atual`), usado para decidir
quais linhas de RE/RI mostrar (ver abaixo). Um unico template continua
servindo as duas rotas — mudanca de estilo feita uma vez vale para as
duas telas.

### Mostrar so a subatividade que bate com o Setor da tela

Na tela do Setor "Suprimentos": se `escola.rede_externa.setor.nome ==
"Suprimentos"`, mostrar a linha de RE; se `escola.rede_interna.setor.nome
== "Suprimentos"`, mostrar a linha de RI. Uma escola pode aparecer com as
duas linhas (RE e RI, se as duas estiverem em Suprimentos), so uma, nunca
as duas linhas fixas incondicionalmente como no grid global de Enderecos
Lastmile (que sempre mostra RE e RI, seja qual for o Setor de cada um).

No grid **global** (`/prospeccao/enderecos/`, sem filtro de Setor), o
comportamento atual continua: sempre mostrar as duas linhas (RE e RI),
qualquer que seja o Setor de cada uma — isso nao muda.

### Edicao habilitada na tela de Setor

Mesmo componente de edicao (Setor/Status em cascata, RN-026), mesma
permissao (`grupo_LastMile_required`) — sem controle novo. Quem esta
olhando a fila de "Suprimentos" pode avancar o Status ou mover o RE/RI
para outro Setor ali mesmo.

### Descontinuado

- a view `setor_detail` antiga (lista Tipo/Escola/Status/Parceiro) e seu
  template dedicado (`leads/setor_detail.html`) saem de uso, substituidos
  pela versao que reaproveita `enderecos_lastmile.html`;
- a URL `/prospeccao/setores/<nome>/` continua existindo (mesmo nome de
  rota) — só troca o que ela renderiza.

### O que NAO muda

- `setores_list` (`/prospeccao/setores/`) continua sendo o indice de
  nomes de Setor cadastrados, sem mudanca;
- menu lateral "Setores" continua apontando para as mesmas URLs.

## Consequencias positivas

- nenhuma informacao perdida (INEP, Estado, Municipio, Endereco voltam a
  aparecer);
- uma tela so para manter — ajustes visuais futuros (bordas, densidade,
  cores — como os que ja fizemos varias vezes nesta sessao) se aplicam nas
  duas rotas de uma vez;
- edicao de Setor/Status disponivel onde faz mais sentido operacionalmente
  (quem esta na fila do proprio Setor).

## Consequencias negativas / riscos

- a tela de Setor agora tambem permite escrever dados (antes era so
  leitura) — aceito pelo usuario explicitamente; risco de edicao
  indevida e o mesmo que ja existe hoje no grid global, nao um risco novo;
- template com mais uma condicional (mostrar RE/RI condicionalmente
  conforme o Setor da tela) — complexidade aceitavel, unica alternativa
  seria duplicar o template.

## Alternativas consideradas

### Manter as duas telas separadas (lista simples + grid completo)

Rejeitada. O usuario apontou perda de informacao real na lista simples;
manter as duas so aumentaria manutencao duplicada sem beneficio.

### Grid completo, mas sempre mostrando RE e RI (como no grid global)

Rejeitada. O usuario descreveu explicitamente "a subatividade ... pode
ser RE ou RI, ou as duas" — leitura mais direta e mostrar so a(s)
subatividade(s) relevante(s) aquele Setor.

## Pendencias

Nenhuma nova.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
