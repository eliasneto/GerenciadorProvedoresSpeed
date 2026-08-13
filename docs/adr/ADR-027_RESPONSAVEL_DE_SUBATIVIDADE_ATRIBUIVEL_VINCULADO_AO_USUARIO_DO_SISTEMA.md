# ADR-027 - Responsavel de subatividade (RE/RI/Mapa Calor): campo atribuivel vinculado ao usuario do sistema, obrigatorio so via UI

## Status

`Aprovado`

> Esta ADR desenha a decisao de arquitetura. Nao autoriza inicio de execucao —
> a PO-073 (`docs/BACKLOG.md`) so comeca quando o usuario mandar `iniciar
> PO-073`.

> **Emenda (2026-08-13):** a pendencia "detalhe exato de como a trava por
> `setor_atual` se aplica ao Responsavel dentro do grid global" (secao
> Pendencias abaixo) foi resolvida pelo usuario: a obrigatoriedade de
> Responsavel nunca se aplica quando a subatividade muda de Setor, em
> nenhuma das duas telas. Ver RN-056 (`docs/business_rules.md`).
>
> **Correcao (2026-08-13):** o Orquestrador registrou nesta mesma emenda,
> por leitura incompleta do codigo, que o grid global ainda exigiria
> Responsavel ao mover para outro Setor. O Dev investigou e demonstrou que
> isso nao procede: o grid global (sem `setor_atual`) ja bloqueia por
> completo a edicao de uma subatividade que ja tem Setor — so a Tela do
> proprio Setor pode move-la, e essa tela ja aplica a excecao
> (`enviado_a_outro_setor`) desde a decisao original desta ADR. Nao havia
> divergencia real nem pendencia de codigo; confirmado por 193 testes de
> `apps.leads`, incluindo os que cobrem exatamente este cenario.
>
> **Segunda correcao (2026-08-13, mesmo dia):** a conclusao acima estava
> incompleta. O usuario reportou continuar sendo obrigado a informar
> Responsavel "ao enviar a subatividade para outro setor" e, questionado,
> confirmou que o caso e a **primeira atribuicao de Setor pelo grid
> global** (subatividade que ainda nao tinha nenhum Setor) — nao a
> movimentacao entre Setores ja cobertos pela excecao. A regra original do
> usuario ("quem faz a mudanca nao sabe quem sera o responsavel no Setor de
> destino") vale igualmente para essa primeira atribuicao: quem atribui o
> Setor pelo grid global nao esta necessariamente dentro do Setor de
> destino. RN-056 foi ampliada: Responsavel so e obrigatorio dentro da Tela
> do proprio Setor, mantendo a subatividade no mesmo Setor — nunca no grid
> global. Desta vez ha correcao de codigo real e pendente, com o Dev.

## Contexto

Usuario pediu, em 2026-08-12: "toda subatividade precisa de um setor, status
e responsável. Esse responsável vai ser o usuário do sistema quando logar."

Investigacao do Orquestrador (RN-052, registrada inicialmente como
`Pendente`) confirmou o estado real do codigo:

- Setor e Status ja existem em `ProcessoRedeBase` (`apps/escolas/models.py`)
  como `ForeignKey` para `Setor`/`SetorStatus` (ADR-014/ADR-015), herdados
  pelas tres subatividades hoje existentes — `RedeExterna`, `RedeInterna` e
  `MapaCalor` (ADR-012/RN-023, RN-043) — mas sao **opcionais**
  (`null=True, blank=True`). RN-035 so fixa Status="Novo" automaticamente na
  criacao pelo grid global; nao havia obrigatoriedade real no banco nem na
  camada de negocio;
- Responsavel **nao existia** em `ProcessoRedeBase` nem em nenhum model de
  subatividade. O unico precedente no sistema e `Proposal.responsavel`
  (`apps/partners/models.py`, cotacao) — FK para `core.User`,
  `on_delete=SET_NULL`, campo atribuivel/reatribuivel manualmente, com acao
  explicita "assumir responsavel" (`proposal_assumir_responsavel`) e
  historico de troca.

Como o pedido colidia com decisoes ja registradas (ADR-012/ADR-014/RN-023/
RN-025/RN-035 definiram Setor/Status como opcionais) e envolvia dados
persistidos, o Orquestrador nao decidiu por conta propria (CLAUDE.md secao
9) e levantou 6 perguntas. O usuario respondeu, em 2026-08-12:

1. Responsavel e atribuivel/reatribuivel manualmente — mesmo padrao ja usado
   para Parceiro (RN-030) e para `Proposal.responsavel`, com acao de
   "assumir responsavel" e historico de troca;
2. obrigatoriedade so por regra de negocio/UI, mantendo os campos nullable
   no banco — evita migracao de dados legados;
3. escopo: todas as subatividades (RedeExterna, RedeInterna e MapaCalor),
   sem excecao;
4. edicao nas mesmas telas ja existentes — grid global (RN-026) e Tela de
   Setor (RN-027/028) — mantendo a trava por `setor_atual` da RN-033; sem
   superficie de edicao nova;
5. ao trocar de Setor (RN-033 zera o Status para "Aguardando"), o
   Responsavel tambem e zerado, liberado para reatribuicao no novo setor;
6. alteracao de Responsavel gera `RegistroHistorico` no mesmo formato
   De/Para ja usado para Setor/Status/Parceiro (RN-029/041) — confirmado,
   sem objecao a essa recomendacao do Orquestrador.

## Decisao

Adicionar `responsavel` (`ForeignKey` para `core.User`/`AUTH_USER_MODEL`,
`null=True, blank=True`, `on_delete=models.SET_NULL`) a `ProcessoRedeBase`,
herdado por `RedeExterna`, `RedeInterna` e `MapaCalor`. O campo e
atribuivel/reatribuivel manualmente, reaproveitando o padrao ja aprovado
para Parceiro (RN-030) e para `Proposal.responsavel`. A obrigatoriedade de
Setor, Status e Responsavel passa a ser exigida pela camada de negocio/UI
(RN-026), nao pelo schema — os tres campos continuam nullable no banco.
Editavel somente nas telas que ja editam Setor/Status (grid global RN-026 e
Tela de Setor RN-027/028), com a mesma trava por `setor_atual` da RN-033.
Ao trocar de Setor, o Responsavel e zerado junto com o Status. Alteracao de
Responsavel gera `RegistroHistorico` no formato De/Para (RN-029/041).

## Decisao detalhada

### Campo e escopo

- `ProcessoRedeBase.responsavel`: FK `settings.AUTH_USER_MODEL` (`core.User`),
  `null=True, blank=True`, `on_delete=models.SET_NULL` — mesmo padrao de
  nulidade ja usado por `setor`, `status` e `parceiro` na mesma classe;
- `related_name` por subclasse (evitar colisao entre `RedeExterna`,
  `RedeInterna` e `MapaCalor` apontando para o mesmo `core.User`) e decisao
  tecnica do Dev na implementacao, sem impacto de negocio;
- vale igualmente para as tres subatividades hoje existentes — herdado da
  base abstrata, sem excecao por tipo.

### Atribuicao manual, nao preenchimento automatico imutavel

- Responsavel e escolhido manualmente por quem estiver operando a tela —
  nao e preenchido automaticamente com "quem criou" o registro;
- reaproveita o padrao ja aprovado para Parceiro (RN-030: editavel na linha
  expandida de RE/RI/Mapa Calor, mesma trava de setor) e para
  `Proposal.responsavel` (acao de "assumir responsavel" + reatribuicao por
  outro usuario). O padrao de UI exato (campo de selecao simples, modal de
  busca, ou botao "assumir para mim" como em `Proposal`) e decisao tecnica
  do Dev, reaproveitando o mais simples que ja existe no grid (RN-026 ja usa
  `<select>` para Setor/Status).

### Obrigatoriedade via regra de negocio, nao via schema

- Setor, Status e Responsavel continuam `null=True, blank=True` no banco —
  decisao deliberada do usuario, para nao migrar/forcar valor nos registros
  ja existentes em producao;
- a obrigatoriedade e validada na camada de formulario/servico usada pela
  RN-026: o fluxo de edicao nao deve permitir salvar/avancar sem os tres
  campos preenchidos, nas telas onde ja sao editaveis hoje;
- registro ja existente com algum desses campos vazio continua existindo
  sem alteracao retroativa — a obrigatoriedade passa a valer a partir da
  proxima edicao feita pela tela, nao por migracao/backfill.

### Onde se edita

- Mesmas duas telas que ja editam Setor/Status: grid global de Enderecos
  Lastmile (RN-026) e Tela de Setor (RN-027/028) — nenhuma superficie de
  edicao nova;
- mesma trava da RN-033 (edicao restrita ao `setor_atual`, na Tela de
  Setor). O grid global, pela RN-035, nao tem hoje o conceito de
  `setor_atual` para Status (Status la e sempre fixo em "Novo"); como a
  edicao de Responsavel nesse contexto especifico nao foi detalhada pelo
  usuario nesta rodada, fica registrada como pendencia para o Dev resolver
  seguindo o mesmo espirito ja usado para Status naquele contexto (ver
  Pendencias).

### Zeragem ao trocar de Setor e historico

- RN-033 ja zera o Status para "Aguardando" quando o Setor muda (fora do
  `setor_atual`, Tela de Setor); esta ADR estende o mesmo gatilho para
  tambem zerar Responsavel (`responsavel=None`) no mesmo momento, liberando
  a subatividade para reatribuicao no novo Setor;
- gera `RegistroHistorico` (RN-029/041, formato De/Para) tanto para a
  mudanca manual de Responsavel quanto para a zeragem automatica ao trocar
  de Setor — mesmo padrao ja usado para o "Aguardando" automatico (RN-033) e
  para os demais campos estruturados (RN-041).

## Consequencias positivas

- fecha a lacuna de rastreabilidade "quem e responsavel por essa
  subatividade agora", usando o mesmo padrao de usuario do sistema ja
  validado em `Proposal.responsavel`;
- nao exige migracao de dados em producao (Setor/Status/Responsavel
  continuam nullable), reduzindo risco de deploy;
- reaproveita integralmente as telas e o padrao de historico ja existentes —
  nenhuma superficie de edicao nova, nenhum modelo de historico novo.

## Consequencias negativas / riscos

- obrigatoriedade so na camada de aplicacao (nao no schema) significa que
  qualquer gravacao fora do fluxo padrao (Django Admin, script, migracao
  futura) pode salvar uma subatividade sem Setor/Status/Responsavel, sem o
  banco impedir — risco aceito explicitamente pelo usuario para nao migrar
  dados legados;
- zerar Responsavel junto com o Status ao trocar de Setor pode surpreender
  quem espera continuar responsavel apos mudar a subatividade de time —
  mitigado por ser comportamento explicitamente pedido pelo usuario,
  simetrico ao ja aprovado para Status (RN-033);
- o grid global (RN-026/RN-035) nao tem o conceito de `setor_atual` usado
  pela trava da RN-033 — a aplicacao exata dessa trava ao Responsavel nesse
  contexto especifico nao foi decidida nesta rodada (ver Pendencias).

## Alternativas consideradas

### Responsavel como preenchimento automatico e imutavel ("criado por")

Rejeitada pelo usuario — confirmado que o campo deve ser atribuivel e
reatribuivel manualmente, no mesmo padrao de Parceiro/`Proposal.responsavel`.

### Tornar Setor/Status/Responsavel `NOT NULL` no banco, com migracao/backfill

Rejeitada pelo usuario — para nao migrar dados legados em producao. A
obrigatoriedade fica somente na camada de negocio/UI.

### Superficie de edicao nova (tela dedicada de "atribuir responsavel")

Rejeitada pelo usuario — confirmado reaproveitar as mesmas telas ja
existentes (grid global e Tela de Setor), sem criar superficie nova.

## Pendencias

- detalhe exato de como a trava por `setor_atual` (RN-033) se aplica ao
  Responsavel dentro do grid global — esclarecido pela segunda correcao de
  2026-08-13 (ver RN-056): Responsavel nunca e obrigatorio no grid global,
  nem na primeira atribuicao de Setor nem em nenhuma outra edicao ali. Fica
  pendente com o Dev: corrigir `escola_rede_editar` para que a checagem de
  obrigatoriedade nao se aplique no ramo `elif not setor_atual:` (grid
  global);
- padrao exato de UI para atribuir/reatribuir (select simples, modal de
  busca, ou botao "assumir para mim") — decisao tecnica do Dev, sem impacto
  de negocio;
- `related_name` do FK por subclasse — decisao tecnica do Dev, sem impacto
  de negocio.

## Gatilho de regeneracao

Nenhum diagrama documenta hoje o dominio Escola/RE/RI/Mapa Calor com o
detalhe de Setor/Status/Responsavel — o diagrama `03 · Modelo de dominio`
esta desatualizado desde antes desta decisao (ver `docs/ARCHITECTURE.md`,
nota sobre a ADR-025). Quando os diagramas desse dominio forem regenerados
(comando `atualizar diagrama`/`gerar diagrama`, MODO 5), a fonte deve
refletir o campo `responsavel` novo em `ProcessoRedeBase` e a regra de
zeragem ao trocar de Setor.
