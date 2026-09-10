import os
import tempfile
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.escolas.models import (
    Campo, CampoObrigatoriedadeTransicao, Escola, MapaCalor, Processo, RedeExterna, RedeInterna, Setor, SetorEscopo,
    SetorStatus, TargetRedeExterna,
)
from apps.escolas.services import extrair_endereco_estruturado, sincronizar_escolas
from apps.partners.models import Partner


class SincronizarEscolasTests(TestCase):
    """PO-046/ADR-010: sincronizacao grava em Escola, sem tocar Cliente/Endereco."""

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_cria_escolas_novas(self, mock_listar):
        mock_listar.return_value = (
            200,
            [
                {"key": "EACE-1", "uf": "SP", "status_escola": "Conectado", "nome": "Escola A"},
                {"key": "EACE-2", "uf": "TO", "status_escola": "Em andamento", "nome": "Escola B"},
            ],
        )

        total, erro = sincronizar_escolas()

        self.assertIsNone(erro)
        self.assertEqual(total, 2)
        self.assertEqual(Escola.objects.count(), 2)
        escola_a = Escola.objects.get(jira_key="EACE-1")
        self.assertEqual(escola_a.uf, "SP")
        self.assertEqual(escola_a.status_escola, "Conectado")
        self.assertEqual(escola_a.dados_api["nome"], "Escola A")

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_atualiza_escola_existente_sem_duplicar(self, mock_listar):
        Escola.objects.create(jira_key="EACE-1", uf="SP", status_escola="Pendente", dados_api={"nome": "Antigo"})
        mock_listar.return_value = (
            200,
            [{"key": "EACE-1", "uf": "SP", "status_escola": "Conectado", "nome": "Novo"}],
        )

        total, erro = sincronizar_escolas()

        self.assertIsNone(erro)
        self.assertEqual(total, 1)
        self.assertEqual(Escola.objects.count(), 1)
        escola = Escola.objects.get(jira_key="EACE-1")
        self.assertEqual(escola.status_escola, "Conectado")
        self.assertEqual(escola.dados_api["nome"], "Novo")

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_repassa_filtros(self, mock_listar):
        mock_listar.return_value = (200, [])

        sincronizar_escolas(uf="SP", status_escola="Conectado")

        mock_listar.assert_called_once_with(uf="SP", status_escola="Conectado", client=None)

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_nao_grava_nada_em_caso_de_erro_da_api(self, mock_listar):
        mock_listar.return_value = (503, {"detail": "API desligada"})

        total, erro = sincronizar_escolas()

        self.assertEqual(total, 0)
        self.assertIn("503", erro)
        self.assertEqual(Escola.objects.count(), 0)

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_ignora_item_sem_key(self, mock_listar):
        mock_listar.return_value = (200, [{"uf": "SP"}])

        total, erro = sincronizar_escolas()

        self.assertIsNone(erro)
        self.assertEqual(total, 0)
        self.assertEqual(Escola.objects.count(), 0)

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_preenche_endereco_estruturado_a_partir_da_descricao(self, mock_listar):
        """RN-051: Logradouro/Numero/Bairro/CEP saem preenchidos junto com
        a sincronizacao, extraidos do texto de `descricao`."""
        mock_listar.return_value = (
            200,
            [{
                "key": "EACE-1", "uf": "SP", "nome": "Escola A",
                "descricao": "Endereço: JOSE DE ANCHIETA PADRE, 121 RUA. JARDIM VISTA ALEGRE. 13140-194 Paulínia - SP.",
            }],
        )

        sincronizar_escolas()

        escola = Escola.objects.get(jira_key="EACE-1")
        self.assertEqual(escola.logradouro, "JOSE DE ANCHIETA PADRE")
        self.assertEqual(escola.numero, "121")
        self.assertEqual(escola.bairro, "JARDIM VISTA ALEGRE")
        self.assertEqual(escola.cep, "13140-194")


class ExtrairEnderecoEstruturadoTests(TestCase):
    """RN-051/PO-072: extracao de melhor esforco de Logradouro/Numero/
    Bairro/CEP a partir do texto livre de `Escola.endereco_descricao`
    (DashboardEACE) — casos reais encontrados investigando producao."""

    def test_endereco_vazio_devolve_tudo_em_branco(self):
        self.assertEqual(
            extrair_endereco_estruturado(""),
            {"logradouro": "", "numero": "", "bairro": "", "cep": ""},
        )

    def test_formato_com_numero_e_tipo_de_logradouro_separado_do_bairro(self):
        resultado = extrair_endereco_estruturado(
            "Endereço: FLAVIO MONTEIRO DE CASTRO, 500 RUA. RIBEIROPOLIS. "
            "11714-130 Praia Grande - SP.\nMunicípio: Praia Grande\nCódigo INEP: 35296909\nUF: SP"
        )
        self.assertEqual(resultado, {
            "logradouro": "FLAVIO MONTEIRO DE CASTRO",
            "numero": "500",
            "bairro": "RIBEIROPOLIS",
            "cep": "11714-130",
        })

    def test_formato_sem_tipo_de_logradouro_numero_e_bairro_no_mesmo_bloco(self):
        resultado = extrair_endereco_estruturado(
            "Endereço: HANS CHRISTIAN ANDERSEN, 67 GRANJA NOSSA SENHORA APARECIDA. "
            "04860-110 São Paulo - SP."
        )
        self.assertEqual(resultado, {
            "logradouro": "HANS CHRISTIAN ANDERSEN",
            "numero": "67",
            "bairro": "GRANJA NOSSA SENHORA APARECIDA",
            "cep": "04860-110",
        })

    def test_formato_sem_numero_usa_s_n_e_ainda_identifica_bairro(self):
        resultado = extrair_endereco_estruturado(
            "Endereço: SILVEIRANIA, S/N JARDIM RUSSO. 05211-060 São Paulo - SP."
        )
        self.assertEqual(resultado, {
            "logradouro": "SILVEIRANIA",
            "numero": "S/N",
            "bairro": "JARDIM RUSSO",
            "cep": "05211-060",
        })

    def test_formato_sem_numero_nem_bairro_extrai_so_logradouro_e_cep(self):
        resultado = extrair_endereco_estruturado(
            "Endereço: FAZENDA RECANDO DA IARA, 77673-000 Monte Santo do Tocantins - TO."
        )
        self.assertEqual(resultado, {
            "logradouro": "FAZENDA RECANDO DA IARA",
            "numero": "",
            "bairro": "",
            "cep": "77673-000",
        })

    def test_formato_sem_virgula_extrai_so_logradouro_e_cep(self):
        resultado = extrair_endereco_estruturado(
            "Endereço: RUA RUA DOS MOGNOS, 78300-001 Tangará da Serra - MT."
        )
        self.assertEqual(resultado["logradouro"], "RUA RUA DOS MOGNOS")
        self.assertEqual(resultado["cep"], "78300-001")
        self.assertEqual(resultado["numero"], "")

    def test_formato_com_segmento_extra_sem_numero_identificavel_usa_ultimo_como_bairro(self):
        resultado = extrair_endereco_estruturado(
            "Endereço: AVENIDA CEARA, POVOADO. RETIRO. 77368-000 São Salvador do Tocantins - TO."
        )
        self.assertEqual(resultado["logradouro"], "AVENIDA CEARA")
        self.assertEqual(resultado["numero"], "")
        self.assertEqual(resultado["bairro"], "RETIRO")
        self.assertEqual(resultado["cep"], "77368-000")

    def test_sem_cep_nao_arrisca_numero_nem_bairro(self):
        resultado = extrair_endereco_estruturado("Endereço: RUA SEM CEP NENHUM, 123 CENTRO.")
        self.assertEqual(resultado["logradouro"], "RUA SEM CEP NENHUM")
        self.assertEqual(resultado["numero"], "")
        self.assertEqual(resultado["bairro"], "")
        self.assertEqual(resultado["cep"], "")

    def test_nao_altera_texto_original(self):
        # a funcao e pura — nao recebe a instancia de Escola, so o texto;
        # quem chama e responsavel por manter endereco_descricao intacto.
        texto_original = "Endereço: RUA A, 1. BAIRRO B. 01000-000 Cidade - SP."
        extrair_endereco_estruturado(texto_original)
        self.assertEqual(
            texto_original,
            "Endereço: RUA A, 1. BAIRRO B. 01000-000 Cidade - SP.",
        )


class SincronizarEscolasCommandTests(TestCase):
    @mock.patch("apps.escolas.management.commands.sincronizar_escolas_dashboard_eace.sincronizar_escolas")
    def test_comando_repassa_filtros_e_reporta_sucesso(self, mock_sincronizar):
        mock_sincronizar.return_value = (3, None)

        saida = StringIO()
        call_command("sincronizar_escolas_dashboard_eace", "--uf=SP", "--status-escola=Conectado", stdout=saida)

        mock_sincronizar.assert_called_once_with(uf="SP", status_escola="Conectado")
        self.assertIn("3 escola(s) sincronizada(s)", saida.getvalue())

    @mock.patch("apps.escolas.management.commands.sincronizar_escolas_dashboard_eace.sincronizar_escolas")
    def test_comando_falha_quando_servico_retorna_erro(self, mock_sincronizar):
        mock_sincronizar.return_value = (0, "Falha ao consultar o DashboardEACE (status 503): API desligada")

        with self.assertRaises(SystemExit):
            call_command("sincronizar_escolas_dashboard_eace", stderr=StringIO())


class RedeExternaRedeInternaTests(TestCase):
    """PO-048/ADR-012/RN-023: processos RE/RI independentes, vinculados a Escola."""

    def setUp(self):
        self.escola = Escola.objects.create(jira_key="EACE-1", inep="12345678", nome="Escola A")
        self.processo = Processo.objects.create(nome="Processo QA A")
        self.setor_1 = Setor.objects.create(processo=self.processo, nome="Setor 1")
        self.setor_2 = Setor.objects.create(processo=self.processo, nome="Setor 2")
        self.status_andamento = SetorStatus.objects.create(setor=self.setor_1, nome="Em andamento")
        self.status_concluido = SetorStatus.objects.create(setor=self.setor_2, nome="Concluido")

    def test_cria_rede_externa_e_rede_interna_vinculadas_a_escola(self):
        parceiro = Partner.objects.create(nome_fantasia="Parceiro X")

        re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo, setor=self.setor_1, status=self.status_andamento, parceiro=parceiro,
        )
        ri = RedeInterna.objects.create(
            escola=self.escola, processo=self.processo, setor=self.setor_2, status=self.status_concluido, parceiro=parceiro,
        )

        self.assertEqual(self.escola.rede_externa, re)
        self.assertEqual(self.escola.rede_interna, ri)
        self.assertEqual(re.parceiro, ri.parceiro)

    def test_status_de_re_e_ri_sao_independentes(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor_1, status=self.status_andamento)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor_2, status=self.status_concluido)

        self.escola.refresh_from_db()
        self.assertEqual(self.escola.rede_externa.status, self.status_andamento)
        self.assertEqual(self.escola.rede_interna.status, self.status_concluido)

    def test_re_e_ri_podem_ter_parceiros_diferentes(self):
        parceiro_re = Partner.objects.create(nome_fantasia="Parceiro RE")
        parceiro_ri = Partner.objects.create(nome_fantasia="Parceiro RI")

        re = RedeExterna.objects.create(escola=self.escola, parceiro=parceiro_re)
        ri = RedeInterna.objects.create(escola=self.escola, parceiro=parceiro_ri)

        self.assertNotEqual(re.parceiro, ri.parceiro)

    def test_criacao_comeca_em_branco_sem_copiar_dados_api(self):
        escola = Escola.objects.create(
            jira_key="EACE-2",
            dados_api={"setor_re": "Setor da API", "parceiro_re": "Parceiro da API"},
        )

        re = RedeExterna.objects.create(escola=escola)

        self.assertIsNone(re.setor)
        self.assertIsNone(re.parceiro)

    def test_setor_precisa_pertencer_ao_processo_escolhido(self):
        outro_processo = Processo.objects.create(nome="Processo QA B")
        setor_de_outro_processo = Setor.objects.create(processo=outro_processo, nome="Setor X")

        re = RedeExterna(escola=self.escola, processo=self.processo, setor=setor_de_outro_processo)

        with self.assertRaises(ValidationError):
            re.full_clean()

    def test_status_precisa_pertencer_ao_setor_escolhido(self):
        re = RedeExterna(escola=self.escola, processo=self.processo, setor=self.setor_1, status=self.status_concluido)

        with self.assertRaises(ValidationError):
            re.full_clean()

    def test_uma_escola_nao_pode_ter_mais_de_uma_rede_externa(self):
        RedeExterna.objects.create(escola=self.escola)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RedeExterna.objects.create(escola=self.escola)

    def test_excluir_escola_remove_rede_externa_e_rede_interna_em_cascata(self):
        RedeExterna.objects.create(escola=self.escola)
        RedeInterna.objects.create(escola=self.escola)

        self.escola.delete()

        self.assertEqual(RedeExterna.objects.count(), 0)
        self.assertEqual(RedeInterna.objects.count(), 0)


class IndicadorConectividadeTests(TestCase):
    """RN-062: bolinha do grid de Enderecos Lastmile, derivada so de RE/RI
    ("Concluido", sem acento, no nome do Status — mesma grafia do catalogo
    real, bug corrigido) — Mapa Calor nunca entra no calculo."""

    def setUp(self):
        self.escola = Escola.objects.create(jira_key="EACE-1", nome="Escola A")
        self.processo = Processo.objects.create(nome="Processo QA A")
        self.setor = Setor.objects.create(processo=self.processo, nome="Setor 1")
        self.status_concluido = SetorStatus.objects.create(setor=self.setor, nome="Concluido")
        self.status_andamento = SetorStatus.objects.create(setor=self.setor, nome="Em andamento")

    def test_nao_reconhece_concluido_com_acento(self):
        # RN-062 (bug corrigido em 2026-08-14): o catalogo real usa
        # "Concluido" sem acento — a comparacao NAO deve reconhecer a
        # grafia acentuada, para nao voltar a esconder o caso relatado.
        # Setor separado: o MySQL do projeto usa colacao insensivel a
        # acento, e o unique_together (setor, nome) rejeitaria "Concluido"
        # e "Concluído" cadastrados no mesmo Setor.
        outro_setor = Setor.objects.create(processo=self.processo, nome="Setor 2")
        status_com_acento = SetorStatus.objects.create(setor=outro_setor, nome="Concluído")
        RedeExterna.objects.create(escola=self.escola, setor=outro_setor, status=status_com_acento)
        RedeInterna.objects.create(escola=self.escola, setor=outro_setor, status=status_com_acento)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "vermelho")

    def test_verde_quando_re_e_ri_estao_concluidas(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "verde")

    def test_amarelo_quando_so_re_esta_concluida(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "amarelo")

    def test_amarelo_quando_so_ri_esta_concluida(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "amarelo")

    def test_vermelho_quando_nenhuma_esta_concluida(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "vermelho")

    def test_vermelho_quando_re_e_ri_ainda_nao_existem(self):
        self.assertEqual(self.escola.indicador_conectividade["cor"], "vermelho")

    def test_mapa_calor_concluido_nao_torna_a_escola_verde(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)
        MapaCalor.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "vermelho")

    def test_mapa_calor_pendente_nao_impede_verde(self):
        RedeExterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)
        RedeInterna.objects.create(escola=self.escola, setor=self.setor, status=self.status_concluido)
        MapaCalor.objects.create(escola=self.escola, setor=self.setor, status=self.status_andamento)

        self.assertEqual(self.escola.indicador_conectividade["cor"], "verde")


class ProcessoRedeBaseResponsavelTests(TestCase):
    """RN-052/ADR-027: Responsavel (usuario do sistema) em ProcessoRedeBase,
    herdado por RedeExterna/RedeInterna/MapaCalor — opcional no banco
    (`null=True, blank=True`), mesmo padrao de Setor/Status/Parceiro."""

    def setUp(self):
        self.escola = Escola.objects.create(jira_key="EACE-RESP", nome="Escola Responsavel")
        self.usuario = get_user_model().objects.create_user(username="responsavel-qa", password="senha-segura")

    def test_responsavel_e_opcional(self):
        re = RedeExterna.objects.create(escola=self.escola)

        self.assertIsNone(re.responsavel)
        re.full_clean()  # nao deve levantar ValidationError por falta de Responsavel.

    def test_responsavel_e_atribuivel_nos_tres_processos(self):
        re = RedeExterna.objects.create(escola=self.escola, responsavel=self.usuario)
        ri = RedeInterna.objects.create(escola=self.escola, responsavel=self.usuario)
        mc = MapaCalor.objects.create(escola=self.escola, responsavel=self.usuario)

        self.assertEqual(re.responsavel, self.usuario)
        self.assertEqual(ri.responsavel, self.usuario)
        self.assertEqual(mc.responsavel, self.usuario)

    def test_related_name_nao_colide_entre_re_ri_e_mapa_calor(self):
        """Pendencia da ADR-027: `related_name` usa `%(class)s` para que o
        mesmo usuario tenha uma relacao reversa distinta por subclasse."""
        re = RedeExterna.objects.create(escola=self.escola, responsavel=self.usuario)
        ri = RedeInterna.objects.create(escola=self.escola, responsavel=self.usuario)
        mc = MapaCalor.objects.create(escola=self.escola, responsavel=self.usuario)

        self.assertIn(re, self.usuario.redeexterna_responsavel.all())
        self.assertIn(ri, self.usuario.redeinterna_responsavel.all())
        self.assertIn(mc, self.usuario.mapacalor_responsavel.all())

    def test_excluir_usuario_zera_responsavel_sem_apagar_a_subatividade(self):
        re = RedeExterna.objects.create(escola=self.escola, responsavel=self.usuario)

        self.usuario.delete()
        re.refresh_from_db()

        self.assertIsNone(re.responsavel)
        self.assertTrue(RedeExterna.objects.filter(pk=re.pk).exists())


class MapaCalorTests(TestCase):
    """RN-043/PO-067: Mapa Calor (MC), terceira subatividade fixa da Escola,
    no mesmo molde hardcoded de RedeExterna/RedeInterna (ADR-012) —
    decisao de adiar a generalizacao registrada na ADR-025."""

    def setUp(self):
        self.escola = Escola.objects.create(jira_key="EACE-MC-1", inep="87654321", nome="Escola MC")
        self.processo = Processo.objects.create(nome="Processo QA MC")
        self.setor_1 = Setor.objects.create(processo=self.processo, nome="Setor MC 1")
        self.setor_2 = Setor.objects.create(processo=self.processo, nome="Setor MC 2")
        self.status_andamento = SetorStatus.objects.create(setor=self.setor_1, nome="Em andamento")
        self.status_concluido = SetorStatus.objects.create(setor=self.setor_2, nome="Concluido")

    def test_cria_mapa_calor_vinculado_a_escola(self):
        parceiro = Partner.objects.create(nome_fantasia="Parceiro MC")

        mc = MapaCalor.objects.create(
            escola=self.escola, processo=self.processo, setor=self.setor_1, status=self.status_andamento, parceiro=parceiro,
        )

        self.assertEqual(self.escola.mapa_calor, mc)
        self.assertEqual(mc.parceiro, parceiro)

    def test_setor_status_e_parceiro_de_mapa_calor_sao_independentes_de_re_e_ri(self):
        parceiro_re = Partner.objects.create(nome_fantasia="Parceiro RE")
        parceiro_mc = Partner.objects.create(nome_fantasia="Parceiro MC 2")

        re = RedeExterna.objects.create(escola=self.escola, setor=self.setor_1, status=self.status_andamento, parceiro=parceiro_re)
        ri = RedeInterna.objects.create(escola=self.escola, setor=self.setor_2, status=self.status_concluido)
        mc = MapaCalor.objects.create(escola=self.escola, setor=self.setor_2, status=self.status_concluido, parceiro=parceiro_mc)

        self.escola.refresh_from_db()
        self.assertNotEqual(mc.parceiro, re.parceiro)
        self.assertIsNone(ri.parceiro)
        self.assertEqual(self.escola.mapa_calor.status, self.status_concluido)
        self.assertEqual(self.escola.rede_externa.status, self.status_andamento)

    def test_criacao_comeca_em_branco_sem_copiar_dados_api(self):
        """RN-043 (excecao): Mapa Calor nao tem referencia somente-leitura
        da API equivalente a `setor_re`/`parceiro_re` (RN-024) — a criacao
        do processo tambem comeca em branco, mesmo padrao de RE/RI."""
        escola = Escola.objects.create(
            jira_key="EACE-MC-2",
            dados_api={"setor_re": "Setor da API", "parceiro_re": "Parceiro da API"},
        )

        mc = MapaCalor.objects.create(escola=escola)

        self.assertIsNone(mc.setor)
        self.assertIsNone(mc.parceiro)
        self.assertEqual(escola.referencia_mapa_calor, {"setor": "", "parceiro": "", "velocidade_ofertada": ""})

    def test_setor_precisa_pertencer_ao_processo_escolhido(self):
        outro_processo = Processo.objects.create(nome="Processo QA MC B")
        setor_de_outro_processo = Setor.objects.create(processo=outro_processo, nome="Setor MC X")

        mc = MapaCalor(escola=self.escola, processo=self.processo, setor=setor_de_outro_processo)

        with self.assertRaises(ValidationError):
            mc.full_clean()

    def test_status_precisa_pertencer_ao_setor_escolhido(self):
        mc = MapaCalor(escola=self.escola, processo=self.processo, setor=self.setor_1, status=self.status_concluido)

        with self.assertRaises(ValidationError):
            mc.full_clean()

    def test_uma_escola_nao_pode_ter_mais_de_um_mapa_calor(self):
        MapaCalor.objects.create(escola=self.escola)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MapaCalor.objects.create(escola=self.escola)

    def test_excluir_escola_remove_mapa_calor_em_cascata(self):
        RedeExterna.objects.create(escola=self.escola)
        MapaCalor.objects.create(escola=self.escola)

        self.escola.delete()

        self.assertEqual(RedeExterna.objects.count(), 0)
        self.assertEqual(MapaCalor.objects.count(), 0)


class ReferenciaReRiDaApiTests(TestCase):
    """PO-049/ADR-013/RN-024: referencia somente-leitura de RE/RI que ja vem
    da API do DashboardEACE, direto de Escola.dados_api."""

    def test_referencia_extrai_campos_re_e_ri_do_dados_api(self):
        escola = Escola.objects.create(
            jira_key="EACE-1",
            dados_api={
                "setor_re": "Setor Norte",
                "parceiro_re": "Parceiro RE Ltda",
                "setor_ri": "Setor Sul",
                "parceiro_ri": "Parceiro RI Ltda",
                "velocidade_dl_ofertada": 100,
            },
        )

        self.assertEqual(escola.referencia_rede_externa["setor"], "Setor Norte")
        self.assertEqual(escola.referencia_rede_externa["parceiro"], "Parceiro RE Ltda")
        self.assertEqual(escola.referencia_rede_externa["velocidade_ofertada"], "100 Mbps")
        self.assertEqual(escola.referencia_rede_interna["setor"], "Setor Sul")
        self.assertEqual(escola.referencia_rede_interna["parceiro"], "Parceiro RI Ltda")
        self.assertEqual(escola.referencia_rede_interna["velocidade_ofertada"], "100 Mbps")

    def test_referencia_com_dados_api_vazio_devolve_campos_em_branco(self):
        escola = Escola.objects.create(jira_key="EACE-2")

        self.assertEqual(escola.referencia_rede_externa["setor"], "")
        self.assertEqual(escola.referencia_rede_externa["parceiro"], "")
        self.assertEqual(escola.referencia_rede_externa["velocidade_ofertada"], "")
        self.assertEqual(escola.referencia_rede_interna["setor"], "")

    def test_referencia_distingue_velocidade_zero_de_velocidade_ausente(self):
        escola = Escola.objects.create(jira_key="EACE-3", dados_api={"velocidade_dl_ofertada": 0})

        self.assertEqual(escola.referencia_rede_externa["velocidade_ofertada"], "0 Mbps")

        escola_sem_dado = Escola.objects.create(jira_key="EACE-4")
        self.assertEqual(escola_sem_dado.referencia_rede_externa["velocidade_ofertada"], "")


class SincronizarEscolasVelocidadeMinimaKitInicialTests(TestCase):
    """RN-057 Partes 1 e 2/PO-076: promocao de Velocidade Minima e Kit
    Inicial de dentro de dados_api para colunas tipadas em Escola,
    preenchidas pela sincronizacao (mesmo padrao de inep/nome/municipio,
    ADR-010)."""

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_preenche_velocidade_minima_e_kit_inicial(self, mock_listar):
        mock_listar.return_value = (
            200,
            [{"key": "EACE-1", "uf": "SP", "velocidade_dl_minima": "100.00", "kit_wifi": "2.00"}],
        )

        sincronizar_escolas()

        escola = Escola.objects.get(jira_key="EACE-1")
        self.assertEqual(escola.velocidade_dl_minima, Decimal("100.00"))
        self.assertEqual(escola.kit_inicial, Decimal("2.00"))

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_sem_dado_deixa_campos_em_branco(self, mock_listar):
        mock_listar.return_value = (200, [{"key": "EACE-1", "uf": "SP"}])

        sincronizar_escolas()

        escola = Escola.objects.get(jira_key="EACE-1")
        self.assertIsNone(escola.velocidade_dl_minima)
        self.assertIsNone(escola.kit_inicial)

    @mock.patch("apps.escolas.services.listar_escolas")
    def test_sincronizar_com_valor_nao_numerico_nao_falha_e_deixa_em_branco(self, mock_listar):
        """RN-057: nunca falha silenciosamente, mas tambem nunca inventa
        valor a partir de um dado sujo vindo da API."""
        mock_listar.return_value = (
            200,
            [{"key": "EACE-1", "uf": "SP", "velocidade_dl_minima": "N/A", "kit_wifi": ""}],
        )

        total, erro = sincronizar_escolas()

        self.assertIsNone(erro)
        self.assertEqual(total, 1)
        escola = Escola.objects.get(jira_key="EACE-1")
        self.assertIsNone(escola.velocidade_dl_minima)
        self.assertIsNone(escola.kit_inicial)


class TargetRedeExternaModelTests(TestCase):
    """RN-057 Parte 3/ADR-029: catalogo de referencia UF + Velocidade ->
    Valor, sem FK com Escola — lookup exato via `buscar_valor`."""

    def test_buscar_valor_com_correspondencia_exata(self):
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("543.21"))

        self.assertEqual(TargetRedeExterna.buscar_valor("SP", Decimal("100")), Decimal("543.21"))

    def test_buscar_valor_sem_combinacao_devolve_none(self):
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("543.21"))

        self.assertIsNone(TargetRedeExterna.buscar_valor("SP", Decimal("200")))
        self.assertIsNone(TargetRedeExterna.buscar_valor("TO", Decimal("100")))

    def test_buscar_valor_com_velocidade_fracionaria_nao_aproxima(self):
        """ADR-029: velocidade_mbps e int na origem — uma Velocidade Minima
        fracionaria (ex.: 100.50) nunca deve ser aproximada para 100 ou 101;
        o resultado precisa ficar vazio."""
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("543.21"))

        self.assertIsNone(TargetRedeExterna.buscar_valor("SP", Decimal("100.50")))

    def test_buscar_valor_sem_uf_ou_velocidade_devolve_none(self):
        self.assertIsNone(TargetRedeExterna.buscar_valor("", Decimal("100")))
        self.assertIsNone(TargetRedeExterna.buscar_valor("SP", None))

    def test_uf_e_velocidade_sao_unicos_no_catalogo(self):
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("543.21"))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("999.99"))


class EscolaDadosTecnicosEaceTests(TestCase):
    """RN-057/PO-076: Escola.target_eace (derivado, nunca armazenado) e
    Escola.dados_tecnicos_eace (agrupa os 3 dados para exibicao)."""

    def test_target_eace_deriva_da_uf_e_velocidade_minima_da_escola(self):
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("543.21"))
        escola = Escola.objects.create(jira_key="EACE-1", uf="SP", velocidade_dl_minima=Decimal("100"))

        self.assertEqual(escola.target_eace, Decimal("543.21"))

    def test_target_eace_sem_correspondencia_fica_vazio(self):
        escola = Escola.objects.create(jira_key="EACE-1", uf="SP", velocidade_dl_minima=Decimal("100"))

        self.assertIsNone(escola.target_eace)

    def test_dados_tecnicos_eace_formata_os_tres_valores(self):
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("543.21"))
        escola = Escola.objects.create(
            jira_key="EACE-1", uf="SP", velocidade_dl_minima=Decimal("100.00"), kit_inicial=Decimal("2.00"),
        )

        dados = escola.dados_tecnicos_eace
        self.assertEqual(dados["velocidade_minima"], "100 Mbps")
        self.assertEqual(dados["kit_inicial"], "2")
        self.assertEqual(dados["target_eace"], "543.21")

    def test_dados_tecnicos_eace_em_branco_quando_ausentes(self):
        escola = Escola.objects.create(jira_key="EACE-1")

        dados = escola.dados_tecnicos_eace
        self.assertEqual(dados["velocidade_minima"], "")
        self.assertEqual(dados["kit_inicial"], "")
        self.assertEqual(dados["target_eace"], "")

    def test_dados_tecnicos_eace_com_valor_grande_nao_usa_notacao_cientifica(self):
        """`max_digits=10` permite valores de 8 digitos inteiros — a
        formatacao precisa manter precisao decimal, sem cair em notacao
        cientifica (bug latente de usar float(...):g em numeros grandes)."""
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("1234567.89"))
        escola = Escola.objects.create(jira_key="EACE-1", uf="SP", velocidade_dl_minima=Decimal("100"))

        self.assertEqual(escola.dados_tecnicos_eace["target_eace"], "1234567.89")


class ImportarTargetRedeExternaCommandTests(TestCase):
    """RN-057 Parte 3/ADR-029: importacao do catalogo TargetRedeExterna a
    partir de um CSV (uf,velocidade_mbps,valor) — mecanismo tecnico do Dev,
    sem endpoint de API. Os valores usados aqui sao ficticios (apenas para
    teste), nunca dados reais da origem."""

    def _escrever_csv(self, conteudo):
        arquivo = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline="",
        )
        arquivo.write(conteudo)
        arquivo.close()
        self.addCleanup(os.remove, arquivo.name)
        return arquivo.name

    def test_importa_linhas_validas(self):
        caminho = self._escrever_csv("uf,velocidade_mbps,valor\nSP,100,543.21\nTO,50,111.00\n")

        saida = StringIO()
        call_command("importar_target_rede_externa", caminho, stdout=saida)

        self.assertEqual(TargetRedeExterna.objects.count(), 2)
        self.assertEqual(TargetRedeExterna.objects.get(uf="SP", velocidade_mbps=100).valor, Decimal("543.21"))
        self.assertIn("2 criado(s)", saida.getvalue())

    def test_reimportar_atualiza_em_vez_de_duplicar(self):
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor=Decimal("1.00"))
        caminho = self._escrever_csv("uf,velocidade_mbps,valor\nSP,100,543.21\n")

        call_command("importar_target_rede_externa", caminho, stdout=StringIO())

        self.assertEqual(TargetRedeExterna.objects.count(), 1)
        self.assertEqual(TargetRedeExterna.objects.get(uf="SP", velocidade_mbps=100).valor, Decimal("543.21"))

    def test_linha_invalida_e_ignorada_sem_interromper_as_demais(self):
        caminho = self._escrever_csv("uf,velocidade_mbps,valor\nSP,100,543.21\nTO,abc,111.00\n")

        saida = StringIO()
        call_command("importar_target_rede_externa", caminho, stdout=saida, stderr=StringIO())

        self.assertEqual(TargetRedeExterna.objects.count(), 1)
        self.assertIn("1 linha(s) ignorada(s)", saida.getvalue())

    def test_csv_sem_colunas_esperadas_gera_erro(self):
        caminho = self._escrever_csv("coluna_a,coluna_b\n1,2\n")

        with self.assertRaises(CommandError):
            call_command("importar_target_rede_externa", caminho, stdout=StringIO())

    def test_arquivo_inexistente_gera_erro(self):
        with self.assertRaises(CommandError):
            call_command("importar_target_rede_externa", "C:/caminho/inexistente.csv", stdout=StringIO())


class ProcessoSetorStatusTests(TestCase):
    """PO-050/ADR-014/RN-025: catalogo Processo->Setor->SetorStatus, generico
    (sem tipo RE/RI), vinculavel a RedeExterna/RedeInterna."""

    def test_cria_hierarquia_processo_setor_status(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        status = SetorStatus.objects.create(setor=setor, nome="A fazer")

        self.assertEqual(list(processo.setores.all()), [setor])
        self.assertEqual(list(setor.status_opcoes.all()), [status])

    def test_nome_de_setor_e_unico_por_processo(self):
        processo = Processo.objects.create(nome="Processo QA A")
        Setor.objects.create(processo=processo, nome="Lastmile")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Setor.objects.create(processo=processo, nome="Lastmile")

    def test_mesmo_nome_de_setor_e_permitido_em_processos_diferentes(self):
        processo_re = Processo.objects.create(nome="Processo QA A")
        processo_ri = Processo.objects.create(nome="Processo QA B")

        setor_re = Setor.objects.create(processo=processo_re, nome="Lastmile")
        setor_ri = Setor.objects.create(processo=processo_ri, nome="Lastmile")

        self.assertNotEqual(setor_re.pk, setor_ri.pk)

    def test_nome_de_status_e_unico_por_setor(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        SetorStatus.objects.create(setor=setor, nome="A fazer")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SetorStatus.objects.create(setor=setor, nome="A fazer")

    def test_rede_externa_e_rede_interna_podem_se_vincular_a_processos_diferentes(self):
        escola = Escola.objects.create(jira_key="EACE-1")
        processo_re = Processo.objects.create(nome="Processo QA A")
        processo_ri = Processo.objects.create(nome="Processo QA B")

        re = RedeExterna.objects.create(escola=escola, processo=processo_re)
        ri = RedeInterna.objects.create(escola=escola, processo=processo_ri)

        self.assertEqual(re.processo, processo_re)
        self.assertEqual(ri.processo, processo_ri)

    def test_rede_externa_pode_nao_ter_processo_vinculado(self):
        escola = Escola.objects.create(jira_key="EACE-1")

        re = RedeExterna.objects.create(escola=escola)

        self.assertIsNone(re.processo)

    def test_excluir_processo_nao_apaga_rede_externa_vinculada(self):
        escola = Escola.objects.create(jira_key="EACE-1")
        processo = Processo.objects.create(nome="Processo QA A")
        re = RedeExterna.objects.create(escola=escola, processo=processo)

        processo.delete()
        re.refresh_from_db()

        self.assertIsNone(re.processo)

    def test_seed_de_dados_de_teste_criado_pela_migration(self):
        self.assertTrue(Processo.objects.filter(nome="Rede Externa (RE)").exists())
        self.assertTrue(Processo.objects.filter(nome="Rede Interna (RI)").exists())

        processo_re = Processo.objects.get(nome="Rede Externa (RE)")
        self.assertEqual(processo_re.setores.count(), 5)
        setor_lastmile = processo_re.setores.get(nome="Lastmile")
        # 3 status de teste (migration 0006) + "Cotacao" (RN-044/ADR-026,
        # migration 0016_seed_status_cotacao_lastmile).
        self.assertEqual(setor_lastmile.status_opcoes.count(), 4)
        self.assertTrue(setor_lastmile.status_opcoes.filter(nome="Cotacao").exists())


class SetorEscopoModelTests(TestCase):
    """PO-062/RN-037/ADR-022: escopo de exibicao do Setor entre Escola e
    RE/RI/Mapa Calor (RN-043), por nome de Setor (mesmo precedente de
    `Campo.setor_nome`, ADR-019)."""

    def test_escopo_escola_nao_exige_re_nem_ri(self):
        escopo = SetorEscopo(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)

        escopo.full_clean()  # nao deve levantar ValidationError

    def test_escopo_sub_atividades_sem_re_ri_nem_mapa_calor_e_invalido(self):
        escopo = SetorEscopo(
            setor_nome="Lastmile",
            atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            aplica_re=False,
            aplica_ri=False,
            aplica_mapa_calor=False,
        )

        with self.assertRaises(ValidationError):
            escopo.full_clean()

    def test_escopo_sub_atividades_com_apenas_re_e_valido(self):
        escopo = SetorEscopo(
            setor_nome="Lastmile",
            atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            aplica_re=True,
            aplica_ri=False,
            aplica_mapa_calor=False,
        )

        escopo.full_clean()  # nao deve levantar ValidationError

    def test_escopo_sub_atividades_com_apenas_mapa_calor_e_valido(self):
        """RN-043: Mapa Calor pode ser a unica sub-atividade marcada para
        um Setor, assim como ja acontecia com RE ou RI isoladamente."""
        escopo = SetorEscopo(
            setor_nome="Lastmile",
            atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            aplica_re=False,
            aplica_ri=False,
            aplica_mapa_calor=True,
        )

        escopo.full_clean()  # nao deve levantar ValidationError

    def test_aplica_mapa_calor_e_true_por_padrao(self):
        """RN-043: default `True` preserva o comportamento ja configurado
        para Setores existentes antes desta feature (aplica a todas as
        sub-atividades, incluindo a nova)."""
        escopo = SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES)

        self.assertTrue(escopo.aplica_mapa_calor)

    def test_setor_nome_e_unico(self):
        SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES)


class SetorEscopoMigrationSeedTests(TestCase):
    """PO-062/ADR-022: a migration 0010 semeia SetorEscopo (Sub-atividades:
    RE e RI) para todo nome de Setor ja usado por um Campo (RN-031) antes
    desta feature — preserva o comportamento atual sem exigir configuracao
    manual. A migration real ja rodou (sem nenhum Campo) ao montar o banco
    de teste; aqui a mesma funcao `RunPython` e chamada diretamente contra
    o registry atual para validar seu comportamento com dados presentes."""

    @staticmethod
    def _semear_escopo_padrao():
        import importlib

        from django.apps import apps as app_registry

        modulo = importlib.import_module("apps.escolas.migrations.0010_setor_escopo")
        modulo.semear_escopo_padrao(app_registry, None)

    def test_semeia_escopo_padrao_para_setor_usado_por_campo(self):
        Campo.objects.create(nome="Data de instalação", tipo=Campo.TIPO_DATA, setor_nome="Suprimentos")

        self._semear_escopo_padrao()

        escopo = SetorEscopo.objects.get(setor_nome="Suprimentos")
        self.assertEqual(escopo.atividade, SetorEscopo.ATIVIDADE_SUB_ATIVIDADES)
        self.assertTrue(escopo.aplica_re)
        self.assertTrue(escopo.aplica_ri)
        # RN-043: Mapa Calor tambem aplicado por padrao para Setor ja
        # usado por Campo antes desta feature (default True do model).
        self.assertTrue(escopo.aplica_mapa_calor)

    def test_nao_sobrescreve_escopo_ja_configurado(self):
        Campo.objects.create(nome="Categoria", tipo=Campo.TIPO_TEXTO, setor_nome="Lastmile")
        SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)

        self._semear_escopo_padrao()

        escopo = SetorEscopo.objects.get(setor_nome="Lastmile")
        self.assertEqual(escopo.atividade, SetorEscopo.ATIVIDADE_ESCOLA)

    def test_campo_sem_setorescopo_mantem_comportamento_legado(self):
        """Setor usado por Campo mas ainda sem SetorEscopo (antes de rodar
        a semeadura): tratado como Sub-atividades RE e RI pelo restante do
        sistema (RN-037), nao um bug — ver `campos_grid_rede`, apps.leads."""
        Campo.objects.create(nome="Categoria", tipo=Campo.TIPO_TEXTO, setor_nome="Suprimentos")

        self.assertFalse(SetorEscopo.objects.filter(setor_nome="Suprimentos").exists())


class CampoCalculadoModelTests(TestCase):
    """PO-063/RN-039/ADR-024: validacao de `Campo.clean()` para o tipo
    Calculado e protecao contra exclusao do Campo base (on_delete=PROTECT
    — o valor calculado nunca deve sumir silenciosamente)."""

    def setUp(self):
        self.processo = Processo.objects.create(nome="Processo Calculado")
        Setor.objects.create(processo=self.processo, nome="Implantacao")
        self.campo_data = Campo.objects.create(
            nome="Início Implantação", tipo=Campo.TIPO_DATA, setor_nome="Implantacao",
        )

    def test_calculado_exige_campo_base(self):
        campo = Campo(nome="Data Final", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao", horas_prazo=72)

        with self.assertRaises(ValidationError):
            campo.full_clean()

    def test_calculado_exige_horas_prazo_positivo(self):
        campo = Campo(
            nome="Data Final", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao", campo_base=self.campo_data,
        )

        with self.assertRaises(ValidationError):
            campo.full_clean()

    def test_calculado_exige_campo_base_do_tipo_data(self):
        campo_texto = Campo.objects.create(nome="Observação", tipo=Campo.TIPO_TEXTO, setor_nome="Implantacao")
        campo = Campo(
            nome="Data Final", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=campo_texto, horas_prazo=72,
        )

        with self.assertRaises(ValidationError):
            campo.full_clean()

    def test_calculado_exige_campo_base_do_mesmo_setor(self):
        campo_data_outro_setor = Campo.objects.create(
            nome="Data em outro Setor", tipo=Campo.TIPO_DATA, setor_nome="Suprimentos",
        )
        campo = Campo(
            nome="Data Final", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=campo_data_outro_setor, horas_prazo=72,
        )

        with self.assertRaises(ValidationError):
            campo.full_clean()

    def test_calculado_valido_passa_na_validacao(self):
        campo = Campo(
            nome="Data Final Implantação", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=self.campo_data, horas_prazo=72,
        )

        campo.full_clean()  # nao deve levantar ValidationError

    def test_excluir_campo_base_de_um_calculado_e_bloqueado(self):
        Campo.objects.create(
            nome="Data Final Implantação", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=self.campo_data, horas_prazo=72,
        )

        with self.assertRaises(ProtectedError):
            self.campo_data.delete()


class CampoObrigatoriedadeTransicaoModelTests(TestCase):
    """PO-079/RN-061/ADR-031: regra de obrigatoriedade de um Campo ao
    trocar de Setor — o Setor de origem e sempre `campo.setor_nome`."""

    def setUp(self):
        self.campo = Campo.objects.create(nome="Numero do pedido", tipo=Campo.TIPO_TEXTO, setor_nome="Cotacao")

    def test_regra_valida_passa_na_validacao(self):
        regra = CampoObrigatoriedadeTransicao(campo=self.campo, setor_destino_nome="Suprimentos")

        regra.full_clean()  # nao deve levantar ValidationError

    def test_setor_destino_igual_ao_setor_dono_e_bloqueado(self):
        regra = CampoObrigatoriedadeTransicao(campo=self.campo, setor_destino_nome="Cotacao")

        with self.assertRaises(ValidationError):
            regra.full_clean()

    def test_campo_tipo_calculado_nao_pode_ter_regra(self):
        campo_base = Campo.objects.create(nome="Data Base", tipo=Campo.TIPO_DATA, setor_nome="Cotacao")
        campo_calculado = Campo.objects.create(
            nome="Prazo Final", tipo=Campo.TIPO_CALCULADO, setor_nome="Cotacao",
            campo_base=campo_base, horas_prazo=24,
        )
        regra = CampoObrigatoriedadeTransicao(campo=campo_calculado, setor_destino_nome="Suprimentos")

        with self.assertRaises(ValidationError):
            regra.full_clean()

    def test_duas_regras_para_o_mesmo_destino_e_bloqueado_no_banco(self):
        CampoObrigatoriedadeTransicao.objects.create(campo=self.campo, setor_destino_nome="Suprimentos")

        with self.assertRaises(IntegrityError), transaction.atomic():
            CampoObrigatoriedadeTransicao.objects.create(campo=self.campo, setor_destino_nome="Suprimentos")

    def test_mesmo_campo_pode_ter_regras_para_destinos_diferentes(self):
        CampoObrigatoriedadeTransicao.objects.create(campo=self.campo, setor_destino_nome="Suprimentos")
        CampoObrigatoriedadeTransicao.objects.create(campo=self.campo, setor_destino_nome="Compras")

        self.assertEqual(self.campo.regras_obrigatoriedade.count(), 2)

    def test_excluir_campo_exclui_regras_em_cascata(self):
        CampoObrigatoriedadeTransicao.objects.create(campo=self.campo, setor_destino_nome="Suprimentos")

        self.campo.delete()

        self.assertEqual(CampoObrigatoriedadeTransicao.objects.count(), 0)
