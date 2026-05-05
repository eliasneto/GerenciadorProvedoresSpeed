# Changelog

Este arquivo registra as versoes publicadas do sistema e os principais itens adicionados ou alterados em cada release.

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
- fluxo do modal de abertura de cotacao por endereco ajustado para aguardar o carregamento dos parceiros elegiveis antes de permitir a criacao

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
