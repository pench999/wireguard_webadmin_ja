from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wireguard', '0034_peer_mfa_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='peer',
            name='mfa_owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mfa_peers',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
