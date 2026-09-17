from datetime import timedelta
from unittest.mock import patch

import pyotp
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from scheduler.models import PeerScheduling
from user_manager.models import UserAcl, UserMfaSettings
from user_manager.trusted_browser import TRUSTED_BROWSER_COOKIE_NAME, hash_trusted_browser_token
from wireguard.models import Peer, WireGuardInstance
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
