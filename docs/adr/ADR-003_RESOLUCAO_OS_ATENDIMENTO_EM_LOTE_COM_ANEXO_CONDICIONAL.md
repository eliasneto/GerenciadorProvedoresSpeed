# ADR-003 - Resolucao de O.S. de atendimento em lote, com anexo condicional via ZIP

## Status

`Proposto`

> Nota de correcao (2026-07-09): o passo 5 de "Fluxo por linha", abaixo,
> descreve o fechamento das O.S. como uma lista fixa obtida uma unica vez.
> Isso foi corrigido por `docs/adr/ADR-004_FECHAMENTO_OS_EM_LOOP_ATE_ESGOTAR.md`,
> que passa a repetir a busca e o fechamento até esgotar as O.S. abertas do
> atendimento (RN-010), pois fechar uma O.S. pode criar a proxima tarefa do
> workflow do IXC como uma nova O.S. aberta. As demais decisoes deste ADR
> (lote via planilha, anexo condicional, ZIP) permanecem validas.

## Contexto

`ADR-002` decidiu processar um atendimento por execucao (tela com
`Atendimento_ID` + upload de arquivo unico + mensagem), rejeitando
explicitamente as alternativas de lote por falta de necessidade comprovada.

No mesmo dia, o usuario informou que o volume real exige lote: a planilha
tera varios `Atendimento_ID` diferentes (um por cliente/atendimento). Alem
disso, nem todo atendimento tem documento a anexar, e cada atendimento que
tiver documento pode ter um arquivo PDF diferente. Este ADR substitui a
decisao de execucao unitaria de `ADR-002` mantendo as demais decisoes desse
ADR (nao finalizar o atendimento, ordem de fechamento, ausencia de rollback,
reuso de integracao).

## Decisao

Processar a resolucao de O.S. por planilha, no mesmo padrao de
import/export (log de resultado) ja usado nas demais automacoes do
`core_admin`, com um ZIP opcional de anexos casados por nome de arquivo.

## Decisao detalhada

### Entrada

- Planilha com colunas: `Atendimento_ID` (obrigatorio), `Tem_Anexo`
  (obrigatorio, Sim/Nao), `Nome_Anexo` (obrigatorio somente quando
  `Tem_Anexo = Sim`), `Mensagem` (opcional).
- Um arquivo ZIP opcional, contendo os documentos PDF citados na coluna
  `Nome_Anexo` das linhas com `Tem_Anexo = Sim`.

### Fluxo por linha

1. Validar `Atendimento_ID` e `Tem_Anexo`.
2. Buscar o atendimento no IXC (`su_ticket`).
3. Se `Tem_Anexo = Sim`:
   - localizar o arquivo `Nome_Anexo` dentro do ZIP (em memoria, sem salvar
     em disco);
   - se nao encontrado, ou se nao for PDF, a linha falha e nenhuma O.S.
     daquele atendimento e tocada;
   - anexar o documento ao atendimento (`anexar_arquivo_ticket_ixc`); se
     falhar, a linha falha e nenhuma O.S. e tocada (RN-006).
4. Se `Tem_Anexo = Nao`, pular a etapa de anexo e ir direto para o
   fechamento das O.S.
5. Listar e ordenar as O.S. abertas do atendimento (reuso de
   `desativar_atendimento_ixc.py`) e fechar cada uma com
   `finaliza_atendimento=False` (RN-001, RN-004).
6. Falha parcial no fechamento das O.S. de uma linha nao interrompe o
   processamento das demais linhas da planilha (RN-005 aplicada por linha).
7. Gerar planilha/log de saida com o resultado de cada linha (padrao ja
   usado nas demais automacoes).

### Componentes a alterar (a cargo do Dev)

- `resolver_os_atendimento_ixc.py`: a funcao unitaria
  `executar_resolucao_os_atendimento_ixc` precisa ser adaptada para operar
  linha a linha a partir da planilha, reaproveitando a logica ja existente
  de anexo e fechamento por atendimento.
- Nova logica de leitura do ZIP em memoria e busca do arquivo por nome
  (RN-008), sem persistir o PDF (RN-009).
- View e template devem seguir o padrao de upload de planilha (+ZIP) ja
  usado nas demais automacoes do modulo, em vez do formulario unitario
  desenhado em `ADR-002`.

### Componentes reaproveitados (sem duplicar logica)

- `finalizar_os_existente`, `resumir_erro_finalizacao`
  (`ixc_finalizacao_service.py`).
- `anexar_arquivo_ticket_ixc` (`ixc_ticket_arquivo_service.py`).
- `buscar_atendimento_ixc_por_id`, `listar_os_para_desativacao`
  (`desativar_atendimento_ixc.py`).
- Padrao de leitura/validacao de planilha e geracao de log de execucao ja
  usado nas demais automacoes do `core_admin`.

## Consequencias positivas

- Atende o volume real de operacao (varios atendimentos por execucao).
- Anexo condicional evita falha artificial em atendimentos que nao precisam
  de documento.
- Nao persistir o PDF reduz superficie de dados sensiveis armazenados e
  simplifica a limpeza pos-execucao.

## Consequencias negativas / riscos

- Erro de nome de arquivo na planilha (`Nome_Anexo` nao bate com o ZIP) so e
  detectado em tempo de execucao, linha a linha; o relatorio de saida deve
  deixar isso explicito por linha.
- Reexecutar a planilha sobre os mesmos atendimentos ainda anexa o
  documento novamente (mesma limitacao ja registrada em `ADR-002`); como
  agora e lote, o aviso deve ser generico na tela (nao por atendimento) e
  reforcado no cabecalho do relatorio de saida.
- Risco de seguranca do token IXC hardcoded, registrado em `ADR-002`,
  permanece nao resolvido e nao e tratado por este ADR.

## Alternativas consideradas

### 1. Manter execucao unitaria (ADR-002)

Rejeitada. Nao atende o volume real informado pelo usuario.

### 2. ZIP obrigatorio em toda execucao, mesmo sem nenhum atendimento com anexo

Rejeitada. Cria upload obrigatorio desnecessario quando nenhuma linha da
planilha tiver `Tem_Anexo = Sim`.

## Proxima acao

Atualizar `PO-013` (`docs/BACKLOG.md`) com os novos criterios de aceite e
acionar o Dev para reescrever `resolver_os_atendimento_ixc.py` e a
view/template correspondente.
