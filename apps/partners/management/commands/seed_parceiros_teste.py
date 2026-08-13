from django.core.management.base import BaseCommand
from django.db import transaction

from apps.partners.models import Partner

# Dados ficticios de provedores de internet para apoio a teste manual.
# Nao representa clientes, parceiros ou empresas reais.
PROVEDORES_FICTICIOS = [
    "NetFibra Telecom",
    "VelozNet Internet",
    "ConectaSul Provedor",
    "FibraMax Telecomunicacoes",
    "Rede Horizonte Internet",
    "TurboLink Provedor",
    "SinalForte Telecom",
    "BandaLivre Internet",
    "ConexaoTotal Provedor",
    "FibraViva Telecomunicacoes",
    "NetPrime Internet",
    "AtlasNet Provedor",
    "LinkCerto Telecom",
    "OndaDigital Internet",
    "RotaFibra Provedor",
    "ZenithNet Telecomunicacoes",
    "InterConecta Provedor",
    "FibraExpress Internet",
    "NexoNet Telecom",
    "VoaNet Provedor",
    "PulsoDigital Internet",
    "TrilhaFibra Telecomunicacoes",
    "Conecta Norte Provedor",
    "SulNet Internet",
    "CentralFibra Telecom",
    "RedeAtiva Provedor",
    "NetHorizon Internet",
    "FibraSat Telecomunicacoes",
    "VeloxCity Provedor",
    "InfinityNet Internet",
    "PontoNet Telecom",
    "AraraFibra Provedor",
    "BrisaNet Internet",
    "CoraNet Telecomunicacoes",
    "DeltaFibra Provedor",
    "EixoNet Internet",
    "FluxoDigital Telecom",
    "GiraNet Provedor",
    "HiperLink Internet",
    "IguacuNet Telecomunicacoes",
    "JatoFibra Provedor",
    "KairosNet Internet",
    "LumenNet Telecom",
    "MetroFibra Provedor",
    "NimbusNet Internet",
    "OrbitaNet Telecomunicacoes",
    "PlanaltoNet Provedor",
    "QuantumFibra Internet",
    "RaioNet Telecom",
    "SertaoNet Provedor",
]

NOMES_CONTATO = [
    "Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Alves", "Elaine Costa",
    "Fabio Rocha", "Gabriela Nunes", "Hugo Ferreira", "Isabela Ramos", "Joao Pereira",
]


def gerar_cnpj_ficticio(indice):
    """Gera um CNPJ com formato plausivel (XX.XXX.XXX/0001-XX), apenas para
    diferenciacao no cadastro de teste. Nao corresponde a um CNPJ real ou validado."""
    base = 10000000 + indice
    base_str = f"{base:08d}"
    dv = 90 + (indice % 9)
    return f"{base_str[0:2]}.{base_str[2:5]}.{base_str[5:8]}/0001-{dv:02d}"


class Command(BaseCommand):
    help = (
        "Cria ~50 parceiros ficticios (provedores de internet) com dados basicos de "
        "cadastro, para apoio a teste manual. Idempotente por cnpj_cpf."
    )

    def handle(self, *args, **options):
        criados = 0
        existentes = 0

        with transaction.atomic():
            for indice, nome_fantasia in enumerate(PROVEDORES_FICTICIOS, start=1):
                cnpj = gerar_cnpj_ficticio(indice)
                contato = NOMES_CONTATO[indice % len(NOMES_CONTATO)]
                slug_email = (
                    nome_fantasia.lower()
                    .replace(" ", "")
                    .replace("ç", "c")
                    .replace("ã", "a")
                    .replace("á", "a")
                )
                partner, created = Partner.objects.get_or_create(
                    cnpj_cpf=cnpj,
                    defaults={
                        "razao_social": f"{nome_fantasia} Ltda",
                        "nome_fantasia": nome_fantasia,
                        "contato_nome": contato,
                        "email": f"contato@{slug_email}.com.br",
                        "telefone": f"(85) 9{8000 + indice:04d}-{indice:04d}",
                        "status": "ativo",
                    },
                )
                if created:
                    criados += 1
                else:
                    existentes += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluido. Parceiros ficticios criados: {criados}. "
                f"Ja existentes (ignorados): {existentes}."
            )
        )
