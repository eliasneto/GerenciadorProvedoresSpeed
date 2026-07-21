# ADR-002 - Resolucao em massa das O.S. de um atendimento sem finalizar o atendimento (IXC)

## Status

`Substituido por ADR-003` (2026-07-09)

> A decisao de execucao unitaria (um atendimento por execucao, sem planilha)
> e as secoes "Fluxo", "Alternativas 1 e 2" abaixo foram revertidas pelo
> usuario no mesmo dia em que este ADR foi criado. O volume real de
> atendimentos por operacao exige processamento em lote via planilha, com
> anexo condicional por atendimento e correspondencia de documento dentro de
> um ZIP. Ver `docs/adr/ADR-003_RESOLUCAO_OS_ATENDIMENTO_EM_LOTE_COM_ANEXO_CONDICIONAL.md`.
> As decisoes de reuso de integracao (RN-001, RN-004, RN-005) e o registro de
> risco de seguranca do token IXC permanecem validos.

## Contexto

O projeto ja possui uma automacao de "Desativacao de Atendimento IXC"
(`scripts/integracoes/backoffice/desativar_atendimento_ixc.py`, exposta em
`/ferramentas/atendimentos/desativacao/`) que busca todas as O.S. abertas de um
atendimento e as fecha em sequencia, finalizando o atendimento ao fechar a
ultima O.S.

A necessidade agora e diferente: fechar (solucionar) as O.S. abertas de um
atendimento **sem finalizar o atendimento**, que deve continuar ativo no IXC.
Alem disso, antes de qualquer O.S. ser solucionada, um documento enviado pelo
usuario precisa ser anexado ao atendimento no IXC.

Levantamento no codigo mostrou que as pecas de integracao ja existem e sao
reutilizaveis:

- `finalizar_os_existente()` em `ixc_finalizacao_service.py` ja aceita
  `finaliza_atendimento=False` (inclusive e o valor padrao da funcao);
- `anexar_arquivo_ticket_ixc()` em `ixc_ticket_arquivo_service.py` ja envia um
  arquivo para o endpoint `su_ticket_arquivos` do IXC, vinculado a um
  `id_ticket`;
- `buscar_atendimento_ixc_por_id()`, `buscar_os_atendimento_ixc()` e
  `_ordenar_os_por_id()` em `desativar_atendimento_ixc.py` ja resolvem o
  atendimento e listam suas O.S. abertas em ordem de workflow.

Falta apenas uma nova orquestracao que combine essas pecas com uma ordem e um
criterio de sucesso diferentes dos ja implementados.

## Decisao

Criar uma nova automacao, independente da "Desativacao de Atendimento",
que processa **um atendimento por execucao**: recebe `Atendimento_ID` + um
arquivo + uma mensagem opcional, anexa o arquivo ao atendimento primeiro e,
somente se o anexo for confirmado, fecha todas as O.S. abertas do atendimento
com `finaliza_atendimento=False`, mantendo o atendimento ativo no IXC.

## Decisao detalhada

### Fluxo

1. Usuario informa `Atendimento_ID`, anexa um arquivo e, opcionalmente, uma
   mensagem de fechamento.
2. Sistema busca o atendimento no IXC (`su_ticket`) e confirma que ele existe.
3. Sistema envia o arquivo via `anexar_arquivo_ticket_ixc(atendimento_id,
   arquivo, descricao)`.
   - Se o anexo falhar, a execucao para aqui. Nenhuma O.S. e tocada. (RN-002)
4. Sistema lista as O.S. abertas do atendimento e ordena por ID crescente,
   reaproveitando a logica ja usada na desativacao de atendimento. (RN-004)
5. Sistema chama `finalizar_os_existente(os_id, mensagem,
   finaliza_atendimento=False, ...)` para cada O.S., inclusive a ultima.
   (RN-001)
6. Se uma O.S. falhar no meio do lote, as anteriores ja fechadas permanecem
   fechadas; a execucao para e reporta qual O.S. falhou. (RN-005)
7. Ao final, o sistema confirma que o atendimento **continua ativo**
   (`status != F`). Se o atendimento tiver sido finalizado por algum efeito
   colateral do IXC, isso deve ser reportado como anomalia, nao como sucesso.
8. Relatorio de execucao mostra: resultado do anexo, lista de O.S.
   processadas com status individual, e status final do atendimento.

### Componentes novos

- `scripts/integracoes/backoffice/resolver_os_atendimento_ixc.py`:
  orquestracao nova (`executar_resolucao_os_atendimento`).
- Nova view em `apps/core_admin/views.py` (`resolver_os_atendimento_ixc`),
  protegida por `@user_passes_test(grupo_Administrador_required)` e
  `@login_required`, seguindo o mesmo padrao de auditoria via
  `registrar_auditoria_integracao` / `IntegrationAudit` usado nas demais
  automacoes do modulo.
- Nova rota, ex.: `/ferramentas/atendimentos/resolucao-os/`.
- Novo card em `core_admin/automacoes.html`, com formulario de
  `Atendimento_ID` + upload de arquivo + campo de mensagem (sem planilha).

### Componentes reaproveitados (sem duplicar logica)

- `finalizar_os_existente`, `resumir_erro_finalizacao` (ixc_finalizacao_service.py).
- `anexar_arquivo_ticket_ixc` (ixc_ticket_arquivo_service.py).
- `buscar_atendimento_ixc_por_id`, `buscar_os_atendimento_ixc`,
  `_ordenar_os_por_id` (desativar_atendimento_ixc.py).

Recomendacao tecnica para quando a implementacao for feita: extrair
`buscar_atendimento_ixc_por_id`, `buscar_os_atendimento_ixc` e
`_ordenar_os_por_id` de `desativar_atendimento_ixc.py` para um modulo
compartilhado (ex.: `ixc_atendimento_service.py`), evitando duas automacoes
com copias da mesma logica de busca/ordenacao de O.S. Decisao de refactor
fica a cargo do `backend_django` no momento da implementacao.

## Consequencias positivas

- Reaproveita quase toda a integracao ja validada com o IXC; risco tecnico
  baixo.
- Documento fica registrado no atendimento antes de qualquer O.S. ser
  encerrada, criando rastreabilidade.
- Atendimento permanece ativo, permitindo continuidade do fluxo comercial/suporte.
- Execucao unitaria (um atendimento por vez) reduz risco de anexar o
  documento errado no atendimento errado, comparado a um lote com arquivos
  multiplos.

## Consequencias negativas / riscos

- Reexecutar a automacao no mesmo atendimento anexa o arquivo novamente
  (nao ha deduplicacao de anexos no IXC); a tela deve deixar isso explicito
  para o usuario antes de confirmar.
- Por processar um atendimento por vez, nao serve para o caso de volume alto
  de atendimentos (dezenas/centenas) na mesma operacao; se isso for
  necessario no futuro, exigira nova decisao (ex.: endpoint aceitando N
  atendimentos com um arquivo cada, ou reaproveitar o padrao assincrono ja
  usado na importacao de leads).
- Risco de seguranca ja existente e nao relacionado a esta decisao, mas que
  afeta diretamente esta automacao por reusar o mesmo `IXCClient`: o token de
  acesso ao IXC tem um valor padrao gravado no codigo (`ixc_client.py`,
  `ixc_os_comercial_lastmile.py`, `ixc_faxina.py`, `ixc_primeira_os.py`), o
  que viola a regra de seguranca do projeto (CLAUDE.md, secao 6). Isso nao
  bloqueia esta ADR, mas deve ser tratado pelo Dev como correcao de
  seguranca independente, idealmente antes ou junto da implementacao desta
  feature.

## Alternativas consideradas

### 1. Lote de atendimentos com o mesmo documento anexado a todos

Rejeitada por enquanto. O caso de uso descrito e de um atendimento por vez;
manter o escopo unitario evita complexidade de UI sem necessidade
comprovada.

### 2. Lote de atendimentos com documento diferente por atendimento (zip / upload multiplo)

Rejeitada por enquanto. Aumenta significativamente a complexidade de upload
e de correspondencia arquivo-atendimento sem necessidade comprovada.

### 3. Fechar as O.S. mesmo se o anexo falhar (apenas avisar)

Rejeitada. O usuario definiu que o anexo e pre-requisito: se falhar, nenhuma
O.S. deve ser fechada.

### 4. Reaproveitar a automacao de desativacao de atendimento com uma flag

Nao escolhida. Misturar os dois comportamentos (finalizar vs. nao finalizar
o atendimento, com vs. sem anexo obrigatorio) na mesma funcao aumentaria o
risco de um dos dois fluxos usar a flag errada. Preferido manter duas
automacoes pequenas e explicitas.

## Proxima acao

Registrar a feature no backlog (`PO-013`) e detalhar como `FEAT-XXX` quando o
Dev for acionado para implementar.
