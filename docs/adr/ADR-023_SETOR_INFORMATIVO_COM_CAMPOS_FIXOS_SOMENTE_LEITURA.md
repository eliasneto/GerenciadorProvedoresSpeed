# ADR-023 - Setor informativo com Campos fixos, somente leitura em Escola e/ou RE/RI

## Status

`Aprovado`

> Esta ADR desenha a decisao de arquitetura. Nao autoriza inicio de execucao —
> a PO-062 (`docs/BACKLOG.md`) so comeca quando o usuario mandar `iniciar
> PO-062`.

## Contexto

Substitui a ADR-022, que partiu de um entendimento errado. O Dev chegou a
construir a tela desenhada na ADR-022 (model `SetorEscopo` reaproveitando
o Setor do catalogo de Processos, RN-025; escopo exclusivo entre Escola e
Sub-atividades; valor por instancia via `CampoValor`). Ao ver a tela
pronta, o usuario apontou que nao era isso: "Eu só pedi um setor e
adicionar uns campos nesse setor e esses campos aparecer como apenas
visualização e eu definir se quero que apareça na escola, na RE ou RI ou
os dois ou os 3, só isso".

Perguntado sobre o modal de Campos ja existente no grid de Enderecos
Lastmile (RN-032, o mesmo que lista os grupos "Implantacao", "Lastmile"
etc. por Setor), confirmou que os campos do Setor informativo devem
aparecer ali dentro, como mais um grupo, sempre somente leitura.
Perguntado se o valor varia por escola, confirmou que e fixo — o mesmo
valor aparece em qualquer Escola, RE ou RI onde o Setor informativo
estiver marcado para aparecer.

## Decisao

Criar um catalogo novo e independente — `SetorInformativo` → `CampoInformativo`
— em `apps.escolas`, sem nenhum vinculo com o Setor do catalogo de
Processos (`Setor`/RN-025) nem com o `Campo`/`CampoValor` editavel
(RN-031/032). `SetorInformativo` tem tres marcacoes independentes de onde
aparece (Escola, RE, RI, nao exclusivas). Os `CampoInformativo` de um
Setor informativo aparecem, sempre somente leitura, nos lugares marcados:
dentro do modal de Campos ja existente (RN-032) quando RE e/ou RI
estiver marcado, e em um local equivalente na Escola quando "Escola"
estiver marcado.

## Decisao detalhada

### Por que uma entidade nova, em vez de reaproveitar `Setor` (RN-025) ou `Campo` (RN-031)

- `Setor` (RN-025) existe dentro de um `Processo` — criar um exige
  escolher/ja ter um Processo, o que contraria "eu só pedi um setor",
  sem esse passo extra;
- `Campo`/`CampoValor` (RN-031/032) sao feitos para valor por instancia
  (um valor diferente por RE/RI) e edicao restrita por `setor_atual` —
  nenhuma das duas coisas se aplica aqui (valor fixo, sempre somente
  leitura). Reaproveitar esses models exigiria campos e logica extra so
  para desligar recursos que eles tem por padrao;
- manter os dois conceitos ("Setor" do catalogo de Processos e "Setor
  informativo") em models separados evita a confusao que gerou a
  ADR-022 errada: o nome "Setor" e o mesmo na conversa com o usuario, mas
  sao dois catalogos diferentes no sistema, sem relacao entre si.

### Modelos

- `SetorInformativo`: `nome` (`CharField`, unico), `aparece_escola`,
  `aparece_re`, `aparece_ri` (`BooleanField`, default `False` cada,
  validacao exige pelo menos um marcado — mesmo padrao de validacao ja
  usado em `RedeExterna`/`RedeInterna` via `clean()`);
- `CampoInformativo`: `setor_informativo` (`ForeignKey`, `on_delete=CASCADE`,
  `related_name="campos"`), `nome` (`CharField`), `valor` (`TextField`,
  texto livre — nao ha tipo/validacao de formato, e so exibicao);
- nenhum model de valor por instancia (sem `CampoValor` novo) — o valor
  mora direto no `CampoInformativo`, o mesmo para qualquer Escola/RE/RI.

### Tela "Setor" (`apps.core_admin`, secao Administracao)

Uma unica tela, terceira opcao ao lado de "Processos" e "Campos":

- criar um `SetorInformativo` (nome + as tres marcacoes de onde aparece)
  e, na mesma tela, adicionar/editar/remover os `CampoInformativo` dele
  (nome + valor);
- lista os Setores informativos ja cadastrados, com seus Campos e onde
  cada um aparece;
- mesma permissao das demais telas da Administracao (`grupo_Administrador_required`).

### Exibicao em RE/RI — dentro do modal de Campos ja existente (RN-032)

O modal aberto pelo botao "Campos" na linha de RE/RI (`escola_rede_campos_modal.html`)
ganha um grupo adicional por `SetorInformativo` marcado com `aparece_re`
(no modal de RE) ou `aparece_ri` (no modal de RI) — ao lado dos grupos
existentes de `Campo` (RN-031). Esse grupo novo:

- mostra `nome: valor` de cada `CampoInformativo`, sempre como texto,
  nunca como campo de formulario editavel;
- nao entra na contagem nem na logica de `editavel`/`setor_atual` — e
  puramente informativo, igual em qualquer tela (grid global, Tela de
  Setor, qualquer `setor_atual`).

### Exibicao na Escola

Botao na linha da Escola (grid de Enderecos Lastmile), abrindo um modal
com os `CampoInformativo` de todo `SetorInformativo` marcado com
`aparece_escola` — mesmo padrao visual do modal de RE/RI, mas sem
formulario: so leitura, sem botao "Salvar".

### O que fica fora desta ADR

- nao ha edicao de valor pela Escola/RE/RI — o unico lugar que edita
  `CampoInformativo.valor` e a propria tela "Setor" (Administracao);
- nao ha necessidade de `GenericForeignKey`/`CampoValor` novo — resolvida
  a causa raiz do erro da ADR-022 (supor valor por instancia).

## Consequencias positivas

- modelo de dados simples — dois models novos, sem tocar em `Campo`/
  `CampoValor`/`Setor` existentes, sem risco de regressao no que ja esta
  em producao (RN-025/031/032);
- exibicao nao exclusiva (Escola + RE + RI juntos) resolve exatamente o
  "os dois ou os 3" pedido, sem forcar uma escolha unica;
- reaproveita o modal de Campos ja existente no grid (RN-032) como local
  de exibicao, em vez de inventar uma superficie nova so para RE/RI.

## Consequencias negativas / riscos

- dois conceitos chamados "Setor" convivendo no sistema (o do catalogo de
  Processos, RN-025, e o Setor informativo desta ADR), sem nenhuma
  relacao entre si — mitigado batizando a tela/menu como "Setor" (pedido
  do usuario) mas o model como `SetorInformativo`, e documentando aqui a
  distincao para nao repetir a confusao da ADR-022;
- valor fixo (nao por instancia) significa que, se o usuario um dia
  precisar de um valor diferente por Escola, sera nova decisao — nao
  coberta por esta ADR.

## Alternativas consideradas

### Reaproveitar `Setor` (RN-025) e `Campo`/`CampoValor` (RN-031/032) — ADR-022

Rejeitada. Era a decisao original desta feature, corrigida pelo usuario
depois de ver a tela: exigia Processo para criar o Setor, tratava o valor
como por instancia (`CampoValor`) e a exibicao como escopo exclusivo —
nenhuma das tres coisas foi pedida.

### Valor por instancia (um `CampoInformativoValor` por Escola/RE/RI)

Rejeitada. Usuario confirmou explicitamente que o valor e fixo, igual
para qualquer Escola — nao ha necessidade de um valor por instancia.

## Pendencias

- nenhuma decisao futura conhecida para este escopo.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
