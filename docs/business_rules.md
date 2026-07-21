# Regras de Negocio - GerenciadorProvedoresSpeed
_Ultima atualizacao: 2026-07-09_

## Automacoes IXC - Resolucao de O.S. de atendimento

### RN-001 - Fechamento de O.S. em massa nao finaliza o atendimento
**Descricao:** Ao resolver em massa as O.S. abertas de um atendimento no IXC, o atendimento (ticket) deve permanecer ativo. Nenhuma chamada de fechamento de O.S. desta automacao pode finalizar o atendimento.
**Contexto:** Automacao diferente da "Desativacao de Atendimento IXC" ja existente, que finaliza o atendimento de proposito.
**Criterios:** Toda chamada a `finalizar_os_existente` (ou equivalente) usa `finaliza_atendimento=False`, inclusive na ultima O.S. da lista. Ao final, o sistema confirma que o status do atendimento continua diferente de `F`.
**Excecoes:** nenhuma.
**Impacto tecnico:** nova orquestracao dedicada, distinta de `executar_desativacao_atendimento`.
**Features relacionadas:** PO-013 (docs/BACKLOG.md), ADR-002.
**Status:** Ativa

### RN-002 - Anexo obrigatorio antes do fechamento das O.S.
**Descricao:** O documento enviado pelo usuario deve ser anexado ao atendimento no IXC antes de qualquer O.S. ser finalizada.
**Contexto:** Definido explicitamente pelo usuario: se o anexo falhar, nenhuma O.S. pode ser fechada.
**Criterios:** Se o envio do anexo (`anexar_arquivo_ticket_ixc`) nao retornar sucesso, a execucao para imediatamente e nenhuma O.S. do atendimento e tocada.
**Excecoes:** nenhuma.
**Impacto tecnico:** o anexo deve ocorrer e ser validado antes do laco de fechamento de O.S.
**Features relacionadas:** PO-013, ADR-002.
**Status:** Substituida por RN-006

### RN-003 - Execucao por atendimento unico
**Descricao:** A automacao de resolucao de O.S. com anexo processa um atendimento por execucao (nao e upload em massa de planilha).
**Contexto:** Decisao confirmada com o usuario em 2026-07-09, para reduzir o risco de anexar o documento errado no atendimento errado em um lote.
**Criterios:** Tela com um campo de `Atendimento_ID`, um campo de upload de arquivo e um campo opcional de mensagem.
**Excecoes:** revisitar se surgir necessidade real de volume alto (ver ADR-002, riscos).
**Impacto tecnico:** nova view dedicada, sem reaproveitar o padrao de upload de planilha das demais automacoes do core_admin.
**Features relacionadas:** PO-013, ADR-002.
**Status:** Substituida por RN-007

### RN-004 - Ordem de fechamento respeita a sequencia do workflow
**Descricao:** As O.S. abertas do atendimento devem ser fechadas em ordem crescente de ID.
**Contexto:** O IXC trata o fechamento de O.S. como parte de um workflow sequencial (tarefa atual, proxima sequencia). Fechar fora de ordem pode gerar inconsistencia no processo do IXC.
**Criterios:** Reaproveitar a mesma ordenacao ja usada em `desativar_atendimento_ixc.py` (`_ordenar_os_por_id`). Esta regra vale dentro de cada rodada de busca; ver RN-010 para o comportamento entre rodadas.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** reuso de logica existente; nao deve ser duplicada nem reimplementada.
**Features relacionadas:** PO-013, ADR-002.
**Status:** Ativa

### RN-005 - Falha parcial nao desfaz o que ja foi concluido
**Descricao:** Se uma O.S. falhar ao fechar no meio do lote de um atendimento, as O.S. ja fechadas com sucesso permanecem fechadas. Nao ha rollback.
**Contexto:** Consistente com o comportamento ja existente em `executar_desativacao_atendimento`.
**Criterios:** O relatorio de execucao deve listar quais O.S. fecharam e qual foi a primeira a falhar, com a mensagem de erro tratada por `resumir_erro_finalizacao`.
**Excecoes:** nenhuma.
**Impacto tecnico:** nenhum mecanismo de rollback deve ser criado para este fluxo.
**Features relacionadas:** PO-013, ADR-002.
**Status:** Ativa

### RN-006 - Anexo condicional por atendimento
**Descricao:** O anexo de documento e opcional e definido por linha da planilha, via coluna `Tem_Anexo` (Sim/Nao). Quando `Tem_Anexo = Sim`, o documento correspondente deve ser anexado ao atendimento antes de qualquer O.S. ser fechada; se o anexo falhar, nenhuma O.S. daquele atendimento e fechada. Quando `Tem_Anexo = Nao`, a automacao fecha as O.S. do atendimento sem tentar nenhum anexo.
**Contexto:** Ampliacao de RN-002, solicitada pelo usuario em 2026-07-09 para suportar lote de atendimentos onde nem todos tem documento a anexar.
**Criterios:** `Tem_Anexo` aceita Sim/Nao (e variacoes equivalentes ja usadas nas demais automacoes, ex. S/N). Se `Tem_Anexo = Sim` e `Nome_Anexo` nao corresponder a um arquivo do ZIP (RN-008), a linha falha antes de qualquer fechamento de O.S. Se `Tem_Anexo = Nao`, o campo `Nome_Anexo` e ignorado mesmo se preenchido.
**Excecoes:** nenhuma.
**Impacto tecnico:** a orquestracao por atendimento precisa aceitar um indicador "possui anexo" e pular a chamada de anexo quando falso.
**Features relacionadas:** PO-013, ADR-003.
**Status:** Ativa

### RN-007 - Execucao em lote via planilha
**Descricao:** A automacao de resolucao de O.S. processa varios atendimentos em uma unica execucao, a partir de uma planilha de importacao, no mesmo padrao de import/export (log de resultado) ja usado nas demais automacoes do backoffice.
**Contexto:** Decisao revertida pelo usuario em 2026-07-09, no mesmo dia em que RN-003 (execucao unitaria) foi registrada — o volume real de atendimentos por operacao e maior do que o assumido inicialmente.
**Criterios:** a planilha contem, por linha, no minimo `Atendimento_ID`, `Tem_Anexo` e, opcionalmente, `Nome_Anexo` e `Mensagem`; cada linha e processada e reportada individualmente no arquivo de saida; falha em uma linha nao interrompe o processamento das demais linhas do lote.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** reescreve a orquestracao unitaria hoje existente em `resolver_os_atendimento_ixc.py` (`executar_resolucao_os_atendimento_ixc`) para operar linha a linha, reaproveitando o padrao de leitura/validacao de planilha das demais automacoes do modulo.
**Features relacionadas:** PO-013, ADR-003.
**Status:** Ativa

### RN-008 - Correspondencia de anexo por nome de arquivo dentro do ZIP
**Descricao:** Quando `Tem_Anexo = Sim`, o documento a anexar e localizado dentro de um arquivo ZIP importado junto com a planilha, casando pelo nome informado na coluna `Nome_Anexo` daquela linha.
**Contexto:** Cada atendimento (cliente) pode ter um documento PDF diferente; o usuario importa todos os documentos de uma vez em um unico ZIP e referencia cada um pelo nome na planilha.
**Criterios:** `Nome_Anexo` deve corresponder a um arquivo dentro do ZIP; apenas PDF e aceito; se o nome informado nao existir no ZIP ou nao for PDF, a linha falha com mensagem explicita e nenhuma O.S. daquele atendimento e tocada; um mesmo arquivo do ZIP pode ser referenciado por mais de uma linha.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** nova funcao de extracao/busca de arquivo dentro do ZIP em memoria, sem persistir o PDF em disco (RN-009).
**Features relacionadas:** PO-013, ADR-003.
**Status:** Ativa

### RN-009 - Documentos nao sao persistidos no sistema
**Descricao:** Os PDFs enviados dentro do ZIP sao usados apenas para a chamada de anexo ao IXC durante a execucao e nao sao salvos no banco de dados nem em storage do sistema.
**Contexto:** Definido explicitamente pelo usuario; apenas a planilha de entrada e a planilha/log de saida devem ser mantidas, seguindo o padrao ja usado pelas demais automacoes do backoffice.
**Criterios:** o PDF e lido em memoria a partir do ZIP e enviado diretamente a chamada de anexo do IXC; nenhum model, campo de upload persistente ou diretorio de midia deve ser criado para armazenar esses arquivos.
**Excecoes:** nenhuma.
**Impacto tecnico:** reaproveitar o padrao de arquivo em memoria ja usado para os demais uploads de planilha do modulo, sem introduzir novo storage.
**Features relacionadas:** PO-013, ADR-003.
**Status:** Ativa

### RN-010 - Fechamento de O.S. repete ate esgotar, com limite de seguranca
**Descricao:** O fechamento de O.S. de um atendimento nao pode se basear em uma unica listagem estatica. Para cada atendimento: (1) listar as O.S. abertas; (2) fechar cada uma em ordem crescente de ID (RN-004); (3) listar novamente as O.S. abertas do mesmo atendimento; (4) repetir os passos 2-3 enquanto houver O.S. aberta, até um limite maximo de rodadas.
**Contexto:** O payload de fechamento de O.S. no IXC (`id_tarefa_atual`, `proxima_sequencia_forcada`, `id_proxima_tarefa`, em `ixc_finalizacao_service.montar_payload_fechamento_real`) mostra que fechar uma O.S. avanca um workflow BPM do IXC, que pode criar automaticamente a proxima tarefa do processo como uma nova O.S. aberta no mesmo atendimento. Identificado pelo usuario a partir da tela de Acoes da O.S. no IXC (Finalizar, Analisar, Executar, etc.) e confirmado pelo Dev na estrutura do payload, em 2026-07-09. A implementacao anterior (apenas RN-004) listava as O.S. abertas uma unica vez e fechava somente essa lista, podendo deixar sem fechar uma O.S. criada durante o proprio processamento do atendimento.
**Criterios:**
- se, apos o limite maximo de rodadas, ainda houver O.S. aberta, o atendimento/linha deve ser reportado como falha (nao como sucesso), listando as O.S. ja fechadas até aquele ponto;
- cada rodada individual continua respeitando RN-004 (ordem crescente de ID) e RN-005 (falha parcial nao desfaz o que ja foi concluido);
- o limite maximo de rodadas e uma constante nomeada no codigo (valor inicial sugerido: 20), ajustavel sem exigir nova decisao de arquitetura.
**Excecoes:** nenhuma conhecida. Se a hipotese de criacao automatica de O.S. for refutada em teste real no IXC, o comportamento se reduz a uma unica rodada (equivalente ao anterior), sem custo relevante.
**Impacto tecnico:** `resolver_os_atendimento_ixc.py` (PO-013) precisa trocar o `for os_atual in os_abertas` por um laco que repete a consulta ate esgotar ou atingir o limite. A mesma lacuna existe em `desativar_atendimento_ixc.py` (`executar_desativacao_atendimento`), que hoje decide finalizar o atendimento com base na ultima O.S. de uma lista inicial estatica — tratado como risco separado (ver `docs/BACKLOG.md`, PO-014).
**Excecao adicional (RN-012):** quando a linha da planilha pedir fechamento parcial (`Fechar_Todas_OS = NAO`), o loop desta regra nao se aplica — ver RN-012.
**Features relacionadas:** PO-013, PO-014, ADR-004.
**Status:** Ativa

### RN-012 - Fechamento parcial opcional por linha (Fechar_Todas_OS)
**Descricao:** A planilha de resolucao de O.S. aceita, por linha, a coluna `Fechar_Todas_OS` (Sim/Nao). Quando `Sim`, vale o comportamento padrao de RN-010 (repetir busca+fechamento ate esgotar). Quando `Nao`, a automacao fecha somente a O.S. aberta mais antiga do atendimento (a primeira da ordenacao de RN-004), sem repetir a busca.
**Contexto:** Identificado no mapeamento de 2026-07-21: a implementacao de PO-013 ja incluia este campo, sem estar registrado em RN-XXX nem nos criterios de aceite originais. Confirmado pelo usuario em 2026-07-21 que o comportamento deve ser mantido e documentado.
**Criterios:** `Fechar_Todas_OS` e obrigatorio na planilha, aceitando Sim/Nao (e variacoes ja usadas nas demais automacoes, ex. S/N); quando `Nao`, apenas a O.S. mais antiga em aberto e fechada e o loop de RN-010 nao e executado; o atendimento permanece ativo em ambos os modos (RN-001).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** jah implementado em `executar_resolucao_os_atendimento_ixc` (`resolver_os_atendimento_ixc.py`).
**Features relacionadas:** PO-013.
**Status:** Ativa

### RN-013 - Confirmacao explicita de fechamento (Confirmar_Resolucao)
**Descricao:** A planilha exige, por linha, a coluna `Confirmar_Resolucao` preenchida com `SIM` para autorizar o fechamento das O.S. daquele atendimento. Sem essa confirmacao explicita, a linha falha antes de qualquer acao no IXC.
**Contexto:** Identificado no mapeamento de 2026-07-21: segue o mesmo padrao ja usado por `Confirmar_Desativacao` na automacao de Desativacao de Atendimento (`desativar_atendimento_ixc.py`), nao estava apenas registrado como RN propria de PO-013. Confirmado pelo usuario em 2026-07-21.
**Criterios:** `Confirmar_Resolucao` aceita valores equivalentes a SIM (mesma tolerancia das demais automacoes); ausencia ou valor diferente de SIM bloqueia a linha com mensagem explicita, sem tocar o IXC.
**Excecoes:** nenhuma.
**Impacto tecnico:** jah implementado em `executar_resolucao_os_atendimento_ixc`; consistente com o padrao ja usado em `executar_desativacao_atendimento`.
**Features relacionadas:** PO-013.
**Status:** Ativa

### RN-014 - Atendimento precisa estar em progresso para fechar O.S.
**Descricao:** A automacao so fecha O.S. de um atendimento cujo `su_status` no IXC seja `EP` (Em Progresso). Atendimentos com outro status sao rejeitados antes de qualquer fechamento.
**Contexto:** Identificado no mapeamento de 2026-07-21: criterio novo, presente na implementacao de PO-013 mas nao previsto em nenhuma RN nem nos criterios de aceite originais — protege contra fechar O.S. de atendimentos ja finalizados, cancelados ou em outro estado do workflow do IXC. Confirmado pelo usuario em 2026-07-21 que deve ser mantido e documentado.
**Criterios:** antes de qualquer verificacao de anexo ou fechamento, a linha e rejeitada com mensagem explicita se `su_status` do atendimento for diferente de `EP`.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** jah implementado em `executar_resolucao_os_atendimento_ixc`.
**Features relacionadas:** PO-013.
**Status:** Ativa

## Configuracao de Menu de Automacoes

### RN-011 - Menu de exibicao de automacao e configuravel, com Administrador como padrao
**Descricao:** Toda automacao deve ter um menu de exibicao definido (Administrador, Backoffice, LastMile, Parceiro). O padrao de uma automacao nova, sem configuracao explicita, e sempre Administrador. Automacoes existentes podem ser realocadas para outro menu sem alterar template ou codigo de view, apenas a configuracao.
**Contexto:** Hoje o menu de cada automacao esta fixo no template (`core/templates/core/base.html`), exigindo edicao de codigo e deploy para mover uma automacao de um menu para outro (ex.: de Administrador para Backoffice). Solicitado pelo usuario em 2026-07-13 para permitir essa realocacao sem depender de alteracao de codigo.
**Criterios:**
- toda automacao possui um registro de configuracao com o menu de destino;
- o valor padrao do menu, quando nao configurado, e Administrador;
- somente usuario com permissao de Administrador pode alterar o menu de destino de uma automacao;
- o menu exibido para o usuario deve refletir a configuracao atual sem exigir deploy.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** nova fonte de verdade (model `AutomacaoMenu`) para o menu de cada automacao; template de menu deixa de ter link fixo por automacao e passa a renderizar a partir dessa configuracao.
**Features relacionadas:** PO-015 (docs/BACKLOG.md).
**Status:** Ativa

## Historico de Alteracoes
| Data | Regra | Alteracao |
|---|---|---|
| 2026-07-09 | RN-001 a RN-005 | Criacao inicial a partir do desenho da automacao de resolucao de O.S. de atendimento (ADR-002) |
| 2026-07-09 | RN-002, RN-003 substituidas; RN-006 a RN-009 criadas | Usuario reverteu execucao unitaria para lote via planilha, com anexo condicional e ZIP de documentos (ADR-003) |
| 2026-07-09 | RN-010 criada; RN-004 ampliada | Usuario identificou que o fechamento de O.S. pode gerar nova O.S. via workflow do IXC; fechamento passa a repetir até esgotar (ADR-004) |
| 2026-07-13 | RN-011 criada | Usuario solicitou tornar o menu de exibicao de automacoes configuravel em vez de fixo em template, com Administrador como padrao |
| 2026-07-21 | RN-012, RN-013, RN-014 criadas; RN-010 ampliada | Mapeamento de PO-013 encontrou 3 comportamentos ja implementados e nao documentados (fechamento parcial opcional, confirmacao explicita, gate de status do atendimento); usuario confirmou manter e documentar todos |
