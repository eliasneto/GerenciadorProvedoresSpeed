# ADR-013 - Exibicao dos dados de referencia de RE e RI (API DashboardEACE) na tela de Enderecos Lastmile

## Status

`Aprovado`

## Contexto

A tela "Enderecos / Lastmile" (`leads:enderecos_lastmile`, ADR-011/PO-047)
lista as `Escola` sincronizadas do DashboardEACE. O usuario pediu para ver,
ao clicar numa escola, duas linhas expandidas abaixo dela — uma de Rede
Externa (RE) e outra de Rede Interna (RI) — com "dados de RE e RI que ja
vem pela API" da EACE.

Esses dados ja existem hoje, sem uso, dentro de `Escola.dados_api` (JSON):
`setor_re`, `setor_ri`, `parceiro_re`, `parceiro_ri`,
`custo_re_implantacao`, `custo_re_recorrente`, `custo_ri_implantacao`,
`custo_ri_recorrente` (confirmados contra a API real na ADR-010).

Perguntado se essa expansao deveria tambem exibir/editar o processo interno
`RedeExterna`/`RedeInterna` (models criados na PO-048/ADR-012, hoje vazios
para toda escola), o usuario confirmou: **por agora, so a referencia que ja
vem da API**, sem edicao e sem tocar nos models de processo interno.

## Decisao

Na tela de Enderecos Lastmile, cada linha de `Escola` ganha uma acao de
expandir que revela duas linhas somente-leitura abaixo dela — RE e RI —
com os campos `setor_*`, `parceiro_*`, `custo_*_implantacao` e
`custo_*_recorrente` lidos diretamente de `Escola.dados_api`.

## Decisao detalhada

### Fonte do dado — sem promover para coluna nova, sem tocar em RedeExterna/RedeInterna

Os 8 campos continuam vivendo somente em `Escola.dados_api` (JSON). Nao ha
necessidade de promove-los a coluna tipada (ADR-010 autoriza isso quando
necessario, mas aqui nao ha busca/ordenacao/filtro por esses campos — so
exibicao). Decisao tecnica reversivel e de baixo risco (secao 11 do
`CLAUDE.md`): ler o JSON direto no template/contexto da view.

Esta feature **nao** cria, le nem exibe `RedeExterna`/`RedeInterna`
(PO-048) — sao coisas propositalmente diferentes agora: um e o dado bruto
de referencia da API (o que ja veio), o outro e o processo que o sistema
vai gerir daqui pra frente (hoje vazio). Ligar os dois e decisao futura, se
o usuario pedir.

### Campos exibidos por processo

RE: Setor (`setor_re`), Parceiro (`parceiro_re`), Custo de implantacao
(`custo_re_implantacao`), Custo recorrente (`custo_re_recorrente`).

RI: Setor (`setor_ri`), Parceiro (`parceiro_ri`), Custo de implantacao
(`custo_ri_implantacao`), Custo recorrente (`custo_ri_recorrente`).

Campo ausente ou vazio no JSON exibe placeholder "Nao informado", no mesmo
padrao ja usado nas demais colunas desta tela (ex.: municipio).

### Comportamento de expansao

Clique na linha da escola alterna (mostra/esconde) as duas linhas de RE/RI
imediatamente abaixo, sem nova requisicao ao servidor — os dados de
`dados_api` ja vem carregados na consulta que monta a pagina (mesmo
queryset que hoje alimenta a tabela). Implementado (2026-08-07, pelo Dev)
com JavaScript simples (`classList.toggle`/`addEventListener`), no mesmo
padrao ja usado em outras telas do app `leads` — nao introduziu Alpine.js,
por nao haver necessidade real (tecnologia ja usada no projeto tem
prioridade sobre nova biblioteca, mesmo quando esta ADR previu Alpine
como opcao).

### O que NAO faz parte desta ADR

- edicao de setor/parceiro/custo (esses campos vem da sincronizacao com o
  DashboardEACE, ADR-010 — nao sao editaveis pelo sistema);
- qualquer leitura, criacao ou exibicao de `RedeExterna`/`RedeInterna`
  nesta tela;
- promocao dos 8 campos para colunas tipadas em `Escola`.

## Consequencias positivas

- Responde exatamente ao que foi pedido ("dados que ja vem pela API"), sem
  inventar edicao nem misturar com o processo interno ainda vazio;
- nenhuma migration necessaria — leitura direta do JSON ja sincronizado;
- baixo acoplamento: nao toca em `RedeExterna`/`RedeInterna`/ADR-012.

## Consequencias negativas / riscos

- se o usuario esperar, ao ver a linha de RE/RI expandida, editar aqueles
  valores ou vincular um `Partner`/status, essa expectativa nao e atendida
  por esta feature — o usuario confirmou explicitamente que quer so a
  referencia por agora;
- os 8 campos podem estar ausentes para escolas sincronizadas antes de a
  API os preencher, ou nunca preenchidos por aquela escola nao ter aquele
  processo — tratado como "Nao informado", nao como erro.

## Alternativas consideradas

### Exibir tambem RedeExterna/RedeInterna (criando o registro na hora, se nao existir)

Rejeitada por agora. Usuario escolheu explicitamente a opcao mais simples
("so a referencia da API"), deixando a uniao dos dois conceitos (dado de
referencia da API x processo interno gerido pelo sistema) para decisao
futura.

### Promover os 8 campos para colunas tipadas em Escola

Rejeitada por agora. Nao ha necessidade de busca/ordenacao/filtro por eles
nesta feature — leitura direta do JSON e suficiente e evita migration sem
beneficio imediato.

## Pendencias

- Decisao futura: se/quando a referencia da API (`setor_re`/`parceiro_re`/
  etc.) e o processo interno (`RedeExterna`/`RedeInterna`) devem aparecer
  juntos na mesma tela, e como reconciliar os dois.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
