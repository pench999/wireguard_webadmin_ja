from django.shortcuts import render

ANDROID_RETURN_URI = (
    'intent://auth/complete#Intent;scheme=wireguardmfa;'
    'package=jp.co.fairway.wireguard_mfa_client;end'
)


def remember_app_return(request, client_session):
    if request.GET.get('return_to_app') == 'android':
        request.session['mfa_android_return_session'] = str(client_session.uuid)


def app_return_requested(request, client_session):
    return request.session.get('mfa_android_return_session') == str(client_session.uuid)


def render_app_return(request):
    request.session.pop('mfa_android_return_session', None)
    response = render(request, 'wireguard/client_auth_complete.html', {
        'app_return_uri': ANDROID_RETURN_URI,
    })
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response
