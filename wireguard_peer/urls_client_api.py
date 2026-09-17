from django.urls import path

from wireguard_peer.views_client import create_client_session, client_session_status, lock_client_session


urlpatterns = [
    path('sessions/', create_client_session, name='mfa_client_session_create'),
    path('sessions/<uuid:session_id>/status/', client_session_status, name='mfa_client_session_status'),
    path('sessions/<uuid:session_id>/lock/', lock_client_session, name='mfa_client_session_lock'),
]
