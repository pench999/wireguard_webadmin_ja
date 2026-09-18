import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wireguard', '0040_peermfaclientsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserMfaDevice',
            fields=[
                ('device_id', models.UUIDField(unique=True)),
                ('name', models.CharField(max_length=120)),
                ('token_hash', models.CharField(max_length=64)),
                ('registered_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wireguard_mfa_devices', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='peermfaclientsession', name='device_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='peermfaclientsession', name='device_name',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='peermfaclientsession', name='device_token_hash',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='peermfaclientsession', name='registered_device',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='client_sessions', to='wireguard.usermfadevice'),
        ),
    ]
