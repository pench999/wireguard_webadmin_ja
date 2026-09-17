import hashlib
import json
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from wireguard.models import Peer, PeerMfaClientSession, UserMfaDevice
from wireguard_tools.audit import write_audit_log
from wireguard_tools.functions import func_reload_wireguard_interface
from wireguard_tools.views import export_wireguard_configuration


def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _poll_session(request, session_id):
    authorization = request.headers.get('Authorization', '')
    scheme, separator, token = authorization.partition(' ')
    if not separator or scheme.lower() != 'bearer' or not token:
        return None
    session = PeerMfaClientSession.objects.select_related('peer', 'user').filter(uuid=session_id).first()
    if not session or not secrets.compare_digest(session.poll_token_hash, _token_hash(token)):
        return None
    if session.is_expired and session.status in (
        PeerMfaClientSession.STATUS_PENDING,
        PeerMfaClientSession.STATUS_AUTHORIZING,
    ):
        session.status = PeerMfaClientSession.STATUS_EXPIRED
        session.save(update_fields=['status', 'updated'])
    elif session.status == PeerMfaClientSession.STATUS_UNLOCKED and not session.peer.mfa_unlocked:
        session.status = PeerMfaClientSession.STATUS_LOCKED
        session.save(update_fields=['status', 'updated'])
    return session


@csrf_exempt
@require_POST
def create_client_session(request):
    body = _json_body(request)
    if not isinstance(body, dict):
        return JsonResponse({'error': 'invalid_json'}, status=400)

    try:
        peer_uuid = uuid.UUID(str(body.get('peer_uuid')))
    except (TypeError, ValueError, AttributeError):
        return JsonResponse({'error': 'peer_unavailable'}, status=404)

    peer = Peer.objects.filter(
        uuid=peer_uuid,
        mfa_required=True,
        assigned_user__isnull=False,
        suspended=False,
        disabled_by_schedule=False,
    ).first()
    if not peer:
        return JsonResponse({'error': 'peer_unavailable'}, status=404)

    raw_device_id = body.get('device_id')
    raw_device_token = body.get('device_token')
    device_name = str(body.get('device_name') or '').strip()[:120]
    device_id = None
    device_token_hash = ''
    registered_device = None
    has_any_device = UserMfaDevice.objects.filter(user=peer.assigned_user).exists()
    if raw_device_id or raw_device_token or device_name:
        try:
            device_id = uuid.UUID(str(raw_device_id))
        except (TypeError, ValueError, AttributeError):
            return JsonResponse({'error': 'invalid_device'}, status=400)
        if not isinstance(raw_device_token, str) or not 32 <= len(raw_device_token) <= 128 or not device_name:
            return JsonResponse({'error': 'invalid_device'}, status=400)
        device_token_hash = _token_hash(raw_device_token)
        registered_device = UserMfaDevice.objects.filter(device_id=device_id).first()
        if registered_device:
            if registered_device.user_id != peer.assigned_user_id:
                return JsonResponse({'error': 'device_unauthorized'}, status=401)
            if registered_device.revoked_at:
                return JsonResponse({'error': 'device_revoked'}, status=403)
            if not secrets.compare_digest(registered_device.token_hash, device_token_hash):
                return JsonResponse({'error': 'device_unauthorized'}, status=401)
    elif has_any_device:
        return JsonResponse({'error': 'device_required'}, status=401)

    now = timezone.now()
    PeerMfaClientSession.objects.filter(
        expires_at__lte=now,
        status__in=[PeerMfaClientSession.STATUS_PENDING, PeerMfaClientSession.STATUS_AUTHORIZING],
    ).update(status=PeerMfaClientSession.STATUS_EXPIRED)
    active_count = PeerMfaClientSession.objects.filter(
        peer=peer,
        expires_at__gt=now,
        status__in=[PeerMfaClientSession.STATUS_PENDING, PeerMfaClientSession.STATUS_AUTHORIZING],
    ).count()
    if active_count >= 5:
        return JsonResponse({'error': 'too_many_sessions'}, status=429)

    browser_token = secrets.token_urlsafe(32)
    poll_token = secrets.token_urlsafe(32)
    ttl_seconds = int(getattr(settings, 'MFA_CLIENT_SESSION_TTL_SECONDS', 300))
    client_session = PeerMfaClientSession.objects.create(
        peer=peer,
        browser_token_hash=_token_hash(browser_token),
        poll_token_hash=_token_hash(poll_token),
        registered_device=registered_device,
        device_id=device_id,
        device_name=device_name,
        device_token_hash=device_token_hash,
        expires_at=now + timezone.timedelta(seconds=max(60, min(ttl_seconds, 900))),
    )
    browser_path = reverse('mfa_client_connect', kwargs={'browser_token': browser_token})
    return JsonResponse({
        'session_id': str(client_session.uuid),
        'browser_url': request.build_absolute_uri(browser_path),
        'poll_token': poll_token,
        'expires_at': client_session.expires_at.isoformat(),
        'device_status': 'registered' if registered_device else ('pending' if device_id else 'legacy'),
    }, status=201)


@login_required
@require_GET
def client_connect(request, browser_token):
    client_session = PeerMfaClientSession.objects.select_related('peer').filter(
        browser_token_hash=_token_hash(browser_token),
        status=PeerMfaClientSession.STATUS_PENDING,
    ).first()
    if not client_session:
        raise Http404
    if client_session.is_expired:
        client_session.status = PeerMfaClientSession.STATUS_EXPIRED
        client_session.save(update_fields=['status', 'updated'])
        raise Http404
    if client_session.peer.assigned_user_id != request.user.id:
        raise Http404

    client_session.user = request.user
    client_session.status = PeerMfaClientSession.STATUS_AUTHORIZING
    client_session.browser_token_hash = None
    client_session.save(update_fields=['user', 'status', 'browser_token_hash', 'updated'])
    request.session['peer_mfa_client_session_id'] = str(client_session.uuid)
    return redirect('/peer/mfa_unlock/?peer=' + str(client_session.peer_id))


@require_GET
def client_session_status(request, session_id):
    client_session = _poll_session(request, session_id)
    if not client_session:
        return JsonResponse({'error': 'unauthorized'}, status=401)
    response = {
        'status': client_session.status,
        'expires_at': client_session.expires_at.isoformat(),
    }
    if client_session.status in (
        PeerMfaClientSession.STATUS_UNLOCKED,
        PeerMfaClientSession.STATUS_LOCKED,
    ):
        response.update({
            'peer_uuid': str(client_session.peer_id),
            'lock_mode': client_session.peer.mfa_lock_mode,
            'unlocked_until': (
                client_session.peer.mfa_unlocked_until.isoformat()
                if client_session.peer.mfa_unlocked_until else None
            ),
        })
    if client_session.status == PeerMfaClientSession.STATUS_FAILED:
        response['error_code'] = client_session.error_code
    return JsonResponse(response)


@csrf_exempt
@require_http_methods(['POST'])
def lock_client_session(request, session_id):
    client_session = _poll_session(request, session_id)
    if not client_session:
        return JsonResponse({'error': 'unauthorized'}, status=401)
    if client_session.status not in (
        PeerMfaClientSession.STATUS_UNLOCKED,
        PeerMfaClientSession.STATUS_LOCKED,
    ):
        return JsonResponse({'error': 'invalid_state'}, status=409)
    if client_session.status == PeerMfaClientSession.STATUS_LOCKED:
        return JsonResponse({'status': PeerMfaClientSession.STATUS_LOCKED})

    peer = client_session.peer
    peer.mfa_unlocked_until = None
    peer.save(update_fields=['mfa_unlocked_until', 'updated'])
    try:
        export_wireguard_configuration(peer.wireguard_instance)
        success, message = func_reload_wireguard_interface(peer.wireguard_instance)
    except Exception as exc:
        success, message = False, str(exc)
    request.user = client_session.user
    if not success:
        client_session.status = PeerMfaClientSession.STATUS_FAILED
        client_session.error_code = 'wireguard_reload_failed'
        client_session.save(update_fields=['status', 'error_code', 'updated'])
        write_audit_log(request, 'peer_mfa_lock_failed', peer, details={'message': str(message)})
        return JsonResponse({'status': 'failed', 'error': 'wireguard_reload_failed'}, status=500)

    client_session.status = PeerMfaClientSession.STATUS_LOCKED
    client_session.save(update_fields=['status', 'updated'])
    write_audit_log(request, 'peer_mfa_locked', peer, details={'reason': 'Client requested disconnect'})
    return JsonResponse({'status': PeerMfaClientSession.STATUS_LOCKED})
