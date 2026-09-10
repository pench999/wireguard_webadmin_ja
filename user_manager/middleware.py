from django.shortcuts import redirect

from user_manager.models import UserAcl


class VpnUserPortalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            user_acl = UserAcl.objects.filter(user=user).first()
            if user_acl and user_acl.user_level == 0 and not self._is_allowed_path(request.path_info):
                return redirect('/vpn/')
        return self.get_response(request)

    def _is_allowed_path(self, path):
        allowed_prefixes = (
            '/vpn/',
            '/accounts/logout/',
            '/user/mfa/',
            '/peer/mfa_unlock/',
            '/change_language/',
            '/static/',
        )
        allowed_exact = (
            '/vpn',
            '/accounts/login/',
        )
        return path in allowed_exact or path.startswith(allowed_prefixes)
