from django.urls import path

from wireguard_peer.views_client import client_connect


urlpatterns = [
    path('connect/<str:browser_token>/', client_connect, name='mfa_client_connect'),
]
