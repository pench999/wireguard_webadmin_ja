from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wireguard', '0035_peer_mfa_owner'),
    ]

    operations = [
        migrations.RenameField(
            model_name='peer',
            old_name='mfa_owner',
            new_name='assigned_user',
        ),
        migrations.AlterField(
            model_name='peer',
            name='assigned_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_peers',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
