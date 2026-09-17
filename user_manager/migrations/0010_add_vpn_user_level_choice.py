from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_manager', '0009_usermfasettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useracl',
            name='user_level',
            field=models.PositiveIntegerField(
                choices=[
                    (0, 'VPNユーザー'),
                    (10, 'Debugging Analyst'),
                    (20, 'View Only'),
                    (30, 'Peer Manager'),
                    (40, 'WireGuard Manager'),
                    (50, 'Administrator'),
                ],
                default=0,
            ),
        ),
    ]
