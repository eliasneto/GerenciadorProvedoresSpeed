# ADR-028 - Grupo dedicado "Setor" e permissao granular por Setor individual

## Status

`Aprovado`

## Contexto

O modulo "Setores" (RN-027, ADR-016) hoje reaproveita a mesma permissao de
Enderecos Lastmile — grupo `LastMile` ou superuser — sem nenhuma
diferenciacao por usuario. A propria ADR-016 ja deixava isso registrado
como pendencia: "decisao futura: restringir cada tela de Setor a um
grupo/time especifico de usuarios".

Usuario pediu, em 2026-08-13, para resolver essa pendencia em duas partes:

1. o modulo "Setores" passa a aparecer para o usuario "como os outros [modulos]
   que ja tem hoje" — ou seja, com um grupo proprio, no mesmo padrao ja usado
   por `Parceiro`, `Backoffice` e `Administrador` (cada modulo com seu grupo
   dedicado, verificado por `has_group`/`user_passes_test` em
   `core/base.html` e nas views);
2. dentro do modulo, a permissao precisa ser concedida "para cada um
   separadamente" — confirmado que significa por Setor individual: um
   usuario do grupo `Setor` deve ver/acessar somente os nomes de Setor que
   foram liberados para ele, nao todos os cadastrados no catalogo (RN-025)
   de uma vez.

Contexto tecnico relevante (ja registrado na ADR-016): `Setor` e cadastrado
por Processo (RN-025) — o mesmo nome (ex.: "Lastmile") existe como duas
linhas distintas no banco, uma por Processo, deliberadamente espelhadas.
O modulo "Setores" ja agrupa por **nome**, cruzando Processos. A concessao
individual descrita nesta ADR segue o mesmo criterio: por nome, nao por
linha de `Setor`.

Nota de nomenclatura: o grupo Django criado por esta decisao se chama
`Setor` — mesmo nome do model `apps.escolas.models.Setor` e do proprio
modulo. Sao tres coisas diferentes (grupo de permissao, model de catalogo,
nome do modulo/menu); o Dev deve deixar isso explicito no codigo (ex.:
comentario no decorator) para nao confundir revisores futuros.

## Decisao

Duas camadas de permissao, uma em cima da outra:

1. **Visibilidade do modulo** — grupo Django dedicado `Setor` (mais
   superuser, que continua irrestrito em todos os grupos do sistema),
   controlando o item de menu "Setores" e as views `setores_list`/
   `setor_detail`. Mesmo padrao dos grupos existentes (`grupo_X_required`
   + `has_group` no template) — nenhum mecanismo novo nesta camada.
2. **Granularidade dentro do modulo** — uma concessao adicional, por
   usuario, de quais nomes de Setor especificos ele pode ver/acessar.
   Usuario do grupo `Setor` sem nenhum Setor concedido nao ve a secao no
   menu (mesmo comportamento hoje ja aplicado quando a lista de nomes esta
   vazia); usuario com alguns Setores concedidos ve so esses.

A modelagem exata da concessao (tabela dedicada relacionando usuario e
nome de Setor, ou outra forma equivalente) e decisao tecnica do Dev —
reversivel e de baixo risco, registrada aqui apenas como direcao: a chave
da concessao deve ser o **nome** do Setor (RN-025/RN-055), nao o `id` da
linha `Setor`, pelo motivo tecnico ja descrito na ADR-016 (mesmo nome
existe em mais de uma linha, uma por Processo).

## Consequencias positivas

- reaproveita 100% o padrao de grupo por modulo ja usado em todo o
  sistema para a camada de visibilidade — nenhum conceito novo nessa
  parte;
- resolve a pendencia que a ADR-016 ja tinha deixado explicita, sem
  reabrir ou contradizer nenhuma outra decisao daquela ADR;
- abre um padrao reutilizavel (grupo do modulo + concessao granular por
  item) caso outro modulo precise da mesma necessidade no futuro.

## Consequencias negativas / riscos

- este e o primeiro mecanismo de permissao **por item** do sistema — até
  aqui, toda a autorizacao era feita inteiramente por grupo Django,
  aplicada de forma igual a todos os membros do grupo. A partir desta
  decisao, o sistema passa a ter duas granularidades diferentes
  convivendo (grupo simples nos demais modulos; grupo + concessao
  individual neste);
- sem uma tela de administracao amigavel para conceder/revogar Setores por
  usuario, a gestao dessa concessao pode ficar manual e sujeita a erro
  (esquecer de conceder, conceder Setor errado) — a existencia dessa tela
  fica registrada como criterio de aceite da PO-075, nao resolvida por
  esta ADR.

## Alternativas consideradas

### Um grupo Django por Setor (ex.: grupo "Setor-Lastmile", "Setor-Comercial")

Rejeitada. `Setor` e um catalogo dinamico, cadastrado pelo usuario a
qualquer momento na tela de Processos (RN-025) — cada Setor novo exigiria
criar um grupo novo manualmente, e cada usuario precisaria ser adicionado
a varios grupos (um por Setor liberado). Multiplica a administracao de
grupos sem necessidade, para um caso que uma concessao simples (usuario +
nome de Setor) resolve com uma tabela so.

### Permissao de objeto generica (ex.: `django-guardian`)

Rejeitada por desproporcional. Nenhum outro modulo do sistema usa
permissao por objeto — toda a autorizacao existente e por grupo simples,
com decorators customizados (`grupo_X_required`). Introduzir uma
dependencia nova e um paradigma de permissao diferente para resolver um
unico caso de uso concentraria complexidade desnecessaria; se surgir uma
segunda necessidade parecida, vale reavaliar.

### Framework de permissao nativo do Django (`Permission` por instancia)

Rejeitada pelo mesmo motivo da alternativa anterior — o framework nativo
de `Permission` do Django, sem uma biblioteca de permissao por objeto por
cima dele, nao concede nem verifica permissao por instancia de model; usar
so o framework nativo exigiria a mesma tabela de concessao proposta na
Decisao, sem ganhar nada dele.

## Pendencias

- modelagem exata da tabela/relacao de concessao usuario-Setor: Dev decide
  na implementacao (PO-075);
- decisao de interface para conceder/revogar Setores por usuario (Django
  Admin padrao ou tela propria): Dev decide na implementacao (PO-075);
- cadastro do grupo `Setor` em producao (fixture versionada ou cadastro
  manual pelo Administrador): a confirmar no levantamento tecnico da
  PO-075.

## Gatilho de regeneracao

Nenhum diagrama documenta o fluxo de permissoes do sistema hoje. Se um
diagrama vier a ser criado para esse fluxo, deve refletir as duas camadas
descritas nesta ADR (grupo do modulo + concessao por Setor individual).
