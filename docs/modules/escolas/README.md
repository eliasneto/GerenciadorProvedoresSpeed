# Modulo Escolas

## Objetivo

Gerenciar o dominio de Escolas sincronizadas do DashboardEACE e seus processos internos de conectividade (Rede Externa/Rede Interna), independentes do dominio de Cliente/Endereco/Cotacao.

## Responsabilidades atuais observadas

- model `Escola`, sincronizada por comando manual a partir da API do DashboardEACE (sem agendamento);
- `RedeExterna`/`RedeInterna`: processos 1:1 por Escola, cada um com setor, status, parceiro e dados adicionais proprios;
- catalogo `Processo`/`Setor`/`SetorStatus` e `Campo`/`CampoValor` (campos personalizados por Setor), reaproveitado por RE e RI;
- sem views/urls proprias: as telas de edicao (grid de Enderecos Lastmile, Tela de Setor) vivem em `apps.leads`; as telas de Administracao (Processos, Campos, Setor) vivem em `apps.core_admin`.

## Pontos de atencao

- `SetorEscopo` ainda esta pendente de rework (PO-062) — e a implementacao rejeitada da ADR-022, substituida pela ADR-023 (`SetorInformativo`/`CampoInformativo`, ainda nao construidos);
- sem relacao com `apps.clientes`/`Proposal` — o unico vinculo com o restante do dominio e o `Partner` (parceiro) de RE/RI;
- generalizar para um catalogo administravel de subatividades (alem de RE/RI) foi avaliado e adiado (ADR-025) — qualquer nova subatividade fixa (ex.: PO-067) segue o mesmo padrao hardcoded de RE/RI, sem cadastro pelo usuario.
