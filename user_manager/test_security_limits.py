from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace
import uuid
from unittest.mock import patch

import pyotp
from django.contrib.auth.models import User
from django.db import DatabaseError, connections
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from user_manager.models import SecurityRateLimit
from user_manager.security_limits import anonymous_api_limit, verify_mfa
from user_manager.models import UserMfaSettings
from wireguard_peer import tests as peer_tests


@override_settings(MFA_MAX_FAILURES=2, MFA_FAILURE_WINDOW_SECONDS=900)
class MfaLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('limit-user')
        self.secret = pyotp.random_base32()
        self.factory = RequestFactory()
        clock = patch('user_manager.security_limits.timezone.now', return_value=timezone.now())
        clock.start()
        self.addCleanup(clock.stop)

    def request(self, path='/peer/mfa_unlock/'):
        request = self.factory.post(path)
        request.user = self.user
        return request

    def test_failures_are_shared_across_sessions_and_mfa_paths(self):
        self.assertFalse(verify_mfa(self.request('/user/mfa/setup/'), self.secret, 'abcdef').valid)
        self.assertFalse(verify_mfa(self.request('/client/provision/token/'), self.secret, 'abcdef').valid)
        result = verify_mfa(self.request(), self.secret, pyotp.TOTP(self.secret).now())
        self.assertFalse(result.valid)
        self.assertGreater(result.retry_after, 0)
        self.assertEqual(SecurityRateLimit.objects.get().count, 2)

    def test_success_does_not_count_but_does_not_clear_prior_failures(self):
        request = self.request()
        verify_mfa(request, self.secret, 'abcdef')
        for _ in range(4):
            self.assertTrue(verify_mfa(request, self.secret, pyotp.TOTP(self.secret).now()).valid)
        self.assertEqual(SecurityRateLimit.objects.get().count, 1)
        verify_mfa(request, self.secret, 'abcdef')
        self.assertGreater(verify_mfa(request, self.secret, 'abcdef').retry_after, 0)

    def test_other_users_are_not_blocked(self):
        request = self.request()
        verify_mfa(request, self.secret, 'abcdef')
        verify_mfa(request, self.secret, 'abcdef')
        request.user = User.objects.create_user('another-user')
        self.assertTrue(verify_mfa(request, self.secret, pyotp.TOTP(self.secret).now()).valid)

    def test_limit_expires_and_old_rows_are_cleaned(self):
        request = self.request()
        verify_mfa(request, self.secret, 'abcdef')
        verify_mfa(request, self.secret, 'abcdef')
        later = timezone.now() + timedelta(seconds=901)
        with patch('user_manager.security_limits.timezone.now', return_value=later):
            self.assertTrue(verify_mfa(request, self.secret, pyotp.TOTP(self.secret).now()).valid)
        self.assertEqual(SecurityRateLimit.objects.count(), 1)

    @patch('user_manager.security_limits._reserve', side_effect=DatabaseError('unavailable'))
    def test_storage_failure_denies_verification(self, _reserve):
        result = verify_mfa(self.request(), self.secret, pyotp.TOTP(self.secret).now())
        self.assertFalse(result.valid)
        self.assertTrue(result.unavailable)


@override_settings(ANONYMOUS_API_IP_LIMIT=2, ANONYMOUS_API_GLOBAL_LIMIT=20,
                   ANONYMOUS_API_WINDOW_SECONDS=60, SECURITY_TRUSTED_PROXY_CIDRS=[])
class AnonymousLimitTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        clock = patch('user_manager.security_limits.timezone.now', return_value=timezone.now())
        clock.start()
        self.addCleanup(clock.stop)

    def request(self, ip='198.51.100.1', forwarded=''):
        return self.factory.post('/api/client/v1/provisioning/', REMOTE_ADDR=ip,
                                 HTTP_X_FORWARDED_FOR=forwarded)

    def test_untrusted_forwarded_header_cannot_rotate_identity(self):
        self.assertIsNone(anonymous_api_limit(self.request(forwarded='192.0.2.1')))
        self.assertIsNone(anonymous_api_limit(self.request(forwarded='192.0.2.2')))
        response = anonymous_api_limit(self.request(forwarded='192.0.2.3'))
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)

    @override_settings(SECURITY_TRUSTED_PROXY_CIDRS=['10.0.0.10/32'])
    def test_trusted_proxy_separates_clients_and_ignores_forged_left_prefix(self):
        self.assertIsNone(anonymous_api_limit(self.request('10.0.0.10', '192.0.2.1, 198.51.100.1')))
        self.assertIsNone(anonymous_api_limit(self.request('10.0.0.10', '192.0.2.2, 198.51.100.1')))
        self.assertEqual(anonymous_api_limit(self.request('10.0.0.10', '192.0.2.3, 198.51.100.1')).status_code, 429)
        self.assertIsNone(anonymous_api_limit(self.request('10.0.0.10', '198.51.100.2')))

    @override_settings(ANONYMOUS_API_GLOBAL_LIMIT=2, ANONYMOUS_API_IP_LIMIT=1)
    def test_rejected_ip_requests_do_not_exhaust_global_budget(self):
        self.assertIsNone(anonymous_api_limit(self.request()))
        for _ in range(5):
            self.assertEqual(anonymous_api_limit(self.request()).status_code, 429)
        self.assertIsNone(anonymous_api_limit(self.request('198.51.100.2')))
        self.assertEqual(anonymous_api_limit(self.request('198.51.100.3')).status_code, 429)
        self.assertEqual(SecurityRateLimit.objects.count(), 3)

    def test_counters_do_not_store_plaintext_ip(self):
        anonymous_api_limit(self.request())
        for row in SecurityRateLimit.objects.all():
            self.assertEqual(len(row.key), 64)
            self.assertNotIn('198.51.100.1', row.key)

    @override_settings(SECURITY_TRUSTED_PROXY_CIDRS=['0.0.0.0/0'])
    def test_universal_proxy_trust_is_rejected(self):
        self.assertEqual(anonymous_api_limit(self.request(forwarded='192.0.2.1')).status_code, 503)

    @override_settings(ANONYMOUS_API_IP_LIMIT=1)
    def test_both_creation_routes_share_budget_before_body_validation(self):
        first = self.client.post('/api/client/v1/provisioning/', data='{}', content_type='application/json')
        self.assertEqual(first.status_code, 400)
        second = self.client.post('/api/client/v1/sessions/', data='{}', content_type='application/json')
        self.assertEqual(second.status_code, 429)
        self.assertIn('retry_after', second.json())

    @patch('user_manager.security_limits._reserve', side_effect=DatabaseError('unavailable'))
    def test_storage_failure_returns_unavailable_not_permission(self, _reserve):
        self.assertEqual(anonymous_api_limit(self.request()).status_code, 503)

    def test_rotating_device_ids_cannot_reset_creation_budget(self):
        statuses = []
        for _ in range(3):
            response = self.client.post('/api/client/v1/provisioning/', data=json.dumps({
                'device_id': str(uuid.uuid4()), 'device_token': 'x' * 40, 'device_name': 'TEST',
            }), content_type='application/json')
            statuses.append(response.status_code)
        self.assertEqual(statuses, [201, 201, 429])


@override_settings(MFA_MAX_FAILURES=2, MFA_FAILURE_WINDOW_SECONDS=900)
class MfaEndpointLimitTests(TestCase):
    def setUp(self):
        peer_tests.PeerProvisioningSessionTests.setUp(self)
        clock = patch('user_manager.security_limits.timezone.now', return_value=timezone.now())
        clock.start()
        self.addCleanup(clock.stop)

    _create = peer_tests.PeerProvisioningSessionTests._create

    def test_provisioning_failures_block_unlock_and_setup(self):
        from urllib.parse import urlparse
        data = self._create()
        self.client.force_login(self.user)
        path = urlparse(data['browser_url']).path
        for _ in range(2):
            response = self.client.post(path, {'peer_uuid': str(self.peer.uuid), 'totp_pin': 'abcdef'})
            self.assertEqual(response.status_code, 200)
        with patch('wireguard_peer.views.export_wireguard_configuration') as export, patch(
            'wireguard_peer.views.func_reload_wireguard_interface', return_value=(True, 'ok'),
        ):
            response = self.client.post('/peer/mfa_unlock/?peer=' + str(self.peer.uuid), {
                'totp_pin': pyotp.TOTP(self.secret).now(),
            })
            self.assertEqual(response.status_code, 429)
            export.assert_not_called()
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertGreater(int(response['Retry-After']), 0)
        UserMfaSettings.objects.filter(user=self.user).update(reset_allowed=True)
        self.client.get('/user/mfa/setup/')
        pending = self.client.session['pending_mfa_totp_secret']
        response = self.client.post('/user/mfa/setup/', {'totp_pin': pyotp.TOTP(pending).now()})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, '認証の試行回数が上限に達しました', status_code=429)


@override_settings(MFA_MAX_FAILURES=3, MFA_FAILURE_WINDOW_SECONDS=900)
class ConcurrentLimitTests(TransactionTestCase):
    def test_independent_connections_cannot_exceed_failure_budget(self):
        secret = pyotp.random_base32()

        def attempt(_):
            request = RequestFactory().post('/peer/mfa_unlock/')
            request.user = SimpleNamespace(pk=42)
            try:
                return verify_mfa(request, secret, 'abcdef')
            finally:
                connections.close_all()

        with patch('user_manager.security_limits.timezone.now', return_value=timezone.now()):
            self.assertEqual(attempt(0).retry_after, 0)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(attempt, range(12)))
        self.assertLessEqual(1 + sum(result.retry_after == 0 for result in results), 3)
        self.assertLessEqual(SecurityRateLimit.objects.get().count, 3)
