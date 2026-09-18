from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('wireguard', '0041_usermfadevice_client_device'),
    ]

    operations = [
        migrations.AddField(
            model_name='peer',
            name='mfa_client_required',
            field=models.BooleanField(default=False),
        ),
    ]
