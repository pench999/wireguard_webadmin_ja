from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wireguard', '0036_rename_mfa_owner_assigned_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='peer',
            name='mfa_unlock_minutes',
            field=models.PositiveIntegerField(default=120),
        ),
    ]
