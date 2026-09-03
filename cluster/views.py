from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from api.models import WireguardStatusCache
from dns.functions import compress_dnsmasq_config
from user_manager.models import UserAcl
from .forms import WorkerForm, ClusterSettingsForm
from .models import ClusterSettings, Worker


@login_required
def cluster_main(request):
    """Main cluster page with workers list"""
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})
    
    cluster_settings, created = ClusterSettings.objects.get_or_create(name='cluster_settings')
    page_title = _('Cluster')
    workers = Worker.objects.all().order_by('name')

    master_cache_times = ", ".join([str(c.processing_time_ms) for c in WireguardStatusCache.objects.filter(cache_type='master').order_by('-created')])
    cluster_cache_times = ", ".join([str(c.processing_time_ms) for c in WireguardStatusCache.objects.filter(cache_type='cluster').order_by('-created')])

    context = {
        'page_title': page_title,
        'workers': workers,
        'current_worker_version': settings.CLUSTER_WORKER_CURRENT_VERSION,
        'cluster_settings': cluster_settings,
        'cache_refresh_interval': settings.WIREGUARD_STATUS_CACHE_REFRESH_INTERVAL,
        'cache_enabled': settings.WIREGUARD_STATUS_CACHE_ENABLED,
        'cache_web_load_previous_count': settings.WIREGUARD_STATUS_CACHE_WEB_LOAD_PREVIOUS_COUNT,
        'master_cache_times': master_cache_times,
        'cluster_cache_times': cluster_cache_times,
    }
    return render(request, 'cluster/workers_list.html', context)


@login_required
def worker_manage(request):
    """Add/Edit worker view"""
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})
    
    worker = None
    if 'uuid' in request.GET:
        worker = get_object_or_404(Worker, uuid=request.GET['uuid'])
        form = WorkerForm(instance=worker)
        page_title = _('Edit Worker: ') + worker.name
        
        if request.GET.get('action') == 'delete':
            worker_name = worker.name
            if request.GET.get('confirmation') == 'delete':
                worker.delete()
                messages.success(request, _('Worker deleted|Worker deleted: ') + worker_name)
                return redirect('/cluster/')
            else:
                messages.warning(request, _('Worker not deleted|Invalid confirmation.'))
            return redirect('/cluster/')
    else:
        form = WorkerForm()
        page_title = _('Add Worker')

    if request.method == 'POST':
        if worker:
            form = WorkerForm(request.POST, instance=worker)
        else:
            form = WorkerForm(request.POST)

        if form.is_valid():
            worker = form.save()
            if worker.pk:
                messages.success(request, _('Worker updated|Worker updated: ') + worker.name)
            else:
                messages.success(request, _('Worker created|Worker created: ') + worker.name)
            return redirect('/cluster/')

    form_description = {
        'size': 'col-lg-6',
        'content': _('''
        <h5>ワーカー設定</h5>
        <p>このプライマリインスタンスと同期するクラスタワーカーノードを設定します。</p>
        
        <h5>名前</h5>
        <p>このワーカーを識別するための一意な名前です。</p>
        
        <h5>IP アドレス</h5>
        <p>ワーカーノードの IP アドレスです。IP ロックを無効にする場合は空欄のままにします。</p>
        
        <h5>IP ロック</h5>
        <p>有効にすると、ワーカーは指定した IP アドレスからのみ接続できます。</p>
        
        <h5>ロケーション情報</h5>
        <p>このワーカーの任意のロケーション情報です (国、都市、ホスト名)。</p>
        ''')
    }
    
    context = {
        'page_title': page_title, 
        'form': form, 
        'worker': worker, 
        'instance': worker,
        'form_description': form_description
    }
    return render(request, 'generic_form.html', context)


@login_required
def cluster_settings(request):
    """Cluster settings configuration"""
    if not UserAcl.objects.filter(user=request.user).filter(user_level__gte=50).exists():
        return render(request, 'access_denied.html', {'page_title': _('Access Denied')})
    
    cluster_settings, created = ClusterSettings.objects.get_or_create(name='cluster_settings')
    page_title = _('Cluster Settings')
    
    if request.method == 'POST':
        form = ClusterSettingsForm(request.POST, instance=cluster_settings)
        if form.is_valid():
            form.save()
            messages.success(request, _('Cluster settings updated successfully.'))
            if cluster_settings.enabled:
                if cluster_settings.config_version == 0:
                    cluster_settings.config_version += 1
                    cluster_settings.save()
            compress_dnsmasq_config()
            return redirect('/cluster/')
    else:
        form = ClusterSettingsForm(instance=cluster_settings)

    form_description = {
        'size': 'col-lg-6',
        'content': _('''
        <h5>クラスタモード</h5>
        <p>クラスタの動作方法と、ノード間で設定を同期する方法を設定します。</p>
        
        <h5>同期間隔</h5>
        <p>統計情報とキャッシュデータをクラスタノード間で同期する頻度を設定します。</p>
        
        <h5>再起動モード</h5>
        <p>設定変更時に WireGuard サービスを自動再起動するか、手動対応を必要とするかを選択します。</p>
        
        <h5>ワーカー表示</h5>
        <p>インターフェース上でワーカーを名前、サーバーアドレス、ロケーション、またはその組み合わせのどれで識別するかを選択します。</p>
        ''')
    }
    
    context = {
        'page_title': page_title,
        'form': form,
        'cluster_settings': cluster_settings,
        'instance': cluster_settings,
        'form_description': form_description
    }
    return render(request, 'generic_form.html', context)
