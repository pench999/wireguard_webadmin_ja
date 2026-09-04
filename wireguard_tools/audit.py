import logging

from wireguard_tools.models import AuditLog

logger = logging.getLogger(__name__)


def _request_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def write_audit_log(request, action, obj=None, details=None, wireguard_instance=None):
    try:
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            username = user.get_username()
        else:
            user = None
            username = ''

        object_type = obj.__class__.__name__ if obj is not None else ''
        object_uuid = str(getattr(obj, 'uuid', '')) if obj is not None else ''
        object_name = str(obj) if obj is not None else ''

        instance_name = ''
        instance = wireguard_instance or getattr(obj, 'wireguard_instance', None)
        if instance:
            instance_id = getattr(instance, 'instance_id', None)
            instance_name = f'wg{instance_id}' if instance_id is not None else str(instance)

        AuditLog.objects.create(
            user=user,
            username=username,
            action=action,
            object_type=object_type,
            object_uuid=object_uuid,
            object_name=object_name[:255],
            wireguard_instance=instance_name,
            ip_address=_request_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=details or {},
        )
    except Exception:
        logger.exception('Failed to write audit log for action %s', action)
