from django.contrib import admin
from .models import AuditLog, EmailSettings
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
