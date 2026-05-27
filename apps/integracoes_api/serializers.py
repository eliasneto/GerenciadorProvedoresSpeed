from rest_framework import serializers

from clientes.models import Cliente, Endereco
from partners.models import Partner, Proposal


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            "id",
            "id_ixc",
            "razao_social",
            "nome_fantasia",
            "cnpj_cpf",
            "contato_nome",
            "email",
            "telefone",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class ClienteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            "id",
            "id_ixc",
            "razao_social",
            "nome_fantasia",
            "cnpj_cpf",
            "contato_nome",
            "email",
            "telefone",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class EnderecoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endereco
        fields = [
            "id",
            "cliente_id",
            "tipo",
            "cep",
            "logradouro",
            "numero",
            "bairro",
            "cidade",
            "estado",
            "login_ixc",
            "login_id_ixc",
            "contrato_id_ixc",
            "filial_ixc",
            "velocidade",
            "tecnologia",
            "status",
            "principal",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class EnderecoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endereco
        fields = [
            "id",
            "tipo",
            "cep",
            "logradouro",
            "numero",
            "bairro",
            "cidade",
            "estado",
            "login_ixc",
            "login_id_ixc",
            "contrato_id_ixc",
            "filial_ixc",
            "velocidade",
            "tecnologia",
            "status",
            "principal",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            "id",
            "razao_social",
            "cnpj_cpf",
            "nome_fantasia",
            "contato_nome",
            "email",
            "telefone",
            "status",
            "data_cadastro",
        ]
        read_only_fields = ["id", "data_cadastro"]


class PartnerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            "id",
            "razao_social",
            "cnpj_cpf",
            "nome_fantasia",
            "contato_nome",
            "email",
            "telefone",
            "status",
            "data_cadastro",
        ]
        read_only_fields = ["id", "data_cadastro"]


class ProposalSerializer(serializers.ModelSerializer):
    partner_nome = serializers.SerializerMethodField()
    cliente_nome = serializers.SerializerMethodField()
    codigo_exibicao = serializers.CharField(read_only=True)

    class Meta:
        model = Proposal
        fields = [
            "id",
            "partner_id",
            "partner_nome",
            "responsavel_id",
            "cliente_id",
            "cliente_nome",
            "client_address_id",
            "lead_id",
            "lead_endereco_id",
            "grupo_proposta_id",
            "codigo_proposta",
            "codigo_exibicao",
            "nome_proposta",
            "os_numero",
            "data_emissao",
            "velocidade",
            "tecnologia",
            "valor_mensal",
            "taxa_instalacao",
            "valor_parceiro",
            "status",
            "data_ativacao",
            "data_vencimento",
        ]
        read_only_fields = ["id", "partner_nome", "cliente_nome", "codigo_exibicao"]

    def get_partner_nome(self, obj):
        return obj.partner.nome_fantasia or obj.partner.razao_social or ""

    def get_cliente_nome(self, obj):
        if not obj.cliente:
            return ""
        return obj.cliente.nome_fantasia or obj.cliente.razao_social or ""


class ProposalCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proposal
        fields = [
            "id",
            "partner",
            "responsavel",
            "cliente",
            "client_address",
            "lead",
            "lead_endereco",
            "grupo_proposta_id",
            "codigo_proposta",
            "nome_proposta",
            "os_numero",
            "data_emissao",
            "velocidade",
            "tecnologia",
            "valor_mensal",
            "taxa_instalacao",
            "valor_parceiro",
            "status",
            "data_ativacao",
        ]
        read_only_fields = ["id"]
