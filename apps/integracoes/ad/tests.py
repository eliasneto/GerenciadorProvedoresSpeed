from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.integracoes.ad import ad_sync


class SincronizarNomeUsuarioTests(TestCase):
    """PO-080: nome (first_name/last_name) sincronizado do AD (displayName/sn)."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="elias.neto@howbe.local",
            email="elias.neto@howbe.local",
            password="senha-teste",
        )

    def test_usuario_invalido_nao_sincroniza(self):
        atualizado, motivo = ad_sync.sincronizar_nome_usuario(None)
        self.assertFalse(atualizado)
        self.assertEqual(motivo, "usuario_invalido")

    def test_ldap_indisponivel_nao_sincroniza(self):
        client = MagicMock()
        client.ready.return_value = False

        atualizado, motivo = ad_sync.sincronizar_nome_usuario(self.user, client=client)

        self.assertFalse(atualizado)
        self.assertEqual(motivo, "ldap_indisponivel")

    def test_nome_nao_encontrado_no_ad(self):
        client = MagicMock()
        client.ready.return_value = True
        client.buscar_nome.return_value = ("", "")

        atualizado, motivo = ad_sync.sincronizar_nome_usuario(self.user, client=client)

        self.assertFalse(atualizado)
        self.assertEqual(motivo, "nome_nao_encontrado")

    def test_nome_ja_atualizado_nao_grava_novamente(self):
        self.user.first_name = "Elias"
        self.user.last_name = "Neto"
        self.user.save(update_fields=["first_name", "last_name"])

        client = MagicMock()
        client.ready.return_value = True
        client.buscar_nome.return_value = ("Elias", "Neto")

        with patch.object(get_user_model(), "save") as save_mock:
            atualizado, motivo = ad_sync.sincronizar_nome_usuario(self.user, client=client)

        self.assertFalse(atualizado)
        self.assertEqual(motivo, "nome_ja_atualizado")
        save_mock.assert_not_called()

    def test_nome_e_sobrenome_sincronizados_do_ad(self):
        client = MagicMock()
        client.ready.return_value = True
        client.buscar_nome.return_value = ("Elias", "Neto")

        atualizado, resultado = ad_sync.sincronizar_nome_usuario(self.user, client=client)

        self.user.refresh_from_db()
        self.assertTrue(atualizado)
        self.assertEqual(self.user.first_name, "Elias")
        self.assertEqual(self.user.last_name, "Neto")
        self.assertEqual(resultado, "Elias Neto")

    def test_sobrenome_vazio_no_ad_nao_apaga_valor_existente(self):
        self.user.last_name = "Neto"
        self.user.save(update_fields=["last_name"])

        client = MagicMock()
        client.ready.return_value = True
        client.buscar_nome.return_value = ("Elias", "")

        atualizado, _ = ad_sync.sincronizar_nome_usuario(self.user, client=client)

        self.user.refresh_from_db()
        self.assertTrue(atualizado)
        self.assertEqual(self.user.first_name, "Elias")
        self.assertEqual(self.user.last_name, "Neto")


class ADDirectoryClientBuscarNomeTests(TestCase):
    def test_buscar_nome_extrai_displayname_e_sn(self):
        client = ad_sync.ADDirectoryClient()
        with patch.object(client, "buscar_usuario", return_value=("dn", {
            "displayName": [b"Elias Neto"],
            "sn": [b"Neto"],
        })):
            first_name, last_name = client.buscar_nome("elias.neto@howbe.local")

        self.assertEqual(first_name, "Elias Neto")
        self.assertEqual(last_name, "Neto")

    def test_buscar_nome_sem_usuario_no_ldap_retorna_vazio(self):
        client = ad_sync.ADDirectoryClient()
        with patch.object(client, "buscar_usuario", return_value=(None, {})):
            first_name, last_name = client.buscar_nome("desconhecido")

        self.assertEqual((first_name, last_name), ("", ""))


class SincronizarNomeUsuarioNoLoginTests(TestCase):
    """Receiver conectado a `user_logged_in` (mesmo padrao do sync de e-mail)."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="elias.neto@howbe.local",
            email="elias.neto@howbe.local",
            password="senha-teste",
        )

    def test_receiver_atualiza_nome_quando_sincronizacao_tem_sucesso(self):
        with patch.object(
            ad_sync, "sincronizar_nome_usuario", return_value=(True, "Elias Neto")
        ) as sync_mock:
            ad_sync.sincronizar_nome_usuario_no_login(sender=None, user=self.user, request=None)

        sync_mock.assert_called_once_with(self.user)

    def test_receiver_nao_propaga_excecao(self):
        with patch.object(
            ad_sync, "sincronizar_nome_usuario", side_effect=Exception("falha ldap")
        ):
            try:
                ad_sync.sincronizar_nome_usuario_no_login(sender=None, user=self.user, request=None)
            except Exception:  # noqa: BLE001
                self.fail("o receiver nao deve propagar excecao do sync do AD")
