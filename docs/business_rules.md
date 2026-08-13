# Regras de Negocio - GerenciadorProvedoresSpeed
_Ultima atualizacao: 2026-08-11_

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

## Automacoes IXC - Cadastro de Cliente

### RN-015 - Verificacao de duplicidade no Cadastro de Cliente IXC e por CNPJ/CPF; mensagem deve identificar o campo de correspondencia
**Descricao:** A automacao de Cadastro de Cliente IXC bloqueia a criacao de um cliente quando ja existe, no IXC, outro cliente com o mesmo CNPJ/CPF (ou a mesma razao social). O CNPJ/CPF continua sendo criterio valido de duplicidade e o bloqueio por padrao deve ser mantido. Porem, a mensagem de erro deve deixar explicito qual campo gerou a correspondencia (CNPJ/CPF ou razao social) e o valor comparado, para que quem revisa o relatorio saiba que, ao abrir o `ID_IXC` indicado, deve conferir o CNPJ/CPF daquele registro — nao o nome/razao social, que pode ser de outro cliente legitimamente diferente.
**Contexto:** Investigacao do `log_integracao_274` (2026-07-24) mostrou que orgaos publicos municipais (ex.: secretaria de educacao) usam um unico CNPJ para varias escolas distintas. Quando a automacao encontra esse CNPJ ja cadastrado no IXC (referente a uma escola), ela bloqueia o cadastro de todas as demais escolas com o mesmo CNPJ, reportando o ID da escola ja cadastrada. O usuario, ao abrir esse ID no IXC, encontrou um cadastro com nome/login diferente do esperado e interpretou como possivel erro do sistema. Confirmado pelo usuario em 2026-07-24 que o bloqueio por CNPJ deve ser mantido (nao cadastrar duplicado automaticamente), mas a mensagem precisa deixar claro que a correspondencia foi por CNPJ/CPF, incluindo o valor do documento, eliminando a ambiguidade.
**Criterios:**
- a mensagem de bloqueio informa explicitamente que a correspondencia foi encontrada pelo campo CNPJ/CPF (ou por razao social, quando for esse o caso) e o valor comparado;
- o `ID_IXC` retornado no relatorio continua sendo o do cliente ja existente encontrado;
- o comportamento de bloqueio por padrao (sem `Permitir_Duplicidade = Sim`) nao muda;
- `Permitir_Duplicidade` continua sendo o unico caminho para forcar o cadastro mesmo com CNPJ/CPF repetido.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** ajuste de mensagem em `executar_cadastro_cliente_ixc` (`scripts/integracoes/backoffice/cadastrar_cliente_ixc.py`), a partir do retorno de `buscar_cliente_por_cnpj_cpf`/`buscar_cliente_por_razao_social`; sem alteracao de logica de bloqueio.
**Features relacionadas:** PO-020 (docs/BACKLOG.md).
**Status:** Ativa

### RN-016 - Validacao previa do Cadastro de Cliente IXC detecta CNPJ/CPF duplicado antes do envio
**Descricao:** Na validacao "tudo ou nada" que roda antes do envio ao IXC (fase 1 de `cadastrar_clientes_ixc`), a planilha passa a ser verificada quanto a CNPJ/CPF duplicado em duas frentes: (1) duplicidade DENTRO da propria planilha (mesmo CNPJ/CPF em mais de uma linha do arquivo importado); e (2) duplicidade contra cliente ja cadastrado no IXC (mesma checagem que hoje so roda em `executar_cadastro_cliente_ixc` na hora do envio — RN-015). Qualquer linha com CNPJ/CPF duplicado (interno ou contra o IXC) reprova a validacao da planilha inteira, seguindo o padrao "tudo ou nada" ja usado para os demais erros, a menos que a linha tenha `Permitir_Duplicidade = Sim`.
**Contexto:** Usuario percebeu, ao revisar o `log_integracao_274`, que o mesmo CNPJ aparecia repetido em varias linhas da planilha enviada, e que o erro de "cliente ja existente" (RN-015) so era descoberto depois do envio, linha a linha. Confirmado pelo usuario em 2026-07-24 que a validacao previa deve antecipar os dois casos (duplicidade interna da planilha e duplicidade contra o IXC), reprovando a planilha inteira ate que o operador resolva ou confirme `Permitir_Duplicidade = Sim` nas linhas afetadas. Usuario tambem confirmou que a validacao previa deve consultar o IXC (uma chamada por linha), mesmo que isso deixe a validacao mais lenta.
**Criterios:**
- durante a validacao previa, cada linha tem seu CNPJ/CPF comparado com as demais linhas da mesma planilha; havendo repeticao, a(s) linha(s) recebem erro de validacao indicando as linhas envolvidas, exceto quando `Permitir_Duplicidade = Sim`;
- durante a mesma validacao previa, cada linha tem seu CNPJ/CPF (e, no fallback, a razao social) consultado no IXC, replicando `buscar_cliente_por_cnpj_cpf`/`buscar_cliente_por_razao_social` (RN-015); havendo correspondencia, a linha recebe erro de validacao no mesmo formato de RN-015 (campo e valor que geraram a correspondencia, incluindo o ID do cliente ja existente), exceto quando `Permitir_Duplicidade = Sim`;
- qualquer uma dessas duas ocorrencias reprova a planilha inteira (nenhuma linha e enviada ao IXC ate a planilha inteira passar na validacao), mantendo o comportamento "tudo ou nada" ja existente;
- `Permitir_Duplicidade = Sim` continua sendo o unico mecanismo para a linha passar na validacao mesmo com duplicidade encontrada (interna ou contra o IXC).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** fase de pre-validacao em `cadastrar_clientes_ixc` (`apps/backoffice/views.py`) e `validar_linha_pre_envio` (`scripts/integracoes/backoffice/cadastrar_cliente_ixc.py`) passam a: (1) comparar CNPJ/CPF entre todas as linhas da planilha antes de iniciar o envio; (2) chamar `buscar_cliente_por_cnpj_cpf`/`buscar_cliente_por_razao_social` durante essa validacao previa, alem de dentro de `executar_cadastro_cliente_ixc`. Consulta ao IXC por linha durante a validacao torna o processo mais lento — aceito pelo usuario.
**Features relacionadas:** PO-021 (docs/BACKLOG.md).
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

## Ciclo de vida da cotacao

### RN-017 - Abrir a medicao exige endereco do IXC e provedor cadastrado
**Descricao:** Uma cotacao (`Proposal`) so pode ser aberta quando existem os dois requisitos obrigatorios: o endereco (login) do cliente, e o provedor (`Partner`), cadastrado dentro do sistema. Os dois sao requisitos paralelos — nao ha ordem entre eles, mas nenhum e dispensavel.
**Contexto:** Confirmado pelo dono do produto em 2026-07-29, durante o desenho do diagrama `02 · Ciclo de vida da cotacao`. A primeira versao do diagrama mostrava apenas o endereco; o usuario apontou a ausencia do provedor. Em 2026-08-07, a origem do endereco mudou duas vezes no mesmo dia: primeiro a ADR-008 desativou a sincronizacao automatica com o IXC (previu importacao manual); depois o usuario decidiu que os dados do DashboardEACE (ADR-009) nao vao para `Cliente`/`Endereco` — vao para um model novo e independente, `apps.escolas.Escola` (ADR-010). Resultado: hoje `Cliente`/`Endereco` nao tem nenhuma fonte automatica de dados novos.
**Criterios:**
- o endereco/login e o registro `clientes.Endereco` vinculado ao `Cliente`; ate 2026-08-07 vinha exclusivamente das rotinas de sincronizacao do IXC (app `clientes`), desativadas por ADR-008; hoje nao ha fonte automatica definida (nem IXC, nem DashboardEACE, que alimenta uma tabela separada por ADR-010) — mecanismo futuro ainda nao decidido;
- o provedor e cadastrado e mantido dentro do sistema, com seu plano (`PartnerPlan`);
- faltando qualquer um dos dois, nao existe medicao a ser aberta.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `Proposal` tem FK obrigatoria para `Partner` e vinculo com `clientes.Cliente`/endereco. Verificar se a obrigatoriedade esta de fato imposta no model/form, ou apenas assumida pelo fluxo de tela. Ver tambem ADR-008 para o efeito colateral em `apps/leads`/`apps/partners` (campos `em_os_comercial_lastmile`/`os_atual_aberta` deixam de atualizar).
**Features relacionadas:** nenhuma aberta.
**Status:** Ativa

### RN-018 - Transicoes validas do status da cotacao
**Descricao:** O status de uma cotacao (`Proposal.status`) so pode seguir os caminhos abaixo. Nenhuma outra transicao e valida do ponto de vista de negocio.
**Contexto:** Confirmado pelo dono do produto em 2026-07-29. O levantamento do codigo mostrou que **nao existe maquina de estado**: as views validam apenas se o valor pertence a `Proposal.STATUS_CHOICES` (`status_validos = {choice[0] for choice in Proposal.STATUS_CHOICES}`, `apps/partners/views.py`), sem impedir nenhuma transicao. Esta RN registra a regra de negocio; a validacao em codigo ainda nao existe.
**Criterios:**
- `analise` (Em Negociacao) pode ir somente para `ativa` (Viavel) ou `encerrada` (Inviavel);
- `ativa` (Viavel) segue para `aguardando_contratacao`;
- `aguardando_contratacao` pode ir para `contratado` ou `declinado`;
- **declinar so e possivel depois de Viavel** — nao ha caminho de Em Negociacao direto para Declinado;
- `encerrada` (Inviavel) e terminal: nao pode ser reaberta no momento;
- `contratado` e `declinado` sao terminais.
**Excecoes:** a reabertura de Inviavel foi explicitamente descartada "no momento" — se voltar a pauta, reavaliar esta RN em vez de abrir excecao pontual.
**Impacto tecnico:** hoje qualquer status pode ir para qualquer outro, inclusive pular etapas ou sair de um terminal. Implementar a validacao exige feature propria (a definir): onde validar (model `clean`/`save` ou camada de servico) e o que fazer com registros ja fora do fluxo.
**Features relacionadas:** nenhuma aberta.
**Status:** Ativa

### RN-019 - Proxima tarefa do workflow deve ser informada quando a O.S. exigir decisao
**Descricao:** Quando a tarefa atual de uma O.S. for uma tarefa de decisao do workflow do IXC (tela com varias opcoes de "Proxima tarefa", ex.: Realizar Implantacao, Realizar Implantacao EACE, Nao Atende Requisitos Tecnicos), a automacao de resolucao de O.S. em massa deve receber, por linha da planilha, qual o ID da proxima tarefa a seguir. Sem essa informacao a O.S. nao deve ser fechada.
**Contexto:** Usuario identificou em 2026-08-06, ao operar o IXC manualmente, que o fechamento de uma O.S. pode abrir uma tela de decisao obrigatoria de proxima tarefa. `montar_payload_fechamento_real` (`ixc_finalizacao_service.py`) ja hoje fixa `eh_tarefa_decisao="N"` e `id_proxima_tarefa="0"`, sem nenhuma forma de a planilha informar outro valor — lacuna coerente com o risco ja registrado em ADR-004 (fechamento de O.S. como avanco de workflow BPM, nao simples marcacao de status). Usuario confirmou que a solucao deve ser uma nova coluna na planilha, e nao um valor fixo nem rejeitar a linha.
**Criterios:** nova coluna obrigatoria na planilha (nome a definir pelo Dev na implementacao, ex.: `Proxima_Tarefa_ID`) preenchida com o ID da proxima tarefa quando a O.S. exigir decisao; o valor informado deve ser enviado em `id_proxima_tarefa` e `eh_tarefa_decisao` deve refletir "S" nesse caso; se a O.S. nao for uma tarefa de decisao, o comportamento atual (sem exigir o campo) permanece.
**Excecoes:** a forma de detectar se a tarefa atual e uma tarefa de decisao (campo do IXC a consultar) fica a cargo do levantamento tecnico do Dev na implementacao; se o IXC nao expuser essa informacao antecipadamente, avaliar com o usuario se o campo passa a ser sempre obrigatorio na planilha.
**Impacto tecnico:** `resolver_os_atendimento_ixc.py` (colunas da planilha) e `ixc_finalizacao_service.montar_payload_fechamento_real` (parar de fixar `eh_tarefa_decisao`/`id_proxima_tarefa`).
**Features relacionadas:** PO-013, PO-040, ADR-004.
**Status:** Ativa

### RN-020 - Multiplos anexos por atendimento (Mais_de_um_anexo)
**Descricao:** Um atendimento pode ter mais de um documento a anexar antes do fechamento das O.S. A planilha aceita, por linha, a coluna `Mais_de_um_anexo` (Sim/Nao). Quando `Sim`, a automacao anexa todos os arquivos preenchidos entre `Nome_Anexo`, `Nome_Anexo_2` e `Nome_Anexo_3`, repetindo a chamada de anexo ao IXC uma vez por arquivo (a API do IXC aceita um arquivo por chamada). Quando `Nao`, a automacao usa somente `Nome_Anexo`, mesmo comportamento atual.
**Contexto:** Usuario identificou em 2026-08-06 que um atendimento pode ter mais de um documento a anexar (ex.: contrato + aditivos), e hoje a automacao so suporta um arquivo por atendimento (RN-006/RN-008). Confirmou que a solucao e 3 colunas de nome de arquivo (nao lista separada por virgula em uma unica coluna) mais uma coluna de controle explicita `Mais_de_um_anexo`, seguindo o mesmo padrao de flag Sim/Nao ja usado em `Tem_Anexo` e `Fechar_Todas_OS`.
**Criterios:**
- `Mais_de_um_anexo` so e avaliado quando `Tem_Anexo = SIM`; se `Tem_Anexo = NAO`, `Mais_de_um_anexo` e ignorado.
- `Mais_de_um_anexo = NAO` (ou vazio): comportamento atual — so `Nome_Anexo` e usado; `Nome_Anexo_2` e `Nome_Anexo_3`, mesmo se preenchidos, sao ignorados.
- `Mais_de_um_anexo = SIM`: a automacao anexa, em sequencia, cada nome preenchido entre `Nome_Anexo`, `Nome_Anexo_2` e `Nome_Anexo_3` (nessa ordem), repetindo para cada um a correspondencia por nome dentro do ZIP (RN-008).
- Mantem o comportamento tudo-ou-nada de RN-002: se qualquer um dos anexos preenchidos falhar (arquivo nao encontrado no ZIP, nao ser PDF, ou falha ao enviar ao IXC), a execucao para naquela linha antes de qualquer O.S. ser finalizada; anexos ja enviados com sucesso antes da falha permanecem enviados (o IXC nao desfaz um anexo ja gravado).
- A mesma `Mensagem` da linha e usada como descricao de cada anexo enviado.
**Excecoes:** limite de 3 anexos por atendimento (`Nome_Anexo` + 2 colunas extras); se precisar de mais no futuro, e nova decisao.
**Impacto tecnico:** `resolver_os_atendimento_ixc.py` (novas colunas `Mais_de_um_anexo`, `Nome_Anexo_2`, `Nome_Anexo_3` e loop sobre os nomes preenchidos) e o gerador de planilha modelo/aba de ajuda em `apps/core_admin/services.py`.
**Features relacionadas:** PO-013, PO-041, RN-002, RN-006, RN-008, RN-009.
**Status:** Ativa

### RN-021 - Colaborador do fechamento pode ser informado por e-mail (Informar_Colaborador / Email_Colaborador)
**Descricao:** Por padrao, a automacao de resolucao de O.S. atribui o fechamento ao usuario do sistema logado (resolvido para um usuario do IXC pelo e-mail/nome/usuario). A planilha aceita, por linha, a coluna `Informar_Colaborador` (Sim/Nao). Quando `Sim`, a coluna `Email_Colaborador` deve conter o e-mail do colaborador do IXC que deve constar como responsavel pela finalizacao daquela O.S., em vez de quem esta executando a automacao. Quando `Nao` (ou vazio), o comportamento atual e mantido — usa o e-mail do usuario logado no sistema.
**Contexto:** Usuario identificou que o nome do colaborador exibido no IXC e sempre de quem executa a automacao e perguntou como especificar outra pessoa. Confirmou que a busca deve ser por e-mail (`resolver_usuario_ixc_por_email`, ja existente em `ixc_finalizacao_service.py`), nao por ID do IXC (sem visibilidade facil de qual ID pertence a qual pessoa), e que essa informacao deve ser opcional via flag Sim/Nao, no mesmo padrao das demais flags da planilha (RN-006, RN-020).
**Criterios:**
- `Informar_Colaborador = SIM` exige `Email_Colaborador` preenchido; vazio bloqueia a linha antes de qualquer O.S. ser tocada.
- `Informar_Colaborador = SIM` com e-mail que nao corresponde a nenhum usuario cadastrado no IXC bloqueia a linha, reportando que o e-mail nao foi encontrado — nao deve cair silenciosamente no usuario/tecnico padrao generico que `resolver_usuario_ixc_por_email` usa como fallback interno.
- `Informar_Colaborador = NAO` ou vazio: `Email_Colaborador`, mesmo se preenchido, e ignorado; usa o e-mail do usuario logado no sistema (comportamento atual, via `usuario_sistema`).
- O e-mail informado (ou o do usuario logado, quando `Informar_Colaborador = NAO`) e usado para todas as O.S. fechadas naquela linha/atendimento.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `resolver_os_atendimento_ixc.py` (novas colunas `Informar_Colaborador` e `Email_Colaborador`; repassar `email_ixc` para `finalizar_os_existente` em vez de depender so de `usuario_sistema`) e o gerador de planilha modelo/aba de ajuda em `apps/core_admin/services.py`.
**Features relacionadas:** PO-042, RN-002, RN-006, RN-020.
**Status:** Ativa

### RN-022 - Visibilidade da linha atual durante a execucao da resolucao de O.S.
**Descricao:** A automacao de resolucao de O.S. em massa deve expor, durante a execucao, qual linha/atendimento esta sendo processado no momento, para o usuario acompanhar o progresso sem esperar as cegas até o fim.
**Contexto:** Usuario relatou que hoje, durante execucoes longas (ex.: 148 linhas, ~18 minutos), nao ha nenhuma indicacao de progresso na tela — so um spinner estatico. Confirmado que a solucao deve manter a execucao sincrona atual (mesmo request HTTP), apenas adicionando visibilidade via consulta periodica (polling) da tela, sem tornar a automacao assincrona.
**Criterios:**
- durante o processamento, a cada linha (ou a cada N linhas, decisao tecnica do Dev), o sistema grava o progresso atual (numero da linha, total de linhas, Atendimento_ID sendo processado) em um registro consultavel;
- a tela de "Resolucao de O.S. do Atendimento" passa a consultar esse progresso periodicamente (polling via JS/HTMX) enquanto a requisicao principal esta em andamento, exibindo algo como "Processando linha X de Y (Atendimento Z)";
- ao concluir (sucesso, erro ou falha), o indicador de progresso e finalizado normalmente, junto com o fluxo de download do relatorio ja existente;
- a gravacao do progresso nao deve impedir nem atrasar de forma perceptivel o processamento das linhas (e um registro leve, sem chamada adicional ao IXC).
**Excecoes:** nao resolve o risco, ja registrado separadamente (2026-08-06, ajuste do timeout do Gunicorn), de perda do relatorio se o processo for interrompido no meio (worker morto, timeout, etc.) — tratado como pendencia distinta, nao no escopo desta RN.
**Impacto tecnico:** provavel extensao de `IntegrationAudit` (ou registro equivalente) para guardar o progresso atual; novo endpoint leve de consulta de progresso; ajuste no template/JS de `resolver_os_atendimento_ixc.html` para fazer polling durante o carregamento.
**Features relacionadas:** PO-043, RN-002.
**Status:** Ativa

### RN-023 - Rede Externa (RE) e Rede Interna (RI) sao processos independentes por escola
**Descricao:** Cada `Escola` tem, no maximo, um processo de Rede Externa (RE) e um processo de Rede Interna (RI), cada um com seu proprio setor, status e parceiro. RE e RI sao independentes entre si: podem estar em setores diferentes, com status diferentes ao mesmo tempo, e podem ter o mesmo parceiro ou parceiros diferentes. Os dois processos sao subordinados a Escola (identificada pelo INEP) — nao existem sem uma Escola associada.
**Contexto:** Usuario confirmou em 2026-08-07 que a API do DashboardEACE ja sugere essa separacao (campos `setor_re`/`setor_ri`, `parceiro_re`/`parceiro_ri`, `custo_re_*`/`custo_ri_*`), mas que RE/RI devem ser processos **geridos pelo proprio sistema** (fluxo de trabalho atualizado por quem opera), nao um espelho somente-leitura desses campos da API. Confirmado tambem que cada Escola tem no maximo 1 RE e 1 RI, sem historico de ciclos/tentativas por agora.
**Criterios:**
- RE e RI sao registros separados, cada um vinculado a uma Escola (relacao 1 para 1);
- setor, status e parceiro de RE nao dependem nem se limitam aos de RI, e vice-versa;
- parceiro de RE e de RI referencia o cadastro existente (`apps.partners.Partner`) — pode ser o mesmo `Partner` para os dois, ou dois diferentes;
- criacao do processo comeca em branco (setor/status/parceiro vazios); nao ha pre-preenchimento automatico a partir dos campos `setor_re`/`setor_ri`/`parceiro_re`/`parceiro_ri` ja existentes em `Escola.dados_api` (decisao tecnica reversivel, ver ADR-012 — evita assumir que o formato desses campos bate com o vocabulario que o sistema vai usar);
- vocabulario de setor e status ainda nao e uma lista fixa — campos de texto livre por agora; se o usuario definir a lista, migrar para `choices=`.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** novos models `RedeExterna`/`RedeInterna` em `apps.escolas`, cada um com `OneToOneField(Escola, on_delete=CASCADE)`. Ver ADR-012 para o desenho completo (por que duas tabelas em vez de uma so com discriminador, e por que nao sincronizar automaticamente com os campos `*_re`/`*_ri` da API).
**Features relacionadas:** PO-048, ADR-010, ADR-012.
**Status:** Ativa

### RN-024 - Referencia de RE e RI (dados da API DashboardEACE) visivel na tela de Enderecos Lastmile
**Descricao:** Na tela de Enderecos Lastmile, cada Escola pode ser expandida para mostrar os dados de Rede Externa (RE) e Rede Interna (RI) que ja vem da API do DashboardEACE (setor, parceiro, custo de implantacao, custo recorrente — de cada um). Sao dados de referencia, somente leitura; nao ha edicao nem vinculo com os processos internos `RedeExterna`/`RedeInterna` (RN-023) nesta tela.
**Contexto:** Usuario pediu para ver, ao clicar na escola, duas linhas expandidas (RE e RI) com os dados que ja vem da API. Confirmado que, por agora, e so a referencia da API — sem editar nem criar os registros de processo interno (RN-023), que continuam vazios.
**Criterios:**
- clicar na linha da escola alterna a exibicao de duas linhas abaixo dela: RE e RI;
- RE mostra setor, parceiro, custo de implantacao e custo recorrente do campo `setor_re`/`parceiro_re`/`custo_re_implantacao`/`custo_re_recorrente` (dentro de `Escola.dados_api`); RI mostra o equivalente com sufixo `_ri`;
- campo ausente ou vazio exibe "Nao informado";
- nenhum desses campos e editavel nesta tela.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** leitura direta de `Escola.dados_api` no template/contexto da view `enderecos_lastmile_view`; comportamento de expandir/recolher implementado em Alpine.js, sem nova requisicao ao servidor. Ver ADR-013.
**Features relacionadas:** PO-049, RN-023, ADR-010, ADR-013.
**Status:** Ativa

### RN-025 - Catalogo de Processos (Setor/Status) vinculado a RedeExterna e RedeInterna
**Descricao:** Um Processo tem nome, e reune um conjunto de Setores; cada Setor reune um conjunto de Status. `RedeExterna` e `RedeInterna` podem ser vinculados a um Processo (o mesmo ou um diferente entre os dois). O Processo em si nao se marca como "de RE" ou "de RI" — essa distincao vem de qual model (RedeExterna ou RedeInterna) esta apontando para ele.
**Contexto:** Usuario pediu uma tela para cadastrar Processos, seus Setores e os Status de cada Setor, resolvendo a pendencia de vocabulario deixada pela RN-023/ADR-012. Perguntado se o Processo precisa de um campo tipo (RE/RI), respondeu que nao — o vinculo fica a cargo de `RedeExterna`/`RedeInterna` apontarem para o Processo. Pediu tambem para semear, so para teste, os Setores Lastmile/Suprimentos/Implantacao/Pos venda/Suporte e Status genericos (A fazer/Em andamento/Concluido) em dois Processos (Rede Externa e Rede Interna).
**Criterios:**
- um Processo tem varios Setores; um Setor tem varios Status — hierarquia propria de cada Processo, sem compartilhamento entre Processos diferentes;
- `RedeExterna.processo` e `RedeInterna.processo` sao opcionais (podem nao ter processo definido);
- nesta primeira versao, a tela de gestao de Processos permite somente visualizar e criar — sem editar nem excluir;
- `RedeExterna.setor`/`status` (texto livre, RN-023) nao sao validados contra o Processo vinculado nesta versao — podem divergir do catalogo.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** models `Processo`, `Setor`, `SetorStatus` (`apps.escolas`); campo `processo` (FK opcional) adicionado a `RedeExterna`/`RedeInterna`; tela em `apps.core_admin`, secao Administracao. Ver ADR-014.
**Features relacionadas:** PO-050, RN-023, ADR-012, ADR-014.
**Status:** Ativa

### RN-026 - Setor e Status de RE/RI editaveis no grid, com Processo escolhido em cascata
**Descricao:** No grid de Enderecos Lastmile, a linha expandida de RE e a de RI passam a permitir editar Processo, Setor e Status do processo interno (`RedeExterna`/`RedeInterna`, RN-023), em cascata: o Setor mostra somente opcoes do Processo escolhido, e o Status mostra somente opcoes do Setor escolhido. Se a escola ainda nao tiver um `RedeExterna`/`RedeInterna`, ele e criado ao salvar. A referencia somente-leitura da API (RN-024) nao muda e nao se mistura com este processo interno.
**Contexto:** Usuario pediu para editar Setor no grid porque precisa mudar o status do RE/RI e move-lo entre setores. Confirmou que Setor e Status ficam editaveis juntos, usando o catalogo Processo/Setor/Status (RN-025), e que a propria tela deixa escolher o Processo tambem, sem exigir passo previo no Admin.
**Criterios:**
- `RedeExterna.setor`/`status` e `RedeInterna.setor`/`status` passam a ser `ForeignKey` para `Setor`/`SetorStatus` (antes texto livre, RN-023) — integridade validada: setor deve pertencer ao processo escolhido, status deve pertencer ao setor escolhido;
- edicao em cascata: Processo → Setor (do processo) → Status (do setor);
- salvar sem `RedeExterna`/`RedeInterna` existente para aquela escola cria o registro;
- `Parceiro` nao entra nesta edicao (fora de escopo, RN-023 continua so editavel pelo Admin);
- a referencia da API (RN-024) continua somente leitura, exibida como esta;
- **revogado parcialmente pela RN-035 (2026-08-10):** no grid global de Enderecos Lastmile (sem `setor_atual`), a edicao de Status deixou de existir — somente Setor continua editavel ali. A cascata Setor→Status descrita nesta regra continua valendo integralmente na Tela de Setor (RN-027/RN-028), com a restricao adicional da RN-033.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** migration convertendo `setor`/`status` de `CharField` para `ForeignKey` (sem dado real a perder — 0 registros hoje); views/endpoints HTMX para cascata Processo→Setor→Status; atualizar `apps/escolas/admin.py` (list_filter/search_fields dos campos que mudaram de tipo). Ver ADR-015.
**Features relacionadas:** PO-051, RN-023, RN-025, RN-035, ADR-012, ADR-014, ADR-015.
**Status:** Ativa

### RN-027 - Visao por Setor das atividades de RE e RI
**Descricao:** Cada nome de Setor cadastrado (RN-025) tem sua propria tela, acessivel por um item de menu dedicado ("Setores"), mostrando um grid com todo `RedeExterna`/`RedeInterna` (RN-023) vinculado a um `Setor` com aquele nome — em qualquer Processo. Somente visualizacao nesta versao.
**Contexto:** Usuario pediu que cada Setor (ex.: "Suprimentos") tenha um ambiente proprio mostrando as atividades de RE/RI que estao com ele, para quem trabalha naquele Setor nao precisar abrir a lista completa de escolas. Como o mesmo nome de Setor existe cadastrado tanto no Processo de RE quanto no de RI (RN-025, espelhado de proposito), a visao agrupa por nome, cruzando os dois Processos.
**Criterios:**
- item de menu "Setores", com um link por nome de Setor cadastrado (dinamico, vem do banco);
- tela por Setor mostra RE e RI (tipo, escola, status, parceiro) vinculados a qualquer `Setor` com aquele nome;
- somente leitura — editar Setor/Status continua sendo feito em Enderecos Lastmile (RN-026), nao nesta tela;
- mesma permissao de acesso que Enderecos Lastmile hoje (grupo LastMile ou superuser) — sem restricao por time/Setor especifico nesta versao.
- **substituido pela RN-054/RN-055 (2026-08-13):** a permissao deste modulo deixa de depender do grupo LastMile e passa a ter grupo proprio (`Setor`), com restricao adicional por nome de Setor individual por usuario — resolve a pendencia que a propria ADR-016 ja registrava ("restringir cada tela de Setor a um grupo/time especifico de usuarios").
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** novas views/URLs/templates em `apps.leads`; item de menu dinamico via context processor. Nenhum model novo. Ver ADR-016.
**Features relacionadas:** PO-052, RN-023, RN-025, RN-026, RN-054, RN-055, ADR-015, ADR-016.
**Status:** Ativa

### RN-028 - Tela de Setor mostra Escola completa e permite editar Setor/Status
**Descricao:** A tela de um Setor (RN-027) reaproveita o mesmo grid da tela global de Enderecos Lastmile (Escola com INEP/Estado/Municipio/Endereco), filtrado para mostrar so as escolas com RE ou RI vinculado a aquele Setor. Mostra a linha de RE quando o RE daquela escola estiver naquele Setor, a linha de RI quando o RI estiver, ou as duas quando ambas estiverem. A edicao de Setor/Status (RN-026) fica disponivel nesta tela tambem.
**Contexto:** Usuario apontou que a versao anterior (lista simples Tipo/Escola/Status/Parceiro, RN-027) perdia informacao (INEP, Estado, Municipio, Endereco). Pediu para reaproveitar a mesma visao de Escola que a tela global ja tem. Confirmado tambem que a edicao deve ficar disponivel aqui, revogando a restricao de somente-leitura da RN-027/ADR-016.
**Criterios:**
- filtro de escolas usa `Q(rede_externa__setor__nome=X) | Q(rede_interna__setor__nome=X)`, mantendo busca/ordenacao existentes;
- linha de RE aparece somente se `rede_externa.setor.nome == nome do Setor da tela`; idem para RI — nunca as duas fixas incondicionalmente (isso e exclusivo do grid global, que continua mostrando as duas sempre);
- edicao de Setor/Status (cascata, RN-026) habilitada nesta tela, mesma permissao (`grupo_LastMile_required`) — sem controle novo;
- um unico template atende a tela global e a tela de Setor — mudanca visual futura vale para as duas.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `filtrar_escolas_lastmile` ganha parametro opcional `setor_nome`; `enderecos_lastmile.html` recebe `setor_atual` para decidir quais linhas de RE/RI mostrar e ajustar titulo/subtitulo; view/template dedicados da RN-027 (lista simples) saem de uso. Ver ADR-017.
**Features relacionadas:** PO-053, RN-023, RN-025, RN-026, RN-027, ADR-016, ADR-017.
**Status:** Ativa

### RN-029 - Historico e anexo individuais de RE e RI, com visao combinada na Escola
**Descricao:** Cada processo de Rede Externa (RE) e Rede Interna (RI) de uma Escola (RN-023) passa a ter historico e anexo proprios, reaproveitando o model generico `RegistroHistorico` (ja usado em Partner/Proposal). O historico registra comentario manual, anexo e alteracao de setor/status/parceiro feita pela tela de edicao. A Escola (registro "pai" dos dois processos) pode ver o historico combinado de RE e RI.
**Contexto:** Usuario pediu em 2026-08-10 anexo individual por processo e historico separado para RE e RI, contemplando alteracao de dados, comentarios, alteracao de status e anexos, com a Escola vendo o historico dos dois. Confirmado que a exibicao acontece no proprio grid de Enderecos Lastmile, via botao de historico que abre um modal (layout vertical); e que o log automatico de alteracao de dados cobre somente edicoes feitas pela tela (`escola_rede_editar`), nao pelo Django Admin.
**Criterios:**
- RE e RI passam a ter historico via `RegistroHistorico`/`GenericForeignKey`, um registro por instancia (`content_type` + `object_id`) — mesmo padrao ja usado por Partner/Proposal;
- anexo (`RegistroHistorico.arquivo`) e individual por processo: arquivo anexado ao RE de uma escola nao aparece no historico do RI da mesma escola, e vice-versa;
- toda alteracao de `setor`, `status` ou `parceiro` feita pela tela (`escola_rede_editar`) gera um `RegistroHistorico` tipo `sistema`, com valor anterior e novo (mesmo padrao "Antes/Depois" ja usado em `apps/partners/services.py`); edicao feita direto no Django Admin nao gera esse log;
- **ampliado pela RN-040 (2026-08-11):** alteracao de valor de Campo personalizado (RN-031/032, qualquer Setor) tambem passa a gerar `RegistroHistorico`, mesmo padrao aqui descrito;
- usuario pode adicionar comentario manual (tipo `comentario`) e anexo (tipo `anexo`) pelo mesmo modal;
- botao de historico no RE abre modal mostrando somente o historico do RE; botao no RI, somente o do RI;
- a linha da Escola tem botao proprio que abre um modal combinado com as entradas de RE e RI juntas, identificando de qual processo cada entrada veio;
- mesma permissao que ja protege a edicao de RE/RI no grid (`grupo_LastMile_required`).
**Excecoes:** nenhuma.
**Impacto tecnico:** reaproveita `apps.core.models.RegistroHistorico`; views/services novos em `apps.leads` para listar/criar historico de RE/RI e para o modal combinado da Escola; templates novos (modal), reaproveitando o padrao visual de `core/templates/core/timeline_global.html` (PO-039). Nenhum model novo.
**Features relacionadas:** PO-054, RN-023, RN-026.
**Status:** Ativa

### RN-030 - Parceiro de RE/RI editavel somente no Setor Lastmile, via modal de selecao
**Descricao:** Parceiro (`RedeExterna.parceiro`/`RedeInterna.parceiro`, RN-023) passa a ser editavel no grid de Enderecos Lastmile, mas somente quando o RE/RI esta sendo visualizado atraves da tela do Setor de negocio "Lastmile" (RN-025/RN-027) — no grid global (sem filtro de Setor) e nas telas dos demais Setores, o campo permanece somente leitura. A edicao abre um modal de selecao de Parceiro (busca por nome, cidade, UF e bairro, reaproveitando a logica ja usada na conversao de Lead em Proposta) em vez de uma lista suspensa.
**Contexto:** Usuario identificou, em 2026-08-10, que hoje e possivel vincular um Parceiro a um RE/RI somente pelo Django Admin (pendencia da RN-026/ADR-015), e que cada RE e RI pode ter um Parceiro diferente. Pediu que apenas o setor de Lastmile possa fazer esse vinculo. Perguntado, confirmou que "setor de Lastmile" e o Setor de negocio do catalogo (RN-025), nao o grupo de permissao Django que ja protege a tela inteira; e que, apesar de acreditar que ja existia um modal pronto para isso, nao ha um — deve ser criado um novo, reaproveitando a busca de parceiros ja usada na conversao de Lead (ADR-018).
**Criterios:**
- campo Parceiro fica editavel na linha expandida de RE/RI (RN-024/RN-026) somente quando a tela atual for a do Setor "Lastmile" (`setor_atual == "Lastmile"`) — condicao fixa, independente de qual Setor o RE/RI esta atualmente vinculado;
- no grid global e nas telas dos demais Setores (Suprimentos, Implantacao, Pos venda, Suporte), o campo Parceiro e somente leitura;
- editar abre um modal (mesmo padrao visual dos modais ja existentes no grid, ex. historico) com busca de Parceiros por nome, cidade, UF e bairro; selecionar um parceiro preenche o campo na linha, sem salvar ainda;
- salvar sem `RedeExterna`/`RedeInterna` existente para aquela escola cria o registro (mesmo comportamento ja usado para Setor/Status, RN-026);
- alteracao de Parceiro pela tela gera `RegistroHistorico` com valor anterior/novo (mesmo padrao ja usado para Setor/Status, RN-029); edicao direta no Django Admin nao gera esse log;
- permissao de acesso ao grid continua a mesma ja existente (`grupo_LastMile_required`) — a restricao por Setor "Lastmile" e adicional, nao substitui essa permissao.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** view `escola_rede_editar` (`apps/leads/views.py`) ganha validacao adicional (bloquear alteracao de parceiro quando `setor_atual != "Lastmile"`); novo endpoint/modal de busca de Parceiro reaproveitando parte da logica de `endereco_lastmile_partner_search`; `escola_rede_row.html` ganha bloco condicional para o campo Parceiro. Ver ADR-018.
**Features relacionadas:** PO-056, RN-023, RN-025, RN-026, RN-029, ADR-015, ADR-018.
**Status:** Ativa

### RN-031 - Cadastro de Campos personalizados por Setor
**Descricao:** Tela "Campos", na Administracao, permite cadastrar campos dinamicos: nome, tipo (Texto curto, Numero, Data, Sim/Nao ou Lista) e o Setor dono (pelo nome do Setor, RN-025). Quando o tipo for Lista, o cadastro tambem pede as opcoes validas, digitadas. Um Campo pertence a um unico Setor (por nome); um mesmo Setor pode ter varios Campos.
**Contexto:** Usuario pediu, em 2026-08-10, reduzir a quantidade de informacao direto no grid de Enderecos Lastmile, criando campos adicionais especificos de cada Setor, cadastraveis pela Administracao. Perguntado, confirmou que o dono do campo e o Setor pelo nome (RN-025) — nao uma linha especifica de Setor de um Processo — para que o mesmo campo valha tanto para RE quanto para RI, e que os tipos do MVP sao Texto curto, Numero, Data, Sim/Nao e Lista.
**Criterios:**
- tipos suportados no MVP: texto curto, numero, data, sim/nao e lista;
- tipo lista exige pelo menos uma opcao cadastrada; as demais opcoes de tipo nao usam esse campo;
- Setor dono e escolhido pelo nome (mesmo vocabulario de `Setor.nome`, RN-025) — nao por uma linha especifica de Setor de um Processo; um Campo do Setor "Suprimentos" vale tanto para RE quanto para RI;
- nesta primeira versao, a tela permite somente listar e criar (mesmo padrao inicial da PO-050) — sem editar nem excluir;
- tela restrita ao grupo Administrador, mesma permissao da tela de Processos.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** novo model `Campo` em `apps.escolas` (`nome`, `tipo`, `setor_nome`, `opcoes`); tela nova em `apps.core_admin`, secao Administracao. Ver ADR-019.
**Features relacionadas:** PO-057, RN-025, ADR-019.
**Status:** Ativa

### RN-032 - Modal de Campos personalizados no grid de Enderecos Lastmile, agrupados e editaveis por Setor
**Descricao:** RE e RI ganham um botao que abre um modal listando os Campos cadastrados (RN-031), agrupados por Setor dono. O grupo do Setor da tela atual (`setor_atual`) aparece expandido; os grupos dos demais Setores aparecem recolhidos, abrindo somente se a pessoa clicar. Dentro de cada grupo, so os campos cujo Setor dono e igual a `setor_atual` ficam editaveis — os demais aparecem somente leitura.
**Contexto:** Usuario pediu reduzir a quantidade de informacao direto na linha do grid, movendo campos adicionais para dentro de um modal, com visibilidade cruzada entre Setores mas edicao restrita a cada dono. Confirmado que os campos ja existentes (Setor, Status RN-026; Parceiro RN-030) continuam como estao, fora do modal — o modal e so para os campos novos cadastrados em "Campos" (RN-031). Confirmado tambem que a regra de edicao reaproveita a mesma logica ja usada no Parceiro (RN-030): a tela atual (`setor_atual`) decide o que e editavel, sem vincular usuario a um Setor.
**Criterios:**
- botao na linha expandida de RE e de RI abre um modal com os Campos (RN-031) aplicaveis aquele tipo de processo;
- campos agrupados por Setor dono (nome); grupo do Setor atual (`setor_atual`) vem expandido, os demais recolhidos por padrao;
- edicao habilitada somente nos campos cujo Setor dono e igual a `setor_atual`; os demais mostram o valor, somente leitura;
- no grid global (sem `setor_atual`) e nas telas de Setor diferentes do dono de cada campo, todos os campos aparecem somente leitura;
- salvar grava em `CampoValor`, vinculado a instancia de `RedeExterna`/`RedeInterna` (RN-023) e ao `Campo`;
- valor validado conforme o tipo do Campo (ex.: lista so aceita uma das opcoes cadastradas).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** novo model `CampoValor` (`GenericForeignKey` para `RedeExterna`/`RedeInterna`, mesmo padrao de `RegistroHistorico`); view/endpoint de modal e de salvar; template novo, reaproveitando o padrao visual dos modais ja existentes no grid. Ver ADR-019.
**Features relacionadas:** PO-058, RN-023, RN-025, RN-030, RN-031, ADR-019.
**Status:** Ativa

### RN-033 - Status de RE/RI editavel somente pelo Setor atual; troca de Setor define Status como "Aguardando" automaticamente
**Descricao:** Na edicao de Setor/Status de RE/RI feita pela Tela de Setor (RN-027/RN-028), o campo Status (RN-026) fica editavel somente enquanto o Setor selecionado na cascata continuar sendo igual ao Setor da tela atual (`setor_atual`). Ao mudar o Setor selecionado para um Setor diferente do `setor_atual` — enviando a subatividade (RE ou RI) para outro Setor — o campo Status fica desabilitado (somente leitura) e o valor salvo passa a ser, automaticamente, o Status "Aguardando" do Setor de destino, descartando qualquer Status escolhido manualmente antes da troca. Se o Setor de destino ainda nao tiver um Status "Aguardando" cadastrado, o sistema cria esse Status para ele no momento da troca.
**Contexto:** Usuario identificou, em 2026-08-10, que hoje e possivel editar o Status de um RE/RI para qualquer Setor a partir da Tela de Setor, mesmo quando o Setor selecionado deixa de ser o Setor da tela atual — permitindo que uma equipe defina o status de um processo que ja nao e mais dela. Pediu para travar a edicao de Status quando o Setor selecionado for diferente do Setor atual (cada Setor so decide o status do que esta com ele) e para o Status ir automaticamente para "Aguardando" sempre que a subatividade for enviada a outro Setor. Perguntado sobre o Status "Aguardando" nao existir ainda para o Setor de destino, confirmou criacao automatica; perguntado sobre o alcance da trava, confirmou que vale somente nas Telas de Setor — o grid global de Enderecos Lastmile (sem `setor_atual`) manteve o Status livremente editavel como definido pela RN-026, ate a RN-035 (2026-08-10) revogar essa edicao no grid global.
**Criterios:**
- regra vale para a edicao feita pela Tela de Setor (`setor_atual` definido, RN-027/RN-028); no grid global de Enderecos Lastmile (sem `setor_atual`), a edicao de Status foi revogada pela RN-035 (2026-08-10) — Status passa a ser sempre "Novo", sem escolha manual;
- enquanto o Setor selecionado na cascata (RN-026) for igual ao `setor_atual`, o campo Status continua editavel normalmente, com as opcoes daquele Setor;
- ao selecionar um Setor diferente do `setor_atual`, o campo Status fica desabilitado na tela; ao salvar, recebe automaticamente o Status "Aguardando" do novo Setor, descartando qualquer Status escolhido antes da troca;
- se o Setor de destino nao tiver um Status "Aguardando" cadastrado, o sistema cria esse `SetorStatus` (`nome="Aguardando"`) para ele antes de aplicar a troca;
- alteracao de Setor/Status continua gerando `RegistroHistorico` (RN-029), com o valor "Aguardando" ja refletido como novo status.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** view/endpoint da cascata Setor->Status (`escola_rede_editar`, RN-026) ganha validacao para ignorar/sobrescrever o Status enviado quando `setor != setor_atual`, aplicando `SetorStatus.objects.get_or_create(setor=setor_destino, nome="Aguardando")`; `escola_rede_row.html` desabilita o campo Status via JS/HTMX quando o Setor selecionado difere do `setor_atual`.
**Features relacionadas:** PO-051 (ainda em Aguardando QA — emenda registrada antes da revisao), RN-023, RN-025, RN-026, RN-027, RN-028, RN-029.
**Status:** Ativa

### RN-034 - Exclusao de Status do catalogo de Processos, por Setor
**Descricao:** Na tela de gestao de Processos (RN-025), cada Status cadastrado em um Setor passa a poder ser excluido individualmente, a partir da tela de detalhe daquele Setor. Setor e Processo continuam sem exclusao (RN-025). Ao excluir um Status em uso por algum RedeExterna/RedeInterna, o campo `status` desses registros fica em branco — comportamento ja suportado pelo `on_delete=SET_NULL` definido na RN-026, sem necessidade de nova migracao.
**Contexto:** Usuario pediu, em 2026-08-10, uma rota para excluir Status dentro de um Setor, revogando parcialmente a restricao "sem editar nem excluir" da RN-025 (somente para Status; Setor e Processo continuam sem exclusao). Perguntado sobre o comportamento quando o Status excluido estiver em uso, confirmou permitir a exclusao e deixar o campo em branco nos RE/RI afetados, aproveitando o `SET_NULL` ja existente.
**Criterios:**
- exclusao por Status individual, disponivel na tela de detalhe do Setor, respeitando a hierarquia Processo -> Setor -> Status;
- exclusao exige confirmacao explicita do usuario antes de efetivar;
- RedeExterna/RedeInterna que referenciavam o Status excluido ficam com `status` nulo (mesmo comportamento de `on_delete=SET_NULL` ja definido na RN-026) — nenhum registro de RE/RI e apagado;
- exclusao de Status nao gera novo `RegistroHistorico` (RN-029) nos RE/RI afetados — e limpeza de catalogo, nao edicao feita pela tela de RE/RI;
- Setor e Processo continuam sem exclusao nesta versao (pendencia da RN-025/ADR-014 permanece aberta para esses dois niveis);
- mesma permissao da tela de Processos (grupo Administrador).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** nova view/endpoint em `apps.core_admin` para exclusao de `SetorStatus`, aninhada em Processo/Setor; atualizar template de detalhe do Setor com acao de exclusao; nenhuma migracao necessaria (FK ja e `SET_NULL`). Ver ADR-020.
**Features relacionadas:** PO-059, RN-025, RN-026, ADR-014, ADR-020.
**Status:** Ativa

### RN-035 - Status de RE/RI deixa de ser editavel no grid global de Enderecos Lastmile; passa a ser fixo em "Novo"
**Descricao:** No grid global de Enderecos Lastmile (menu Projeto → Endereços, fora da Tela de Setor — sem `setor_atual`), a linha expandida de RE e a de RI deixam de permitir edicao de Status. Somente Setor continua editavel nessa tela. O Status exibido passa a ser sempre "Novo" (do Setor atual do RE/RI), sem escolha manual, e nao muda mesmo quando o Setor e alterado.
**Contexto:** Usuario identificou, em 2026-08-10, que a RN-026 permite editar Setor e Status juntos no grid global, mas isso nao deveria valer para o Status: no grid global, so o Setor deve ser editavel, e o Status deve permanecer sempre "Novo" (status inicial), sem escolha manual. Perguntado sobre o alcance, confirmou que a mudanca vale somente para o grid global — a Tela de Setor (RN-027/RN-028) continua exatamente como a RN-033 ja define, usando "Aguardando" quando o Setor muda.
**Criterios:**
- no grid global de Enderecos Lastmile (sem `setor_atual`), a linha expandida de RE/RI perde o campo de edicao de Status — a cascata da RN-026 passa a ter somente Setor nesse contexto;
- o Status exibido (somente leitura) nesse contexto e sempre "Novo" do Setor atual do RE/RI, mesmo apos trocar de Setor;
- se o Setor atual (ou o de destino, ao trocar) ainda nao tiver um Status "Novo" cadastrado, o sistema cria esse `SetorStatus` (`nome="Novo"`) automaticamente — mesmo padrao ja usado para "Aguardando" na RN-033;
- salvar sem `RedeExterna`/`RedeInterna` existente para aquela escola continua criando o registro (mesmo comportamento da RN-026), ja com Status "Novo";
- a Tela de Setor (RN-027/RN-028) nao e afetada por esta regra — continua com a edicao de Status definida pela RN-033 (trava fora do Setor atual, "Aguardando" ao mudar de Setor).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `escola_rede_row.html`/`escola_rede_editar` (`apps.leads`) deixam de expor o campo Status na cascata quando nao ha `setor_atual` (grid global); a view passa a aplicar `SetorStatus.objects.get_or_create(setor=<setor atual do registro>, nome="Novo")` ao salvar nesse contexto, ignorando qualquer Status recebido. Revisa parcialmente a RN-026 (grid global deixa de ter Status na cascata) e o texto da RN-033 (que descrevia o grid global como Status "livremente editavel"). **Pendencia de implementacao:** PO-051 esta em Aguardando QA com o comportamento antigo (Status livre no grid global) — precisa de ajuste do Dev antes do QA avaliar.
**Features relacionadas:** PO-051, RN-023, RN-025, RN-026, RN-033.
**Status:** Ativa

### RN-036 - Edicao e exclusao de Campos personalizados por Setor
**Descricao:** A tela "Campos" (Administracao, RN-031) ganha rotas de editar e excluir um Campo cadastrado, alem de listar e criar.
**Contexto:** Usuario pediu, em 2026-08-10, as rotas de editar e excluir para a tela de Campos, resolvendo a pendencia "fase 2" deixada pela ADR-019/RN-031. Perguntado, confirmou: exclusao de um Campo com `CampoValor` (PO-058) gravados exige confirmacao explicita informando os valores que serao perdidos e exclui em cascata; edicao pode trocar o tipo do Campo livremente mesmo havendo `CampoValor` gravados, sem bloqueio nem limpeza automatica dos valores existentes.
**Criterios:**
- edicao permite alterar nome, tipo, setor_nome e opcoes (quando tipo=lista) de um Campo ja cadastrado;
- trocar o tipo de um Campo com `CampoValor` gravados e permitido sem bloqueio nem limpeza automatica — valor que ficar incompativel com o novo tipo e responsabilidade de quem edita;
- exclusao de um Campo exige confirmacao explicita, informando quantos `CampoValor` serao perdidos;
- confirmada a exclusao, o Campo e todos os `CampoValor` vinculados a ele sao apagados em cascata;
- mesma permissao das demais operacoes da tela (grupo Administrador, RN-031).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** rotas `campo_editar` e `campo_excluir` em `apps.core_admin`; exclusao ja e coberta pelo `on_delete=models.CASCADE` existente em `CampoValor.campo` (`apps/escolas/models.py`) — sem migracao nova. Ver ADR-021.
**Features relacionadas:** PO-060, RN-031, RN-032, ADR-021.
**Status:** Ativa

### RN-037 - Setor como catalogo global de exibicao, com escopo entre Escola e RE/RI
**Descricao:** Cada Setor (RN-025) passa a ter uma tela propria na Administracao ("Setor"), separada de "Processos" e "Campos", onde o usuario gerencia o Setor e escolhe o escopo de exibicao das suas informacoes (Campos, RN-031) no sistema: Atividade principal (Escola) ou Sub-atividades (RE/RI). Quando o escopo for Sub-atividades, o usuario ainda escolhe se vale para RE, para RI, ou para as duas.
**Contexto:** Usuario identificou, em 2026-08-10, que os Campos personalizados (RN-031) so existem vinculados a RE e RI (RN-032), mas parte da informacao pertence direto ao cliente (Escola), nao a um processo interno. Pediu uma tela nova "Setor" na Administracao para tratar o Setor como catalogo global, escolhendo onde a informacao de cada Setor aparece. Perguntado, confirmou: e uma tela nova, separada de Processos e Campos; e o mesmo Setor ja cadastrado (RN-025), nao uma entidade nova; os Campos ja existentes recebem escopo padrao "Sub-atividades: RE e RI", preservando o comportamento atual; a escolha entre Escola e Sub-atividades e exclusiva, e dentro de Sub-atividades ainda se escolhe RE, RI ou ambas.
**Criterios:**
- nova tela "Setor" na Administracao, mesma secao e permissao de Processos/Campos (grupo Administrador);
- cada Setor (por nome, RN-025) ganha um escopo com duas opcoes mutuamente exclusivas: "Atividade principal (Escola)" ou "Sub-atividades (RE/RI)";
- quando o escopo for "Sub-atividades", uma segunda escolha define se vale para RE, para RI, ou para as duas;
- Campos (RN-031) ja cadastrados recebem escopo padrao "Sub-atividades: RE e RI" automaticamente, sem exigir edicao manual;
- quando o escopo de um Setor for "Escola", os Campos daquele Setor passam a ser exibidos/editaveis vinculados a Escola, em vez de a RE/RI — mesmo mecanismo de campo dinamico ja usado hoje (RN-031/032), mudando so o alvo do valor;
- quando o escopo for "Sub-atividades", o comportamento atual (RN-032) continua valendo, restrito a RE, a RI, ou a ambas, conforme a escolha.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** novo model `SetorEscopo` em `apps.escolas` (`setor_nome`, `atividade`, `aplica_re`, `aplica_ri`); `CampoValor.content_object` passa a aceitar `Escola` como terceiro alvo possivel, alem de `RedeExterna`/`RedeInterna`; migracao de dados cria escopo padrao "Sub-atividades: RE e RI" para os Setores ja usados por Campo hoje. Ver ADR-022.
**Features relacionadas:** PO-062, RN-025, RN-031, RN-032, ADR-014, ADR-019, ADR-022.
**Status:** Substituida pela RN-038 — entendimento inicial estava errado (ver RN-038).

### RN-038 - Setor informativo com campos fixos, exibidos somente leitura em Escola e/ou RE/RI
**Descricao:** Nova tela "Setor" na Administracao, independente do Setor do catalogo de Processos (RN-025): o usuario cria um Setor informativo (so o nome, sem vincular a Processo) e cadastra Campos informativos dentro dele (nome e valor fixo — o mesmo valor para qualquer Escola, nao varia por instancia). Para cada Setor informativo, o usuario marca em quais lugares os campos dele aparecem: Escola, Rede Externa (RE), Rede Interna (RI) — podendo marcar um, dois ou os tres ao mesmo tempo, sem exclusividade entre eles. Os campos aparecem somente como visualizacao (somente leitura) em todos os lugares marcados — nunca editaveis pela pessoa que esta vendo a Escola/RE/RI.
**Contexto:** RN-037/ADR-022 foram desenhadas com um entendimento errado, corrigido pelo usuario em 2026-08-10 depois de ver a tela construida pelo Dev. Nas proprias palavras do usuario: "Eu só pedi um setor e adicionar uns campos nesse setor e esses campos aparecer como apenas visualização e eu definir se quero que apareça na escola, na RE ou RI ou os dois ou os 3, só isso"; ao ver o modal de Campos ja existente no grid de Enderecos Lastmile (RN-032), confirmou que os campos do Setor informativo devem aparecer dentro desse mesmo modal, como mais um grupo, sempre somente leitura; perguntado se o valor varia por escola, confirmou que e fixo, igual para qualquer escola — descartando a necessidade de um valor por instancia (diferente do que RN-031/032 fazem para `Campo`/`CampoValor`).
**Criterios:**
- nova tela "Setor" na Administracao (mesma permissao das demais telas, grupo Administrador), independente da tela "Processos" (RN-025) e da tela "Campos" (RN-031) — sem exigir Processo para criar;
- ao criar o Setor informativo, o usuario tambem cadastra os Campos informativos dele (nome e valor) na mesma tela;
- cada Setor informativo tem tres marcacoes independentes (nao exclusivas) de onde aparece: Escola, RE, RI — pelo menos uma marcada;
- os Campos informativos de um Setor aparecem em todos os lugares marcados: no modal de Campos ja existente (RN-032) quando RE e/ou RI estiver marcado, como mais um grupo somente leitura ao lado dos grupos de `Campo` (RN-031); em um local equivalente na Escola quando "Escola" estiver marcado;
- em nenhum lugar esses campos sao editaveis — sempre somente leitura, independente de setor_atual ou de quem esta vendo;
- o valor de um Campo informativo e fixo por cadastro — o mesmo valor aparece em qualquer Escola/RE/RI onde o Setor informativo estiver marcado para aparecer; nao ha valor por instancia.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** ver ADR-023 (substitui a ADR-022).
**Features relacionadas:** PO-062, RN-025, RN-031, RN-032, ADR-023.
**Status:** Ativa

### RN-039 - Campo condicionado a Status e Campo calculado, no cadastro de Campos personalizados por Setor
**Descricao:** O cadastro de Campos (RN-031) ganha duas capacidades novas, genericas para qualquer Setor: (1) um Campo pode receber um Status condicionante (pelo nome, mesmo vocabulario do catalogo de Processos, RN-025) — quando preenchido, o Campo so aparece no modal de Campos (RN-032) quando o Status atual do RE/RI exibido tiver esse mesmo nome; (2) um novo tipo de Campo, "Calculado", cujo valor nao e digitado — e somado automaticamente a partir de outro Campo do mesmo Setor, do tipo Data (o "Campo base"), acrescentando um numero fixo de horas (convertidas em dias corridos). Campo calculado e sempre somente leitura, em qualquer Setor e qualquer tela.
**Contexto:** Usuario pediu, em 2026-08-11, que no Setor "Implantacao" (RN-025), ao definir o Status "Agendando Parceiro" em um RE/RI, apareca um campo "Inicio Implantacao" para informar a data combinada com o parceiro, e que o sistema calcule automaticamente, 72 horas depois, um campo "Data Final Implantacao", somente visual e nao editavel. Perguntado se esse recurso deveria ser generico (reutilizavel por outros Setores/Status no futuro, pela propria tela Campos) ou especifico so para este caso, confirmou o mecanismo generico. Perguntado sobre a precisao do campo Inicio Implantacao, confirmou somente data (dia) — as 72 horas viram 3 dias corridos a partir do dia informado.
**Criterios:**
- tela "Campos" (RN-031) ganha um campo opcional "Status condicionante" (texto, mesmo vocabulario de `SetorStatus.nome`) no cadastro de qualquer Campo, independente do tipo;
- quando um Campo tem Status condicionante preenchido, ele so aparece no modal de Campos (RN-032) — dentro do grupo do respectivo Setor dono — quando o Status atual do RE/RI (RN-026) tiver o mesmo nome; caso contrario o campo nao aparece (nem como somente leitura); Campo sem Status condicionante mantem o comportamento atual (RN-032), sempre visivel dentro do grupo do seu Setor;
- novo tipo de Campo "Calculado" nas opcoes de tipo (RN-031), disponivel junto com Texto curto/Numero/Data/Sim-Nao/Lista;
- Campo do tipo Calculado exige, no cadastro, um "Campo base" (outro Campo ja cadastrado, do mesmo Setor dono, obrigatoriamente do tipo Data) e "Horas de prazo" (numero inteiro positivo);
- o valor de um Campo calculado nunca e digitado nem gravado em `CampoValor` — e obtido em tempo de exibicao, somando ao valor atual do Campo base (quando preenchido) a quantidade de dias corridos equivalente as Horas de prazo (arredondado para cima quando nao for multiplo exato de 24); quando o Campo base ainda nao tem valor, o Campo calculado aparece em branco;
- Campo calculado e sempre somente leitura no modal (RN-032), em qualquer Setor e qualquer tela, mesmo quando o Setor dono e igual a `setor_atual`;
- uso concreto desta entrega: cadastrar, pela tela Campos, o Campo "Inicio Implantacao" (Setor "Implantacao", tipo Data, Status condicionante "Agendando Parceiro") e o Campo "Data Final Implantacao" (Setor "Implantacao", tipo Calculado, Campo base = "Inicio Implantacao", Horas de prazo = 72) — cadastro feito depois da entrega do Dev, nao faz parte do codigo;
- criar o Status "Agendando Parceiro" nos Processos de Rede Externa e Rede Interna, dentro do Setor "Implantacao", usa a tela ja existente de criacao de Status (RN-034) — nao e codigo novo desta regra.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `Campo` (`apps.escolas`) ganha `status_condicionante_nome` (CharField opcional), `campo_base` (FK para `Campo`, opcional, usado so quando tipo=calculado) e `horas_prazo` (IntegerField, opcional, usado so quando tipo=calculado); validacao em `clean()` exige campo_base do tipo Data e do mesmo `setor_nome` quando tipo=calculado; view/servico do modal de Campos (RN-032, `apps/leads/services.py`) passa a filtrar por `status_condicionante_nome` e a calcular o valor exibido de Campos tipo calculado sem consultar `CampoValor`. Ver ADR-024.
**Features relacionadas:** PO-063, RN-025, RN-026, RN-031, RN-032, RN-034, RN-036, ADR-024.
**Status:** Ativa

### RN-040 - Alteracao de Campo personalizado gera historico, com o valor calculado embutido no registro do Campo base
**Descricao:** Alteracao de valor de Campo personalizado (RN-031/032), feita pela tela (modal de Campos), passa a gerar um `RegistroHistorico` tipo `sistema` com valor anterior e novo — mesmo padrao ja usado para Setor/Status/Parceiro (RN-029). Vale para qualquer Campo, de qualquer Setor, nao somente os de Implantacao (RN-039). Como um Campo do tipo Calculado (RN-039) nunca e salvo em `CampoValor` — e sempre derivado ao vivo —, ele nao gera log proprio; quando o Campo base de um Calculado e alterado, o registro de historico dessa alteracao tambem traz o valor calculado resultante (ex.: Data Final Implantacao), calculado no momento do registro, para quem le o historico ver os dois valores juntos.
**Contexto:** Usuario pediu, em 2026-08-11, que "Inicio Implantacao" e "Data Final Implantacao" (RN-039) fiquem registrados no historico. Como o historico hoje (RN-029) so cobre Setor/Status/Parceiro — Campo personalizado (RN-031/032) nao gera log —, e como "Data Final Implantacao" nunca e salva (e calculada, ADR-024), a extensao precisa cobrir os dois casos. Perguntado se o log deveria valer so para os campos de Implantacao ou para qualquer Campo, confirmou o alcance generico (qualquer Setor).
**Criterios:**
- toda alteracao de `CampoValor` feita pela tela (modal de Campos no grid de Enderecos Lastmile ou na Escola, RN-032/037/038) gera um `RegistroHistorico` tipo `sistema`, com valor anterior e novo (RN-029, "Antes/Depois");
- alteracao feita direto no Django Admin nao gera esse log (mesmo padrao ja usado, RN-029);
- criacao do primeiro valor de um Campo (sem `CampoValor` anterior) registra "anterior: (vazio)";
- quando o Campo alterado for `campo_base` de algum Campo tipo Calculado (RN-039) do mesmo Setor, o mesmo registro de historico tambem traz `nome do Campo calculado: valor calculado resultante`, computado com a regra da RN-039 no momento do registro — nao cria um `RegistroHistorico` separado para o Calculado, que continua sem `CampoValor` proprio;
- Campo tipo Calculado nunca gera `RegistroHistorico` por conta propria (nao ha alteracao direta a registrar);
- historico de RE/RI e de Escola exibem essas entradas junto com as demais (Setor/Status/Parceiro, RN-029), na mesma ordem cronologica, sem modal separado.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `salvar_campos_rede`/`salvar_campos_escola` (`apps/leads/services.py`, RN-032/037/038) passam a comparar valor anterior/novo de cada `CampoValor` salvo e criar `RegistroHistorico` (reaproveita `GenericForeignKey` ja usado por RN-029); ao salvar um Campo que e `campo_base` de algum Calculado, o servico busca os Calculados dependentes (`Campo.objects.filter(campo_base=...)`) e inclui o valor calculado na mesma entrada.
**Features relacionadas:** PO-064, RN-029, RN-031, RN-032, RN-039, ADR-024.
**Status:** Ativa

### RN-041 - Historico do sistema registra Setor atual e valor anterior/novo de forma estruturada (De/Para)
**Descricao:** Todo registro de historico tipo `sistema` (RN-029), gerado por alteracao de Setor/Status (RN-026), Parceiro (RN-030) ou Campo personalizado (RN-040), passa a guardar de forma estruturada o rotulo do que mudou (ex.: "Status", "Parceiro", "Inicio Implantacao"), o valor anterior, o valor novo e o nome do Setor em que a tela estava (`setor_atual`) no momento do registro — em vez de somente uma frase de texto livre. O modal de historico (RN-029) exibe essa alteracao como "De/Para" na mesma linha (separado por uma coluna), com data, hora, usuario e Setor numa linha abaixo. O modal tambem aumenta 20% de largura e reduz o espacamento interno entre os blocos de informacao.
**Contexto:** Usuario pediu, em 2026-08-11, que toda alteracao de Campo (RN-040) aparecesse no historico, sugerindo o formato "De/Para" na mesma linha com data/hora/usuario/Setor abaixo, alem de mais largura e menos espaco vazio no modal. Hoje `RegistroHistorico` so guarda uma frase livre em `acao`, sem Setor capturado — o formato pedido nao existe para nenhum tipo de registro ainda. Seguindo o mesmo alcance generico ja adotado nesta sessao (RN-039/RN-040), a estruturacao vale para qualquer registro tipo sistema, nao somente Campo.
**Criterios:**
- `RegistroHistorico` ganha campos estruturados, usados somente pelo tipo `sistema`: rotulo do que mudou, valor anterior, valor novo e nome do Setor (`setor_atual`) no momento do registro;
- toda geracao de log tipo sistema — Setor/Status (RN-026), Parceiro (RN-030) e Campo (RN-040) — passa a preencher esses campos estruturados, em vez de somente uma frase em `acao`;
- registros ja existentes (texto livre em `acao`) continuam sendo exibidos como estao — sem migracao retroativa de dado;
- modal de historico (RN-029) exibe, para cada registro tipo sistema com dado estruturado, o rotulo e "valor anterior → valor novo" na mesma linha (separado por uma coluna), e numa linha abaixo: data, hora, usuario e Setor;
- Setor nao capturado (registro antigo, ou geracao fora de uma tela de Setor) mostra "—", sem quebrar o layout;
- modal aumenta 20% de largura em relacao ao tamanho atual, e reduz o espacamento entre os blocos de informacao (comentario/anexo e cada entrada do historico);
- **quando mais de um campo mudar no mesmo salvamento** (ex.: cascata Setor→Status, RN-026/033/035, onde trocar o Setor tambem muda o Status automaticamente no mesmo clique), o sistema cria um `RegistroHistorico` estruturado **por campo alterado** — um registro para Setor, outro para Status, cada um com seu proprio rotulo e "valor anterior → valor novo" — em vez de um unico registro com frase combinada; todos os registros daquele salvamento compartilham o mesmo instante e o mesmo Setor capturado.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** `RegistroHistorico` (`apps/core/models.py`) ganha `rotulo`, `valor_anterior`, `valor_novo`, `setor_nome` (todos opcionais, usados so quando `tipo=sistema`); pontos de geracao de log das RN-026/030/040 (`apps/leads/services.py`) passam a preencher esses campos; templates do modal de historico (`escola_rede_historico_modal.html`/`escola_historico_modal.html`) reformatados (layout e largura).
**Features relacionadas:** PO-065, RN-026, RN-029, RN-030, RN-040.
**Status:** Ativa

### RN-042 - Envio de e-mail pelo ticket principal (Escola) ou pelos sub-tickets (RE/RI), com log conforme RN-029
**Descricao:** Para efeito de envio de e-mail, a Escola (RN-023) passa a atuar como "ticket principal" e RedeExterna (RE)/RedeInterna (RI) como seus "sub-tickets". O e-mail pode ser enviado a partir da tela da Escola ou a partir da tela de RE/RI. Enviado (e respondido) a partir do RE ou do RI, o envio e a resposta ficam somente no historico individual daquele processo — nao aparecem um no outro. Enviado (e respondido) a partir da Escola, o envio e a resposta ficam no historico da Escola e sao visiveis pelas duas sub-atividades (RE e RI), na mesma visao combinada ja usada pelo modal de historico da Escola.
**Contexto:** Usuario identificou em 2026-08-11 que a opcao de e-mail hoje configurada no sistema precisa se adequar ao layout atual de Escola/RE/RI: log de RE e de RI individuais entre si (mesmo padrao ja estabelecido pela RN-029 para comentario/anexo/historico de sistema), e e-mail enviado pela Escola visivel pelas duas sub-atividades.
**Criterios:**
- log de e-mail segue a mesma regra de visibilidade ja estabelecida pela RN-029: individual por RE, individual por RI, combinado na Escola;
- e-mail enviado a partir do RE (e sua resposta) aparece somente no historico do RE;
- e-mail enviado a partir do RI (e sua resposta) aparece somente no historico do RI;
- e-mail enviado a partir da Escola (e sua resposta) aparece no historico da Escola e e visivel na visao combinada de RE e RI;
- a resposta a um e-mail e correlacionada ao mesmo nivel (Escola, RE ou RI) de onde o e-mail original foi enviado, por um numero de rastreio unico composto por data do dia do envio + INEP da Escola + sufixo do nivel (`RE`, `RI` ou `Global`, sendo `Global` a Escola/ticket principal) — decisao do usuario em 2026-08-11; formato exato de separadores/ordem no assunto do e-mail e a criterio do Dev, mantendo esses tres componentes;
- o mesmo mecanismo de sincronizacao de respostas por e-mail via Microsoft Graph ja usado para cotacao (hoje restrito a `Proposal`, `apps/integracoes/email/sincronizar_respostas_email_cotacao.py`) e reaproveitado, com a mesma caixa/credenciais — sem caixa separada para Escola/RE/RI (decisao do usuario em 2026-08-11); o numero de rastreio evita que um e-mail de cotacao seja confundido com um de Escola/RE/RI ou vice-versa, na mesma caixa compartilhada.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** implementado pelo Dev em 2026-08-11 (PO-066). `RegistroHistorico` **nao** precisou de novo tipo/campo — o envio reaproveita `tipo="sistema"` (mesmo padrao do envio de e-mail da cotacao, `apps/core_admin/quotes_views.py::minhas_cotacoes_enviar_email`), e a visibilidade por nivel usa o `content_type`/`object_id` (GenericForeignKey) ja existente: RE/RI gravam no proprio processo interno, Escola grava em `content_type=Escola`. `apps/leads/services.py::historico_combinado_escola` passou a incluir tambem os registros gravados direto no nivel da Escola (antes so combinava RE+RI) — e exatamente essa tela combinada que atua como "historico da Escola" da RN-029, entao os dois requisitos (aparecer no historico da Escola e na visao combinada) sao satisfeitos pelo mesmo modal, sem tela nova. Numero de rastreio (`apps/core/email_tracking.py`, sem dependencia de model): prefixo fixo `ESC-` + data (`AAAAMMDD`) + INEP + sufixo (`RE`/`RI`/`Global`), ex. `ESC-20260811-12345678-RE`, embutido no assunto como `#{codigo} - {assunto}` (mesmo padrao do `#{codigo}` da cotacao) — o prefixo `ESC-` garante que o codigo nunca colide com o codigo puramente numerico da cotacao na mesma caixa compartilhada. Novo model `EmailEscolaRespostaImportacao` (`apps/core/models.py`, GenericForeignKey — `apps.core` nao pode importar `apps.escolas`) equivalente a `EmailCotacaoRespostaImportacao`, mas dedicado a Escola/RE/RI, para nao confundir os dois dominios na mesma caixa. `apps/integracoes/email/sincronizar_respostas_email_cotacao.py` passou a classificar cada mensagem (cotacao ou Escola/RE/RI) na mesma passagem pela caixa (uma so leitura da API do Graph por execucao) e delegar ao importador certo; RE/RI so recebe a resposta se o processo interno correspondente ja tiver sido criado ao menos uma vez (mesma pre-condicao da RN-029). UI de envio: `<details>` (HTML nativo, sem JS de toggle) dentro dos modais existentes `escola_historico_modal.html`/`escola_rede_historico_modal.html` (RN-029), com campos Para/Cc/Assunto/Mensagem/Anexos. As rotas de envio (`escola_enviar_email`/`escola_rede_enviar_email`) vivem em `apps.core_admin` (dono de `ConfiguracaoEmailEnvio`) para nao inverter a ordem de camada da ADR-007 (`apps.leads`, dominio, nao pode importar de `apps.core_admin`, aplicacao) — os templates continuam em `apps.leads`, reaproveitados via `render()` cross-app (sem duplicar layout); a mesma permissao do grid de RE/RI (`grupo_LastMile_required`) e reaproveitada por import direto.
**Features relacionadas:** PO-066, RN-023, RN-029.
**Status:** Ativa

### RN-043 - Mapa Calor como terceira subatividade da Escola, seguindo o mesmo padrao de RE/RI
**Descricao:** A Escola passa a ter uma terceira subatividade fixa, "Mapa Calor" (`apps.escolas.MapaCalor`), no mesmo molde de Rede Externa (RE) e Rede Interna (RI, RN-023): processo independente, 1-para-1 com a Escola, reaproveitando a mesma classe abstrata `ProcessoRedeBase` (setor, status, parceiro, dados_adicionais). Todas as regras ja registradas para RE/RI que descrevem comportamento generico de "subatividade" (RN-023 a RN-042) passam a valer igualmente para Mapa Calor, por extensao, sem precisar de regra propria — exceto os pontos especificos listados abaixo.
**Contexto:** Usuario pediu, em 2026-08-11, mais uma subatividade alem de RE e RI, com a possibilidade de criar quantas precisasse pelo Admin. Investigacao do Orquestrador mostrou que RE/RI sao hoje dois models hardcoded (nao um cadastro dinamico) e que generalizar isso e uma refatoracao arquitetural de grande porte. Apresentadas as alternativas, o usuario decidiu (2026-08-11) adiar a generalizacao (ver ADR-025) e manter o pedido concreto imediato: uma terceira subatividade fixa, "Mapa Calor", implementada em codigo pelo Dev no mesmo padrao hardcoded de RE/RI — nao um cadastro pelo usuario via Admin.
**Criterios:**
- Mapa Calor e um terceiro processo independente por Escola (mesmo nivel de RE/RI, RN-023), com seu proprio setor, status, parceiro e dados adicionais — pode estar em setor/status diferentes de RE e RI, e ter parceiro igual ou diferente;
- catalogo de Processo/Setor/Status (RN-025) vale igualmente para Mapa Calor: precisa de um Processo proprio (mesmo padrao de `NOME_PROCESSO_PADRAO` de RE/RI), com seus Setores e Status cadastrados como qualquer outro Processo;
- edicao de Setor/Status em cascata (RN-026), inclusive a trava de Status somente pelo Setor atual e o "Aguardando" automatico ao trocar de Setor (RN-033), e a exclusao de Status por Setor (RN-034), aplicam-se a Mapa Calor da mesma forma que a RE/RI;
- Parceiro de Mapa Calor segue a mesma regra de RE/RI (RN-030): editavel somente na Tela de Setor "Lastmile", via modal de selecao;
- historico e anexo individuais de Mapa Calor (RN-029), com formato De/Para estruturado (RN-041); a visao combinada da Escola passa a reunir os tres processos (RE, RI e Mapa Calor), nao somente RE+RI;
- Campos personalizados por Setor (RN-031/032), incluindo Campo condicionado a Status e Campo calculado (RN-039/040), aplicam-se a Mapa Calor: o modal de Campos do Mapa Calor mostra os mesmos grupos por Setor (Setor da tela atual expandido, demais recolhidos);
- envio de e-mail (RN-042) passa a incluir Mapa Calor como um terceiro "sub-ticket": envio/resposta feito a partir de Mapa Calor fica so no historico dele; o numero de rastreio ganha um terceiro sufixo de nivel (ao lado de `RE`/`RI`/`Global`);
- visao por Setor (RN-027/RN-028) passa a agregar tambem Mapa Calor, alem de RE e RI, ao listar as atividades vinculadas a um Setor;
- na tela de Enderecos Lastmile, a linha da Escola ganha uma terceira linha expansivel para Mapa Calor, no mesmo padrao visual e de permissao (`grupo_LastMile_required`) ja usado por RE e RI.
**Excecoes:** Mapa Calor nao tem, ate o momento, nenhum dado de referencia somente-leitura equivalente ao `dados_api.setor_re`/`parceiro_re` (RN-024) vindo da API do DashboardEACE — nao ha linha de referencia somente-leitura para Mapa Calor na Escola, apenas o processo interno editavel.
**Impacto tecnico:** novo model `MapaCalor(ProcessoRedeBase)` em `apps/escolas/models.py`, com `escola = OneToOneField(Escola, on_delete=CASCADE, related_name="mapa_calor")` e `processo = ForeignKey("Processo", ..., related_name="mapas_calor")` (mesmo padrao de `RedeExterna`/`RedeInterna`, PO-048); migration aditiva. Os pontos de `apps/leads` e `apps/escolas/admin.py` que hoje enumeram RE/RI explicitamente (grid, cascata Setor/Status, modal de Campos, modal de historico, envio de e-mail) precisam passar a reconhecer um terceiro processo.
**Features relacionadas:** PO-067, RN-023, RN-025, RN-026, RN-027, RN-028, RN-029, RN-030, RN-031, RN-032, RN-033, RN-034, RN-039, RN-040, RN-041, RN-042, ADR-012, ADR-025.
**Status:** Ativa

### RN-044 - Cotacao de RE/RI com multiplos parceiros candidatos, com selecao de um vencedor
**Descricao:** Quando um RedeExterna (RE) ou RedeInterna (RI) estiver com Status "Cotacao" (catalogo Setor/Status, RN-025) dentro da Tela do Setor "Lastmile", o analista passa a poder vincular esse RE/RI a varios Parceiros candidatos e, depois, marcar um deles como vencedor ("Selecionado"). Os demais candidatos passam automaticamente para "Recusado". O Parceiro vencedor preenche o campo `parceiro` do RE/RI (RN-030).
**Contexto:** Usuario pediu, em 2026-08-12, para adaptar a arquitetura atual um processo que ja existe na arquitetura antiga: dentro do Setor "Lastmile", quando o RE/RI estiver no Status de Cotacao, aquela subatividade pode ter N Parceiros cadastrados em cotacao para a Escola, mas so um vai seguir. Investigacao do Orquestrador identificou que o processo antigo citado e, com alta confianca, o mesmo padrao ja usado por `Proposal` (`apps.partners`) na cotacao de Lead (N propostas por parceiro, uma vira `contratado`). Perguntado para nao inventar o desenho, confirmado em 2026-08-12: Parceiro do RE/RI passa a ser preenchido automaticamente pelo vencedor da cotacao; escopo limitado a RE e RI (Mapa Calor fora por agora); cada candidato guarda so Parceiro + situacao da candidatura, sem dados comerciais; selecionar o vencedor nao move o Status automaticamente para fora de "Cotacao" (RN-033 continua regendo a troca manual de Status). Ver ADR-026 para o motivo de nao reaproveitar `Proposal` diretamente.
**Criterios:**
- "Cotacao" precisa existir como `SetorStatus` do Setor "Lastmile", nos Processos de RE e de RI (RN-025) — sem mudanca de schema, e um valor de catalogo como outro qualquer;
- enquanto o RE/RI exibido estiver com esse Status, a linha expandida (Tela do Setor "Lastmile") ganha um controle que abre um modal de gestao de cotacao, no mesmo padrao visual dos demais modais do grid;
- o modal permite buscar e adicionar Parceiros candidatos (mesmo filtro por nome/cidade/UF/bairro reaproveitado pela RN-030), listar os candidatos com sua situacao (Em cotacao / Selecionado / Recusado) e remover candidato ainda nao selecionado;
- marcar um candidato como "Selecionado" move automaticamente os demais candidatos daquele mesmo RE/RI para "Recusado" — nunca mais de um "Selecionado" por RE/RI ao mesmo tempo;
- confirmar o "Selecionado" preenche `RedeExterna.parceiro`/`RedeInterna.parceiro` (RN-030) com esse Parceiro, gerando `RegistroHistorico` no mesmo padrao Antes/Depois ja usado para Parceiro (RN-030/041);
- a disponibilidade do modal segue a mesma trava da RN-030: somente na Tela do Setor "Lastmile" (`setor_atual == "Lastmile"`), dentro da permissao `grupo_LastMile_required` que ja protege a tela;
- trocar o Status do RE/RI para fora de "Cotacao" continua sendo acao manual e separada do analista (RN-026/RN-033) — nao ha transicao automatica ao selecionar o vencedor.
**Excecoes:** Mapa Calor (RN-043) fora do escopo desta regra; sem dados comerciais (valor, prazo, plano) por candidato nesta versao.
**Impacto tecnico:** novo model `CotacaoParceiro` em `apps.escolas`, com `GenericForeignKey` para `RedeExterna`/`RedeInterna` (mesmo padrao ja usado por `CampoValor`/`RegistroHistorico`), FK para `partners.Partner` e campo de situacao da candidatura; sem FK nova partindo de `apps.partners` para `apps.escolas` (evita reabrir ciclo de importacao, ADR-007 item 7). Ver ADR-026 para o desenho completo e as alternativas descartadas.
**Features relacionadas:** PO-068, RN-023, RN-025, RN-026, RN-030, RN-033, RN-041, ADR-012, ADR-018, ADR-026.
**Status:** Ativa

### RN-045 - Provedores (Partner) ganha tela propria de listagem em grid e cadastro, dentro do menu Projeto
**Descricao:** O menu "Projeto" (grupo "LastMile") ganha um item novo "Provedores", com uma tela dedicada listando em grid todos os `Partner` cadastrados e um botao para cadastrar um novo, usando os campos basicos do cadastro. E uma tela independente da ja existente "Parceiros" (grupo "Parceiro", com propostas/cotacoes) — nenhuma das duas e removida.
**Contexto:** Usuario apontou, em 2026-08-12, que o item de menu "Provedores" (dentro de Projeto) deveria mostrar os provedores cadastrados e permitir cadastrar um novo. Investigacao do Orquestrador encontrou que esse item hoje abre a tela de Leads (`lead_list`), nao um cadastro de provedores — o cadastro real de provedores de internet e outro model, `partners.Partner` (mesmo usado nos 50 parceiros ficticios e na cotacao RE/RI, RN-044), com tela propria numa secao de menu separada ("Parceiros", grupo "Parceiro"), sem nenhuma view de criar novo Partner ainda (`PartnerForm` existe no codigo, sem uso). Perguntado para nao inventar o desenho, confirmado em 2026-08-12: "Provedores" e mesmo o cadastro de Partner, numa tela nova e independente, sem tocar na tela "Parceiros" existente. Investigacao adicional mostrou que o item "Provedores" e hoje o unico ponto de acesso a tela de Leads no menu inteiro — repontar sem mais nada orfanaria essa tela (regressao nao pedida); decisao tecnica reversivel do Orquestrador (secao 9 do CLAUDE.md): renomear o item existente para "Leads" (mesmo precedente de correcao de rotulo da PO-060) e adicionar um item novo "Provedores" apontando para a tela nova.
**Criterios:**
- novo item de menu "Provedores", dentro do submenu de "Projeto", abre uma tela em grid listando todos os `Partner` cadastrados (colunas: Nome Fantasia/Razao Social, CNPJ/CPF, Contato, E-mail, Telefone, Status);
- botao "Novo Provedor" abre formulario de cadastro com os mesmos campos basicos (Razao Social, Nome Fantasia, CNPJ/CPF, Contato, E-mail, Telefone, Status) — reaproveita o `PartnerForm` ja existente (`apps/partners/forms.py`);
- o item de menu hoje rotulado "Provedores" (que abre a tela de Leads) e renomeado para "Leads", sem mudar a rota nem o comportamento daquela tela;
- tela nova protegida pela mesma permissao ja usada no restante do menu "Projeto" (`grupo_LastMile_required`);
- tela "Parceiros" existente (grupo "Parceiro", com propostas/cotacoes) nao e alterada nem removida.
**Excecoes:** sem edicao/exclusao de Partner nesta tela nova (fora do escopo pedido); sem filtro alem do grid basico, salvo o que o Dev considerar necessario para volume de dados.
**Impacto tecnico:** novas views `provedores_list`/`provedores_create` em `apps/partners/views.py` (nomes distintos de `partner_list`, que continua servindo a tela "Parceiros"), novo template de grid, reaproveitando `PartnerForm`; ajuste de rotulo e `href` em `apps/core/templates/core/base.html` (item atual "Provedores" passa a "Leads", continua em `lead_list`; item novo "Provedores" aponta para `provedores_list`).
**Features relacionadas:** PO-069, RN-030, RN-044.
**Status:** Ativa

### RN-046 - Menu Projeto deixa de exibir "Leads"; Provedores (Partner) ganha rota de edicao
**Descricao:** O item de menu "Leads" (criado pela RN-045 para preservar acesso a tela antiga apos o reaproveitamento do rotulo "Provedores") e retirado do menu "Projeto" — a rota/view `lead_list` continua existindo no codigo, so deixa de ter entrada de navegacao. A tela "Provedores" (RN-045/PO-069) ganha uma rota de edicao de `Partner`, com os mesmos campos basicos do cadastro.
**Contexto:** Usuario aprovou a tela nova de Provedores (PO-069) e pediu, em 2026-08-12, para retirar do menu o item que ficou como "Leads" e para acrescentar uma rota de editar provedor. Revoga parcialmente a RN-045 (item "Leads" deixa de existir no menu; a tela de grid/criacao em si nao muda).
**Criterios:**
- item de menu "Leads" (submenu Projeto) e removido de `apps/core/templates/core/base.html`; a rota `lead_list` nao e alterada nem removida, so perde a entrada de menu — sem acesso por navegacao, mas sem quebrar quem acessar a URL direto;
- nova rota de edicao de `Partner`, com os mesmos campos basicos usados no cadastro (RN-045): Razao Social, Nome Fantasia, CNPJ/CPF, Contato, E-mail, Telefone, Status — reaproveitando `PartnerForm`;
- acesso a edicao a partir da tela de grid "Provedores" (ex.: acao por linha), protegido pela mesma permissao `grupo_LastMile_required`;
- fora do escopo: exclusao de Partner (nao pedida).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** remocao do item "Leads" em `base.html`; nova view/rota de edicao em `apps/partners/views.py`/`urls.py`, reaproveitando `PartnerForm` (mesmo padrao de `provedores_create`, RN-045).
**Features relacionadas:** PO-070, RN-045.
**Status:** Ativa

## Exportacao de Dados (Administracao)

### RN-047 - Exportacao completa dos dados de negocio do sistema em CSV, com Setor ou "Global" por campo
**Descricao:** A tela "Importacao e Exportacao" (Administracao) ganha um card de exportacao que gera um CSV unico, em formato longo (uma linha por campo de um registro), cobrindo os modulos de negocio do sistema (Clientes, Enderecos/Escolas, Backoffice, Provedores/Parceiros, Cotacoes, Processos/Campos/Setor). Cada linha traz: Setor (ou "Global"), Modulo, Registro, Campo, Valor. O "Setor" de cada campo segue a mesma taxonomia ja usada em `AutomacaoMenu.MENU_CHOICES` (Administrador, Backoffice, LastMile, Parceiro); modulo sem dono exclusivo de um unico setor e marcado "Global".
**Contexto:** Usuario solicitou, em 2026-08-12, uma tela de Importacao e Exportacao dentro de Administracao, com um primeiro card para exportar "todos os campos do sistema com os dados", informando o setor de cada campo ou se e global — no mesmo padrao visual dos cards de automacao ja existentes. Perguntado sobre formato e escopo (decisao que mudaria arquitetura e exposicao de dados, CLAUDE.md secao 9), usuario confirmou: CSV unico em formato longo (Setor/Global, Modulo, Registro, Campo, Valor) e escopo restrito aos modulos de negocio, excluindo tabelas tecnicas do Django e qualquer campo de credencial/segredo.
**Criterios:**
- novo card na tela "Importacao e Exportacao" (Administracao), no mesmo padrao visual dos cards de automacao ja existentes (`core_admin/partials/*.html`);
- gera um unico arquivo CSV para download, com colunas Setor, Modulo, Registro, Campo, Valor;
- cobre somente os modulos de negocio (Clientes, Enderecos/Escolas, Backoffice, Provedores/Parceiros, Cotacoes, Processos/Campos/Setor), excluindo tabelas internas do Django (sessions, permissions, admin log, contenttypes) e qualquer app/tabela de autenticacao;
- campos de senha, hash, token, chave de API ou qualquer credencial/segredo nunca sao exportados, mesmo que pertencam a um modulo de negocio (CLAUDE.md secao 6);
- Setor de cada campo segue a taxonomia de `AutomacaoMenu.MENU_CHOICES`; modulo sem dono exclusivo de um unico setor e marcado "Global";
- acesso restrito ao grupo Administrador (mesmo padrao das demais telas de Administracao).
**Excecoes:** lista exata de apps/models incluidos no export e a definir na implementacao (PO-071), respeitando os criterios acima; nao decidida aqui para nao antecipar detalhe de codigo.
**Impacto tecnico:** nova view/rota em `core_admin` para o card de exportacao; servico que percorre os models dos apps de negocio (introspection do Django) e monta o CSV; allowlist explicita de apps e de campos sensiveis excluidos, mantida no codigo.
**Features relacionadas:** PO-071.
**Status:** Substituída por RN-048

### RN-048 - Exportacao de Setores e Escolas em uma unica tabela, replicando as colunas da tela de Setor (RE/RI/Mapa Calor)
**Descricao:** O card de exportacao (tela "Importacao e Exportacao", Administracao) passa a gerar um unico CSV com uma linha por Escola, replicando exatamente as colunas ja exibidas hoje na tela de Setor/grid de Enderecos Lastmile (`apps/leads/templates/leads/enderecos_lastmile.html` e `partials/escola_rede_row.html`): dados da Escola (INEP, Nome, Estado, Municipio, Endereco, Status) e, para cada subatividade (Rede Externa, Rede Interna, Mapa Calor), as colunas Setor, Parceiro e Status daquela subatividade. Cada campo e uma coluna; nao ha mais linha-por-campo (RN-047) nem os demais modulos de negocio (Clientes/Enderecos, Leads, Provedores/Parceiros/Cotacoes) — escopo passa a ser somente Setores e Escolas.
**Contexto:** Usuario testou a entrega da RN-047 (PO-071) e informou, em 2026-08-12, que nao ficou do jeito que queria: pediu para restringir a exportacao a "Setores e Escolas" e para cada campo virar uma coluna, nao uma linha. Perguntado sobre o formato exato (uma tabela unica no molde da tela de Setor, versus uma tabela por tipo de registro com Campos personalizados como coluna extra), usuario confirmou a primeira opcao: replicar as colunas ja existentes na tela de Setor, uma linha por Escola. Revoga a RN-047 (marcada Substituida).
**Criterios:**
- CSV com uma linha por Escola e as colunas: INEP, Nome da Escola, Estado, Municipio, Endereco, Status (da Escola);
- para Rede Externa, Rede Interna e Mapa Calor, tres colunas cada — Setor, Parceiro, Status —, vazias quando a Escola nao tiver aquela subatividade criada;
- nao inclui Campos personalizados (Campo/CampoValor) como coluna — fora do escopo desta regra, mesma limitacao ja assumida na RN-047;
- nao inclui os demais modulos de negocio (Clientes/Enderecos, Leads, Provedores/Parceiros, Cotacoes) — escopo agora e somente Escola + RE/RI/Mapa Calor;
- acesso restrito ao grupo Administrador (mantido da RN-047).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** reescreve o servico de exportacao criado pela RN-047 (`apps/core_admin/services.py::gerar_linhas_exportacao_sistema`) para montar uma linha por Escola em vez de uma linha por campo/registro; remove a allowlist de modulos de negocio da RN-047 (Clientes/Leads/Partners), mantendo so `apps.escolas` (Escola, RedeExterna, RedeInterna, MapaCalor).
**Features relacionadas:** PO-071.
**Status:** Ativa

### RN-049 - Campos personalizados entram na exportacao de Setores e Escolas como colunas dinamicas
**Descricao:** A exportacao de Setores e Escolas (RN-048) ganha, alem das colunas fixas, uma coluna para cada `Campo` personalizado (RN-031) cadastrado em Administracao > Campos — descoberta em tempo de exportacao, sem precisar de nova versao de codigo quando um Campo novo for criado. Reaproveita a mesma regra de escopo/valor ja usada no modal de RE/RI/Escola (RN-032/RN-037/RN-039/RN-040), so trocando "mostrar na tela" por "virar coluna do CSV": Campo cujo Setor tem escopo "Escola" (`SetorEscopo`) gera 1 coluna, com o valor daquela Escola; Campo cujo Setor tem escopo "Sub-atividades" (ou sem registro em `SetorEscopo`, comportamento legado) gera 1 coluna por subatividade aplicavel (RE/RI/Mapa Calor, conforme `aplica_re`/`aplica_ri`/`aplica_mapa_calor`), com o valor daquela instancia de RedeExterna/RedeInterna/MapaCalor. Campo tipo Calculado usa o mesmo valor derivado ao vivo do modal (RN-039), nunca o bruto de `CampoValor`. Campo com Status condicionante fica em branco na linha quando o Status atual daquela subatividade nao bate (mesma regra do modal, RN-039) — a coluna sempre existe, o que varia e o valor por linha.
**Contexto:** Apos a correcao da RN-048, usuario pediu, em 2026-08-12, para os Campos personalizados tambem entrarem na exportacao, aparecendo automaticamente sempre que um Campo novo for criado. Nao ha ambiguidade sobre incluir ou nao — a decisao registrada aqui e apenas de como cada Campo se traduz em coluna(s), reaproveitando a logica de escopo/valor ja implementada e aprovada para o modal (RN-032/037/039/040), em vez de inventar uma regra nova.
**Criterios:**
- coluna por Campo e descoberta a cada exportacao (consulta ao catalogo de `Campo` no momento do download), nao fixa no codigo — Campo criado hoje aparece na proxima exportacao sem deploy;
- nome da coluna usa o prefixo "Campo Personalizado - " seguido do nome do Campo (e do sufixo RE/RI/MC quando aplicavel), para nunca colidir com as colunas fixas da RN-048 (ex.: um Campo chamado "Status" nao sobrescreve a coluna "Status" da Escola);
- Campo com escopo Escola (`SetorEscopo.ATIVIDADE_ESCOLA`): 1 coluna, valor de `CampoValor` da Escola;
- Campo com escopo Sub-atividades (ou sem `SetorEscopo` cadastrado — default legado RE+RI+MC): 1 coluna por subatividade marcada (`aplica_re`/`aplica_ri`/`aplica_mapa_calor`), valor de `CampoValor` daquela instancia de RE/RI/MC; branco quando a Escola nao tiver aquela subatividade;
- Campo tipo Calculado: valor derivado ao vivo (mesma formula/funcao do modal, RN-039), nunca o valor bruto gravado;
- Campo com Status condicionante: branco na linha quando o Status atual da subatividade nao bate com o condicionante (RN-039);
- formatacao do valor no CSV segue o mesmo padrao ja usado no historico de Campos (RN-040): data `dd/mm/aaaa`, booleano Sim/Nao, demais tipos como texto.
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** reaproveita `apps/leads/services.py` (`campos_grid_escola`, `campos_grid_rede`, `_valor_campo_calculado`, `_campo_visivel`, `_formatar_valor_campo_historico`) em vez de duplicar a logica de escopo; atencao a N+1 ao aplicar isso a todas as Escolas de uma vez — a consulta de `Campo`/`CampoValor` deve ser feita em lote (uma vez para o catalogo, uma vez para os valores por tipo de conteudo), nao por Escola.
**Features relacionadas:** PO-071.
**Status:** Ativa

### RN-050 - Card de exportacao de Setores e Escolas ganha duas opcoes de download: modelo (so colunas) e dados completos
**Descricao:** O card "Exportacao de Setores e Escolas" (RN-048/RN-049) passa a oferecer dois downloads: "Baixar Modelo" — CSV so com a linha de cabecalho (todas as colunas atuais, fixas e os Campos personalizados descobertos no momento), sem nenhuma linha de Escola — e "Baixar com Todos os Dados" — o CSV completo ja existente, uma linha por Escola. Mesmo padrao ja usado pelas automacoes de planilha do sistema (`download_template_*`), que sempre oferecem um modelo vazio antes do envio/upload.
**Contexto:** Usuario aprovou a exportacao de dados (RN-048/RN-049) e pediu, em 2026-08-12, uma opcao de baixar essa planilha como modelo (vazia, so a estrutura) alem da opcao de baixar com todos os dados do banco.
**Criterios:**
- botao "Baixar Modelo" gera um CSV com a mesma lista de colunas da exportacao de dados (fixas + Campos personalizados atuais), sem nenhuma linha de Escola;
- botao "Baixar com Todos os Dados" mantem o comportamento ja existente (uma linha por Escola);
- os dois botoes vivem no mesmo card "Exportacao de Setores e Escolas";
- nenhuma alteracao nas regras de coluna/valor ja definidas (RN-048/RN-049).
**Excecoes:** nenhuma.
**Impacto tecnico:** nova rota/view para o modelo, reaproveitando `services.montar_exportacao_setores_escolas()` para obter as colunas sem precisar consumir o gerador de linhas (dados).
**Features relacionadas:** PO-071.
**Status:** Ativa

### RN-051 - Escola ganha campos estruturados de Logradouro, Numero, Bairro e CEP, extraidos do endereco em texto livre
**Descricao:** `Escola` ganha 4 campos novos — `logradouro`, `numero`, `bairro`, `cep` — preenchidos automaticamente a partir do texto livre ja existente em `endereco_descricao` (campo que vem do DashboardEACE, ADR-010, e permanece intacto como fonte bruta). CEP e extraido com certeza (formato fixo `00000-000`, sempre presente no texto); Logradouro/Numero/Bairro sao extraidos por um separador de melhor esforco, ja que o texto de origem nao segue um formato fixo (confirmado investigando 2622 registros reais — ha casos sem numero, sem tipo de logradouro, sem bairro, e ordem variavel entre eles). Quando o separador nao tiver confianca suficiente para um desses 3 campos, o campo fica em branco (nunca um palpite claramente errado) — o texto original completo continua disponivel em `endereco_descricao` para consulta/correcao manual. A sincronizacao com o DashboardEACE (`sincronizar_escolas`) passa a preencher os 4 campos novos tambem para toda Escola nova ou atualizada; um backfill unico roda sobre as Escolas ja existentes.
**Contexto:** Usuario pediu, em 2026-08-12, para separar em colunas proprias as informacoes hoje misturadas na coluna "Endereco" (planilha e banco), citando como exemplo uma escola com "Endereço: FLAVIO MONTEIRO DE CASTRO, 500 RUA. RIBEIROPOLIS. 11714-130 Praia Grande - SP." Investigacao do Orquestrador (amostra de 8 registros reais em producao) confirmou que o texto nao segue um formato fixo — casos sem numero ("SILVEIRANIA, S/N JARDIM RUSSO..."), sem separador de tipo de logradouro apos o numero ("HANS CHRISTIAN ANDERSEN, 67 GRANJA NOSSA SENHORA APARECIDA..."), e sem numero nem bairro ("FAZENDA RECANDO DA IARA, 77673-000..."). Perguntado como proceder dado esse risco (unica parte confiavel de extrair e o CEP), usuario confirmou: separar por melhor esforco, aceitando imprecisao em parte dos registros, sem nunca apagar o texto original.
**Criterios:**
- novos campos em `Escola`: `logradouro`, `numero`, `bairro`, `cep` (nomes no mesmo padrao ja usado em `apps.clientes.Endereco`);
- `cep` extraido com o padrao fixo `\d{5}-\d{3}` presente no texto — sempre preenchido quando o texto tiver um CEP;
- `logradouro`, `numero` e `bairro` extraidos por heuristica de melhor esforco; quando a heuristica nao tiver confianca, o campo fica em branco (nunca um valor claramente incorreto);
- `endereco_descricao` (texto bruto) nunca e apagado nem alterado — continua sendo a fonte de consulta/correcao manual;
- `sincronizar_escolas` (DashboardEACE) passa a preencher os 4 campos novos em toda sincronizacao futura (Escola nova ou atualizada);
- migracao de dados (backfill) roda a mesma extracao sobre as Escolas ja existentes, uma unica vez;
- exportacao de Setores e Escolas (RN-048/049/050) troca a coluna unica "Endereco" por 4 colunas — Logradouro, Numero, Bairro, CEP — tanto no CSV de dados quanto no modelo; o texto bruto completo deixa de ser exportado.
**Excecoes:** nao ha garantia de 100% de acerto para Logradouro/Numero/Bairro — parte das 2622 Escolas atuais pode ficar com um ou mais desses 3 campos em branco quando o texto de origem nao permitir extrair com confianca; correcao, quando necessaria, e manual.
**Impacto tecnico:** migration aditiva em `apps/escolas` (4 campos novos, opcionais); funcao de extracao (services), coberta por testes com os formatos reais encontrados na amostra; alteracao em `apps/escolas/services.py::sincronizar_escolas` para preencher os campos novos; data migration ou management command para o backfill unico; ajuste do servico de exportacao (`apps/core_admin/services.py`) para trocar a coluna "Endereco" pelas 4 novas.
**Features relacionadas:** PO-072.
**Status:** Ativa

### RN-052 - Subatividade (RE/RI/Mapa Calor) deve ter Setor, Status e Responsavel; Responsavel referencia o usuario autenticado do sistema
**Descricao:** Toda subatividade (`RedeExterna`/`RedeInterna`/`MapaCalor`, ADR-012/RN-023/RN-043, via `ProcessoRedeBase`) deve possuir Setor (RN-025), Status (RN-025) e um Responsavel. O Responsavel referencia obrigatoriamente um usuario autenticado do proprio sistema (`core.User`/Django auth) — nunca texto livre nem cadastro externo, mesmo padrao ja usado por `Proposal.responsavel` (`apps/partners/models.py`, FK para `core.User`, `SET_NULL`). Responsavel e atribuivel/reatribuivel manualmente (nao e preenchido automaticamente com "quem criou"); a obrigatoriedade dos tres campos e imposta pela camada de negocio/UI, nao pelo schema (Setor/Status/Responsavel continuam `null=True, blank=True` no banco).
**Contexto:** Usuario pediu, em 2026-08-12: "toda subatividade precisa de um setor, status e responsável. Esse responsável vai ser o usuário do sistema quando logar." Investigacao do Orquestrador confirmou o estado atual do codigo: Setor e Status ja existem em `ProcessoRedeBase` como `ForeignKey` para `Setor`/`SetorStatus` (ADR-014/ADR-015), herdados por RE, RI e Mapa Calor — mas eram **opcionais** (`null=True, blank=True`); RN-035 so fixa Status="Novo" automaticamente na criacao pelo grid global, sem tornar o campo obrigatorio no banco. Responsavel **nao existia** em `ProcessoRedeBase` nem em nenhum model de subatividade; o unico precedente no sistema e `Proposal.responsavel` (cotacao, apps.partners) — um campo atribuivel/reatribuivel, com acao explicita "assumir responsavel" (`proposal_assumir_responsavel`) e historico de troca. Diante da divergencia com ADR-012/ADR-014/RN-023/RN-025/RN-035 (Setor/Status opcionais), o Orquestrador registrou a regra como `Pendente` e levantou 6 perguntas (CLAUDE.md secao 9). Usuario respondeu em 2026-08-12 (decisao registrada em ADR-027): atribuicao manual/reatribuivel; obrigatoriedade so via UI, sem migrar dados legados; vale para as tres subatividades; edicao nas mesmas telas ja existentes (RN-026/027/028), com a trava da RN-033; Responsavel e zerado junto com o Status ao trocar de Setor; gera `RegistroHistorico` no formato De/Para.
**Criterios:**
- toda subatividade (`RedeExterna`, `RedeInterna`, `MapaCalor`) ganha um campo Responsavel, FK para o usuario do sistema (`core.User`), alem de Setor e Status ja existentes;
- Responsavel e atribuivel e reatribuivel manualmente por quem estiver operando a tela — mesmo padrao ja usado para Parceiro (RN-030) e para `Proposal.responsavel` — nunca preenchido automaticamente e imutavel;
- Setor, Status e Responsavel continuam campos opcionais no banco (nullable); a obrigatoriedade e imposta pela camada de negocio/UI (validacao ao salvar/avancar o fluxo de edicao, RN-026), sem migracao/backfill dos registros ja existentes;
- edicao do Responsavel restrita as mesmas duas telas que ja editam Setor/Status — grid global de Enderecos Lastmile (RN-026) e Tela de Setor (RN-027/028) — com a mesma trava por `setor_atual` da RN-033; nenhuma superficie de edicao nova;
- ao trocar de Setor (RN-033 ja zera o Status para "Aguardando"), o Responsavel tambem e zerado, liberando a subatividade para reatribuicao no novo Setor;
- alteracao de Responsavel (manual ou zeragem automatica ao trocar de Setor) gera `RegistroHistorico` no mesmo formato De/Para ja usado para Setor/Status/Parceiro (RN-029/041);
- vale igualmente para as tres subatividades — RedeExterna, RedeInterna e MapaCalor — sem excecao.
**Excecoes:** registro ja existente sem Setor/Status/Responsavel preenchido (dado legado) continua existindo sem alteracao retroativa — a obrigatoriedade via UI passa a valer a partir da proxima edicao feita pela tela. O comportamento da trava por `setor_atual` sobre o Responsavel dentro do grid global foi esclarecido pela RN-056 (2026-08-13): a primeira atribuicao de Setor pelo grid global nunca exige Responsavel — pendente de correcao de codigo.
**Impacto tecnico:** novo campo `responsavel` (FK `core.User`/`AUTH_USER_MODEL`, `null=True, blank=True`, `on_delete=SET_NULL`) em `ProcessoRedeBase`, herdado por RedeExterna/RedeInterna/MapaCalor (migration aditiva, sem backfill); validacao de obrigatoriedade (Setor+Status+Responsavel) na camada de formulario/servico usada pela RN-026; RN-033 (zeragem ao trocar de Setor) e RN-029/041 (`RegistroHistorico`) estendidas para cobrir Responsavel. Ver ADR-027.
**Features relacionadas:** PO-073, RN-023, RN-025, RN-026, RN-027, RN-028, RN-029, RN-030, RN-033, RN-035, RN-041, RN-043, ADR-012, ADR-014, ADR-015, ADR-025, ADR-027.
**Status:** Ativa — criterio de obrigatoriedade refinado pela RN-056 (2026-08-13)

### RN-056 - Responsavel so e obrigatorio dentro da Tela do proprio Setor, ao definir/alterar Status sem mover a subatividade
**Descricao:** Responsavel (junto com Setor e Status) so e exigido pela camada de negocio quando **todas** as condicoes valem: (a) a edicao ocorre na Tela do proprio Setor (`setor_atual` definido); (b) apos a edicao, a subatividade (RedeExterna/RedeInterna/MapaCalor) continua no mesmo Setor — nao foi movida; (c) o Status esta sendo definido/alterado; (d) Responsavel esta vazio. Em qualquer outro caso — inclusive a **primeira atribuicao de Setor pelo grid global de Enderecos Lastmile** (sem Setor selecionado no menu, subatividade que ainda nao tinha nenhum Setor) — Responsavel nunca e exigido, porque quem faz a atribuicao ou a movimentacao nao necessariamente sabe quem, no Setor de destino, vai assumir a subatividade.
**Contexto:** Usuario pediu, em 2026-08-13: "o campo responsável só pode ser obrigatorio quando eu tiver dentro de um setor e eu alterar o status e o campo responsável estiver vazio. Se eu alterar uma atividade de setor, esse campo não pode ser obrigatorio pois eu não vou saber qual o responsável vai tratar essa atividade em outro setor." O Orquestrador registrou inicialmente esta regra restringindo-a a "subatividade movida para outro Setor", presumindo que a obrigatoriedade na primeira atribuicao (grid global, subatividade sem Setor ainda) estava correta — e concluiu, com o Dev, que nao havia divergencia de codigo. **Correcao em 2026-08-13 (mesmo dia):** o usuario reportou que "ainda continua sendo obrigado a colocar um responsável ao enviar a subatividade para outro setor" e, questionado, confirmou que isso ocorre exatamente na tela Enderecos Lastmile (grid global, sem Setor selecionado) ao atribuir Setor pela primeira vez a uma subatividade que ainda nao tinha nenhum. Isso mostra que o escopo da regra estava incompleto: a primeira atribuicao pelo grid global tambem se encaixa no motivo original ("quem atribui nao sabe quem sera o responsavel no destino"), pois quem faz essa atribuicao nao esta necessariamente dentro do Setor de destino. A regra passa a exigir Responsavel **somente** dentro da Tela do proprio Setor, mantendo a subatividade nesse mesmo Setor.
**Criterios:**
- Responsavel so e exigido quando, simultaneamente: a edicao ocorre com `setor_atual` definido (Tela de Setor); a subatividade permanece nesse mesmo Setor apos a edicao (nao foi movida); o Status esta sendo definido/alterado; e Responsavel esta vazio;
- em qualquer outro caso, Responsavel nunca e exigido: subatividade movida para outro Setor pela Tela de Setor (zerado automaticamente, RN-052); ou Setor atribuido/alterado pelo grid global de Enderecos Lastmile (primeira atribuicao — unico caso de edicao de Setor permitido ali, RN-026/035), com ou sem Responsavel informado;
- Status continua seguindo as regras ja existentes (RN-033/RN-035) — esta regra altera somente o criterio de obrigatoriedade de Responsavel.
**Excecoes:** nenhuma alem das ja registradas na RN-052 (registro legado sem os tres campos; obrigatoriedade so por UI, sem migracao/backfill).
**Impacto tecnico:** `apps/leads/views.py::escola_rede_editar`, ramo `elif not setor_atual:` (grid global, RN-035) — a checagem final de obrigatoriedade (hoje `if not enviado_a_outro_setor and rede.setor_id and rede.status_id and not rede.responsavel_id`) precisa deixar de se aplicar tambem quando a edicao ocorre nesse ramo (grid global), nao somente quando `enviado_a_outro_setor` e True; a obrigatoriedade passa a ficar restrita ao ramo `else` (Tela de Setor, permanecendo no `setor_atual`). Correcao de codigo pendente com o Dev — ver BACKLOG.md PO-073.
**Features relacionadas:** PO-073, RN-052, RN-026, RN-033, RN-035, ADR-027.
**Status:** Ativa — pendente de correcao de codigo

### RN-053 - Velocidade ofertada deixa de ser exibida na linha expandida de RE/RI/Mapa Calor
**Descricao:** A linha expandida de cada subatividade (`RedeExterna`/`RedeInterna`/`MapaCalor`) na tela de Enderecos Lastmile e na Tela de Setor deixa de mostrar o campo "Velocidade ofertada" (referencia somente-leitura vinda de `dados_api.velocidade_dl_ofertada`, exibida ate agora junto com Setor/Parceiro, RN-024). Vale para as tres subatividades, que compartilham a mesma partial de exibicao.
**Contexto:** Usuario pediu para tirar "Velocidade ofertada" das subatividades. Investigacao do Orquestrador confirmou que o campo nunca teve criterio proprio na RN-024 (que descreve a referencia da API citando setor/parceiro/custo de implantacao/custo recorrente — nao "velocidade ofertada"): ele existia somente no codigo (`Escola._referencia_rede`/`_formatar_velocidade`, `apps/escolas/models.py`) e no template (`escola_rede_row.html`), sem registro formal — lacuna de documentacao (CLAUDE.md secao 4). Confirmado tambem que o campo nao aparece na exportacao CSV de Setores e Escolas (PO-071/RN-048/049) — a remocao nao afeta a planilha.
**Criterios:**
- a linha expandida de RE, RI e Mapa Calor (grid global de Enderecos Lastmile e Tela de Setor, mesma partial) deixa de exibir o rotulo e o valor de "Velocidade ofertada";
- vale para as tres subatividades, nas duas variantes da linha (edicao em cascata e leitura simples);
- nao altera a exportacao CSV de Setores e Escolas (PO-071) — o campo nunca fez parte dela;
- demais dados de referencia da API (Setor, Parceiro, RN-024) continuam exibidos como estao.
**Excecoes:** a extracao/formatacao interna do dado (`Escola._referencia_rede` continua montando a chave `velocidade_ofertada`, `_formatar_velocidade`, leitura de `dados_api.velocidade_dl_ofertada`) permanece intacta no model, sem uso por nenhuma tela apos esta mudanca. Usuario confirmou, em 2026-08-13, manter o codigo do model e os testes existentes (`apps/escolas/tests.py`, `apps/leads/tests.py`) como estao — escopo fechado somente na remocao da exibicao.
**Impacto tecnico:** remocao do bloco de exibicao (rotulo + valor) em `apps/leads/templates/leads/partials/escola_rede_row.html` (duas ocorrencias, uma por variante de linha). Sem migration — o dado nunca foi coluna propria (vem de dentro do JSON `dados_api`). Nao altera `apps/escolas/models.py` nem os testes existentes (RN mantida sem impacto no model/testes, por decisao do usuario).
**Features relacionadas:** PO-074, RN-024, RN-043, ADR-013.
**Status:** Ativa

### RN-054 - Grupo dedicado "Setor" controla a visibilidade do menu e das telas de Setores
**Descricao:** O item de menu "Setores" e as views `setores_list`/`setor_detail` (`apps.leads`, RN-027) deixam de exigir o grupo `LastMile` e passam a exigir um grupo proprio, `Setor` — mesmo padrao ja usado pelos demais modulos do sistema (um grupo dedicado por modulo: Parceiro, Backoffice, Administrador). Superusuario continua com acesso irrestrito, como em todos os outros grupos.
**Contexto:** Usuario pediu, em 2026-08-13, que o modulo "Setores" tenha controle de acesso proprio, para nao depender de pertencer ao grupo LastMile. Resolve a pendencia que a ADR-016 ja deixava registrada ("restringir cada tela de Setor a um grupo/time especifico de usuarios").
**Criterios:**
- usuario sem o grupo `Setor` (e sem ser superusuario) nao ve o item "Setores" no menu lateral nem acessa `/prospeccao/setores/` ou `/prospeccao/setores/<nome>/` (403);
- usuario no grupo `Setor` ve o item de menu e acessa as rotas, sujeito a RN-055 (permissao por Setor individual dentro do modulo);
- o grupo `Setor` (concessao de modulo) e independente do grupo `LastMile` — pertencer a um nao implica pertencer ao outro.
**Excecoes:** superusuario sempre tem acesso, como nos demais grupos do sistema.
**Impacto tecnico:** troca do `user_passes_test` de `setores_list`/`setor_detail` (hoje `grupo_LastMile_required`) por um novo `grupo_Setor_required`, no mesmo padrao dos demais (`apps/leads/views.py`); ajuste da condicao do menu em `core/base.html` (hoje `has_group:"LastMile" and nomes_setor_menu"`) para usar o grupo `Setor`; criacao do grupo `Setor` (fixture ou cadastro manual via Admin, a criterio do Dev). Ver ADR-028.
**Features relacionadas:** PO-075, PO-052, RN-025, RN-027, ADR-016, ADR-028.
**Status:** Ativa

### RN-055 - Permissao individual por nome de Setor dentro do modulo Setores
**Descricao:** Dentro do modulo "Setores" (RN-054), cada usuario do grupo `Setor` so ve e acessa os nomes de Setor (ex.: "Comercial", "Lastmile") explicitamente concedidos a ele — nao automaticamente todos os nomes cadastrados no catalogo (RN-025).
**Contexto:** Usuario confirmou, em 2026-08-13, que a concessao deve ser individual por Setor, nao apenas por acao (ver/criar/editar) e nao apenas por pertencer ao grupo do modulo. Como o mesmo nome de Setor se repete em Processos diferentes (RN-025/ADR-014 — "Suprimentos" do Processo de RE e "Suprimentos" do Processo de RI sao duas linhas distintas, deliberadamente espelhadas), a concessao e por **nome**, no mesmo criterio de agrupamento ja usado pela RN-027/ADR-016 — nao por linha de `Setor`.
**Criterios:**
- o menu "Setores" lista somente os nomes concedidos ao usuario logado (intersecao entre nomes cadastrados e nomes concedidos a ele), nao todos os nomes distintos cadastrados;
- `GET /prospeccao/setores/<nome>/` retorna 403 se o nome solicitado nao estiver entre os concedidos ao usuario, mesmo que o nome exista no catalogo e o usuario pertenca ao grupo `Setor`;
- usuario sem nenhum Setor concedido nao ve a secao "Setores" no menu — mesmo comportamento ja aplicado hoje quando a lista de nomes esta vazia;
- superusuario continua vendo e acessando todos os Setores, sem necessidade de concessao explicita.
**Excecoes:** superusuario.
**Impacto tecnico:** nova relacao de concessao entre usuario e nome de Setor — modelagem exata (tabela dedicada, por exemplo) a criterio do Dev (decisao tecnica reversivel e de baixo risco); tela ou Admin padrao para um gestor conceder/revogar Setores por usuario, a decidir pelo Dev. Ver ADR-028.
**Features relacionadas:** PO-075, RN-025, RN-054, ADR-028.
**Status:** Ativa

### RN-057 - Dados tecnicos EACE (Velocidade Minima, Kit Inicial, TARGET EACE) por Escola, vindos do DashboardEACE
**Descricao:** Cada Escola passa a exibir tres dados tecnicos EACE — Velocidade Minima, Kit Inicial e TARGET EACE —, sempre somente leitura (nenhuma edicao pelo SGP). Velocidade Minima e Kit Inicial vem da sincronizacao com o DashboardEACE, um valor proprio por Escola. **TARGET EACE e diferente dos outros dois: nao e um valor armazenado por Escola** — e derivado (lookup) por UF da Escola + velocidade contratada, contra uma tabela de referencia propria do SGP (`TargetRedeExterna`, nome de trabalho — ver ADR-029), espelhada da tabela `target_rede_externa` do banco de origem do DashboardEACE. A exibicao dos tres ocorre dentro da area de Campos vinculada a Atividade Principal (Escola), RN-031/RN-037/RN-038.
**Contexto:** Usuario perguntou, em 2026-08-13, se ja existia no banco uma tabela com esses tres dados por escola, pedindo para exibi-los dentro de "Campos" (Atividade Principal). Investigacao do Orquestrador confirmou que nao existe hoje nenhum dado com esses nomes (nem coluna, nem Campo cadastrado, nem confirmacao dentro do JSON `dados_api` da sincronizacao). Questionado sobre a origem, usuario confirmou o cenario A: os tres valores vem do DashboardEACE. Investigando o backup real fornecido pelo usuario, o Orquestrador identificou que TARGET EACE nao e um dado por escola — e um valor de referencia por UF/velocidade. Questionado sobre como tratar isso, o usuario confirmou, em 2026-08-13: "essa tabela: 'target_rede_externa' informa o valor da rede externa que o cliente EACE disponibilizada para nós, esse é o TARGET EACE. preciso dessa tabela toda no nosso sistema, vamos usar para pegar os valores das velocidades por estado e colocar na escola" — ou seja, replicar a tabela de referencia inteira no SGP (ver ADR-029), e nao guardar um valor individual por Escola.
**Criterios:**
- Velocidade Minima e Kit Inicial sao lidos da sincronizacao com o DashboardEACE (`apps.escolas.Escola`), nunca digitados manualmente no SGP; cada Escola tem seu proprio valor;
- TARGET EACE **nao e lido da sincronizacao de Escola** — e derivado por consulta a uma tabela de referencia propria do SGP (`TargetRedeExterna`, nome de trabalho, ADR-029), casando UF da Escola + velocidade contratada da Escola contra UF + velocidade da tabela de referencia; sem correspondencia exata, o valor fica vazio (nunca inventado);
- a tabela de referencia (`TargetRedeExterna`) e importada por completo (todas as combinacoes UF+velocidade da origem), nao filtrada por escola;
- exibicao dos tres dados dentro da area de Campos vinculada a Atividade Principal (Escola, RN-037), sempre somente leitura;
- a sincronizacao (`sincronizar_escolas_dashboard_eace`) passa a preencher Velocidade Minima e Kit Inicial em toda execucao futura, com backfill unico das Escolas ja existentes; a tabela de referencia de TARGET EACE e importada separadamente (sem API — ver ADR-029), nao pela mesma rotina.
**Excecoes:** Escola cujo UF ou velocidade minima nao tiver combinacao exata na tabela de referencia nao mostra TARGET EACE (fica em branco, nunca calculado por aproximacao).

**Impacto tecnico (atualizado em 2026-08-13, apos analise do backup real `eace_jira_backup_20260813.sql.gz`, banco `eace_jira`, fornecido pelo usuario — somente estrutura inspecionada, nenhum dado real copiado para este documento):**

O backup e do banco MySQL de origem do DashboardEACE (Jira mirror), consumido pelo SGP hoje apenas via API HTTP (`apps/integracoes/dashboard_eace`), nunca por acesso direto a este banco. Ele confirma nomes/tipos de coluna reais, mas nao garante por si so que cada campo esteja exposto pela API HTTP — a confirmacao final depende do Swagger (`/docs`) do DashboardEACE ou de uma sincronizacao real.

- **Velocidade Minima — confirmado com alta confianca.** Existe `issues.velocidade_dl_minima` (`decimal(10,2)`, sem sufixo de unidade) e tambem `escolas.velocidade_dl_minima_mbps` (`int`), em tabelas diferentes do mesmo banco. A tabela `escolas` esta **vazia** nesta copia do backup (0 linhas); `issues` tem dados. Isso, cruzado com o fato de `velocidade_dl_ofertada` (mesmo padrao "sem sufixo") ja ser a chave confirmada em produção dentro de `dados_api` (RN-024/RN-053/PO-046), indica que o campo real vindo da API deve chamar-se `velocidade_dl_minima` (nao `velocidade_dl_minima_mbps`). Promover para `Escola.velocidade_dl_minima` (`Decimal`).
- **Kit Inicial — provavel, confianca media.** Melhor candidato e `issues.kit_wifi` (`decimal(10,2)`), ao lado de `ap_adicional` e `nobreak` (mesmo grupo de equipamento, sugerindo "kit inicial" vs. "equipamento adicional"). Nao ha, no dump, nenhuma coluna literalmente chamada `kit_inicial` — o nome de exibicao do usuario e uma tradução/apelido do time, nao o nome tecnico. Antes de fechar definitivamente, confirmar com o time EACE ou no Swagger que `kit_wifi` e de fato o que o usuario chama de "Kit Inicial" (nao confundir com a tabela `valor_kit`, que e um catalogo de preco por tipo de kit — `kit` (varchar) + `valor_lpu_mega` —, sem relacao 1-para-1 direta com `kit_wifi`).
- **TARGET EACE — decisao de arquitetura tomada em 2026-08-13 (ADR-029).** Nao e coluna por escola. Confirmado com o usuario: a tabela `target_rede_externa` (`uf` + `velocidade_mbps` -> `valor`, ~78 combinacoes na origem) e replicada por completo no SGP como catalogo proprio (nome de trabalho `TargetRedeExterna`); o TARGET EACE de uma Escola e sempre um lookup (UF + velocidade), nunca um valor copiado/gravado na linha da Escola. Nao ha FK direta de Escola para essa tabela. Sem endpoint de API para isso (nao documentado em `API_EXTERNA.md`) — importacao inicial e futuras atualizacoes sao manuais (mecanismo a definir pelo Dev: management command ou Admin), mesmo padrao ja aceito para os catalogos Setor/Processo/Campo. Atencao tecnica para o Dev: `velocidade_mbps` na origem e `int` (match exato); `Escola.velocidade_dl_minima` (Parte 1) e `decimal` — o cruzamento precisa tratar esse mismatch de tipo para nao falhar silenciosamente.
- Promover Velocidade Minima e (apos confirmacao) Kit Inicial de dentro de `Escola.dados_api` (JSON) para colunas tipadas proprias em `apps.escolas.Escola` continua sendo decisao incremental ja prevista na ADR-010 (sem exigir nova ADR); ajustar `apps/escolas/services.py`/comando `sincronizar_escolas_dashboard_eace` para preenche-las; criar a tabela de referencia `TargetRedeExterna` (ADR-029) e a importacao inicial dos dados; exibir os tres valores confirmados dentro da area de Campos vinculada a Escola (RN-031/037/038), sempre somente leitura. A sincronizacao automatica de Escola continua sem rodar contra a API real — `DASHBOARD_EACE_URL`/`DASHBOARD_EACE_TOKEN` continuam vazias (pendencia da ADR-010); isso nao impede a modelagem/migracao, so a populacao automatica de Velocidade Minima/Kit Inicial (a tabela de referencia de TARGET EACE independe dessa pendencia, pois nunca dependeu da API).
**Features relacionadas:** PO-076, RN-024, RN-031, RN-037, RN-038, ADR-010, ADR-029.
**Status:** Implementada pelo Dev (PO-076), aguardando QA — `Escola.velocidade_dl_minima`/`Escola.kit_inicial` (colunas tipadas, preenchidas por `sincronizar_escolas`, com backfill de migracao) e o catalogo `TargetRedeExterna` (ADR-029, com `Escola.target_eace` como lookup somente-leitura, sem FK) criados; os tres dados exibidos, somente leitura, no modal "Campos" da Escola (mesmo acionado pela RN-037/038, sem usar o mecanismo Campo/CampoValor — RN-038 nao se aplica). Pendencia secundaria (nao bloqueia): confirmar `kit_wifi` = "Kit Inicial" com o time EACE; catalogo `TargetRedeExterna` fica vazio no banco ate alguem rodar a importacao (`importar_target_rede_externa`) com dados reais exportados da origem, ou cadastrar manualmente pelo Admin.

### RN-058 - Tela "Acesso" (apps.core_admin) concede/revoga modulo do menu e Setor individual
**Descricao:** Dentro da area "Administracao" ja existente (`apps.core_admin`), uma tela "Acesso" permite, por usuario selecionado, conceder ou revogar (a) pertencimento a cada um dos 6 grupos/modulos do menu principal (`LastMile`/Projeto, `Setor`/Setores, `Parceiro`, `Backoffice`, `Gestao`, `Administrador`) e (b) quais nomes de Setor individuais (RN-025/RN-055) esse usuario pode ver/acessar dentro do modulo "Setores" — em um unico formulario, sem depender do Django Admin nativo.
**Contexto:** Usuario relatou (PO-075, 2026-08-13) dificuldade real em conceder Setor individual usando o Django Admin nativo em duas telas separadas (grupo do usuario + `AcessoSetor`, sem selecao multipla). Pediu, na sequencia, uma tela unica dentro da area propria "Administracao" do sistema. Decisao registrada na ADR-030.
**Criterios:**
- acesso a tela "Acesso" restrito ao grupo de menu `Administrador` (`has_group`/`user_passes_test`, mesmo padrao das demais paginas de `apps.core_admin`) — nao restrito a superusuario Django; superusuario continua com acesso, como em qualquer grupo do sistema;
- lista todos os 6 modulos/grupos hoje existentes, inclusive `Administrador` — revogar `Administrador` de qualquer usuario (inclusive do proprio usuario logado) exige aviso explicito de confirmacao de risco de autoexclusao antes de efetivar;
- concede e revoga pertencimento a grupo (modulo) e concede e revoga Setor individual (`AcessoSetor`) no mesmo formulario, por usuario selecionado;
- antes de qualquer alteracao, a tela mostra o estado atual do usuario selecionado: quais modulos ele ja tem e quais Setores ja estao concedidos a ele (auditoria visual, nao e somente formulario de criacao).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** nenhum model novo — reaproveita `django.contrib.auth.models.Group` (grupos ja criados por `ops/setup_speed.py`) e `apps.leads.models.AcessoSetor` (RN-055/ADR-028); nova view/formulario/template/URL em `apps.core_admin`, mesmo padrao das paginas Processos/Campos/Setor-Escopo. Ver ADR-030.
**Features relacionadas:** PO-077, PO-075, RN-054, RN-055, ADR-028, ADR-030.
**Status:** Ativa

### RN-059 - Concessao de Setor individual pela tela Acesso inclui automaticamente o usuario no grupo Setor
**Descricao:** Ao conceder, pela tela "Acesso" (RN-058), qualquer nome de Setor individual a um usuario que ainda nao pertence ao grupo Django `Setor` (RN-054), o sistema inclui esse usuario no grupo `Setor` automaticamente, sem exigir um passo manual separado. Revogar um Setor individual, por outro lado, **nao** remove automaticamente o usuario do grupo `Setor` — revogar o grupo em si e uma acao separada, tambem disponivel na tela "Acesso".
**Contexto:** Usuario confirmou (2026-08-13) que a concessao de Setor individual deve incluir automaticamente o usuario no grupo `Setor`, eliminando a friccao de duas etapas que causou a dificuldade relatada na PO-075. Decisao registrada na ADR-030.
**Criterios:**
- conceder um Setor individual a usuario fora do grupo `Setor` adiciona esse usuario ao grupo `Setor` como efeito colateral da mesma acao, na mesma tela;
- conceder um Setor individual a usuario ja pertencente ao grupo `Setor` nao tem efeito adicional sobre o grupo (idempotente);
- revogar um Setor individual nunca remove o usuario do grupo `Setor` — usuario sem nenhum Setor concedido, mas ainda no grupo, simplesmente nao ve a secao "Setores" no menu (comportamento ja existente da RN-055);
- revogar o grupo `Setor` em si (modulo inteiro) e uma acao independente, tambem disponivel na tela "Acesso" (RN-058), e nao apaga os registros de `AcessoSetor` do usuario (dado dormente, sem efeito visivel enquanto o usuario nao pertencer ao grupo).
**Excecoes:** nenhuma conhecida.
**Impacto tecnico:** logica de auto-inclusao implementada na view/formulario da tela "Acesso" (`apps.core_admin`), ao salvar concessao de `AcessoSetor` — sem mudanca de model. Ver ADR-030, RN-058.
**Features relacionadas:** PO-077, RN-054, RN-055, RN-058, ADR-028, ADR-030.
**Status:** Ativa

## Historico de Alteracoes
| Data | Regra | Alteracao |
|---|---|---|
| 2026-08-13 | RN-058, RN-059 criadas | Usuario pediu tela unica "Acesso" (apps.core_admin) para conceder/revogar modulo do menu e Setor individual num lugar so, resolvendo a friccao relatada na PO-075; decidiu local (area propria, nao Django Admin), quem acessa (grupo Administrador), auto-inclusao no grupo Setor ao conceder Setor individual, e conceder/revogar no mesmo lugar; Orquestrador decidiu (Lei 9 CLAUDE.md, reversivel e baixo risco) incluir os 6 modulos inclusive Administrador (com aviso de autoexclusao) e mostrar estado atual do usuario (ADR-030) |
| 2026-08-13 | RN-057 atualizada de novo | Usuario decidiu como obter TARGET EACE: replicar a tabela de referencia `target_rede_externa` (UF+velocidade -> valor) por completo no SGP, com o valor por escola sempre derivado por lookup (UF+velocidade), nunca armazenado na linha da Escola (ADR-029) |
| 2026-08-13 | RN-057 atualizada | Usuario forneceu backup real do banco de origem (`eace_jira_backup_20260813.sql.gz`). Orquestrador inspecionou somente a estrutura (sem copiar dados): confirmou `velocidade_dl_minima` com alta confianca, `kit_wifi` como candidato provavel para Kit Inicial, e que TARGET EACE nao e coluna por escola (vem de tabela de referencia `target_rede_externa`, uf+velocidade -> valor, sem endpoint documentado que a exponha) — decisao de arquitetura ainda pendente so para esse ultimo campo |
| 2026-08-13 | RN-057 criada | Usuario perguntou se ja existiam no banco os dados tecnicos EACE (Velocidade Minima, Kit Inicial, TARGET EACE) por escola, pedindo exibicao dentro de Campos (Atividade Principal); confirmou que vem do DashboardEACE, um valor por escola (cenario A). Regra registrada como Pendente — bloqueada por schema/credenciais nao confirmados (ver ADR-010, PO-076) |
| 2026-08-13 | RN-056 criada e corrigida 2x no mesmo dia; RN-052 anotada | Usuario esclareceu criterio de obrigatoriedade de Responsavel ao mudar/atribuir Setor. 1a correcao: Orquestrador achou divergencia por leitura incompleta do codigo, Dev nao achou bug e reverteu a nota. 2a correcao: usuario reportou que o bloqueio persistia na primeira atribuicao pelo grid global (sem Setor ainda) — escopo da regra estava incompleto; RN-056 ampliada para nunca exigir Responsavel fora da Tela do proprio Setor; correcao de codigo fica pendente com o Dev |
| 2026-07-09 | RN-001 a RN-005 | Criacao inicial a partir do desenho da automacao de resolucao de O.S. de atendimento (ADR-002) |
| 2026-07-09 | RN-002, RN-003 substituidas; RN-006 a RN-009 criadas | Usuario reverteu execucao unitaria para lote via planilha, com anexo condicional e ZIP de documentos (ADR-003) |
| 2026-07-09 | RN-010 criada; RN-004 ampliada | Usuario identificou que o fechamento de O.S. pode gerar nova O.S. via workflow do IXC; fechamento passa a repetir até esgotar (ADR-004) |
| 2026-07-13 | RN-011 criada | Usuario solicitou tornar o menu de exibicao de automacoes configuravel em vez de fixo em template, com Administrador como padrao |
| 2026-07-21 | RN-012, RN-013, RN-014 criadas; RN-010 ampliada | Mapeamento de PO-013 encontrou 3 comportamentos ja implementados e nao documentados (fechamento parcial opcional, confirmacao explicita, gate de status do atendimento); usuario confirmou manter e documentar todos |
| 2026-07-24 | RN-015 criada | Investigacao do log_integracao_274 mostrou CNPJ compartilhado por varias escolas municipais bloqueando cadastro; usuario confirmou manter bloqueio por CNPJ, mas exigir mensagem explicita do campo de correspondencia |
| 2026-07-24 | RN-016 criada | Usuario pediu para antecipar a deteccao de CNPJ duplicado (dentro da planilha e contra o IXC) para a validacao previa, em vez de descobrir so na hora do envio; confirmou bloqueio tudo-ou-nada e consulta ao IXC durante a validacao |
| 2026-07-29 | RN-017, RN-018 criadas | Desenho do diagrama `02 · Ciclo de vida da cotacao` levantou o processo de negocio, ate entao nao documentado. Usuario confirmou os dois requisitos obrigatorios de abertura (endereco do IXC + provedor cadastrado) e as transicoes validas de status, incluindo que declinar so e possivel apos Viavel e que Inviavel nao reabre. Registrado que o codigo hoje nao impoe nenhuma transicao |
| 2026-08-06 | RN-019 criada | Usuario identificou, ao operar o IXC manualmente, que o fechamento de O.S. pode exigir escolha obrigatoria de proxima tarefa (tela de decisao); confirmou que a planilha de resolucao em massa deve ganhar uma nova coluna para essa informacao |
| 2026-08-06 | RN-020 criada | Usuario identificou que um atendimento pode ter mais de um documento a anexar; confirmou 3 colunas de nome de arquivo mais uma coluna de controle Mais_de_um_anexo (Sim/Nao), no mesmo padrao das demais flags da planilha |
| 2026-08-06 | RN-021 criada | Usuario perguntou como atribuir o fechamento a outro colaborador (hoje sempre usa quem esta logado); confirmou resolucao por e-mail (nao por ID do IXC) com flag Sim/Nao — Informar_Colaborador/Email_Colaborador |
| 2026-08-06 | RN-022 criada | Usuario relatou nao ter visibilidade de progresso em execucoes longas (~18 min, 148 linhas); confirmou manter execucao sincrona e adicionar visibilidade via polling, sem tornar a automacao assincrona |
| 2026-08-07 | RN-017 ampliada | Usuario decidiu desativar a sincronizacao automatica de Cliente/Endereco com o IXC (ADR-008); endereco passa a ser importado manualmente. Confirmado desligar as 4 rotinas de sincronizacao, mesmo sabendo do efeito colateral em apps/leads e apps/partners |
| 2026-08-07 | RN-017 ampliada de novo | Usuario decidiu que os dados do DashboardEACE (ADR-009) nao mapeiam para Cliente/Endereco — vao para um model novo e independente, Escola (ADR-010). Cliente/Endereco fica sem fonte automatica definida |
| 2026-08-07 | RN-023 criada | Usuario decidiu que cada Escola tem processos independentes de Rede Externa (RE) e Rede Interna (RI), geridos pelo proprio sistema (nao espelho da API), cada um com setor/status/parceiro proprios (ADR-012) |
| 2026-08-07 | RN-024 criada | Usuario pediu para ver, na tela de Enderecos Lastmile, os dados de RE/RI que ja vem da API do DashboardEACE, expandindo a linha da escola; confirmado que e so referencia (somente leitura), sem tocar no processo interno RN-023 (ADR-013) |
| 2026-08-07 | RN-025 criada | Usuario pediu tela de cadastro de Processos (Setor/Status), resolvendo a pendencia de vocabulario da RN-023; confirmou que o Processo e generico (sem campo tipo RE/RI) e que RedeExterna/RedeInterna se vinculam a ele (ADR-014) |
| 2026-08-07 | RN-026 criada | Usuario pediu para editar Setor (e Status) do RE/RI direto no grid de Enderecos Lastmile; confirmou edicao em cascata Processo->Setor->Status, com setor/status passando de texto livre para FK (ADR-015). Emenda posterior no mesmo dia: usuario removeu a escolha de Processo da tela (RE/RI usam Processo fixo por tipo) e pediu para nao duplicar a linha de referencia da API com a linha de edicao |
| 2026-08-07 | RN-027 criada | Usuario pediu uma tela por Setor (menu dedicado) mostrando as atividades de RE/RI que estao com cada Setor, para cada time ver so o que e dele (ADR-016) |
| 2026-08-07 | RN-028 criada | Usuario apontou perda de informacao (INEP, Estado, Municipio, Endereco) na tela de Setor; pediu para reaproveitar o grid de Escola da tela global, filtrado por Setor, com edicao habilitada (ADR-017, revoga a restricao de somente-leitura da RN-027) |
| 2026-08-10 | RN-029 criada | Usuario pediu historico e anexo individuais para RE e RI (comentarios, anexos e alteracao de status/dados), com a Escola (pai) vendo o historico combinado dos dois; confirmado exibicao via modal no grid de Enderecos Lastmile, e log automatico so para edicao feita pela tela |
| 2026-08-10 | RN-030 criada | Usuario pediu para restringir a edicao de Parceiro (RE/RI) ao setor de Lastmile e trocar a lista suspensa por um modal; confirmado que "setor de Lastmile" e o Setor de negocio do catalogo (nao o grupo de permissao) e que o modal precisa ser criado, reaproveitando a busca ja usada na conversao de Lead (ADR-018, resolve pendencia da ADR-015) |
| 2026-08-10 | RN-031, RN-032 criadas | Usuario pediu campos personalizados por Setor (tela "Campos" na Administracao) e um modal no grid para reduzir informacao na linha; confirmado valores por RE/RI separados, edicao pela tela atual (mesma regra do Parceiro, RN-030, sem vinculo usuario-Setor) e visibilidade cruzada com edicao restrita ao Setor dono (ADR-019) |
| 2026-08-10 | RN-033 criada | Usuario pediu travar a edicao de Status do RE/RI (Tela de Setor) quando o Setor selecionado deixa de ser o Setor atual, com Status indo automaticamente para "Aguardando" ao enviar a subatividade a outro Setor; confirmado criacao automatica do Status "Aguardando" quando o Setor de destino ainda nao o tiver, e que a trava vale so nas Telas de Setor, nao no grid global |
| 2026-08-13 | RN-054, RN-055 criadas; RN-027 ampliada | Usuario pediu grupo de permissao proprio para o modulo "Setores" (nao mais atrelado ao grupo LastMile) e permissao individual por Setor dentro do modulo, resolvendo a pendencia ja registrada na ADR-016 (ADR-028) |
| 2026-08-10 | RN-034 criada | Usuario pediu rota para excluir Status dentro de um Setor no catalogo de Processos, resolvendo parcialmente a pendencia de exclusao da RN-025/ADR-014 (somente para Status); confirmado permitir exclusao mesmo com Status em uso, deixando `status` em branco nos RE/RI afetados via `SET_NULL` ja existente (ADR-020) |
| 2026-08-10 | RN-035 criada; RN-026 revogada parcialmente; RN-033 corrigida | Usuario pediu que, no grid global de Enderecos Lastmile (menu Projeto -> Endereços), somente Setor continue editavel — Status deixa de ser escolhido manualmente e passa a ser sempre "Novo" (status inicial); confirmado que a mudanca vale so para o grid global, sem afetar a Tela de Setor (RN-027/RN-028), que continua com a regra da RN-033 ("Aguardando") |
| 2026-08-10 | RN-036 criada | Usuario pediu rotas de editar e excluir na tela de Campos, resolvendo a pendencia "fase 2" da ADR-019/RN-031; confirmado exclusao em cascata dos `CampoValor` com confirmacao explicita, e troca de tipo livre mesmo com valores ja gravados, sem limpeza automatica (ADR-021) |
| 2026-08-10 | RN-037 criada | Usuario pediu uma tela "Setor" separada na Administracao para tratar o Setor (RN-025) como catalogo global, escolhendo se as informacoes de cada Setor aparecem na Escola (atividade principal) ou em RE/RI (sub-atividades, podendo ser uma ou as duas); confirmado que e o mesmo Setor ja existente, e que Campos ja cadastrados recebem escopo padrao RE e RI (ADR-022) |
| 2026-08-10 | RN-037 substituida; RN-038 criada | Apos o Dev construir a tela da RN-037 e o usuario ve-la, identificou entendimento errado: a tela "Setor" e independente do Setor de Processos (sem exigir Processo), cria Setor e Campos informativos juntos, com valor fixo (nao por escola) e exibicao nao exclusiva (Escola, RE e RI podem ser marcados ao mesmo tempo), sempre somente leitura, aparecendo como mais um grupo no modal de Campos ja existente (RN-032) (ADR-023, substitui ADR-022) |
| 2026-08-11 | RN-039 criada | Usuario pediu que o Setor "Implantacao", ao receber o Status "Agendando Parceiro", mostre um campo "Inicio Implantacao" e calcule automaticamente "Data Final Implantacao" (72 horas depois, somente leitura); confirmado mecanismo generico (Status condicionante + tipo de Campo Calculado, reutilizavel por qualquer Setor) e precisao somente de data, sem horario (ADR-024) |
| 2026-08-11 | RN-040 criada; RN-029 ampliada | Usuario pediu que "Inicio Implantacao" e "Data Final Implantacao" (RN-039) ficassem no historico; confirmado alcance generico (qualquer Campo personalizado, qualquer Setor, RN-031/032) gerando `RegistroHistorico`, com o valor calculado embutido no registro do Campo base (Campo Calculado nunca tem `CampoValor` proprio, ADR-024) |
| 2026-08-11 | RN-041 criada | Usuario pediu formato "De/Para" na mesma linha para a alteracao de Campo no historico, com data/hora/usuario/Setor abaixo, mais largura (+20%) e menos espaco vazio no modal; identificado que `RegistroHistorico` nao captura Setor nem estrutura valor anterior/novo hoje — extensao aplicada a qualquer registro tipo sistema (Setor/Status RN-026, Parceiro RN-030, Campo RN-040), mesmo alcance generico ja adotado |
| 2026-08-11 | RN-041 ampliada | Dev identificou, ao implementar, que a regra nao dizia o que fazer quando mais de um campo muda no mesmo salvamento (ex.: cascata Setor→Status); usuario confirmou um `RegistroHistorico` estruturado por campo alterado, em vez de um registro so com frase combinada |
| 2026-08-11 | RN-042 criada | Usuario pediu que a opcao de e-mail do sistema se adeque ao layout Escola (ticket principal) e RE/RI (sub-tickets); confirmado que log de RE e RI sao individuais entre si e que e-mail enviado pela Escola fica visivel pelas duas sub-atividades, mesmo padrao de visibilidade ja usado pela RN-029 |
| 2026-08-11 | RN-042 ampliada | Usuario confirmou reaproveitar a mesma caixa/credenciais de e-mail (Microsoft Graph) ja usadas para cotacao, e definiu o numero de rastreio do e-mail: data do dia do envio + INEP da Escola + sufixo do nivel (RE, RI ou Global) |
| 2026-08-12 | RN-044 criada | Usuario pediu para adaptar, na Tela do Setor "Lastmile", o processo antigo de cotacao com N Parceiros por RE/RI (so um vencedor); confirmado Parceiro preenchido automaticamente pelo vencedor, escopo so RE/RI, sem dados comerciais por candidato, e sem transicao automatica de Status (ADR-026) |
| 2026-08-12 | RN-045 criada | Usuario pediu tela de "Provedores" (grid + criar novo) dentro do menu Projeto; identificado que o item existente com esse rotulo abria a tela de Leads, nao um cadastro de Partner; confirmado que "Provedores" e o cadastro de Partner, em tela nova e independente da tela "Parceiros" ja existente; item antigo renomeado para "Leads" para nao perder o unico acesso aquela tela |
| 2026-08-12 | RN-045 revogada parcialmente (item "Leads"); RN-046 criada | Usuario aprovou a tela de Provedores (PO-069) e pediu para retirar do menu o item "Leads" (rota `lead_list` continua existindo, so sem entrada de menu) e para criar rota de editar Provedor (Partner), reaproveitando os mesmos campos basicos e o `PartnerForm` |
| 2026-08-12 | RN-047 criada | Usuario pediu tela de Importacao e Exportacao (Administracao) com card de exportacao completa dos dados de negocio em CSV; confirmado formato longo (Setor/Global, Modulo, Registro, Campo, Valor) e escopo restrito a modulos de negocio, sem tabelas tecnicas nem campos de credencial |
| 2026-08-12 | RN-047 substituida; RN-048 criada | Usuario testou a entrega da RN-047 e pediu para restringir a exportacao a Setores e Escolas, com cada campo em uma coluna (nao mais uma linha); confirmado replicar as colunas ja existentes na tela de Setor (Escola + Setor/Parceiro/Status de RE/RI/Mapa Calor), uma linha por Escola |
| 2026-08-12 | RN-049 criada | Usuario pediu para os Campos personalizados (RN-031) tambem entrarem na exportacao de Setores e Escolas, aparecendo automaticamente ao criar um Campo novo; decisao de como cada Campo vira coluna reaproveita a logica de escopo/valor ja implementada para o modal (RN-032/037/039/040) |
| 2026-08-12 | RN-050 criada | Usuario aprovou a exportacao de dados e pediu tambem uma opcao de baixar a planilha como modelo vazio (so colunas), alem da opcao de baixar com todos os dados do banco, no mesmo card |
| 2026-08-12 | RN-051 criada | Usuario pediu para separar em colunas proprias (planilha e banco) as informacoes hoje misturadas no texto de "Endereco" da Escola; investigacao do Orquestrador confirmou que o texto de origem (DashboardEACE) nao tem formato fixo, so o CEP e 100% confiavel de extrair; usuario confirmou extracao de melhor esforco para Logradouro/Numero/Bairro, sem apagar o texto original |
| 2026-08-11 | RN-042 implementada (impacto tecnico registrado) | Dev implementou a PO-066: nao foi preciso estender `RegistroHistorico` (GenericForeignKey ja existente resolve a visibilidade por nivel); `historico_combinado_escola` passou a incluir tambem os registros do nivel da Escola, ja e a mesma tela que atua como "historico da Escola" e "visao combinada", sem tela nova; numero de rastreio usa prefixo fixo `ESC-` para nunca colidir com o codigo numerico da cotacao |
| 2026-08-11 | RN-043 criada | Usuario pediu cadastro de subatividades ilimitado pelo Admin; investigacao mostrou que RE/RI sao hoje dois models hardcoded, nao um catalogo dinamico, e que generalizar isso e refatoracao de grande porte. Usuario decidiu adiar a generalizacao (ADR-025) e manter o pedido concreto: terceira subatividade fixa "Mapa Calor", implementada em codigo pelo Dev no mesmo molde de RE/RI, com o conjunto completo de campos/comportamentos (setor, status, parceiro, dados adicionais, historico, Campos personalizados, e-mail) |
| 2026-08-12 | RN-052 criada (Pendente) | Usuario pediu que toda subatividade (RE/RI/Mapa Calor) tenha Setor, Status e Responsavel, com Responsavel vinculado ao usuario autenticado do sistema; investigacao confirmou Setor/Status ja existem mas sao opcionais (ADR-012/ADR-014), e Responsavel nao existe hoje (unico precedente e `Proposal.responsavel`, apps.partners); registrada como Pendente por depender de decisao do usuario sobre semantica de atribuicao, obrigatoriedade no banco e migracao de dados existentes (CLAUDE.md secao 9) |
| 2026-08-12 | RN-052 ativada; ADR-027 criada; PO-073 criada | Usuario respondeu as 6 perguntas: Responsavel atribuivel/reatribuivel manualmente (mesmo padrao de Parceiro/RN-030 e `Proposal.responsavel`); obrigatoriedade so via UI, campos continuam nullable no banco (sem migrar dados legados); vale para as tres subatividades (RE/RI/Mapa Calor); edicao nas mesmas telas existentes (RN-026/027/028), com a trava da RN-033; Responsavel zerado junto com o Status ao trocar de Setor; gera `RegistroHistorico` no formato De/Para (RN-029/041) |
| 2026-08-13 | RN-053 criada; PO-074 criada | Usuario pediu para tirar "Velocidade ofertada" da linha expandida das subatividades (RE/RI/Mapa Calor); investigacao confirmou que o campo nunca teve criterio proprio na RN-024 e nao esta na exportacao CSV (PO-071); registrada a remocao da exibicao, com o escopo de tambem limpar a extracao interna (`apps/escolas/models.py`) pendente de confirmacao do usuario |
| 2026-08-13 | RN-053 fechada | Usuario confirmou manter intacto o codigo do model (`Escola._referencia_rede`/`_formatar_velocidade`) e os testes existentes — escopo fechado somente na remocao da exibicao no template |
