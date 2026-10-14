import ipaddress
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone

import pyotp
from django.conf import settings
from django.db import DatabaseError
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import SecurityRateLimit


@dataclass(frozen=True)
class MfaVerification:
    valid: bool
    retry_after: int = 0
    unavailable: bool = False


def _reserve(scope, identity, limit, seconds):
    now = timezone.now()
    seconds = max(1, int(seconds))
    bucket = int(now.timestamp()) // seconds
    expires_at = datetime.fromtimestamp((bucket + 1) * seconds, datetime_timezone.utc)
    key = salted_hmac(
        'security-rate-limit', f'{scope}:{identity}:{bucket}',
        secret=getattr(settings, 'SECURITY_RATE_LIMIT_KEY', settings.SECRET_KEY),
        algorithm='sha256',
    ).hexdigest()
    _, created = SecurityRateLimit.objects.get_or_create(
        key=key, defaults={'expires_at': expires_at},
    )
    if created:
        SecurityRateLimit.objects.filter(expires_at__lte=now).delete()
    # The conditional SQL increment is shared and atomic across Gunicorn workers.
    accepted = SecurityRateLimit.objects.filter(key=key, count__lt=max(1, int(limit))).update(count=F('count') + 1)
    retry_after = max(1, math.ceil((expires_at - now).total_seconds()))
    return bool(accepted), key, retry_after


def _release(key):
    SecurityRateLimit.objects.filter(key=key, count__gt=0).update(count=F('count') - 1)


def verify_mfa(request, secret, pin):
    try:
        accepted, key, retry_after = _reserve(
            'mfa-user', str(request.user.pk),
            getattr(settings, 'MFA_MAX_FAILURES', 5),
            getattr(settings, 'MFA_FAILURE_WINDOW_SECONDS', 900),
        )
        if not accepted:
            return MfaVerification(False, retry_after)
        valid = bool(re.fullmatch(r'[0-9]{6}', str(pin))) and pyotp.TOTP(secret).verify(str(pin), valid_window=1)
        if valid:
            # Successful verification releases only its own reservation, not prior failures.
            _release(key)
        return MfaVerification(valid)
    except DatabaseError:
        return MfaVerification(False, 60, unavailable=True)


def mfa_limit_response(request, verification):
    response = render(request, 'user_manager/mfa_rate_limited.html', {
        'retry_after': verification.retry_after,
        'unavailable': verification.unavailable,
        'return_url': request.get_full_path(),
    }, status=503 if verification.unavailable else 429)
    response['Retry-After'] = str(verification.retry_after)
    response['Cache-Control'] = 'no-store'
    return response


def _client_ip(request):
    try:
        remote = ipaddress.ip_address(request.META.get('REMOTE_ADDR', ''))
    except ValueError:
        return 'unknown'
    trusted = [ipaddress.ip_network(item.strip(), strict=False) for item in
               getattr(settings, 'SECURITY_TRUSTED_PROXY_CIDRS', []) if item.strip()]
    if any(network.prefixlen == 0 for network in trusted):
        raise ValueError('Universal proxy trust is not allowed')
    if not any(remote in network for network in trusted):
        return str(remote)
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if len(forwarded) > 2048:
        return str(remote)
    try:
        addresses = [ipaddress.ip_address(item.strip()) for item in forwarded.split(',') if item.strip()]
    except ValueError:
        return str(remote)
    for address in reversed(addresses):
        if not any(address in network for network in trusted):
            return str(address)
    return str(remote)


def anonymous_api_limit(request):
    try:
        seconds = getattr(settings, 'ANONYMOUS_API_WINDOW_SECONDS', 60)
        accepted, global_key, retry_after = _reserve(
            'anonymous-global', 'all', getattr(settings, 'ANONYMOUS_API_GLOBAL_LIMIT', 300), seconds,
        )
        if accepted:
            allowed, _, retry_after = _reserve(
                'anonymous-ip', _client_ip(request),
                getattr(settings, 'ANONYMOUS_API_IP_LIMIT', 30), seconds,
            )
            if allowed:
                return None
            _release(global_key)
        response = JsonResponse({'error': 'too_many_sessions', 'retry_after': retry_after}, status=429)
    except (DatabaseError, ValueError):
        retry_after = 60
        response = JsonResponse({'error': 'rate_limit_unavailable', 'retry_after': retry_after}, status=503)
    response['Retry-After'] = str(retry_after)
    response['Cache-Control'] = 'no-store'
    return response
