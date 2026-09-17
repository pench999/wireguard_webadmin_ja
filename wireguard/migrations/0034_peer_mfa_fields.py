from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wireguard', '0033_alter_peer_pre_shared_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='peer',
            name='mfa_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='peer',
            name='mfa_unlocked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='peer',
            name='mfa_last_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
