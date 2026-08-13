from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.core.models import (
    EmailCotacaoRespostaImportacao,
    EmailEscolaRespostaImportacao,
    RegistroHistorico,
)
from apps.escolas.models import Escola, MapaCalor, Processo, RedeExterna, RedeInterna
from apps.integracoes.email import sincronizar_respostas_email_cotacao as sync_module
from apps.partners.models import Partner, Proposal


def _mensagem_graph(id_mensagem, subject, remetente="quemenviou@exemplo.com"):
    return {
        "id": id_mensagem,
        "subject": subject,
        "from": {"emailAddress": {"address": remetente}},
        "receivedDateTime": "2026-08-11T10:00:00Z",
        "internetMessageId": f"<{id_mensagem}@exemplo.com>",
        "hasAttachments": False,
    }


class FindEscolaAlvoBySubjectTests(TestCase):
    """PO-066/RN-042/RN-043: localizacao do alvo (Escola/RE/RI/Mapa Calor)
    a partir do codigo de rastreio no assunto — mesmo mecanismo de
    correlacao por codigo ja usado para cotacao
    (`_find_proposals_by_subject`), sem depender do Microsoft Graph
    (somente consulta ao banco)."""

    def setUp(self):
        self.escola = Escola.objects.create(jira_key="EACE-SYNC", nome="Escola Sync", inep="99999999")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)

    def test_encontra_escola_pelo_nivel_global(self):
        alvo = sync_module._find_escola_alvo_by_subject("Re: #ESC-20260811-99999999-Global aviso")

        self.assertIsNotNone(alvo)
        content_type, object_id, codigo, nivel, escola = alvo
        self.assertEqual(content_type, ContentType.objects.get_for_model(Escola))
        self.assertEqual(object_id, self.escola.id)
        self.assertEqual(codigo, "ESC-20260811-99999999-Global")
        self.assertEqual(nivel, "global")
        self.assertEqual(escola, self.escola)

    def test_encontra_rede_externa_ja_criada(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        alvo = sync_module._find_escola_alvo_by_subject("#ESC-20260811-99999999-RE resposta")

        self.assertIsNotNone(alvo)
        content_type, object_id, codigo, nivel, escola = alvo
        self.assertEqual(content_type, ContentType.objects.get_for_model(RedeExterna))
        self.assertEqual(object_id, re.id)
        self.assertEqual(nivel, "re")

    def test_ri_ainda_nao_criado_devolve_none(self):
        alvo = sync_module._find_escola_alvo_by_subject("#ESC-20260811-99999999-RI resposta")

        self.assertIsNone(alvo)

    def test_encontra_mapa_calor_ja_criado(self):
        """RN-043: Mapa Calor e correlacionado pelo sufixo "MC", mesmo
        mecanismo ja usado para RE/RI."""
        processo_mc, _ = Processo.objects.get_or_create(nome=MapaCalor.NOME_PROCESSO_PADRAO)
        mc = MapaCalor.objects.create(escola=self.escola, processo=processo_mc)

        alvo = sync_module._find_escola_alvo_by_subject("#ESC-20260811-99999999-MC resposta")

        self.assertIsNotNone(alvo)
        content_type, object_id, codigo, nivel, escola = alvo
        self.assertEqual(content_type, ContentType.objects.get_for_model(MapaCalor))
        self.assertEqual(object_id, mc.id)
        self.assertEqual(nivel, "mc")

    def test_mapa_calor_ainda_nao_criado_devolve_none(self):
        alvo = sync_module._find_escola_alvo_by_subject("#ESC-20260811-99999999-MC resposta")

        self.assertIsNone(alvo)

    def test_inep_sem_escola_correspondente_devolve_none(self):
        alvo = sync_module._find_escola_alvo_by_subject("#ESC-20260811-00000000-Global resposta")

        self.assertIsNone(alvo)

    def test_sem_codigo_no_assunto_devolve_none(self):
        self.assertIsNone(sync_module._find_escola_alvo_by_subject("Assunto qualquer sem codigo"))


class ImportMessageDispatchTests(TestCase):
    """PO-066/RN-042: `_import_message` continua roteando corretamente para
    cotacao (comportamento preexistente) e passa a rotear tambem para
    Escola/RE/RI, sem confundir os dois codigos na mesma caixa."""

    def setUp(self):
        self.escola = Escola.objects.create(jira_key="EACE-DISPATCH", nome="Escola Dispatch", inep="11112222")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.rede_externa = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.partner = Partner.objects.create(
            nome_fantasia="Parceiro Sync", razao_social="Parceiro Sync LTDA",
            cnpj_cpf="11222333000144", status="ativo",
        )
        self.proposal = Proposal.objects.create(partner=self.partner, codigo_proposta="654321")

    @patch.object(sync_module, "_fetch_mime_content", return_value=b"conteudo-eml")
    def test_mensagem_de_cotacao_continua_funcionando(self, _mock_mime):
        resultado, alvo = sync_module._import_message(
            "caixa@exemplo.com", "token-fake",
            _mensagem_graph("msg-cotacao-1", "RE: #654321 sua cotacao"),
        )

        self.assertEqual(resultado, "imported")
        self.assertEqual(alvo, self.proposal)
        self.assertTrue(EmailCotacaoRespostaImportacao.objects.filter(graph_message_id="msg-cotacao-1").exists())
        self.assertFalse(EmailEscolaRespostaImportacao.objects.exists())

    @patch.object(sync_module, "_fetch_mime_content", return_value=b"conteudo-eml")
    def test_mensagem_de_re_gera_correlacao_separada_da_cotacao(self, _mock_mime):
        resultado, alvo = sync_module._import_message(
            "caixa@exemplo.com", "token-fake",
            _mensagem_graph("msg-escola-1", "Re: #ESC-20260811-11112222-RE documentacao"),
        )

        self.assertEqual(resultado, "imported_escola")
        self.assertEqual(alvo, self.escola)

        correlacao = EmailEscolaRespostaImportacao.objects.get(graph_message_id="msg-escola-1")
        self.assertEqual(correlacao.nivel, "re")
        self.assertEqual(correlacao.content_type, ContentType.objects.get_for_model(RedeExterna))
        self.assertEqual(correlacao.object_id, self.rede_externa.id)
        self.assertFalse(EmailCotacaoRespostaImportacao.objects.exists())

        historico = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(RedeExterna), object_id=self.rede_externa.id,
        )
        self.assertEqual(historico.tipo, "sistema")

    @patch.object(sync_module, "_fetch_mime_content", return_value=b"conteudo-eml")
    def test_mensagem_repetida_de_escola_e_ignorada_como_duplicada(self, _mock_mime):
        mensagem = _mensagem_graph("msg-escola-dup", "#ESC-20260811-11112222-RE de novo")

        primeiro_resultado, _alvo = sync_module._import_message("caixa@exemplo.com", "token-fake", mensagem)
        segundo_resultado, segundo_alvo = sync_module._import_message("caixa@exemplo.com", "token-fake", mensagem)

        self.assertEqual(primeiro_resultado, "imported_escola")
        self.assertEqual(segundo_resultado, "ignored_duplicate_escola")
        self.assertIsNone(segundo_alvo)
        self.assertEqual(EmailEscolaRespostaImportacao.objects.filter(graph_message_id="msg-escola-dup").count(), 1)

    def test_mensagem_sem_nenhum_codigo_e_ignorada(self):
        resultado, alvo = sync_module._import_message(
            "caixa@exemplo.com", "token-fake",
            _mensagem_graph("msg-sem-codigo", "Assunto qualquer, sem cotacao nem escola"),
        )

        self.assertEqual(resultado, "ignored_no_quote")
        self.assertIsNone(alvo)

    def test_mensagem_da_propria_caixa_monitorada_e_ignorada(self):
        resultado, alvo = sync_module._import_message(
            "caixa@exemplo.com", "token-fake",
            _mensagem_graph(
                "msg-mesma-caixa", "#ESC-20260811-11112222-RE aviso",
                remetente="caixa@exemplo.com",
            ),
        )

        self.assertEqual(resultado, "ignored_same_mailbox")
        self.assertEqual(alvo, self.escola)
        self.assertFalse(EmailEscolaRespostaImportacao.objects.exists())
