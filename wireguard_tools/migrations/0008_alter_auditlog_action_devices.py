from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('wireguard_tools', '0007_alter_auditlog_action_client_mfa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[
                ('peer_created', 'Peer created'), ('peer_updated', 'Peer updated'),
                ('peer_deleted', 'Peer deleted'), ('peer_suspended', 'Peer suspended'),
                ('peer_reactivated', 'Peer reactivated'),
                ('peer_suspend_schedule_updated', 'Peer suspend schedule updated'),
                ('peer_suspend_schedule_cleared', 'Peer suspend schedule cleared'),
                ('peer_schedule_profile_updated', 'Peer schedule profile updated'),
                ('peer_ip_added', 'Peer IP added'), ('peer_ip_updated', 'Peer IP updated'),
                ('peer_ip_deleted', 'Peer IP deleted'),
                ('peer_route_template_applied', 'Peer route template applied'),
                ('peer_route_template_unlinked', 'Peer route template unlinked'),
                ('peer_connected', 'Peer connected'), ('peer_disconnected', 'Peer disconnected'),
                ('peer_handshake_updated', 'Peer handshake updated'),
                ('wireguard_config_exported', 'WireGuard config exported'),
                ('wireguard_reloaded', 'WireGuard reloaded'),
                ('wireguard_restarted', 'WireGuard restarted'),
                ('wireguard_reload_failed', 'WireGuard reload failed'),
                ('wireguard_restart_failed', 'WireGuard restart failed'),
                ('vpn_mfa_failed', 'VPN MFA failed'),
                ('vpn_mfa_untrusted_browser_blocked', 'VPN MFA untrusted browser blocked'),
                ('peer_mfa_unlocked', 'Peer MFA unlocked'),
                ('peer_mfa_unlock_failed', 'Peer MFA unlock failed'),
                ('peer_mfa_locked', 'Peer MFA locked'),
                ('peer_mfa_lock_failed', 'Peer MFA lock failed'),
                ('peer_mfa_required_enabled', 'Peer MFA requirement enabled'),
                ('peer_mfa_required_disabled', 'Peer MFA requirement disabled'),
                ('mfa_device_registered', 'MFA device registered'),
                ('mfa_device_revoked', 'MFA device revoked'),
            ], max_length=64),
        ),
    ]
