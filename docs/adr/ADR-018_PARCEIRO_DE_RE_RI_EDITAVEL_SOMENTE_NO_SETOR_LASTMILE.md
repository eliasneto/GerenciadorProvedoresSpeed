# ADR-018 - Parceiro de RE/RI editavel somente no Setor Lastmile, via modal de selecao

## Status

`Aprovado`

## Contexto

ADR-015 deixou uma pendencia registrada: `Parceiro`
(`RedeExterna.parceiro`/`RedeInterna.parceiro`, ADR-012) ficou sem editor
dedicado, editavel so pelo Django Admin.

O usuario pediu para resolver essa pendencia, explicando o motivo: cada RE e
cada RI pode ter um Parceiro diferente, e apenas o setor de Lastmile deve
poder fazer esse vinculo. Perguntado se "setor de Lastmile" era o Setor de
negocio cadastrado no catalogo (RN-025/ADR-014 — um dos 5 nomes: Lastmile,
Suprimentos, Implantacao, Pos venda, Suporte) ou o grupo de permissao Django
`LastMile` que ja protege a tela inteira (ADR-011), confirmou que e o Setor
de negocio.

O usuario tambem informou acreditar que ja existia, no sistema, um modal
pronto para escolher Parceiro. Verificado: nao existe. O que existe e um
painel de busca de Parceiro (nome, cidade, UF, bairro) usado na conversao de
Lead em Proposta (`endereco_lastmile_partner_search`, `apps.leads`) — um
painel embutido na pagina, nao uma janela modal, e atuando sobre outro
modelo (`LeadEndereco`), nao sobre `RedeExterna`/`RedeInterna`. Perguntado,
o usuario confirmou criar um modal novo, reaproveitando essa logica de
busca.

## Decisao

1. O campo `parceiro` de `RedeExterna`/`RedeInterna` passa a ser editavel na
   linha expandida do grid de Enderecos Lastmile (RN-024/RN-026), mas
   somente quando a linha esta sendo vista a partir da tela do Setor de
   negocio "Lastmile" (`setor_atual == "Lastmile"`, RN-027/ADR-016). No grid
   global e nas telas dos demais Setores, o campo permanece somente leitura
   — mesmo que o RE/RI ja tenha um Parceiro vinculado.
2. Diferente da regra de "pertence ao setor atual" usada para Setor/Status
   (ADR-015 — editavel quando o RE/RI ja esta naquele Setor), a edicao de
   Parceiro e fixa ao Setor "Lastmile": um RE/RI que esteja hoje no Setor
   "Suprimentos", por exemplo, so tem seu Parceiro editado a partir da tela
   do Setor "Lastmile", nunca a partir da tela de "Suprimentos".
3. A edicao abre um modal (mesmo padrao visual dos modais ja existentes no
   grid — historico, RN-029) com busca de Parceiros por nome, cidade, UF e
   bairro, reaproveitando a logica de filtro ja implementada em
   `endereco_lastmile_partner_search` — adaptada para retornar a lista
   dentro do modal, sem o contexto de cobertura regional do endereco de
   Lead.

## Decisao detalhada

### Campo Parceiro — condicao de edicao

```text
editavel_parceiro = (setor_atual == "Lastmile")
```

Independe de a linha de RE/RI ja ter Setor definido ou nao, e independe de
qual seja esse Setor — a unica condicao e estar na tela do Setor "Lastmile".

### Modal de selecao

- reaproveita os filtros de `endereco_lastmile_partner_search` (nome,
  cidade, UF, bairro), consultando `partners.Partner` diretamente — sem o
  calculo de cobertura regional por endereco de Lead, que nao se aplica
  aqui;
- abre pelo mesmo botao/padrao visual dos demais modais do grid (ex.:
  historico, RN-029);
- selecionar um Parceiro na lista fecha o modal e preenche o campo na
  linha, sem salvar ainda — salvar continua sendo a acao explicita do
  botao "Salvar" da linha (mesmo fluxo de Setor/Status, RN-026).

### Historico

- alteracao de Parceiro pela tela gera `RegistroHistorico` (RN-029), no
  mesmo padrao "Antes/Depois" ja usado para Setor/Status; edicao feita
  direto no Django Admin nao gera esse log.

### O que NAO muda

- a permissao de acesso ao grid inteiro continua `grupo_LastMile_required`
  (ADR-011) — a restricao por Setor "Lastmile" e adicional, nao substitui
  essa permissao;
- Setor/Status continuam com a regra propria de "pertence ao setor atual"
  (ADR-015) — Parceiro tem regra propria, fixa ao Setor "Lastmile".

## Consequencias positivas

- resolve a pendencia deixada pela ADR-015;
- restringe uma decisao comercial sensivel (vinculo com Parceiro) a quem de
  fato faz esse trabalho, sem exigir Django Admin;
- reaproveita busca de parceiro ja validada em producao, sem inventar
  filtro novo.

## Consequencias negativas / riscos

- um RE/RI so tem o Parceiro alterado quando alguem abrir especificamente a
  tela do Setor "Lastmile" — se o habito do time for trabalhar pelo grid
  global, exige adaptacao;
- duas regras de edicao diferentes convivendo na mesma linha (Setor/Status
  por "pertence ao setor atual", Parceiro fixo em "Lastmile") pode confundir
  quem le o codigo sem esta ADR — mitigado por este documento e por
  comentario no codigo apontando para ele.

## Alternativas consideradas

### Restringir por grupo de permissao Django `LastMile` (em vez de Setor de negocio)

Rejeitada. O grupo `LastMile` ja da acesso a tela inteira hoje; usar o
mesmo grupo para restringir Parceiro nao mudaria nada na pratica (todo
usuario que ve a tela ja e do grupo). O usuario confirmou que a restricao
real e pelo Setor de negocio do catalogo.

### Manter o painel de busca existente como esta, sem modal

Rejeitada. O painel de `endereco_lastmile_partner_search` tem layout
proprio da pagina de conversao de Lead; o usuario pediu explicitamente um
modal, e o grid de Enderecos Lastmile ja usa modais para outras acoes
(historico), mantendo o padrao visual da tela.

## Pendencias

Nenhuma nova identificada; esta ADR resolve a pendencia deixada pela
ADR-015.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
