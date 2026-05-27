import re
from django.core.management.base import BaseCommand
from leads.models import LeadEmpresa, Lead


def _converter_notacao_cientifica(valor):
    """Converte '5,42E+13' ou '5.42e+13' para '54200000000000'."""
    if not valor:
        return valor
    if not re.search(r'[eE][+\-]?\d+', str(valor)):
        return valor
    try:
        numero = int(float(str(valor).replace(',', '.')))
        return str(numero)
    except (ValueError, OverflowError):
        return valor


class Command(BaseCommand):
    help = 'Corrige CNPJs em notação científica (ex: 5,42E+13 → 54200000000000)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria corrigido sem salvar no banco.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN — nenhuma alteração será salva.\n'))

        corrigidos = 0

        for model, label in [(LeadEmpresa, 'LeadEmpresa'), (Lead, 'Lead')]:
            qs = model.objects.exclude(cnpj_cpf__isnull=True).exclude(cnpj_cpf='')
            for obj in qs.iterator():
                original = obj.cnpj_cpf
                normalizado = _converter_notacao_cientifica(original)
                if normalizado != original:
                    self.stdout.write(f'[{label} #{obj.pk}] {original!r} → {normalizado!r}')
                    if not dry_run:
                        obj.cnpj_cpf = normalizado
                        obj.save(update_fields=['cnpj_cpf'])
                    corrigidos += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n{corrigidos} registro(s) seriam corrigidos.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n{corrigidos} registro(s) corrigido(s) com sucesso.'))
