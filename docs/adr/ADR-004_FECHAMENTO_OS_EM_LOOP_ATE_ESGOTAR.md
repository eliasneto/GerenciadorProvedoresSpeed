# ADR-004 - Fechamento de O.S. em loop ate esgotar (workflow BPM do IXC)

## Status

`Proposto`

## Contexto

`ADR-002` e `ADR-003` descrevem o fechamento das O.S. de um atendimento como
uma lista fixa: listar as O.S. abertas uma vez, ordenar por ID crescente
(RN-004) e fechar cada uma dessa lista.

O usuario observou, a partir da tela de "Acoes" de uma O.S. no IXC (opcoes
como Agendar, Encaminhar, Assumir, Executar, Necessario reagendar,
Finalizar, Analisar, Reabrir), que o fechamento de uma O.S. no IXC nao e uma
simples marcacao de status — e um avanco de workflow. O Dev confirmou isso
na estrutura do payload em `ixc_finalizacao_service.montar_payload_fechamento_real`:
campos como `id_tarefa_atual`, `sequencia_atual`, `proxima_sequencia_forcada`
e `id_proxima_tarefa` indicam que finalizar a tarefa atual avanca o processo
BPM do atendimento para a proxima tarefa, que pode aparecer como uma **nova
O.S. aberta** no mesmo atendimento — inexistente no momento da consulta
inicial.

Se essa hipotese for verdadeira, a listagem fixa usada em `ADR-002`/`ADR-003`
deixa O.S. criadas durante o proprio processamento sem fechar, resolvendo o
atendimento apenas parcialmente.

## Decisao

Fechar as O.S. de um atendimento em um laco que repete busca e fechamento
até esgotar, em vez de uma listagem fixa, com um limite maximo de rodadas
por seguranca.

## Decisao detalhada

### Algoritmo por atendimento

```text
rodada = 0
enquanto rodada < LIMITE_MAXIMO_RODADAS:
    os_abertas = buscar O.S. abertas do atendimento, ordenadas por ID (RN-004)
    se os_abertas estiver vazia:
        sucesso, encerra
    fechar cada O.S. de os_abertas, em ordem
        se uma falhar: parar tudo, reportar falha parcial (RN-005)
    rodada += 1

se rodada == LIMITE_MAXIMO_RODADAS e ainda houver O.S. aberta:
    reportar como falha (nao como sucesso), listando o que foi fechado
```

- `LIMITE_MAXIMO_RODADAS`: constante nomeada no codigo, valor inicial `20`.
  Decisao tecnica reversivel e de baixo risco — ajustavel sem nova decisao
  de arquitetura.
- Se a hipotese de criacao automatica de O.S. for falsa (ou nao se aplicar a
  todo atendimento), o laco custa apenas uma consulta extra por atendimento
  (a segunda rodada, que retorna lista vazia) — overhead desprezivel.

### Componentes a alterar (a cargo do Dev)

- `scripts/integracoes/backoffice/resolver_os_atendimento_ixc.py`
  (`executar_resolucao_os_atendimento_ixc`): trocar o `for os_atual in
  os_abertas` por este laco de repeticao.

### Risco relacionado, fora do escopo desta ADR

- `scripts/integracoes/backoffice/desativar_atendimento_ixc.py`
  (`executar_desativacao_atendimento`) tem a mesma lacuna: decide finalizar
  o atendimento com base na ultima O.S. de uma lista inicial estatica
  (`finaliza_atendimento = indice == len(os_alvos) - 1`). Se uma nova O.S.
  for criada apos finalizar essa "ultima" O.S. da lista original, o
  atendimento pode ser finalizado no IXC enquanto ainda existe uma O.S.
  aberta pendente, ou a chamada de finalizacao do atendimento pode falhar
  por haver uma O.S. aberta que o codigo nao sabia existir. Registrado como
  `PO-014` em `docs/BACKLOG.md`, sem correcao automatica nesta ADR.

## Consequencias positivas

- Resolve a lacuna real de nao fechar O.S. criadas durante o proprio
  processamento do atendimento.
- Funciona corretamente mesmo que a hipotese de criacao automatica de O.S.
  seja falsa (custo extra desprezivel).
- Limite de rodadas evita loop infinito em caso de comportamento
  inesperado do IXC (ex.: workflow que gera O.S. indefinidamente, ou falha
  silenciosa de fechamento que nunca reduz a lista).

## Consequencias negativas / riscos

- Aumenta o numero de chamadas a API do IXC por atendimento (uma consulta
  extra por rodada). Aceitavel dado o volume esperado (planilhas em lote,
  nao milhares de atendimentos simultaneos).
- Nao valida empiricamente a hipotese antes de implementar. Recomenda-se
  que o Dev, ao implementar, teste em um atendimento real de homologacao
  que tenha mais de uma tarefa no workflow, para confirmar o comportamento
  antes de considerar a feature validada pelo QA.

## Alternativas consideradas

### 1. Manter listagem fixa (ADR-002/ADR-003 originais)

Rejeitada. Deixa O.S. criadas durante o processamento sem fechar, se a
hipotese do workflow BPM for confirmada.

### 2. Round-robin entre atendimentos (fechar 1 O.S. por atendimento, avancar para o proximo, voltar ao primeiro ao final do lote, repetir até nenhum atendimento ter O.S. aberta)

Rejeitada por complexidade desnecessaria. Nao ha indicio de rate-limit ou
contencao na API do IXC que justifique intercalar atendimentos; resolver um
atendimento por completo antes de seguir para o proximo é mais simples e
produz o mesmo resultado.

## Proxima acao

Atualizar `PO-013` com o novo criterio de aceite (fechamento por rodadas) e
acionar o Dev para ajustar `resolver_os_atendimento_ixc.py`. Avaliar
`PO-014` (risco em `desativar_atendimento_ixc.py`) separadamente.
