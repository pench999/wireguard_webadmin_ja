from django.contrib import admin
from .models import AuditLog, EmailSettings, PeerConnectionState
# Register your models here.
admin.site.register(EmailSettings)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created', 'username', 'action', 'object_type', 'object_name', 'wireguard_instance', 'ip_address')
    list_filter = ('action', 'object_type', 'wireguard_instance', 'created')
    search_fields = ('username', 'object_name', 'object_uuid', 'wireguard_instance')
    readonly_fields = (
        'user', 'username', 'action', 'object_type', 'object_uuid', 'object_name',
        'wireguard_instance', 'ip_address', 'user_agent', 'details', 'created', 'uuid'
    )
    ordering = ('-created',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PeerConnectionState)
class PeerConnectionStateAdmin(admin.ModelAdmin):
    list_display = ('peer', 'is_connected', 'last_handshake', 'transfer_rx', 'transfer_tx', 'last_event_at', 'updated')
    list_filter = ('is_connected', 'updated')
    search_fields = ('peer__name', 'peer__public_key')
    readonly_fields = (
        'peer', 'is_connected', 'last_handshake', 'transfer_rx', 'transfer_tx',
        'last_event_at', 'created', 'updated', 'uuid'
    )
    ordering = ('-updated',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
