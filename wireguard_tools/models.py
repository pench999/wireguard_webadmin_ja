import uuid

from django.conf import settings
from django.db import models


class EmailSettings(models.Model):
    name = models.CharField(default='email_settings', max_length=20, unique=True)
    smtp_username = models.CharField(max_length=100, blank=True, null=True)
    smtp_password = models.CharField(max_length=100, blank=True, null=True)
    smtp_host = models.CharField(max_length=100, blank=True, null=True)
    smtp_port = models.IntegerField(default=587)
    smtp_encryption = models.CharField(default='tls', choices=(('ssl', 'SSL'), ('tls', 'TLS'), ('none', 'None (Insecure)'), ('noauth', 'No authentication (Insecure)')), max_length=6)
    smtp_from_address = models.EmailField(blank=True, null=True)
    enabled = models.BooleanField(default=True)

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class AuditLog(models.Model):
    ACTION_CHOICES = (
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
        ('wireguard_config_exported', 'WireGuard config exported'),
        ('wireguard_reloaded', 'WireGuard reloaded'),
        ('wireguard_restarted', 'WireGuard restarted'),
        ('wireguard_reload_failed', 'WireGuard reload failed'),
        ('wireguard_restart_failed', 'WireGuard restart failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=64, blank=True)
    object_uuid = models.CharField(max_length=64, blank=True)
    object_name = models.CharField(max_length=255, blank=True)
    wireguard_instance = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ('-created',)
        indexes = [
            models.Index(fields=('created',)),
            models.Index(fields=('action',)),
            models.Index(fields=('username',)),
            models.Index(fields=('object_type', 'object_uuid')),
        ]

    def __str__(self):
        return f'{self.created:%Y-%m-%d %H:%M:%S} {self.username} {self.action} {self.object_name}'
