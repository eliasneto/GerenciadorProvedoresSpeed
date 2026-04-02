from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0018_proposal_status_fluxo_contratacao'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='proposal',
            name='responsavel',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='propostas_responsavel',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Responsável',
            ),
        ),
    ]
