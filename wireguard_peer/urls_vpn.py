from django.urls import path

from wireguard_peer.views import view_vpn_portal, view_vpn_portal_download_config, view_vpn_portal_qrcode


urlpatterns = [
    path('', view_vpn_portal, name='vpn_portal'),
    path('download/', view_vpn_portal_download_config, name='vpn_portal_download_config'),
    path('qrcode/', view_vpn_portal_qrcode, name='vpn_portal_qrcode'),
]
