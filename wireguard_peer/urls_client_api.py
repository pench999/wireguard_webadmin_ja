from django.urls import path

from wireguard_peer.views_client import (
    create_client_session,
    client_session_status,
    create_provisioning_session,
    download_provisioning_config,
    lock_client_session,
    provisioning_session_status,
)


urlpatterns = [
    path('sessions/', create_client_session, name='mfa_client_session_create'),
    path('sessions/<uuid:session_id>/status/', client_session_status, name='mfa_client_session_status'),
    path('sessions/<uuid:session_id>/lock/', lock_client_session, name='mfa_client_session_lock'),
    path('provisioning/', create_provisioning_session, name='mfa_client_provisioning_create'),
    path('provisioning/<uuid:session_id>/status/', provisioning_session_status, name='mfa_client_provisioning_status'),
    path('provisioning/<uuid:session_id>/config/', download_provisioning_config, name='mfa_client_provisioning_config'),
]
