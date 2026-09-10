from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wireguard', '0037_peer_mfa_unlock_minutes'),
    ]

    operations = [
        migrations.AddField(
            model_name='peer',
            name='mfa_disconnect_grace_seconds',
            field=models.PositiveIntegerField(default=300),
        ),
        migrations.AddField(
            model_name='peer',
            name='mfa_lock_mode',
            field=models.CharField(
                choices=[
                    ('time', '時間でロック'),
                    ('disconnect', '切断検知でロック'),
                ],
                default='time',
                max_length=16,
            ),
        ),
    ]
