from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wireguard', '0032_remove_peer_enabled_by_schedule'),
    ]

    operations = [
        migrations.AlterField(
            model_name='peer',
            name='pre_shared_key',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
