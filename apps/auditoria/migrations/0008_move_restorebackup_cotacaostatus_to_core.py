# PO-036 (ADR-007 item 8): remove RestoreBackupAuditoria e CotacaoStatusAuditoria
# do estado real de auditoria (as tabelas fisicas permanecem intocadas; o dono
# passa a ser apps.core - ver apps/core/migrations/0012_move_auditoria_models_from_auditoria.py)
# e recria os dois nomes como proxy do model agora hospedado em core, apenas
# para preservar a secao do Django Admin onde esses logs ja eram exibidos
# (mesmo precedente do IntegrationAudit/IntegrationAuditAuditoria).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0007_edicaoatendimentoixcauditoria'),
        ('core', '0012_move_auditoria_models_from_auditoria'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='RestoreBackupAuditoria'),
                migrations.DeleteModel(name='CotacaoStatusAuditoria'),
            ],
            database_operations=[],
        ),
        migrations.CreateModel(
            name='RestoreBackupAuditoria',
            fields=[],
            options={
                'verbose_name': 'Auditoria de Restore de Backup',
                'verbose_name_plural': 'Auditorias de Restore de Backup',
                'ordering': ['-criado_em'],
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('core.restorebackupauditoria',),
        ),
        migrations.CreateModel(
            name='CotacaoStatusAuditoria',
            fields=[],
            options={
                'verbose_name': 'Auditoria de Status da Cotacao',
                'verbose_name_plural': 'Auditorias de Status das Cotacoes',
                'ordering': ['-criado_em'],
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('core.cotacaostatusauditoria',),
        ),
    ]
