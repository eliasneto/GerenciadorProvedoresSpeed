# ADR-030 - Tela "Acesso" em core_admin para conceder modulo do menu e Setor individual

## Status

`Aprovado`

## Contexto

A `ADR-028`/`RN-054`/`RN-055` (PO-075, 2026-08-13) criaram duas camadas de
permissao para o modulo "Setores": grupo Django dedicado `Setor`
(visibilidade do modulo) mais uma concessao individual por nome de Setor
(model `AcessoSetor`). As duas camadas, porem, so podem ser administradas
pelo Django Admin nativo (`/admin/`), em duas telas separadas — a de grupo
do usuario (formulario padrao de `User`) e a de `AcessoSetor` (uma linha
por usuario+nome, sem selecao multipla). A propria `ADR-028` ja registrava
esse formato manual como risco.

No mesmo dia, o usuario relatou dificuldade real usando exatamente esse
fluxo (documentado como pendencia na `PO-075`): nao conseguiu conceder
acesso somente a "Implantacao", nem a "Implantacao e Compras", usando as
duas telas separadas do Django Admin.

Em seguida, o usuario pediu uma tela unica, dentro da area propria
"Administracao" do sistema (nao o Django Admin nativo), para conceder
acesso a cada modulo do menu e a cada Setor individual em um lugar so
(`PO-077`). O Orquestrador levantou 6 pontos em aberto; o usuario decidiu
4 explicitamente e autorizou decisao tecnica reversivel e de baixo risco
(CLAUDE.md, secao 9/Lei 9) para os 2 restantes.

## Decisao

Uma nova tela "Acesso", dentro da area "Administracao" ja existente em
`apps.core_admin` (mesmo padrao das paginas Processos/Campos/
Setor-Escopo — nao Django Admin nativo), que concede e revoga, por
usuario selecionado, em um unico formulario:

1. pertencimento a cada um dos 6 grupos/modulos do menu hoje existentes:
   `LastMile` (Projeto), `Setor` (Setores), `Parceiro`, `Backoffice`,
   `Gestao`, `Administrador` — os 6 aparecem na tela, inclusive
   `Administrador`;
2. quais nomes de Setor individuais (RN-025/RN-055) esse usuario pode
   ver/acessar dentro do modulo "Setores" (`AcessoSetor`).

Nenhum model novo: a tela e uma camada de UI sobre dois mecanismos que ja
existem — `django.contrib.auth.models.Group` (grupos ja criados por
`ops/setup_speed.py`) e `apps.leads.models.AcessoSetor` (RN-055/ADR-028).

### Pontos decididos pelo usuario

1. **Local/tecnologia:** area propria "Administracao" (`apps.core_admin`),
   nao Django Admin nativo.
2. **Quem acessa a tela "Acesso":** grupo de menu `Administrador`
   (`has_group`/`user_passes_test`, mesmo padrao das demais paginas de
   `apps.core_admin`) — nao restrito a superusuario Django. Superusuario
   continua tendo acesso, como em todos os grupos do sistema (`has_group`
   retorna `True` para superuser).
3. **Auto-inclusao no grupo Setor:** ao conceder qualquer Setor individual
   a um usuario que ainda nao pertence ao grupo `Setor`, o sistema inclui
   o usuario nesse grupo automaticamente, sem passo manual separado.
4. **Conceder e revogar no mesmo lugar:** a tela permite as duas acoes,
   tanto para modulo (grupo) quanto para Setor individual.

### Pontos decididos pelo Orquestrador (Lei 9 CLAUDE.md — reversiveis, baixo risco)

5. **Incluir `Administrador` na lista de modulos:** sim, os 6 modulos
   aparecem, inclusive `Administrador`. Risco de autoexclusao (um
   administrador remover o proprio acesso ao modulo Administrador, ou
   remover de outro admin) mitigado por aviso explicito de confirmacao na
   tela antes de revogar `Administrador` de qualquer usuario — nao por
   bloqueio automatico (bloquear seria uma decisao de UX adicional, a
   criterio do Dev se quiser reforcar).
6. **Mostrar estado atual (auditoria visual):** sim — ao selecionar um
   usuario, a tela mostra quais modulos ele ja tem e quais Setores ja
   estao concedidos antes de qualquer alteracao. Padrao esperado numa tela
   de gestao de acesso; nao seria util so para criar concessao as cegas.

### Assimetria deliberada entre revogar Setor individual e revogar o grupo Setor

Revogar um Setor individual (`AcessoSetor`) **nao** remove automaticamente
o usuario do grupo `Setor` — revogar o grupo em si e uma acao separada,
tambem disponivel na mesma tela (ponto 1). Escolhido por simplicidade: a
auto-inclusao (ponto 3) resolve a friccao de esquecer o primeiro passo ao
conceder; nao ha friccao equivalente a resolver ao revogar (usuario sem
nenhum Setor concedido, mas ainda no grupo `Setor`, simplesmente nao ve a
secao "Setores" no menu — comportamento ja existente da RN-055).

## Consequencias positivas

- resolve a dificuldade real relatada pelo usuario (PO-075) de conceder
  Setor individual isoladamente ou em combinacao, sem depender de duas
  telas do Django Admin;
- nenhum model novo, nenhuma dependencia nova — reaproveita 100% o que a
  ADR-028 ja criou, so muda a forma de administrar;
- unifica em um lugar so a gestao de acesso a todos os modulos do sistema,
  hoje espalhada implicitamente pelo Django Admin nativo;
- abre caminho natural para, no futuro, o mesmo padrao (modulo + concessao
  individual) ser usado por outro modulo que precise de granularidade
  parecida (mesma consequencia positiva ja registrada na ADR-028).

## Consequencias negativas / riscos

- superficie de administracao de permissao passa a existir em dois
  lugares (Django Admin nativo continua funcionando para grupos e para
  `AcessoSetor`, sem ser desativado) — divergencia possivel se alguem
  administrar por um caminho e esperar refletir no outro. Aceitavel: os
  dois caminhos escrevem nas mesmas tabelas (`Group`, `AcessoSetor`), sem
  dado duplicado, so uma UI a mais;
- lista fixa de 6 modulos hard-coded na nova tela (nao ha hoje um registro
  dinamico de "modulos do menu" no sistema) — cadastrar um modulo novo no
  menu no futuro exige atualizar tambem esta tela manualmente, mesmo tipo
  de manutencao que ja existe hoje em `core/base.html`;
- incluir `Administrador` na lista permite autoexclusao ou exclusao de
  outro administrador; mitigado por aviso de confirmacao, nao eliminado
  (usuario decidiu aceitar esse risco ao pedir os 6 modulos, com a
  sinalizacao como unica salvaguarda).

## Alternativas consideradas

### Manter Django Admin nativo (duas telas separadas) sem nova UI

Rejeitada. E exatamente o fluxo que gerou a dificuldade relatada pelo
usuario na PO-075 (nomes que nao batem exatamente, ausencia de selecao
multipla, necessidade de lembrar o passo do grupo `Setor` separadamente).

### Restringir a tela a superusuario Django em vez do grupo `Administrador`

Rejeitada pelo usuario (decisao explicita, ponto 2) — mesmo padrao das
demais paginas de `apps.core_admin`, que usam grupo de menu, nao a flag
`is_superuser` do Django.

### Excluir `Administrador` da lista de modulos concediveis pela tela

Considerada para eliminar o risco de autoexclusao, mas o usuario preferiu
a sugestao de incluir todos os 6 com aviso, mantendo a tela simetrica e
completa (nenhum modulo de fora tratado como excecao silenciosa).

### Revogar Setor individual tambem remover o usuario do grupo Setor automaticamente

Rejeitada por assimetria desnecessaria — ver secao "Assimetria deliberada"
acima. Nenhuma friccao relatada precisa dessa simetria; manter os dois
controles independentes na revogacao e mais simples e mais previsivel
para quem administra.

## Pendencias

- lista de usuarios elegiveis para aparecer/serem buscados na tela
  "Acesso" (todos os usuarios do sistema, com busca, no mesmo padrao do
  `autocomplete_fields` ja usado em `AcessoSetorAdmin`): decisao tecnica
  do Dev, reversivel e de baixo risco;
- UX exata do aviso de autoexclusao ao revogar `Administrador` (modal de
  confirmacao, texto do aviso): decisao tecnica do Dev;
- se um modulo novo for adicionado ao menu no futuro, esta tela precisa
  ser atualizada manualmente (mesma manutencao ja existente em
  `core/base.html`) — sem mecanismo automatico previsto nesta decisao.

## Gatilho de regeneracao

Nenhum diagrama documenta o fluxo de permissoes do sistema ainda (mesma
observacao ja registrada na ADR-028). Se um diagrama vier a ser criado
para esse fluxo, deve refletir as duas camadas da ADR-028 mais esta tela
de administracao unificada (ADR-030) por cima delas.
