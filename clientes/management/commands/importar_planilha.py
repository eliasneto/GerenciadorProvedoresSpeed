import csv
import uuid  # <-- IMPORTANTE: Adicionamos o gerador de ID único
from django.core.management.base import BaseCommand
from django.db import transaction
from clientes.models import Cliente, Endereco 

class Command(BaseCommand):
    help = 'Importa clientes e endereços de uma planilha CSV padronizada da Speed.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Caminho para o arquivo CSV')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']

        try:
            with open(csv_file, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file, delimiter=';')
                
                clientes_criados = 0
                enderecos_criados = 0

                self.stdout.write(self.style.WARNING(f'Iniciando processamento da planilha: {csv_file}...'))

                with transaction.atomic():
                    for row in reader:
                        nome_cliente = row.get('Cliente', '').strip()
                        if not nome_cliente:
                            continue

                        # GERA UM CNPJ FAKE ÚNICO PARA BURLAR AS TRAVAS DO BANCO (NOT NULL e UNIQUE)
                        cnpj_provisorio = f"IMPORT-{uuid.uuid4().hex[:8].upper()}"

                        cliente, created = Cliente.objects.get_or_create(
                            razao_social=nome_cliente,
                            defaults={
                                'nome_fantasia': nome_cliente,
                                'cnpj_cpf': cnpj_provisorio  # <-- Preenche com o valor provisório único
                            }
                        )
                        if created:
                            clientes_criados += 1

                        # Cria a Unidade
                        Endereco.objects.create(
                            cliente=cliente,
                            tipo=row.get('Login', '').strip()[:100] or 'Unidade Importada',
                            logradouro=row.get('Endereco', '').strip() or 'Não informado',
                            numero=row.get('Numero', '').strip() or 'S/N',
                            bairro=row.get('Bairro', '').strip(),
                            cidade=row.get('Cidade', '').strip(),
                            estado=row.get('Estado', '').strip()[:2],
                            status='ativo',
                            principal=False
                        )
                        enderecos_criados += 1

            self.stdout.write(self.style.SUCCESS(
                f'✅ Operação Speed concluída com sucesso: {clientes_criados} novos clientes e {enderecos_criados} unidades inseridas.'
            ))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'❌ Arquivo não encontrado: {csv_file}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro inesperado durante a importação: {str(e)}'))