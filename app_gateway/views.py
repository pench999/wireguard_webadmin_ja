import ipaddress
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from app_gateway.caddy_config_export import export_caddy_config
from app_gateway.forms import (
    ApplicationForm, ApplicationHostForm, AccessPolicyForm,
    ApplicationPolicyForm, ApplicationRouteForm
)
from app_gateway.models import (
    Application, ApplicationHost, AccessPolicy, ApplicationPolicy, ApplicationRoute, RESERVED_APP_NAME
)
from app_gateway.setup_defaults import create_default_entries
from user_manager.models import UserAcl


@login_required
def view_app_gateway_list(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=20).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    create_default_entries()
    applications = Application.objects.all().order_by('name')
    hosts = ApplicationHost.objects.all().order_by('hostname')
    access_policies = AccessPolicy.objects.all().order_by('name')
    app_policies = ApplicationPolicy.objects.all().order_by('application__name')

    tab = request.GET.get('tab', 'applications')

    context = {
        'applications': applications,
        'hosts': hosts,
        'access_policies': access_policies,
        'app_policies': app_policies,
        'active_tab': tab,
        'caddy_enabled': settings.CADDY_ENABLED,
    }
    return render(request, 'app_gateway/app_gateway_list.html', context)


@login_required
def view_application_details(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=20).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_uuid = request.GET.get('uuid')
    application = get_object_or_404(Application, uuid=application_uuid)

    hosts = application.hosts.all().order_by('hostname')
    routes = application.routes.all().order_by('order', 'path_prefix')

    is_reserved = application.name == RESERVED_APP_NAME
    django_hostnames = []
    if is_reserved:
        for host in settings.ALLOWED_HOSTS:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                django_hostnames.append(host)

    context = {
        'application': application,
        'hosts': hosts,
        'routes': routes,
        'is_reserved': is_reserved,
        'django_hostnames': django_hostnames,
        'page_title': _('Application Details'),
    }
    return render(request, 'app_gateway/application_details.html', context)


@login_required
def view_manage_application(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_uuid = request.GET.get('uuid')

    if application_uuid:
        application = get_object_or_404(Application, uuid=application_uuid)
        if application.name == RESERVED_APP_NAME:
            messages.error(request, _('The WireGuard WebAdmin application cannot be modified.'))
            return redirect(reverse('view_application') + f'?uuid={application.uuid}')
        title = _('Edit Application')
    else:
        application = None
        title = _('Create Application')

    cancel_url = reverse('app_gateway_list') + '?tab=applications'

    form = ApplicationForm(request.POST or None, instance=application, cancel_url=cancel_url)
    if form.is_valid():
        form.save()
        messages.success(request, _('Application saved successfully.'))
        return redirect(cancel_url)

    form_description = {
        'size': 'col-lg-6',
        'content': _('''
        <h5>アプリケーション</h5>
        <p>ゲートウェイ経由で公開するアプリケーションの主要情報を定義します。</p>
        <ul>
            <li><strong>名前</strong>: このアプリケーションの一意な内部識別子です (例: "wiki", "crm")。英数字、ハイフン、アンダースコアのみ使用できます。</li>
            <li><strong>表示名</strong>: 表示用の、人が読みやすい名前です。</li>
            <li><strong>アップストリーム</strong>: リクエストの転送先 URL です (例: <code>http://10.188.18.27:3000</code>)。<code>http://</code> または <code>https://</code> で始まる必要があります。</li>
        </ul>
        ''')
    }

    context = {
        'form': form,
        'title': title,
        'page_title': title,
        'form_description': form_description,
    }
    return render(request, 'generic_form.html', context)


@login_required
def view_delete_application(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application = get_object_or_404(Application, uuid=request.GET.get('uuid'))

    cancel_url = reverse('app_gateway_list') + '?tab=applications'

    if application.name == RESERVED_APP_NAME:
        messages.error(request, _('The WireGuard WebAdmin application cannot be deleted.'))
        return redirect(reverse('view_application') + f'?uuid={application.uuid}')

    if request.method == 'POST':
        application.delete()
        messages.success(request, _('Application deleted successfully.'))
        return redirect(cancel_url)

    context = {
        'application': application,
        'title': _('Delete Application'),
        'cancel_url': cancel_url,
        'text': _('Are you sure you want to delete the application "%(name)s"?') % {'name': application.display_name}
    }
    return render(request, 'generic_delete_confirmation.html', context)


@login_required
def view_manage_application_host(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_host_uuid = request.GET.get('uuid')
    application_uuid = request.GET.get('application_uuid')

    if application_host_uuid:
        application_host = get_object_or_404(ApplicationHost, uuid=application_host_uuid)
        application = application_host.application
        title = _('Edit Application Host')
    else:
        application_host = None
        application = get_object_or_404(Application, uuid=application_uuid)
        title = _('Add Application Host')

    cancel_url = reverse('view_application') + f'?uuid={application.uuid}#hosts'

    if application.name == RESERVED_APP_NAME:
        messages.error(request, _('The WireGuard WebAdmin application cannot be modified.'))
        return redirect(cancel_url)

    form = ApplicationHostForm(request.POST or None, instance=application_host, cancel_url=cancel_url)
    if form.is_valid():
        host = form.save(commit=False)
        host.application = application
        host.save()
        messages.success(request, _('Application Host saved successfully.'))
        return redirect(cancel_url)

    context = {
        'form': form,
        'title': title,
        'page_title': title,
    }
    return render(request, 'generic_form.html', context)


@login_required
def view_delete_application_host(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_host = get_object_or_404(ApplicationHost, uuid=request.GET.get('uuid'))
    application = application_host.application

    cancel_url = reverse('view_application') + f'?uuid={application.uuid}#hosts'

    if application.name == RESERVED_APP_NAME:
        messages.error(request, _('The WireGuard WebAdmin application cannot be modified.'))
        return redirect(cancel_url)

    if request.method == 'POST':
        application_host.delete()
        messages.success(request, _('Application Host deleted successfully.'))
        return redirect(cancel_url)

    context = {
        'application_host': application_host,
        'title': _('Delete Application Host'),
        'cancel_url': cancel_url,
        'text': _('Are you sure you want to delete the host "%(hostname)s"?') % {'hostname': application_host.hostname}
    }
    return render(request, 'generic_delete_confirmation.html', context)


@login_required
def view_select_policy_type(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    context = {
        'page_title': _('Select Access Policy Type'),
    }
    return render(request, 'app_gateway/access_policy_type_select.html', context)


@login_required
def view_manage_access_policy(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    access_policy_uuid = request.GET.get('uuid')
    policy_type = request.GET.get('policy_type')

    if access_policy_uuid:
        access_policy = get_object_or_404(AccessPolicy, uuid=access_policy_uuid)
        title = _('Edit Access Policy')
        policy_type = access_policy.policy_type
    else:
        access_policy = None
        title = _('Create Access Policy')

    cancel_url = reverse('app_gateway_list') + '?tab=policies'

    form = AccessPolicyForm(request.POST or None, instance=access_policy, cancel_url=cancel_url, policy_type=policy_type)
    if form.is_valid():
        form.save()
        messages.success(request, _('Access Policy saved successfully.'))
        return redirect(cancel_url)

    if policy_type == 'public':
        form_description = {
            'size': 'col-lg-6',
            'content': _('''
            <h5>公開ポリシー</h5>
            <p>公開ポリシーでは、認証なしでアプリケーションへのアクセスを許可します。</p>
            ''')
        }
    elif policy_type == 'deny':
        form_description = {
            'size': 'col-lg-6',
            'content': _('''
            <h5>拒否ポリシー</h5>
            <p>拒否ポリシーでは、一致したルートへのすべてのアクセスをブロックします。</p>
            ''')
        }
    else:
        form_description = {
            'size': 'col-lg-6',
            'content': _('''
            <h5>保護ポリシー</h5>
            <p>保護ポリシーでは、アプリケーションへアクセスする前にユーザー認証が必要です。</p>
            <ul>
                <li><strong>許可グループ</strong>: 特定のユーザーグループにアクセスを限定します。グループを使用するには、"ローカルパスワード" 種別の認証方式を選択する必要があります。</li>
                <li><strong>認証方式</strong>: ユーザーが認証に使用できる方式を指定します (例: ローカルパスワード、TOTP、OIDC)。</li>
            </ul>
            ''')
        }

    context = {
        'form': form,
        'title': title,
        'page_title': title,
        'form_description': form_description,
    }
    return render(request, 'generic_form.html', context)


@login_required
def view_delete_access_policy(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    access_policy = get_object_or_404(AccessPolicy, uuid=request.GET.get('uuid'))

    cancel_url = reverse('app_gateway_list') + '?tab=policies'

    if request.method == 'POST':
        try:
            access_policy.delete()
            messages.success(request, _('Access Policy deleted successfully.'))
        except ProtectedError:
            messages.error(request, _('Cannot delete this Access Policy because it is currently in use by an Application Route or Application Default Policy.'))
        return redirect(cancel_url)

    context = {
        'access_policy': access_policy,
        'title': _('Delete Access Policy'),
        'cancel_url': cancel_url,
        'text': _('Are you sure you want to delete the access policy "%(name)s"?') % {'name': access_policy.name}
    }
    return render(request, 'generic_delete_confirmation.html', context)


@login_required
def view_manage_application_policy(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_policy_uuid = request.GET.get('uuid')
    application_uuid = request.GET.get('application_uuid')

    if application_policy_uuid:
        application_policy = get_object_or_404(ApplicationPolicy, uuid=application_policy_uuid)
        application = application_policy.application
        title = _('Edit Application Default Policy')
    else:
        application_policy = None
        application = get_object_or_404(Application, uuid=application_uuid)
        title = _('Set Application Default Policy')

    cancel_url = reverse('view_application') + f'?uuid={application.uuid}'

    form = ApplicationPolicyForm(request.POST or None, instance=application_policy, cancel_url=cancel_url)
    if form.is_valid():
        policy_config = form.save(commit=False)
        policy_config.application = application
        policy_config.save()
        messages.success(request, _('Application Default Policy saved successfully.'))
        return redirect(cancel_url)

    context = {
        'form': form,
        'title': title,
        'page_title': title,
    }
    return render(request, 'generic_form.html', context)


@login_required
def view_delete_application_policy(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_policy = get_object_or_404(ApplicationPolicy, uuid=request.GET.get('uuid'))
    application = application_policy.application

    cancel_url = reverse('view_application') + f'?uuid={application.uuid}'

    if request.method == 'POST':
        application_policy.delete()
        messages.success(request, _('Application Default Policy deleted successfully.'))
        return redirect(cancel_url)

    context = {
        'application_policy': application_policy,
        'title': _('Delete Application Default Policy'),
        'cancel_url': cancel_url,
        'text': _('Are you sure you want to remove the default policy for "%(name)s"?') % {
            'name': application_policy.application.display_name
        }
    }
    return render(request, 'generic_delete_confirmation.html', context)


@login_required
def view_manage_application_route(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_route_uuid = request.GET.get('uuid')
    application_uuid = request.GET.get('application_uuid')

    if application_route_uuid:
        application_route = get_object_or_404(ApplicationRoute, uuid=application_route_uuid)
        application = application_route.application
        title = _('Edit Application Route')
    else:
        application_route = None
        application = get_object_or_404(Application, uuid=application_uuid)
        title = _('Add Application Route')

    cancel_url = reverse('view_application') + f'?uuid={application.uuid}#routes'

    form = ApplicationRouteForm(request.POST or None, instance=application_route, cancel_url=cancel_url)
    if form.is_valid():
        route = form.save(commit=False)
        route.application = application
        route.save()
        messages.success(request, _('Application Route saved successfully.'))
        return redirect(cancel_url)

    form_description = {
        'size': 'col-lg-6',
        'content': _('''
        <h5>アプリケーションルート</h5>
        <p>ルートは、このアプリケーション内で特定のアクセスポリシーを必要とするパスプレフィックスを定義します。</p>
        <ul>
            <li><strong>ルート名</strong>: このルートの内部識別子です (例: "public_api", "admin_area")。参照やエクスポートに使用されます。</li>
            <li><strong>パスプレフィックス</strong>: このルートを適用する URL パスです (例: <code>/api/</code> または <code>/admin/</code>)。残りすべてのパスに一致させるには <code>/</code> を使用します。</li>
            <li><strong>ポリシー</strong>: ユーザーがこのパスへアクセスしたときに適用されるアクセスポリシーです。</li>
            <li><strong>順序</strong>: リクエスト評価時の優先順位を決定します。数値が小さいルートほど先に評価されます。複数のルートが一致した場合、最も小さい順序のルートが優先されます。</li>
        </ul>
        ''')
    }

    context = {
        'form': form,
        'title': title,
        'page_title': title,
        'form_description': form_description,
    }
    return render(request, 'generic_form.html', context)


@login_required
def view_delete_application_route(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    application_route = get_object_or_404(ApplicationRoute, uuid=request.GET.get('uuid'))
    application = application_route.application

    cancel_url = reverse('view_application') + f'?uuid={application.uuid}#routes'

    if request.method == 'POST':
        application_route.delete()
        messages.success(request, _('Application Route deleted successfully.'))
        return redirect(cancel_url)

    context = {
        'application_route': application_route,
        'title': _('Delete Application Route'),
        'cancel_url': cancel_url,
        'text': _('Are you sure you want to delete the route "%(name)s" (%(path)s)?') % {
            'name': application_route.name,
            'path': application_route.path_prefix
        }
    }
    return render(request, 'generic_delete_confirmation.html', context)


@login_required
@require_POST
def view_export_caddy_config(request):
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})

    redirect_url = reverse('app_gateway_list') + '?tab=applications'

    if not settings.CADDY_ENABLED:
        messages.error(request, _(
            'Configuration export is not available because Caddy is not enabled. '
            'To use App Gateway and Gatekeeper, start the application using docker-compose-caddy.yml.'
        ))
        return redirect(redirect_url)

    export_caddy_config('/caddy_json_export/')

    if settings.DEBUG:
        export_caddy_config(os.path.join(settings.BASE_DIR, 'containers', 'caddy', 'config_files'))

    messages.success(request, _('Configuration exported successfully.'))
    return redirect(redirect_url)
