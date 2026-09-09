from django.db import migrations, models


def enable_audit_log_for_administrators(apps, schema_editor):
    UserAcl = apps.get_model('user_manager', 'UserAcl')
    UserAcl.objects.filter(user_level__gte=50).update(enable_audit_log=True)


class Migration(migrations.Migration):

    dependencies = [
        ('user_manager', '0007_alter_useracl_user_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='useracl',
            name='enable_audit_log',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(enable_audit_log_for_administrators, migrations.RunPython.noop),
    ]
