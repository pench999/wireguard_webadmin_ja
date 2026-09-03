import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from wireguard.models import Peer

DEFAULT_INVITE_MESSAGE = _('''こんにちは。

安全な WireGuard VPN ネットワークへの招待です。以下のリンクから、あなた専用の VPN 設定にアクセスしてください。

{invite_url}

注意: この招待リンクは {expire_minutes} 分後に期限切れになります。期限切れ後に新しいリンクが必要な場合は、再度招待を依頼してください。''')

DEFAULT_HTML_MESSAGE = _('''<h2>VPN セットアップへようこそ</h2>
<p>まず、下のリンクからお使いのデバイス用の WireGuard アプリをダウンロードしてください。</p>
<p>インストール後、<strong>QR コードを読み取る</strong>か、<strong>設定ファイルをダウンロード</strong>することで、すぐに設定を取り込み、安全な VPN 接続を利用できます。</p>''')

class InviteSettings(models.Model):
    name = models.CharField(max_length=16, default='default_settings', unique=True)
    default_password = models.CharField(max_length=32, default='', blank=True, null=True)
    enforce_random_password = models.BooleanField(default=True)
    required_user_level = models.PositiveIntegerField(default=50, choices=(
        (20, _('View Only')), (30, _('Peer Manager')), (40, _('WireGuard Manager')), (50, _('Administrator')),
    ))
    random_password_length = models.IntegerField(default=6)
    random_password_complexity = models.CharField(
        max_length=22, default='letters_digits', choices=(
            ('letters_digits_special', _('Letters, Digits, Special Characters')),
            ('letters_digits', _('Letters, Digits')), ('letters', _('Letters')), ('digits', _('Digits'))
        )
    )
    invite_expiration = models.IntegerField(default=30) # minutes
    download_1_label = models.CharField(max_length=32, default='iOS', blank=True, null=True)
    download_2_label = models.CharField(max_length=32, default='Android', blank=True, null=True)
    download_3_label = models.CharField(max_length=32, default='Windows', blank=True, null=True)
    download_4_label = models.CharField(max_length=32, default='macOS', blank=True, null=True)
    download_5_label = models.CharField(max_length=32, default='Linux', blank=True, null=True)
    download_1_icon = models.CharField(max_length=32, default='fab fa-app-store-ios', blank=True, null=True)
    download_2_icon = models.CharField(max_length=32, default='fab fa-google-play', blank=True, null=True)
    download_3_icon = models.CharField(max_length=32, default='fab fa-windows', blank=True, null=True)
    download_4_icon = models.CharField(max_length=32, default='fab fa-apple', blank=True, null=True)
    download_5_icon = models.CharField(max_length=32, default='fas fa-desktop', blank=True, null=True)
    download_1_url = models.URLField(default='https://apps.apple.com/us/app/wireguard/id1441195209', blank=True, null=True)
    download_2_url = models.URLField(default='https://play.google.com/store/apps/details?id=com.wireguard.android', blank=True, null=True)
    download_3_url = models.URLField(default='https://download.wireguard.com/windows-client/wireguard-installer.exe', blank=True, null=True)
    download_4_url = models.URLField(default='https://apps.apple.com/us/app/wireguard/id1451685025', blank=True, null=True)
    download_5_url = models.URLField(default='https://www.wireguard.com/install/', blank=True, null=True)
    download_1_enabled = models.BooleanField(default=True)
    download_2_enabled = models.BooleanField(default=True)
    download_3_enabled = models.BooleanField(default=True)
    download_4_enabled = models.BooleanField(default=True)
    download_5_enabled = models.BooleanField(default=True)
    download_instructions = models.TextField(default=_('下のリンクからお使いのデバイス用の WireGuard アプリをダウンロードしてください。インストール後、QR コードを読み取るか設定ファイルをダウンロードして、デバイスへ取り込めます。'))

    invite_url = models.URLField(default='')

    invite_text_body = models.TextField(default=DEFAULT_INVITE_MESSAGE)

    invite_email_subject = models.CharField(max_length=64, default=_('WireGuard VPN 招待'), blank=True, null=True)
    invite_email_body = models.TextField(default=DEFAULT_INVITE_MESSAGE)
    invite_email_enabled = models.BooleanField(default=True)

    invite_whatsapp_body = models.TextField(default=DEFAULT_INVITE_MESSAGE)
    invite_whatsapp_enabled = models.BooleanField(default=True)

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class PeerInvite(models.Model):
    peer = models.ForeignKey(Peer, on_delete=models.CASCADE)
    invite_password = models.CharField(max_length=32, default='')
    invite_expiration = models.DateTimeField()

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)