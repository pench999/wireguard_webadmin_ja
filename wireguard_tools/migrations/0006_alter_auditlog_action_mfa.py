from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wireguard_tools', '0005_peerconnectionstate_and_connection_audit_actions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[
                ('peer_created', 'Peer created'),
                ('peer_updated', 'Peer updated'),
                ('peer_deleted', 'Peer deleted'),
                ('peer_suspended', 'Peer suspended'),
                ('peer_reactivated', 'Peer reactivated'),
                ('peer_suspend_schedule_updated', 'Peer suspend schedule updated'),
                ('peer_suspend_schedule_cleared', 'Peer suspend schedule cleared'),
                ('peer_schedule_profile_updated', 'Peer schedule profile updated'),
                ('peer_ip_added', 'Peer IP added'),
                ('peer_ip_updated', 'Peer IP updated'),
                ('peer_ip_deleted', 'Peer IP deleted'),
                ('peer_route_template_applied', 'Peer route template applied'),
                ('peer_route_template_unlinked', 'Peer route template unlinked'),
                ('peer_connected', 'Peer connected'),
                ('peer_disconnected', 'Peer disconnected'),
                ('peer_handshake_updated', 'Peer handshake updated'),
                ('wireguard_config_exported', 'WireGuard config exported'),
                ('wireguard_reloaded', 'WireGuard reloaded'),
                ('wireguard_restarted', 'WireGuard restarted'),
                ('wireguard_reload_failed', 'WireGuard reload failed'),
                ('wireguard_restart_failed', 'WireGuard restart failed'),
                ('vpn_mfa_failed', 'VPN MFA failed'),
                ('peer_mfa_unlocked', 'Peer MFA unlocked'),
                ('peer_mfa_locked', 'Peer MFA locked'),
                ('peer_mfa_required_enabled', 'Peer MFA requirement enabled'),
                ('peer_mfa_required_disabled', 'Peer MFA requirement disabled'),
            ], max_length=64),
        ),
    ]
