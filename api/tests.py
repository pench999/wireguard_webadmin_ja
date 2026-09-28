import subprocess
from unittest.mock import patch

from django.test import TestCase, override_settings

from api.models import WireguardStatusCache
from api.views import func_get_wireguard_status, func_process_wireguard_status


WG_DUMP = (
    "wg0\tprivate-key\tpublic-key\t51820\toff\n"
    "wg0\tpeer-key\tpreshared-key\t198.51.100.1:51820\t10.0.0.2/32\t"
    "1700000000\t100\t200\t25\n"
)


class WireGuardStatusCommandTests(TestCase):
    @patch('api.views.subprocess.run')
    def test_status_command_has_timeout_and_parses_dump(self, run_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=['wg', 'show', 'all', 'dump'],
            returncode=0,
            stdout=WG_DUMP,
            stderr='',
        )

        result = func_process_wireguard_status()

        self.assertEqual(result['wg0']['peer-key']['transfer'], {'tx': 200, 'rx': 100})
        run_mock.assert_called_once_with(
            ['wg', 'show', 'all', 'dump'],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    @patch('api.views.subprocess.run')
    def test_status_command_timeout_returns_error(self, run_mock):
        run_mock.side_effect = subprocess.TimeoutExpired(
            cmd=['wg', 'show', 'all', 'dump'],
            timeout=15,
        )

        result = func_process_wireguard_status()

        self.assertEqual(result['status'], 'error')
        self.assertIn('timed out after 15 seconds', result['message'])

    @override_settings(WIREGUARD_STATUS_CACHE_ENABLED=False)
    @patch('api.views.func_process_wireguard_status')
    def test_uncached_status_preserves_command_error(self, status_mock):
        status_mock.return_value = {'status': 'error', 'message': 'command failed'}

        result = func_get_wireguard_status()

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'command failed')
        self.assertFalse(result['cache_information']['cache_enabled'])


class CronRefreshStatusTests(TestCase):
    @override_settings(
        WIREGUARD_STATUS_CACHE_ENABLED=True,
        WIREGUARD_STATUS_CACHE_MAX_AGE=600,
    )
    @patch('api.views.func_update_peer_connection_audit')
    @patch('api.views.func_process_wireguard_status')
    @patch('api.views.get_api_key', return_value='test-key')
    def test_command_error_returns_503_without_cache_or_audit(
        self,
        _api_key_mock,
        status_mock,
        audit_mock,
    ):
        status_mock.return_value = {'status': 'error', 'message': 'command timed out'}

        response = self.client.get(
            '/api/cron/refresh_wireguard_status_cache/',
            {'cron_key': 'test-key'},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'error')
        self.assertFalse(WireguardStatusCache.objects.exists())
        audit_mock.assert_not_called()
