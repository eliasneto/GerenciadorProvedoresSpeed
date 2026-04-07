from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0008_remove_partner_aguardando_ativacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='designador',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Designador'),
        ),
    ]
