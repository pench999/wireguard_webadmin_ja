import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('user_manager', '0008_useracl_enable_audit_log'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserMfaSettings',
            fields=[
                ('totp_secret', models.CharField(blank=True, max_length=255)),
                ('totp_enabled', models.BooleanField(default=False)),
                ('default_unlock_minutes', models.PositiveIntegerField(default=480)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mfa_settings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
