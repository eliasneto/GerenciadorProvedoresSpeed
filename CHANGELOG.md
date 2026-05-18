# Changelog

Este arquivo registra as versoes publicadas do sistema e os principais itens adicionados ou alterados em cada release.

## v1.5.0 - 2026-05-15

Adicionado:
- automacao administrativa para desativacao/finalizacao de atendimentos no IXC via planilha no Django Admin, com modelo dedicado, confirmacao obrigatoria por linha, auditoria e relatorio final exportavel

Melhorado:
- fluxo administrativo do IXC ajustado para finalizar a O.S. vinculada e encerrar o atendimento sem apagar historico
- modelo de planilha de desativacao de atendimento IXC com `Atendimento_ID`, `OS_ID` opcional, `Mensagem` opcional e `Confirmar_Desativacao`
- area administrativa reorganizada para exibir uma Central de Automações no mesmo estilo do Backoffice, reunindo o importador de provedores e a desativacao de atendimentos IXC

- nova automacao administrativa para cadastro de clientes em massa no IXC, com planilha modelo, auditoria, relatorio final e tratamento de duplicidade por CNPJ/CPF
- auditoria administrativa de `Cadastro de Clientes IXC` adicionada como secao dedicada no Django Admin, com exportacao `CSV` e `Excel`
- exportacoes de auditoria das automacoes padronizadas para abrir os dados em colunas no `Excel` e no `CSV`, removendo duplicacao visual de `JSON` bruto e consolidando metadados do resumo
- telas de auditoria de integracoes padronizadas no Django Admin, com cabecalho contextual, acoes de exportacao mais limpas e remocao do botao manual de adicionar logs
- modelo da planilha de cadastro de clientes IXC refinado com `*` vermelho nos campos obrigatorios, legenda para `Tipo_Assinante_ID` e nome mais claro `Tipo_Cliente_Fiscal`

## v1.4.0 - 2026-05-15

Adicionado:
- identificacao do usuario logado na descricao dos atendimentos abertos no IXC via integracao do BackOffice, registrando quem importou e o horario do envio
- exportacao em `CSV` e `Excel` no detalhe dos `Logs de Integracoes` no admin, com abertura do `dados_json` em colunas para facilitar a analise das linhas importadas e rejeitadas

Melhorado:
- rotina `OS Comercial | Lastmile` mantida com leitura direta da tabela de O.S. por cliente no IXC para ganhar velocidade, preservando o criterio de considerar apenas atendimentos com `login` atrelado
- modelo de importacao de atendimento IXC endurecido com validacao de Excel para campos `*_ID` aceitarem apenas numeros
- backend da importacao de atendimento IXC ajustado para rejeitar `Cliente_ID`, `Login_ID`, `Contrato_ID`, `Filial_ID`, `Assunto_ID` e `Departamento_ID` com texto invalido, mesmo quando o arquivo vier por CSV ou for editado fora do modelo
- auditoria da importacao de logins IXC ajustada para gravar no log exportavel a linha ja enriquecida com `Status_Importacao`, `Mensagem_Importacao` e `ID_IXC` criado
- placeholder do campo `Usuario da Rede` na tela de login ajustado para exibir `Nome do usuario`, removendo o exemplo fixo com login pessoal
- modal de criacao de cotacao por endereco ajustado para usar a opcao `Buscar fora da regiao` reaproveitando os filtros ja existentes de busca, cidade e UF, sem exigir campo extra dedicado
- layout do modal de criacao de cotacao por endereco reorganizado para manter o botao `Criar Cotacoes` visivel, com rodape mais compacto e menor altura da grade rolavel

## v1.3.0 - 2026-05-08

Adicionado:
- nova arquitetura de organizacao do Django Admin com a aba `Auditoria`, consolidando historicos, logs de integracao, sincronizacoes, alteracoes do IXC e auditorias de respostas de e-mail em uma secao dedicada
- auditoria de login com registro de login bem-sucedido, falha de autenticacao e logout, incluindo usuario informado, IP, user agent e horario do evento
- auditoria de restore de backup com registro de usuario, origem do arquivo, nome do backup, sucesso ou erro, restauracao de midia, IP e detalhes da operacao
- auditoria de mudanca de status de cotacao, cobrindo alteracao individual, alteracao em lote, conversao de cotacao viavel e fechamento automatico de outras cotacoes do mesmo endereco

Melhorado:
- estrutura do admin preparada para expansao continua da trilha de auditoria em novas tabelas dedicadas
- detalhe do provedor em `/provedores/empresa/<id>/` ajustado com botao para cadastrar novos enderecos, incluindo formulario dedicado so de endereco e criacao automatica do espelho da prospeccao para o novo local

## v1.2.1 - 2026-05-08

Melhorado:
- correcao da sincronizacao de enderecos do IXC para resolver a UF a partir da cidade do IXC, do mapa de estados do proprio IXC e do codigo IBGE da cidade, inclusive quando o estado vier como ID numerico, evitando fallback indevido para `CE` ou gravacao do ID no campo de UF
- processo de backup endurecido para falhar quando o dump `.sql` vier vazio, impedir restore de SQL vazio e unificar o backup automatico com o mesmo fluxo seguro do backup manual, sem incluir `media/backups` dentro do proprio ZIP
- fluxo de restore ajustado para exibir erros de validacao diretamente na tela e concluir com pagina de sucesso sem depender da sessao atual depois da restauracao
- ajuste da hierarquia visual do botao flutuante de expandir/recolher o menu para ficar abaixo dos modais abertos no sistema
- selo de status do topo tornado dinamico com healthcheck leve do Django, verificacao a cada 90 segundos e atualizacao apenas com a aba visivel para reduzir carga no servidor

## v1.2.0 - 2026-05-05

Adicionado:
- envio de e-mail pela tela `Minhas Cotacoes`
- bloqueio do campo `De` para usar apenas o remetente configurado no sistema
- importacao automatica de respostas de e-mail das cotacoes
- salvamento do arquivo `.eml` no historico da proposta
- fechamento de O.S. via sistema no IXC durante o fluxo de conversao/finalizacao

Melhorado:
- limpeza do texto automatico exibido no historico das respostas de e-mail
- correcao do armazenamento dos anexos `.eml` no diretorio compartilhado `media`
- ajuste na paginacao de `Minhas Cotacoes` para trabalhar em blocos de 20 registros
- padronizacao visual da paginacao de `Minhas Cotacoes` com o restante do sistema
- correcao da rotina de O.S. Comercial | Lastmile para nao descartar logins cedo demais e aceitar mais campos de data no recorte de O.S. alteradas
- padronizacao das telas de enderecos para exibir apenas o ID do IXC, sem mostrar o ID local do sistema
- sincronizacao automatica das respostas de e-mail ajustada para rodar a cada 10 minutos
- botao manual de "Respostas de E-mail" adicionado na tela de Historico de Sincronizacoes
- sincronizacao automatica do cadastro/edicao de leads legados com a base estruturada de empresas e enderecos
- ordenacao do grid de empresas de prospeccao ajustada para mostrar primeiro os leads mais recentes
- resumo de cobertura de parceiros por bairro, cidade e estado adicionado no modal de abertura de cotacao por endereco
- mensagem da regra de duplicidade no modal de abertura de cotacao por endereco reescrita para ficar mais clara
- regra de elegibilidade do modal de abertura de cotacao por endereco corrigida para bloquear apenas o mesmo provedor quando ele ja possui cotacao em Em negociacao no mesmo endereco operacional
- modal de abertura de cotacao por endereco ajustado para permitir prosseguir com provedores disponiveis fora da cobertura conhecida quando nao houver provedor elegivel pela heuristica regional
- correcao do fallback do modal de abertura de cotacao por endereco para criar cotacoes apenas com os provedores selecionados na prospeccao, sem puxar parceiros historicos indevidos da base
- fluxo do modal de abertura de cotacao por endereco ajustado para aguardar o carregamento dos parceiros elegiveis antes de permitir a criacao
- padronizacao da area de prospeccao para a rota canonica `/provedores/`, com ajustes de nomenclatura nas telas para exibir `provedores` e `prospeccao`
- ajuste da rota do numero da cotacao em `Minhas Cotacoes` para abrir diretamente a visao consolidada do lote da cotacao
- simplificacao da comunicacao na tela de conversao da cotacao viavel, com textos mais diretos sobre a finalizacao da O.S. no IXC, ajuste dos nomes dos campos comerciais e botao final alterado para `Salvar`
- tela de importacao administrativa renomeada para `Importador de Provedores`, com novo status `interrompida` para cancelamentos manuais e botao para parar importacoes em andamento
- fluxo de criacao de cotacao Lastmile ajustado para abrir cotacoes apenas para os provedores selecionados na prospeccao, evitando criacoes em massa por parceiros historicos da cobertura
- primeira etapa da regra de cotacao viavel por endereco, com modal para decidir se outras cotacoes em negociacao do mesmo endereco devem ser fechadas automaticamente
- fluxo de alteracao da O.S. no IXC ajustado para deixar o anexo opcional e limitar o seletor aos formatos aceitos pelo IXC
- validacao de backend adicionada para impedir finalizacao da O.S. no IXC enquanto ainda existirem outras cotacoes em negociacao para o mesmo endereco sem a opcao de fechamento automatico
- logs da rotina `OS Comercial | Lastmile` reorganizados para exibir progresso por cliente IXC e resumo dos principais motivos de descarte de tickets
- botao dedicado para parar a rotina `OS Comercial | Lastmile` adicionado na tela de Historico de Sincronizacoes quando houver execucao em andamento
- recorte automatico da rotina `OS Comercial | Lastmile` tornado configuravel por `.env` via `OS_LASTMILE_LOOKBACK_DAYS`, removendo o valor fixo de 10 dias do `docker-compose`
- correcao da sincronizacao de enderecos do IXC para resolver a UF a partir da cidade do IXC quando o login ou contrato nao enviar o estado preenchido, evitando fallback indevido para `CE`
- processo de backup endurecido para falhar quando o dump `.sql` vier vazio, impedir restore de SQL vazio e unificar o backup automatico com o mesmo fluxo seguro do backup manual, sem incluir `media/backups` dentro do proprio ZIP

## v1.1.0 - 2026-04-10

Adicionado:
- fluxo estruturado de prospeccao por empresa e endereco com `LeadEmpresa` e `LeadEndereco`
- listagem de empresas de prospeccao e tela de detalhe de enderecos por empresa
- fluxo Lastmile para enderecos com O.S. Comercial | Lastmile
- abertura rapida de cotacao por endereco no fluxo Lastmile
- vinculo da cotacao com `lead` e `lead_endereco` para rastreabilidade
- visualizacao por operador e novos relatorios operacionais
- painel e rotinas de restore/manual de backup nas ferramentas administrativas
- ambiente de homologacao para publicacao e validacao separada

Melhorado:
- filtros regionais de cotacao por bairro e cidade
- importacao de leads com separacao mais precisa de endereco vindo do Google Maps
- importacao de logins/enderecos com correcao de cidade IXC e separacao entre nome e ID da cidade
- busca por login e abertura inicial de cotacao com usuario responsavel vinculado
- remocao da obrigatoriedade do nome da cotacao na abertura inicial
- correcoes de relatorios, inclusive relatorio de responsavel por endereco
- criacao e manutencao de usuarios com ajustes de nomenclatura e classificacao nos relatorios
- melhorias na integracao de busca de parceiros
- validacoes de deploy, ajustes de migrations e endurecimento de configuracoes do `.env`
- ajustes de menu e refinamentos gerais de navegacao

## v1.0.0 - 2026-03-27

Adicionado:
- base inicial do novo sistema Gerenciador de Parceiros
- autenticacao integrada ao Active Directory
- robo de sincronizacao incremental do IXC com execucao automatica em container dedicado
- historico e logs de sincronizacao para auditoria das rotinas
- modulo de prospeccao com busca de fornecedores e automacao integrada com API/Google
- modulo de clientes com grid tecnico de enderecos e apoio ao fluxo operacional
- modulo BackOffice com importacao de cotacoes
- automacoes de login IXC, cadastro de atendimento IXC e criacao de O.S. no IXC
- rotinas administrativas no painel para operacao e acompanhamento das integracoes
- rotina de backup automatizado do banco e arquivos
- estrutura Docker para web, banco, sincronizador e servicos auxiliares

Melhorado:
- seguranca de permissao no Django e ajustes de autenticacao
- layout geral do sistema e tela de historico
- script de atualizacao/sincronizacao do IXC
- tabela de apoio `DE PARA` e ajustes de integracao
- grid de enderecos e experiencia de navegacao operacional
- configuracoes de `settings`, portas, banco de dados, arquivos estaticos e `docker-compose`
- correcoes sucessivas da rotina de backup ate a versao final 1.0.0
