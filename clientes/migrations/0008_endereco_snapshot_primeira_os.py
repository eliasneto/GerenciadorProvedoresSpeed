from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0007_endereco_cidade_id_ixc'),
    ]

    operations = [
        migrations.AddField(
            model_name='endereco',
            name='contrato_id_ixc',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name='Contrato ID IXC'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='login_id_ixc',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name='Login ID IXC'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='possui_primeira_os',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Possui Primeira OS?'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='primeira_os_ixc',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Primeira OS IXC'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='primeira_os_setor_id_ixc',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Primeira OS Setor ID IXC'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='primeira_os_setor_nome',
            field=models.CharField(blank=True, max_length=150, null=True, verbose_name='Primeira OS Setor'),
        ),
        migrations.AddField(
            model_name='endereco',
            name='primeiro_ticket_ixc',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Primeiro Ticket IXC'),
        ),
    ]
