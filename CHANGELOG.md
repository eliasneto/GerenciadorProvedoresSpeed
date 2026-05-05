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

## v1.1.0

Base anterior em uso antes da entrada das funcionalidades de e-mail e automacoes mais recentes de O.S.
