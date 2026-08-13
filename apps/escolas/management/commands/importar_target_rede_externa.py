import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.escolas.models import TargetRedeExterna


class Command(BaseCommand):
    """RN-057 Parte 3/ADR-029: importa (ou reimporta) por completo o
    catalogo TargetRedeExterna a partir de um CSV com colunas `uf`,
    `velocidade_mbps`, `valor` — mesmo formato da tabela de origem
    `target_rede_externa` (DashboardEACE). Sem endpoint de API para isso
    (ADR-029): a origem e uma exportacao manual feita pelo usuario a partir
    do sistema legado, nunca um dado fabricado por este comando."""

    help = (
        "Importa o catalogo TargetRedeExterna (UF + Velocidade -> Valor) a partir de um "
        "CSV com colunas uf,velocidade_mbps,valor. Usa update_or_create por (uf, velocidade_mbps), "
        "sem apagar combinacoes ja cadastradas que nao estiverem no arquivo."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Caminho para o CSV (uf,velocidade_mbps,valor).")
        parser.add_argument(
            "--delimiter", default=",", help="Delimitador do CSV (padrao: vírgula).",
        )

    def handle(self, *args, **options):
        caminho = options["csv_file"]
        delimitador = options["delimiter"]

        try:
            arquivo = open(caminho, mode="r", encoding="utf-8-sig", newline="")
        except OSError as erro:
            raise CommandError(f"Nao foi possivel abrir o arquivo '{caminho}': {erro}")

        criados = 0
        atualizados = 0
        ignorados = 0

        with arquivo:
            leitor = csv.DictReader(arquivo, delimiter=delimitador)
            colunas_esperadas = {"uf", "velocidade_mbps", "valor"}
            if not colunas_esperadas.issubset(set(leitor.fieldnames or [])):
                raise CommandError(
                    f"CSV precisa ter as colunas {sorted(colunas_esperadas)}; "
                    f"encontrado: {leitor.fieldnames}"
                )

            with transaction.atomic():
                for numero_linha, linha in enumerate(leitor, start=2):
                    uf = (linha.get("uf") or "").strip().upper()
                    velocidade_bruta = (linha.get("velocidade_mbps") or "").strip()
                    valor_bruto = (linha.get("valor") or "").strip()

                    if not uf or not velocidade_bruta or not valor_bruto:
                        self.stderr.write(self.style.WARNING(
                            f"Linha {numero_linha}: ignorada (uf/velocidade_mbps/valor ausente)."
                        ))
                        ignorados += 1
                        continue

                    try:
                        velocidade_mbps = int(velocidade_bruta)
                        valor = Decimal(valor_bruto)
                    except (ValueError, InvalidOperation):
                        self.stderr.write(self.style.WARNING(
                            f"Linha {numero_linha}: ignorada (velocidade_mbps/valor nao numerico)."
                        ))
                        ignorados += 1
                        continue

                    _obj, criado = TargetRedeExterna.objects.update_or_create(
                        uf=uf,
                        velocidade_mbps=velocidade_mbps,
                        defaults={"valor": valor},
                    )
                    if criado:
                        criados += 1
                    else:
                        atualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f"TargetRedeExterna: {criados} criado(s), {atualizados} atualizado(s), "
            f"{ignorados} linha(s) ignorada(s)."
        ))
