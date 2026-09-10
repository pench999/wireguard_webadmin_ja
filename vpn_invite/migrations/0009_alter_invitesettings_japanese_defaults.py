from django.db import migrations, models


DEFAULT_INVITE_MESSAGE = '''こんにちは。

安全な WireGuard VPN ネットワークへの招待です。以下のリンクから、あなた専用の VPN 設定にアクセスしてください。

{invite_url}

注意: この招待リンクは {expire_minutes} 分後に期限切れになります。期限切れ後に新しいリンクが必要な場合は、再度招待を依頼してください。'''


class Migration(migrations.Migration):

    dependencies = [
        ('vpn_invite', '0008_alter_invitesettings_invite_email_body_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invitesettings',
            name='download_instructions',
            field=models.TextField(default='下のリンクからお使いのデバイス用の WireGuard アプリをダウンロードしてください。インストール後、QR コードを読み取るか設定ファイルをダウンロードして、デバイスへ取り込めます。'),
        ),
        migrations.AlterField(
            model_name='invitesettings',
            name='invite_email_body',
            field=models.TextField(default=DEFAULT_INVITE_MESSAGE),
        ),
        migrations.AlterField(
            model_name='invitesettings',
            name='invite_email_subject',
            field=models.CharField(blank=True, default='WireGuard VPN 招待', max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='invitesettings',
            name='invite_text_body',
            field=models.TextField(default=DEFAULT_INVITE_MESSAGE),
        ),
        migrations.AlterField(
            model_name='invitesettings',
            name='invite_whatsapp_body',
            field=models.TextField(default=DEFAULT_INVITE_MESSAGE),
        ),
    ]
