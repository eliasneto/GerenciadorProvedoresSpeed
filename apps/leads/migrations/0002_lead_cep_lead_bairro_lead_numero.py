from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='bairro',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Bairro'),
        ),
        migrations.AddField(
            model_name='lead',
            name='cep',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='CEP'),
        ),
        migrations.AddField(
            model_name='lead',
            name='numero',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Número'),
        ),
        migrations.AlterField(
            model_name='lead',
            name='endereco',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Logradouro / Endereço'),
        ),
    ]
