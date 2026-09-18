import hashlib
import uuid

import pyotp
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from user_manager.models import UserAcl, UserMfaSettings
from wireguard.models import UserMfaDevice
from wireguard_tools.models import AuditLog


class UserMfaSetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vpn-user', password='Test-pass-123!')
        UserAcl.objects.create(user=self.user, user_level=0)
        self.client.force_login(self.user)

    def test_setup_button_is_inside_single_post_form(self):
        response = self.client.get('/user/mfa/setup/')

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        form_start = content.index('<form method="post">')
        submit_button = content.index('type="submit"', form_start)
        form_end = content.index('</form>', form_start)
        self.assertLess(form_start, submit_button)
        self.assertLess(submit_button, form_end)
        self.assertEqual(content.count('<form'), 1)
        self.assertEqual(content.count('</form>'), 1)

    def test_valid_totp_enables_mfa(self):
        self.client.get('/user/mfa/setup/')
        secret = self.client.session['pending_mfa_totp_secret']

        response = self.client.post('/user/mfa/setup/', {
            'totp_pin': pyotp.TOTP(secret).now(),
        })

        self.assertRedirects(response, '/vpn/?setup=1', fetch_redirect_response=False)
        settings = UserMfaSettings.objects.get(user=self.user)
        self.assertTrue(settings.totp_enabled)


class UserMfaDeviceAdminTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vpn-user', password='Test-pass-123!')
        UserAcl.objects.create(user=self.user, user_level=0)
        self.admin = User.objects.create_user(username='admin', password='Test-pass-123!')
        UserAcl.objects.create(user=self.admin, user_level=50)
        self.device = UserMfaDevice.objects.create(
            user=self.user,
            device_id=uuid.uuid4(),
            name='TEST-PC',
            token_hash=hashlib.sha256(b'test-device-token').hexdigest(),
        )

    def test_non_admin_cannot_view_registered_devices(self):
        self.client.force_login(self.user)

        response = self.client.get('/user/mfa/devices/')

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'access_denied.html')

    def test_admin_can_revoke_registered_device(self):
        self.client.force_login(self.admin)

        response = self.client.post('/user/mfa/devices/', {
            'device_uuid': str(self.device.uuid),
            'action': 'revoke',
        })

        self.assertRedirects(response, '/user/mfa/devices/', fetch_redirect_response=False)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.revoked_at)
        self.assertTrue(AuditLog.objects.filter(action='mfa_device_revoked', user=self.admin).exists())

    def test_admin_can_allow_revoked_device_to_register_again(self):
        self.device.revoked_at = timezone.now()
        self.device.save(update_fields=['revoked_at', 'updated'])
        self.client.force_login(self.admin)

        response = self.client.post('/user/mfa/devices/', {
            'device_uuid': str(self.device.uuid),
            'action': 'delete',
        })

        self.assertRedirects(response, '/user/mfa/devices/', fetch_redirect_response=False)
        self.assertFalse(UserMfaDevice.objects.filter(uuid=self.device.uuid).exists())
