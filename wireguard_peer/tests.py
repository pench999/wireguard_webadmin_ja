from datetime import timedelta
import hashlib
import json
import uuid
from unittest.mock import patch
from urllib.parse import urlparse

import pyotp
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from scheduler.models import PeerScheduling
from user_manager.models import UserAcl, UserMfaSettings
from user_manager.trusted_browser import TRUSTED_BROWSER_COOKIE_NAME, hash_trusted_browser_token
from wireguard.models import Peer, PeerMfaClientSession, UserMfaDevice, WireGuardInstance
from wireguard_tools.models import AuditLog


class PeerMfaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vpn-user", password="StrongPass!123")
        UserAcl.objects.create(user=self.user, user_level=0)
        self.other_user = User.objects.create_user(username="other-user", password="StrongPass!123")
        UserAcl.objects.create(user=self.other_user, user_level=0)
        self.admin = User.objects.create_user(username="admin-user", password="StrongPass!123")
        UserAcl.objects.create(user=self.admin, user_level=50)
        self.instance = WireGuardInstance.objects.create(
            instance_id=0,
            private_key="private",
            public_key="public",
            hostname="vpn.example.test",
            listen_port=51820,
            address="10.50.0.1",
            netmask=24,
        )
        self.peer = Peer.objects.create(
            name="assigned-peer",
            public_key="peer-public",
            private_key="peer-private",
            wireguard_instance=self.instance,
            assigned_user=self.user,
            mfa_required=True,
            mfa_unlock_minutes=30,
        )
        self.other_peer = Peer.objects.create(
            name="other-peer",
            public_key="other-public",
            private_key="other-private",
            wireguard_instance=self.instance,
            assigned_user=self.other_user,
        )

    def test_time_and_disconnect_lock_modes(self):
        self.peer.mfa_lock_mode = "time"
        self.peer.mfa_unlocked_until = timezone.now() - timedelta(seconds=1)
        self.assertFalse(self.peer.mfa_unlocked)

        self.peer.mfa_lock_mode = "disconnect"
        self.assertTrue(self.peer.mfa_unlocked)
        self.peer.mfa_unlocked_until = None
        self.assertFalse(self.peer.mfa_unlocked)

    def test_vpn_user_is_redirected_from_admin_console(self):
        self.client.force_login(self.user)
        response = self.client.get("/status/")
        self.assertRedirects(response, "/vpn/", fetch_redirect_response=False)

    def test_portal_lists_only_assigned_peers(self):
        UserMfaSettings.objects.create(
            user=self.user,
            totp_secret="JBSWY3DPEHPK3PXP",
            totp_enabled=True,
        )
        self.client.force_login(self.user)
        response = self.client.get("/vpn/?setup=1")
        self.assertEqual(response.status_code, 200)
        peers = list(response.context["peers"])
        self.assertEqual(peers, [self.peer])

    def test_portal_redirects_single_locked_peer_to_mfa(self):
        UserMfaSettings.objects.create(
            user=self.user,
            totp_secret="JBSWY3DPEHPK3PXP",
            totp_enabled=True,
        )
        self.client.force_login(self.user)
        response = self.client.get("/vpn/")
        self.assertRedirects(
            response,
            f"/peer/mfa_unlock/?peer={self.peer.uuid}",
            fetch_redirect_response=False,
        )

    @patch("wireguard_peer.views.export_wireguard_configuration")
    @patch("wireguard_peer.views.func_reload_wireguard_interface", return_value=(True, "ok"))
    def test_valid_totp_unlocks_assigned_peer(self, mock_reload, mock_export):
        secret = "JBSWY3DPEHPK3PXP"
        UserMfaSettings.objects.create(user=self.user, totp_secret=secret, totp_enabled=True)
        self.client.force_login(self.user)

        response = self.client.post(
            f"/peer/mfa_unlock/?peer={self.peer.uuid}",
            {"totp_pin": pyotp.TOTP(secret).now()},
        )

        self.assertRedirects(response, "/vpn/", fetch_redirect_response=False)
        self.peer.refresh_from_db()
        self.assertTrue(self.peer.mfa_unlocked)
        self.assertIsNotNone(self.peer.mfa_last_verified_at)
        self.assertTrue(AuditLog.objects.filter(action="peer_mfa_unlocked", user=self.user).exists())
        mock_export.assert_called_once_with(self.instance)
        mock_reload.assert_called_once_with(self.instance)

    def test_trusted_browser_requirement_blocks_missing_cookie(self):
        UserMfaSettings.objects.create(
            user=self.user,
            totp_secret="JBSWY3DPEHPK3PXP",
            totp_enabled=True,
            trusted_browser_token_hash=hash_trusted_browser_token("registered-token"),
        )
        self.peer.mfa_trusted_browser_required = True
        self.peer.save(update_fields=["mfa_trusted_browser_required", "updated"])
        self.client.force_login(self.user)

        response = self.client.get(f"/peer/mfa_unlock/?peer={self.peer.uuid}")

        self.assertRedirects(response, "/vpn/?setup=1", fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(action="vpn_mfa_untrusted_browser_blocked").exists())

    @patch("wireguard_peer.views.export_wireguard_configuration")
    @patch("wireguard_peer.views.func_reload_wireguard_interface", return_value=(True, "ok"))
    def test_trusted_browser_cookie_allows_mfa_form(self, mock_reload, mock_export):
        token = "registered-token"
        UserMfaSettings.objects.create(
            user=self.user,
            totp_secret="JBSWY3DPEHPK3PXP",
            totp_enabled=True,
            trusted_browser_token_hash=hash_trusted_browser_token(token),
        )
        self.peer.mfa_trusted_browser_required = True
        self.peer.save(update_fields=["mfa_trusted_browser_required", "updated"])
        self.client.cookies[TRUSTED_BROWSER_COOKIE_NAME] = token
        self.client.force_login(self.user)

        response = self.client.get(f"/peer/mfa_unlock/?peer={self.peer.uuid}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VPN接続のMFA認証")

    @patch("wireguard_peer.views.export_wireguard_configuration")
    @patch("wireguard_peer.views.func_reload_wireguard_interface", return_value=(True, "ok"))
    def test_admin_can_bypass_mfa(self, mock_reload, mock_export):
        self.client.force_login(self.admin)
        response = self.client.post(f"/peer/mfa_unlock/?peer={self.peer.uuid}")

        self.assertRedirects(
            response,
            f"/peer/manage/?peer={self.peer.uuid}",
            fetch_redirect_response=False,
        )
        self.peer.refresh_from_db()
        self.assertTrue(self.peer.mfa_unlocked)
        audit = AuditLog.objects.get(action="peer_mfa_unlocked", user=self.admin)
        self.assertTrue(audit.details["bypass_mfa"])

    @patch("api.views.get_api_key", return_value="test-cron-key")
    @patch("api.views.export_wireguard_configuration")
    @patch("api.views.func_reload_wireguard_interface", return_value=(True, "ok"))
    def test_scheduler_disable_clears_mfa_unlock(self, mock_reload, mock_export, mock_key):
        self.peer.mfa_unlocked_until = timezone.now() + timedelta(minutes=30)
        self.peer.save(update_fields=["mfa_unlocked_until", "updated"])
        PeerScheduling.objects.create(
            peer=self.peer,
            next_scheduled_disable_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get("/api/cron/peer_scheduler/?cron_key=test-cron-key")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mfa_peers_locked"], 1)
        self.peer.refresh_from_db()
        self.assertTrue(self.peer.disabled_by_schedule)
        self.assertIsNone(self.peer.mfa_unlocked_until)
        self.assertTrue(AuditLog.objects.filter(action="peer_mfa_locked").exists())


class PeerMfaClientSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='client-user', password='StrongPass!123')
        UserAcl.objects.create(user=self.user, user_level=0)
        self.other_user = User.objects.create_user(username='other-client', password='StrongPass!123')
        UserAcl.objects.create(user=self.other_user, user_level=0)
        self.secret = 'JBSWY3DPEHPK3PXP'
        UserMfaSettings.objects.create(user=self.user, totp_secret=self.secret, totp_enabled=True)
        self.instance = WireGuardInstance.objects.create(
            instance_id=10,
            private_key='private',
            public_key='public',
            hostname='vpn.example.test',
            listen_port=51830,
            address='10.60.0.1',
            netmask=24,
        )
        self.peer = Peer.objects.create(
            name='client-peer',
            public_key='client-public',
            private_key='client-private',
            wireguard_instance=self.instance,
            assigned_user=self.user,
            mfa_required=True,
            mfa_unlock_minutes=30,
        )
        self.device_id = uuid.uuid4()
        self.device_token = 'test-device-token-' + ('a' * 32)
        self.device_name = 'TEST-PC'

    def test_portal_redirects_reset_allowed_user_to_mfa_setup(self):
        mfa_settings = UserMfaSettings.objects.get(user=self.user)
        mfa_settings.reset_allowed = True
        mfa_settings.save(update_fields=['reset_allowed', 'updated'])
        self.client.force_login(self.user)

        response = self.client.get('/vpn/')

        self.assertRedirects(response, '/user/mfa/setup/', fetch_redirect_response=False)

    def test_portal_does_not_offer_browser_unlock_for_client_required_peer(self):
        self.peer.mfa_client_required = True
        self.peer.save(update_fields=['mfa_client_required', 'updated'])
        self.client.force_login(self.user)

        response = self.client.get('/vpn/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MFA Clientから接続してください')
        self.assertNotContains(
            response,
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
        )

    def test_direct_browser_unlock_is_blocked_for_client_required_peer(self):
        self.peer.mfa_client_required = True
        self.peer.save(update_fields=['mfa_client_required', 'updated'])
        self.client.force_login(self.user)

        response = self.client.get(f'/peer/mfa_unlock/?peer={self.peer.uuid}')

        self.assertRedirects(response, '/vpn/?setup=1', fetch_redirect_response=False)
        self.peer.refresh_from_db()
        self.assertFalse(self.peer.mfa_unlocked)

    def _create_session(self, include_device=True, device_token=None):
        payload = {'peer_uuid': str(self.peer.uuid)}
        if include_device:
            payload.update({
                'device_id': str(self.device_id),
                'device_token': device_token or self.device_token,
                'device_name': self.device_name,
            })
        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _authorize_browser(self, session_data, user=None):
        self.client.force_login(user or self.user)
        browser_path = urlparse(session_data['browser_url']).path
        return self.client.get(browser_path)

    def test_create_and_poll_pending_session(self):
        data = self._create_session()
        client_session = PeerMfaClientSession.objects.get(uuid=data['session_id'])
        self.assertNotEqual(client_session.poll_token_hash, data['poll_token'])
        self.assertNotIn(data['poll_token'], data['browser_url'])

        response = self.client.get(
            f"/api/client/v1/sessions/{data['session_id']}/status/",
            HTTP_AUTHORIZATION=f"Bearer {data['poll_token']}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], PeerMfaClientSession.STATUS_PENDING)

    def test_registered_device_can_create_session(self):
        device = UserMfaDevice.objects.create(
            user=self.user,
            device_id=self.device_id,
            name=self.device_name,
            token_hash=hashlib.sha256(self.device_token.encode()).hexdigest(),
        )

        data = self._create_session()

        self.assertEqual(data['device_status'], 'registered')
        client_session = PeerMfaClientSession.objects.get(uuid=data['session_id'])
        self.assertEqual(client_session.registered_device, device)

    def test_registered_device_rejects_wrong_token(self):
        UserMfaDevice.objects.create(
            user=self.user,
            device_id=self.device_id,
            name=self.device_name,
            token_hash=hashlib.sha256(self.device_token.encode()).hexdigest(),
        )

        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps({
                'peer_uuid': str(self.peer.uuid),
                'device_id': str(self.device_id),
                'device_token': 'wrong-device-token-' + ('b' * 32),
                'device_name': self.device_name,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'device_unauthorized')

    def test_revoked_device_cannot_create_session(self):
        UserMfaDevice.objects.create(
            user=self.user,
            device_id=self.device_id,
            name=self.device_name,
            token_hash=hashlib.sha256(self.device_token.encode()).hexdigest(),
            revoked_at=timezone.now(),
        )

        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps({
                'peer_uuid': str(self.peer.uuid),
                'device_id': str(self.device_id),
                'device_token': self.device_token,
                'device_name': self.device_name,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'device_revoked')

    def test_legacy_client_is_rejected_after_device_registration(self):
        UserMfaDevice.objects.create(
            user=self.user,
            device_id=self.device_id,
            name=self.device_name,
            token_hash=hashlib.sha256(self.device_token.encode()).hexdigest(),
        )

        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps({'peer_uuid': str(self.peer.uuid)}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'device_required')

    def test_client_required_peer_rejects_legacy_client_before_registration(self):
        self.peer.mfa_client_required = True
        self.peer.save(update_fields=['mfa_client_required', 'updated'])

        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps({'peer_uuid': str(self.peer.uuid)}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'device_required')

    def test_second_device_registration_is_rejected(self):
        UserMfaDevice.objects.create(
            user=self.user,
            device_id=uuid.uuid4(),
            name='FIRST-PC',
            token_hash=hashlib.sha256(b'first-device-token').hexdigest(),
        )

        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps({
                'peer_uuid': str(self.peer.uuid),
                'device_id': str(self.device_id),
                'device_token': self.device_token,
                'device_name': self.device_name,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'device_registration_not_allowed')

    def test_poll_rejects_invalid_token(self):
        data = self._create_session()
        response = self.client.get(
            f"/api/client/v1/sessions/{data['session_id']}/status/",
            HTTP_AUTHORIZATION='Bearer invalid',
        )
        self.assertEqual(response.status_code, 401)

    def test_create_rejects_invalid_peer_uuid(self):
        response = self.client.post(
            '/api/client/v1/sessions/',
            data=json.dumps({'peer_uuid': 'not-a-uuid'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error'], 'peer_unavailable')

    def test_browser_connect_rejects_unassigned_user(self):
        data = self._create_session()
        response = self._authorize_browser(data, user=self.other_user)
        self.assertEqual(response.status_code, 404)
        client_session = PeerMfaClientSession.objects.get(uuid=data['session_id'])
        self.assertEqual(client_session.status, PeerMfaClientSession.STATUS_PENDING)

    def test_mfa_reset_resumes_client_authorization(self):
        mfa_settings = UserMfaSettings.objects.get(user=self.user)
        mfa_settings.reset_allowed = True
        mfa_settings.save(update_fields=['reset_allowed', 'updated'])
        self.peer.mfa_client_required = True
        self.peer.save(update_fields=['mfa_client_required', 'updated'])
        data = self._create_session()
        connect_response = self._authorize_browser(data)
        self.assertRedirects(
            connect_response,
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
            fetch_redirect_response=False,
        )

        unlock_response = self.client.get(connect_response.url)
        self.assertRedirects(
            unlock_response,
            '/user/mfa/setup/',
            fetch_redirect_response=False,
        )
        setup_response = self.client.get('/user/mfa/setup/')
        self.assertEqual(setup_response.status_code, 200)
        pending_secret = self.client.session['pending_mfa_totp_secret']

        response = self.client.post('/user/mfa/setup/', {
            'totp_pin': pyotp.TOTP(pending_secret).now(),
        })

        self.assertRedirects(
            response,
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
            fetch_redirect_response=False,
        )
        mfa_settings.refresh_from_db()
        self.assertFalse(mfa_settings.reset_allowed)

    @patch('wireguard_peer.views.export_wireguard_configuration')
    @patch('wireguard_peer.views.func_reload_wireguard_interface', return_value=(True, 'ok'))
    def test_browser_mfa_unlock_updates_poll_status(self, mock_reload, mock_export):
        self.peer.mfa_client_required = True
        self.peer.mfa_trusted_browser_required = True
        self.peer.save(update_fields=[
            'mfa_client_required',
            'mfa_trusted_browser_required',
            'updated',
        ])
        data = self._create_session()
        response = self._authorize_browser(data)
        self.assertRedirects(
            response,
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
            fetch_redirect_response=False,
        )

        response = self.client.post(
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
            {'totp_pin': pyotp.TOTP(self.secret).now()},
        )
        self.assertRedirects(response, '/vpn/', fetch_redirect_response=False)

        status_response = self.client.get(
            f"/api/client/v1/sessions/{data['session_id']}/status/",
            HTTP_AUTHORIZATION=f"Bearer {data['poll_token']}",
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()['status'], PeerMfaClientSession.STATUS_UNLOCKED)
        self.assertEqual(status_response.json()['peer_uuid'], str(self.peer.uuid))
        device = UserMfaDevice.objects.get(device_id=self.device_id)
        self.assertEqual(device.user, self.user)
        self.assertEqual(device.name, self.device_name)
        self.assertEqual(device.token_hash, hashlib.sha256(self.device_token.encode()).hexdigest())
        self.assertIsNotNone(device.last_used_at)
        self.assertTrue(AuditLog.objects.filter(action='mfa_device_registered', user=self.user).exists())

    @patch('wireguard_peer.views.export_wireguard_configuration')
    @patch('wireguard_peer.views.func_reload_wireguard_interface', return_value=(True, 'ok'))
    def test_device_conflict_is_rejected_before_peer_unlock(self, mock_reload, mock_export):
        data = self._create_session()
        UserMfaDevice.objects.create(
            user=self.user,
            device_id=self.device_id,
            name='CONFLICTING-PC',
            token_hash=hashlib.sha256(b'different-device-token').hexdigest(),
        )
        self._authorize_browser(data)

        response = self.client.post(
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
            {'totp_pin': pyotp.TOTP(self.secret).now()},
        )

        self.assertRedirects(response, '/vpn/', fetch_redirect_response=False)
        self.peer.refresh_from_db()
        client_session = PeerMfaClientSession.objects.get(uuid=data['session_id'])
        self.assertFalse(self.peer.mfa_unlocked)
        self.assertEqual(client_session.status, PeerMfaClientSession.STATUS_FAILED)
        self.assertEqual(client_session.error_code, 'device_unauthorized')
        mock_export.assert_not_called()
        mock_reload.assert_not_called()

    @patch('wireguard_peer.views.export_wireguard_configuration')
    @patch('wireguard_peer.views.func_reload_wireguard_interface', return_value=(False, 'reload failed'))
    def test_reload_failure_rolls_back_unlock_and_marks_session_failed(self, mock_reload, mock_export):
        data = self._create_session()
        self._authorize_browser(data)

        self.client.post(
            f'/peer/mfa_unlock/?peer={self.peer.uuid}',
            {'totp_pin': pyotp.TOTP(self.secret).now()},
        )

        self.peer.refresh_from_db()
        client_session = PeerMfaClientSession.objects.get(uuid=data['session_id'])
        self.assertFalse(self.peer.mfa_unlocked)
        self.assertIsNone(self.peer.mfa_last_verified_at)
        self.assertEqual(client_session.status, PeerMfaClientSession.STATUS_FAILED)
        self.assertEqual(client_session.error_code, 'wireguard_reload_failed')
        self.assertTrue(AuditLog.objects.filter(action='peer_mfa_unlock_failed').exists())
        self.assertEqual(mock_reload.call_count, 2)

    @patch('wireguard_peer.views_client.export_wireguard_configuration')
    @patch('wireguard_peer.views_client.func_reload_wireguard_interface', return_value=(True, 'ok'))
    def test_lock_endpoint_locks_authorized_peer(self, mock_reload, mock_export):
        data = self._create_session()
        client_session = PeerMfaClientSession.objects.get(uuid=data['session_id'])
        client_session.user = self.user
        client_session.status = PeerMfaClientSession.STATUS_UNLOCKED
        client_session.save(update_fields=['user', 'status', 'updated'])
        self.peer.mfa_unlocked_until = timezone.now() + timedelta(minutes=30)
        self.peer.save(update_fields=['mfa_unlocked_until', 'updated'])

        response = self.client.post(
            f"/api/client/v1/sessions/{data['session_id']}/lock/",
            HTTP_AUTHORIZATION=f"Bearer {data['poll_token']}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], PeerMfaClientSession.STATUS_LOCKED)
        self.peer.refresh_from_db()
        self.assertFalse(self.peer.mfa_unlocked)
