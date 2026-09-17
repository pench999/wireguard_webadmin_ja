import hashlib
import secrets

from django.utils import timezone


TRUSTED_BROWSER_COOKIE_NAME = 'wgwadm_trusted_browser'
TRUSTED_BROWSER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def hash_trusted_browser_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def register_trusted_browser(response, request, mfa_settings):
    token = secrets.token_urlsafe(32)
    mfa_settings.trusted_browser_token_hash = hash_trusted_browser_token(token)
    mfa_settings.trusted_browser_registered_at = timezone.now()
    mfa_settings.trusted_browser_user_agent = request.META.get('HTTP_USER_AGENT', '')[:1000]
    mfa_settings.save()
    response.set_cookie(
        TRUSTED_BROWSER_COOKIE_NAME,
        token,
        max_age=TRUSTED_BROWSER_COOKIE_MAX_AGE,
        httponly=True,
        secure=request.is_secure(),
        samesite='Lax',
    )


def has_trusted_browser(request, mfa_settings):
    token = request.COOKIES.get(TRUSTED_BROWSER_COOKIE_NAME)
    if not token or not mfa_settings.trusted_browser_token_hash:
        return False
    return secrets.compare_digest(
        hash_trusted_browser_token(token),
        mfa_settings.trusted_browser_token_hash,
    )
