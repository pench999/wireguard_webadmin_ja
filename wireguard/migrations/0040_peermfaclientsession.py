import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wireguard', '0039_peer_mfa_trusted_browser_required'),
    ]

    operations = [
        migrations.CreateModel(
            name='PeerMfaClientSession',
            fields=[
                ('status', models.CharField(choices=[('pending', 'Pending'), ('authorizing', 'Authorizing'), ('unlocked', 'Unlocked'), ('failed', 'Failed'), ('expired', 'Expired'), ('cancelled', 'Cancelled'), ('locked', 'Locked')], default='pending', max_length=16)),
                ('browser_token_hash', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('poll_token_hash', models.CharField(max_length=64)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('authorized_at', models.DateTimeField(blank=True, null=True)),
                ('error_code', models.CharField(blank=True, max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('peer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mfa_client_sessions', to='wireguard.peer')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wireguard_mfa_client_sessions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
