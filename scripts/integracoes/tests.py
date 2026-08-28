from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.clientes.models import Cliente, Endereco, LogAlteracaoIXC, HistoricoSincronizacao
from scripts.integracoes.ixc_sync_clientes import (
    _normalizar_contratos,
    _normalizar_login,
    consultar_ixc,
    extrair_campos_tecnicos_obs,
    extrair_clientes_recentes,
    normalizar_uf,
    resolver_uf_por_ibge,
    salvar_clientes_no_django,
)
from scripts.integracoes.ixc_explorador import explorar_tabela
from apps.integracoes.ixc.services.descobrir_rota_IXC import chamar_ixc
from apps.clientes.management.commands.ixc_faxina import consultar_ixc as consultar_ixc_faxina
from apps.clientes.management.commands.ixc_os_comercial_lastmile import consultar_ixc as consultar_ixc_lastmile
from scripts.integracoes.ixc_primeira_os import consultar_ixc as consultar_ixc_primeira_os
from scripts.integracoes.ixc_finalizacao_service import (
    IXCConsultaIndisponivelError,
    buscar_os_por_id,
    finalizar_os_existente,
    montar_payload_fechamento_real,
    resolver_proxima_tarefa_automatica,
)


class ConsultarIxcTests(SimpleTestCase):
    """Toda chamada ao IXC passa pelo IXCClient (PO-022)."""

    @patch("scripts.integracoes.ixc_sync_clientes._get_ixc_client")
    def test_retorna_corpo_quando_sucesso(self, mock_get_client):
        mock_get_client.return_value.listar.return_value = (200, {"registros": [{"id": "1"}]})
        resultado = consultar_ixc("cliente", {"qtype": "id"})
        self.assertEqual(resultado, {"registros": [{"id": "1"}]})

    @patch("scripts.integracoes.ixc_sync_clientes._get_ixc_client")
    def test_retorna_none_quando_status_de_erro(self, mock_get_client):
        mock_get_client.return_value.listar.return_value = (500, {"type": "error", "message": "falha"})
        self.assertIsNone(consultar_ixc("cliente", {}))

    @patch("scripts.integracoes.ixc_sync_clientes._get_ixc_client")
    def test_retorna_none_quando_corpo_nao_e_json(self, mock_get_client):
        mock_get_client.return_value.listar.return_value = (200, {"raw": "<html>erro</html>"})
        self.assertIsNone(consultar_ixc("cliente", {}))


class BuscarOsPorIdFalhaComunicacaoTests(SimpleTestCase):
    """Bug corrigido: falha de comunicacao com o IXC (timeout, HTTP != 200,
    resposta invalida) precisa ser distinguivel de uma consulta que respondeu
    OK e nao achou o registro — antes, os dois casos viravam 'nao encontrada'."""

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_http_diferente_de_200_levanta_erro_de_comunicacao(self, mock_client_cls):
        mock_client_cls.return_value.listar.return_value = (
            503,
            {"type": "error", "message": "Servico indisponivel"},
        )

        with self.assertRaises(IXCConsultaIndisponivelError):
            buscar_os_por_id("6394")

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_corpo_invalido_levanta_erro_de_comunicacao(self, mock_client_cls):
        mock_client_cls.return_value.listar.return_value = (200, {"raw": "<html>erro</html>"})

        with self.assertRaises(IXCConsultaIndisponivelError):
            buscar_os_por_id("6394")

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_http_200_sem_registros_continua_retornando_vazio(self, mock_client_cls):
        mock_client_cls.return_value.listar.return_value = (200, {"registros": []})

        self.assertEqual(buscar_os_por_id("6394"), {})


class FinalizarOsExistenteFalhaComunicacaoTests(SimpleTestCase):
    """A falha ao consultar a O.S. no IXC (antes ou depois de fechar) nao pode
    ser relatada como 'O.S. nao encontrada'."""

    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_os_por_id")
    def test_falha_ao_buscar_os_antes_de_fechar_nao_diz_nao_encontrada(self, mock_buscar_os):
        mock_buscar_os.side_effect = IXCConsultaIndisponivelError(
            "falha ao consultar a O.S. 6394 no IXC (HTTP 503)"
        )

        resultado = finalizar_os_existente("6394", mensagem="Fechado.")

        self.assertFalse(resultado["ok"])
        self.assertIn("Nao foi possivel confirmar", resultado["message"])
        self.assertNotIn("nao encontrada", resultado["message"])

    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_registros_fechamento_os")
    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_os_por_id")
    def test_falha_ao_confirmar_status_apos_fechar_nao_diz_nao_encontrada(
        self, mock_buscar_os, mock_client_cls, mock_registros_fechamento
    ):
        mock_buscar_os.side_effect = [
            {"id": "6394", "id_wfl_tarefa": "148"},
            IXCConsultaIndisponivelError("falha ao consultar a O.S. 6394 no IXC (HTTP 504)"),
        ]
        mock_client_cls.return_value.escrever.return_value = (200, {"type": "success"})

        resultado = finalizar_os_existente("6394", mensagem="Fechado.")

        self.assertFalse(resultado["ok"])
        self.assertIn("nao foi possivel confirmar o status atualizado", resultado["message"])
        self.assertNotIn("nao encontrada", resultado["message"])
        mock_registros_fechamento.assert_not_called()


class MontarPayloadFechamentoRealTests(SimpleTestCase):
    """RN-019: fechar uma O.S. de decisao exige informar a proxima tarefa."""

    def test_sem_proxima_tarefa_mantem_comportamento_padrao(self):
        payload = montar_payload_fechamento_real({"id": "6394"}, mensagem="Fechado.")

        self.assertEqual(payload["eh_tarefa_decisao"], "N")
        self.assertEqual(payload["id_proxima_tarefa"], "0")

    def test_com_proxima_tarefa_marca_como_tarefa_de_decisao(self):
        payload = montar_payload_fechamento_real(
            {"id": "6394"},
            mensagem="Fechado.",
            id_proxima_tarefa="147",
        )

        self.assertEqual(payload["eh_tarefa_decisao"], "S")
        self.assertEqual(payload["id_proxima_tarefa"], "147")


class ResolverProximaTarefaAutomaticaTests(SimpleTestCase):
    """RN-071: proxima tarefa do workflow resolvida automaticamente, sem o
    usuario precisar descobrir o ID no IXC."""

    def test_tarefa_atual_vazia_nao_chama_ixc(self):
        id_proxima, erro = resolver_proxima_tarefa_automatica("")

        self.assertIsNone(id_proxima)
        self.assertIsNone(erro)

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_tarefa_sem_decisao_nao_exige_proxima_tarefa(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.listar.return_value = (
            200,
            {"registros": [{"id": "140", "decisao": "N", "id_processo": "18", "id_proxima_tarefa": "3"}]},
        )

        id_proxima, erro = resolver_proxima_tarefa_automatica("140")

        self.assertIsNone(id_proxima)
        self.assertIsNone(erro)

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_tarefa_de_decisao_com_um_candidato_resolve_sozinha(self, mock_ixc_client_cls):
        mock_listar = mock_ixc_client_cls.return_value.listar
        mock_listar.side_effect = [
            (200, {"registros": [{
                "id": "150", "decisao": "S", "id_processo": "18",
                "id_proxima_tarefa": "6", "descricao": "Realizar Implantacao EACE",
            }]}),
            (200, {"registros": [
                {"id": "148", "sequencia": "6", "ativo": "S", "descricao": "Processo Cotacao Finalizada"},
            ]}),
        ]

        id_proxima, erro = resolver_proxima_tarefa_automatica("150")

        self.assertEqual(id_proxima, "148")
        self.assertIsNone(erro)

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_tarefa_de_decisao_com_varios_candidatos_usa_mapeamento_conhecido(self, mock_ixc_client_cls):
        mock_listar = mock_ixc_client_cls.return_value.listar
        mock_listar.side_effect = [
            (200, {"registros": [{
                "id": "150", "decisao": "S", "id_processo": "18",
                "id_proxima_tarefa": "6", "descricao": "Realizar Implantacao EACE",
            }]}),
            (200, {"registros": [
                {"id": "148", "sequencia": "6", "ativo": "S", "descricao": "Processo Cotacao Finalizada"},
                {"id": "152", "sequencia": "6", "ativo": "S", "descricao": "Parceiro Declinou"},
            ]}),
        ]

        id_proxima, erro = resolver_proxima_tarefa_automatica("150")

        self.assertEqual(id_proxima, "148")
        self.assertIsNone(erro)

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_tarefa_de_decisao_ambigua_sem_mapeamento_bloqueia_com_opcoes(self, mock_ixc_client_cls):
        mock_listar = mock_ixc_client_cls.return_value.listar
        mock_listar.side_effect = [
            (200, {"registros": [{
                "id": "146", "decisao": "S", "id_processo": "18",
                "id_proxima_tarefa": "5", "descricao": "Realizar Contratacao",
            }]}),
            (200, {"registros": [
                {"id": "147", "sequencia": "5", "ativo": "S", "descricao": "Realizar Implantacao"},
                {"id": "150", "sequencia": "5", "ativo": "S", "descricao": "Realizar Implantacao EACE"},
                {"id": "151", "sequencia": "5", "ativo": "S", "descricao": "Nao Atende Requisitos Tecnicos"},
            ]}),
        ]

        id_proxima, erro = resolver_proxima_tarefa_automatica("146")

        self.assertIsNone(id_proxima)
        self.assertIn("147", erro)
        self.assertIn("150", erro)
        self.assertIn("151", erro)
        self.assertIn("Proxima_Tarefa_ID", erro)

    @patch("scripts.integracoes.ixc_finalizacao_service.IXCClient")
    def test_tarefa_de_decisao_sem_candidatos_bloqueia(self, mock_ixc_client_cls):
        mock_listar = mock_ixc_client_cls.return_value.listar
        mock_listar.side_effect = [
            (200, {"registros": [{
                "id": "999", "decisao": "S", "id_processo": "1",
                "id_proxima_tarefa": "99", "descricao": "Tarefa Teste",
            }]}),
            (200, {"registros": []}),
        ]

        id_proxima, erro = resolver_proxima_tarefa_automatica("999")

        self.assertIsNone(id_proxima)
        self.assertIn("nenhuma tarefa ativa", erro)


class NormalizacaoTests(SimpleTestCase):
    def test_normalizar_uf_aceita_sigla_direta(self):
        self.assertEqual(normalizar_uf("ce"), "CE")

    def test_normalizar_uf_aceita_nome_com_acento(self):
        self.assertEqual(normalizar_uf("Ceará"), "CE")

    def test_normalizar_uf_retorna_padrao_quando_desconhecido(self):
        self.assertEqual(normalizar_uf("", padrao="CE"), "CE")

    def test_resolver_uf_por_ibge(self):
        self.assertEqual(resolver_uf_por_ibge("2304400"), "CE")

    def test_extrair_campos_tecnicos_obs(self):
        obs = "VELOCIDADE: 500 MEGA\nTIPO DE ACESSO: FIBRA\nENTREGA RB: SIM"
        campos = extrair_campos_tecnicos_obs(obs)
        self.assertEqual(campos["velocidade"], "500 MEGA")
        self.assertEqual(campos["tipo_acesso"], "FIBRA")
        self.assertEqual(campos["entrega_rb"], "SIM")


class NormalizarContratosELoginTests(SimpleTestCase):
    """Regressao do bug encontrado no PO-022: o sync incremental passava os
    registros crus do IXC (chaves `id`/`id_filial`) direto para a gravacao,
    que esperava `id_contrato`/`filial_id` (formato so produzido pelo sync
    total) - isso gerava KeyError e o incremental falhava silenciosamente
    (capturado pelo except generico) sempre que um cliente tinha contrato.
    """

    def test_normalizar_contratos_converte_chaves_cruas_do_ixc(self):
        registros_crus = [{
            "id": "77",
            "status": "A",
            "endereco": "Rua X",
            "numero": "10",
            "bairro": "Centro",
            "cidade": "123",
            "uf": "CE",
            "id_filial": "3",
            "vendedor": "9",
        }]
        contratos = _normalizar_contratos(registros_crus)
        self.assertEqual(contratos, [{
            "id_contrato": "77",
            "status": "A",
            "endereco": "Rua X",
            "numero": "10",
            "bairro": "Centro",
            "cidade": "123",
            "uf": "CE",
            "filial_id": "3",
            "agente_id": "9",
        }])

    def test_normalizar_login_usa_chave_circuit_id(self):
        login_cru = {
            "id": "50",
            "id_contrato": "77",
            "login": "cliente@fibra",
            "ativo": "S",
            "agent_circuit_id": " ABC123 ",
            "obs": "",
        }
        login = _normalizar_login(login_cru)
        self.assertEqual(login["circuit_id"], "ABC123")
        self.assertEqual(login["id_login"], "50")
        self.assertEqual(login["login"], "cliente@fibra")


class SalvarClientesNoDjangoTests(TestCase):
    def setUp(self):
        self.historico = HistoricoSincronizacao.objects.create(tipo="total", origem="automatica")

    def _dado_cliente(self, **overrides):
        dado = {
            "id_ixc": "1001",
            "nome_com_id": "1001 - Cliente Teste LTDA",
            "fantasia": "Cliente Teste",
            "cpf_cnpj": "12345678000199",
            "contratos": _normalizar_contratos([{
                "id": "500",
                "status": "A",
                "endereco": "Rua Teste",
                "numero": "100",
                "bairro": "Centro",
                "cidade": "Fortaleza",
                "uf": "CE",
                "id_filial": "1",
                "vendedor": "9",
            }]),
            "logins": [_normalizar_login({
                "id": "900",
                "id_contrato": "500",
                "login": "cliente.teste",
                "ativo": "S",
                "agent_circuit_id": "CIRC-1",
                "obs": "",
                "endereco": "",
                "numero": "",
                "bairro": "",
                "cidade": "",
                "uf": "",
                "cep": "",
            })],
        }
        dado.update(overrides)
        return dado

    def test_grava_cliente_e_endereco_sem_erro_com_contrato_normalizado(self):
        mapa_filiais = {"1": "Filial Matriz"}
        salvar_clientes_no_django([self._dado_cliente()], mapa_filiais, {}, self.historico)

        cliente = Cliente.objects.get(id_ixc="1001")
        self.assertEqual(cliente.razao_social, "1001 - Cliente Teste LTDA")

        endereco = Endereco.objects.get(cliente=cliente, login_ixc="cliente.teste")
        self.assertEqual(endereco.status, "ativo")
        self.assertEqual(endereco.filial_ixc, "Filial Matriz")
        self.assertEqual(endereco.agent_circuit_id, "CIRC-1")
        self.assertEqual(endereco.contrato_id_ixc, "500")

    def test_registra_log_de_alteracao_quando_status_muda(self):
        mapa_filiais = {"1": "Filial Matriz"}
        salvar_clientes_no_django([self._dado_cliente()], mapa_filiais, {}, self.historico)

        dado_cancelado = self._dado_cliente(contratos=_normalizar_contratos([{
            "id": "500", "status": "C", "id_filial": "1",
        }]))
        salvar_clientes_no_django([dado_cancelado], mapa_filiais, {}, self.historico)

        cliente = Cliente.objects.get(id_ixc="1001")
        endereco = Endereco.objects.get(cliente=cliente, login_ixc="cliente.teste")
        self.assertEqual(endereco.status, "cancelado")
        self.assertTrue(
            LogAlteracaoIXC.objects.filter(cliente=cliente, campo_alterado="status").exists()
        )

    def test_registra_log_de_alteracao_quando_filial_muda(self):
        mapa_filiais = {"1": "Filial Matriz", "2": "Filial Sul"}
        salvar_clientes_no_django([self._dado_cliente()], mapa_filiais, {}, self.historico)

        dado_outra_filial = self._dado_cliente(contratos=_normalizar_contratos([{
            "id": "500", "status": "A", "id_filial": "2",
        }]))
        salvar_clientes_no_django([dado_outra_filial], mapa_filiais, {}, self.historico)

        cliente = Cliente.objects.get(id_ixc="1001")
        endereco = Endereco.objects.get(cliente=cliente, login_ixc="cliente.teste")
        self.assertEqual(endereco.filial_ixc, "Filial Sul")
        self.assertTrue(
            LogAlteracaoIXC.objects.filter(cliente=cliente, campo_alterado="filial").exists()
        )


class ExtrairClientesRecentesTests(TestCase):
    """Prova, na ponta a ponta da extracao incremental, que os contratos e
    logins crus do IXC chegam normalizados (nao mais nas chaves cruas que
    causavam o KeyError na gravacao)."""

    def setUp(self):
        self.historico = HistoricoSincronizacao.objects.create(tipo="incremental", origem="automatica")

    @patch("scripts.integracoes.ixc_sync_clientes.consultar_ixc")
    def test_contratos_e_logins_saem_normalizados(self, mock_consultar):
        def fake_consultar(tabela, payload):
            if tabela == "cliente":
                if payload.get("qtype") == "data_atualizacao":
                    return {"registros": [{"id": "1001"}]}
                return None
            if tabela == "radusuarios":
                if payload.get("qtype") == "id":
                    return {"registros": []}
                return {"registros": [{
                    "id": "900", "id_contrato": "500", "login": "cliente.teste",
                    "ativo": "S", "agent_circuit_id": "CIRC-1", "obs": "",
                }]}
            if tabela == "cliente/1001":
                return {"id": "1001", "razao": "Cliente Teste LTDA", "fantasia": "", "cnpj_cpf": "111"}
            if tabela == "cliente_contrato":
                return {"registros": [{
                    "id": "500", "status": "A", "endereco": "Rua Teste",
                    "id_filial": "1", "vendedor": "9",
                }]}
            return None

        mock_consultar.side_effect = fake_consultar

        dados = extrair_clientes_recentes(self.historico, dias_retroativos=1)

        self.assertEqual(len(dados), 1)
        contrato = dados[0]["contratos"][0]
        login = dados[0]["logins"][0]
        self.assertEqual(contrato["id_contrato"], "500")
        self.assertEqual(contrato["filial_id"], "1")
        self.assertEqual(login["circuit_id"], "CIRC-1")


class ExplorarTabelaTests(SimpleTestCase):
    """PO-025: ixc_explorador deixou de usar token hardcoded e passou a usar IXCClient."""

    @patch("scripts.integracoes.ixc_explorador.IXCClient")
    def test_usa_ixcclient_e_nao_estoura_em_sucesso(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.listar.return_value = (
            200, {"registros": [{"id": "1", "razao": "Teste"}]},
        )
        explorar_tabela("cliente")
        mock_ixc_client_cls.return_value.listar.assert_called_once()
        tabela_chamada = mock_ixc_client_cls.return_value.listar.call_args[0][0]
        self.assertEqual(tabela_chamada, "cliente")

    @patch("scripts.integracoes.ixc_explorador.IXCClient")
    def test_nao_estoura_quando_ixc_retorna_erro(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.listar.return_value = (500, {"message": "erro"})
        explorar_tabela("cliente")


class ChamarIxcTests(SimpleTestCase):
    """PO-025: descobrir_rota_IXC.chamar_ixc passou a delegar para o IXCClient."""

    @patch("apps.integracoes.ixc.services.descobrir_rota_IXC.IXCClient")
    def test_delega_para_ixcclient_escrever(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (200, {"type": "success"})
        status_code, body = chamar_ixc({"tipo": "I"})
        self.assertEqual(status_code, 200)
        mock_ixc_client_cls.return_value.escrever.assert_called_once_with("su_ticket", {"tipo": "I"})


class ConsultarIxcNosDemaisScriptsTests(SimpleTestCase):
    """PO-025: ixc_faxina, ixc_os_comercial_lastmile e ixc_primeira_os passaram
    a usar IXCClient em vez de HTTP proprio, com o mesmo contrato (dict em
    sucesso, None em falha)."""

    @patch("apps.clientes.management.commands.ixc_faxina.IXCClient")
    def test_ixc_faxina_retorna_corpo_em_sucesso_e_none_em_falha(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.listar.return_value = (200, {"registros": []})
        self.assertEqual(consultar_ixc_faxina("cliente", {}), {"registros": []})

        mock_ixc_client_cls.return_value.listar.return_value = (500, {"message": "erro"})
        self.assertIsNone(consultar_ixc_faxina("cliente", {}))

    @patch("apps.clientes.management.commands.ixc_os_comercial_lastmile.IXCClient")
    def test_ixc_os_comercial_lastmile_retorna_corpo_em_sucesso_e_none_em_falha(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.listar.return_value = (200, {"registros": []})
        self.assertEqual(consultar_ixc_lastmile("su_ticket", {}), {"registros": []})

        mock_ixc_client_cls.return_value.listar.return_value = (500, {"message": "erro"})
        self.assertIsNone(consultar_ixc_lastmile("su_ticket", {}))

    @patch("scripts.integracoes.ixc_primeira_os.IXCClient")
    def test_ixc_primeira_os_retorna_corpo_em_sucesso_e_none_em_falha(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.listar.return_value = (200, {"registros": []})
        self.assertEqual(consultar_ixc_primeira_os("su_ticket", {}), {"registros": []})

        mock_ixc_client_cls.return_value.listar.return_value = (500, {"message": "erro"})
        self.assertIsNone(consultar_ixc_primeira_os("su_ticket", {}))
