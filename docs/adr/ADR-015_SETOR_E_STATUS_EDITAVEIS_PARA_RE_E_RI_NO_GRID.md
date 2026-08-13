# ADR-015 - Setor e Status editaveis para RE e RI, no grid de Enderecos Lastmile

## Status

`Aprovado`

> **Emenda (2026-08-07, durante a implementacao):** o usuario removeu a
> escolha de Processo da tela. RE e RI passam a usar cada um um Processo
> fixo (`RedeExterna.NOME_PROCESSO_PADRAO`/`RedeInterna.NOME_PROCESSO_PADRAO`,
> resolvido por nome exato do Processo cadastrado na PO-050), auto-vinculado
> ao salvar — sem cascata Processo->Setor, so Setor->Status. O usuario
> tambem pediu para nao duplicar a linha de referencia da API (RN-024) com
> a linha de edicao — as duas foram unificadas numa linha so por RE/RI.
> As secoes abaixo descrevem o desenho **original** (com escolha de
> Processo e linhas separadas); o Dev implementou a versao emendada.

## Contexto

ADR-013/RN-024 criaram, no grid de Enderecos Lastmile, uma linha expandida
por escola mostrando a referencia de RE/RI que ja vem da API do
DashboardEACE (`Escola.dados_api`) — somente leitura, sem relacao com
`RedeExterna`/`RedeInterna` (ADR-012). ADR-014/PO-050 criaram, separadamente,
um catalogo `Processo → Setor → SetorStatus`, com `RedeExterna`/
`RedeInterna` ganhando um vinculo opcional (`processo`) — mas sem tela
alguma para editar isso, e sem usar o catalogo para restringir os valores
de `setor`/`status` (que continuavam texto livre, ADR-012).

O usuario pediu para editar "Setor" direto no grid, explicando o motivo:
precisa "alterar o status da RE ou RI e mandar para outro setor". Perguntado,
confirmou:

- o editavel e o processo interno (`RedeExterna`/`RedeInterna`, RN-023) — a
  referencia da API (RN-024) continua exibida como esta, sem edicao;
- **Setor e Status ficam editaveis juntos** nesta mesma entrega (nao so
  Setor);
- os valores de Setor e Status vem do catalogo da PO-050, e a propria tela
  deixa escolher **Processo, Setor e Status juntos**, em cascata — se o
  RE/RI ainda nao tiver Processo vinculado, a edicao no grid resolve isso
  tambem, sem exigir um passo antes no Django Admin.

Verificado (2026-08-07): `RedeExterna`/`RedeInterna` tem **zero registros**
hoje — a conversao de campo abaixo nao tem dado real a perder.

## Decisao

1. Converter `RedeExterna.setor`/`RedeExterna.status` e
   `RedeInterna.setor`/`RedeInterna.status` de `CharField` livre
   (ADR-012) para `ForeignKey` — `setor` → `escolas.Setor`, `status` →
   `escolas.SetorStatus` — resolvendo a pendencia deixada pela ADR-014.
2. No grid de Enderecos Lastmile, a linha expandida de RE/RI ganha um modo
   de edicao com 3 campos em cascata: Processo → Setor (do Processo
   escolhido) → Status (do Setor escolhido). Salvar cria o `RedeExterna`/
   `RedeInterna` daquela escola se ainda nao existir.

## Decisao detalhada

### Campos `setor`/`status` passam a ser FK

```text
setor  = ForeignKey("escolas.Setor",       null=True, blank=True, on_delete=SET_NULL)
status = ForeignKey("escolas.SetorStatus", null=True, blank=True, on_delete=SET_NULL)
```

Nulaveis, no mesmo espirito de `parceiro` (ADR-012): criacao pode comecar
sem nenhum dos dois definidos.

**Integridade exigida** (validada na view/form, nao so na UI):
- `setor.processo` tem que ser igual ao `processo` do `RedeExterna`/
  `RedeInterna` que esta sendo editado;
- `status.setor` tem que ser igual ao `setor` escolhido.

Isso evita salvar uma combinacao invalida (ex.: status de um setor
diferente do que foi escolhido) mesmo se alguem pular a cascata da UI
(chamada direta ao endpoint, por exemplo).

### Edicao no grid — Processo, Setor e Status em cascata

Na linha expandida de RE (e, espelhado, na de RI):

- 3 campos: Processo (todos os `Processo` cadastrados), Setor (somente os
  do Processo escolhido), Status (somente os do Setor escolhido);
- ao trocar o Processo, a lista de Setor recarrega (e Status some, ate
  escolher um Setor novo); ao trocar o Setor, a lista de Status recarrega;
- implementado com HTMX (recarregar as opcoes de Setor/Status), no mesmo
  padrao ja usado nas partes assincronas do projeto — sem biblioteca nova;
- salvar grava em `RedeExterna`/`RedeInterna` daquela `Escola`; se o
  registro ainda nao existir, e criado na hora (`get_or_create` pela
  `Escola`);
- apos salvar, a linha expandida mostra o Setor/Status atuais (mesmo
  padrao visual do restante do grid, ADR-013/PO-049).

### O que NAO muda

- a linha de referencia da API (RN-024, `Escola.dados_api`) continua
  somente leitura, exibida como esta hoje — nao e a mesma informacao, nao
  se mistura com o processo interno;
- `Parceiro` (`RedeExterna.parceiro`/`RedeInterna.parceiro`) **nao** entra
  nesta edicao — usuario nao pediu; fica como pendencia, editavel so pelo
  Django Admin por agora;
- permissao de acesso a esta edicao usa o mesmo grupo que ja protege a
  tela (`LastMile`/superuser) — nao foi pedida nenhuma permissao nova.

## Consequencias positivas

- resolve a pendencia da ADR-014 (texto livre vs catalogo) com integridade
  real (FK), nao so por convencao de nome;
- fluxo completo numa tela so (escolher Processo tambem, nao exige ida ao
  Admin antes);
- reaproveita exatamente o catalogo que a PO-050 ja criou, sem duplicar
  cadastro de setor/status.

## Consequencias negativas / riscos

- se o catalogo (Processo/Setor/Status) estiver incompleto para o caso de
  uso do usuario, a edicao fica bloqueada ate cadastrar o que falta na
  tela de Processos (PO-050) — aceitavel, e o proposito do catalogo;
- `Parceiro` continua sem editor dedicado — se o usuario precisar editar
  isso em breve, e um pedido novo, nao incluido aqui.

## Alternativas consideradas

### Manter setor/status como texto livre, so preenchendo o input com sugestoes do catalogo

Rejeitada. O usuario pediu escolha em cascata Processo→Setor→Status; texto
livre com sugestao nao garante integridade nem cascata real.

### Editar via Django Admin em vez do grid

Rejeitada. Usuario pediu explicitamente a edicao "dentro desse grid".

## Pendencias

- `Parceiro` de RedeExterna/RedeInterna sem editor dedicado ainda;
  **resolvida pela ADR-018** (2026-08-10) — editavel pelo grid, restrito ao
  Setor "Lastmile", via modal de selecao;
- nenhuma tela de historico de mudanca de Setor/Status (quem mudou, quando,
  de onde para onde) — nao foi pedido; se precisar de auditoria disso,
  e decisao futura.

## Gatilho de regeneracao

Nenhum diagrama documenta esta tela ainda.
