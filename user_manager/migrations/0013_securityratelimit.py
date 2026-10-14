from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('user_manager', '0012_usermfasettings_trusted_browser_registered_at_and_more')]
    operations = [
        migrations.CreateModel(
            name='SecurityRateLimit',
            fields=[
                ('key', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('count', models.PositiveIntegerField(default=0)),
                ('expires_at', models.DateTimeField(db_index=True)),
            ],
        ),
    ]
