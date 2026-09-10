from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, HTML, Layout, Row, Submit
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from wireguard.models import PeerGroup
from .models import UserAcl


class UserAclForm(forms.Form):
    username = forms.CharField(max_length=150, label=_("Username"))
    password1 = forms.CharField(widget=forms.PasswordInput, required=False, label=_("Password"))
    password2 = forms.CharField(widget=forms.PasswordInput, required=False, label=_("Password Confirmation"))
    enable_console = forms.BooleanField(required=False, label=_("Console"))
    enable_reload = forms.BooleanField(required=False, label=_("Reload WireGuard"))
    enable_restart = forms.BooleanField(required=False, label=_("Restart WireGuard"))
    enable_enhanced_filter = forms.BooleanField(required=False, label=_("Enhanced Filter"))
    enable_audit_log = forms.BooleanField(required=False, label=_("監査ログ"))
    user_level = forms.ChoiceField(choices=UserAcl.user_level.field.choices, required=True, label=_("User Level"))
    peer_groups = forms.ModelMultipleChoiceField(
        queryset=PeerGroup.objects.all(),
        required=False,
        label=_("Peer Groups"),
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        self.user_id = kwargs.pop('user_id', None)
        super().__init__(*args, **kwargs)

        if self.instance:
            self.fields['username'].initial = self.instance.username
            self.fields['username'].widget.attrs['readonly'] = True
            self.fields['peer_groups'].initial = self.instance.useracl.peer_groups.all()
            self.fields['enable_console'].initial = self.instance.useracl.enable_console
            self.fields['enable_reload'].initial = self.instance.useracl.enable_reload
            self.fields['enable_restart'].initial = self.instance.useracl.enable_restart
            self.fields['enable_enhanced_filter'].initial = self.instance.useracl.enable_enhanced_filter
            self.fields['enable_audit_log'].initial = self.instance.useracl.enable_audit_log
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.fields['enable_console'].initial = True
            self.fields['enable_reload'].initial = True
            self.fields['enable_restart'].initial = True
            self.fields['enable_enhanced_filter'].initial = False
            self.fields['enable_audit_log'].initial = False

        delete_label = _("Delete")
        back_label = _("Back")

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        
        if self.instance:
            delete_html = f"<a href='javascript:void(0)' class='btn btn-outline-danger' data-command='delete' onclick='openCommandDialog(this)'>{delete_label}</a>"
        else:
            delete_html = ''
            
        self.helper.layout = Layout(
            Row(
                Column('username', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('password1', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('password2', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('user_level', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('peer_groups', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('enable_console', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('enable_reload', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('enable_restart', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('enable_enhanced_filter', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('enable_audit_log', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column(
                    Submit('submit', _('Save'), css_class='btn btn-success'),
                    HTML(f' <a class="btn btn-secondary" href="/user/list/">{back_label}</a> '),
                    HTML(delete_html),
                    css_class='col-md-12'),
                css_class='form-row'
            )
        )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exclude(pk=self.user_id).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if not self.instance:  
            if not password1:
                raise ValidationError(_("Password is required for new users."))
            if not password2:
                raise ValidationError(_("Password confirmation is required for new users."))

        if password1 or password2: 
            if password1 != password2:
                raise ValidationError(_("The two password fields didn't match."))
            if len(password1) < 8:
                raise ValidationError(_("Password must be at least 8 characters long."))

        return cleaned_data

    def save(self):
        username = self.cleaned_data['username']
        password = self.cleaned_data.get('password1')
        user_level = self.cleaned_data['user_level']
        peer_groups = self.cleaned_data.get('peer_groups', [])
        enable_console = self.cleaned_data.get('enable_console', False)
        enable_reload = self.cleaned_data.get('enable_reload', False)
        enable_restart = self.cleaned_data.get('enable_restart', False)
        enable_enhanced_filter = self.cleaned_data.get('enable_enhanced_filter', False)
        enable_audit_log = self.cleaned_data.get('enable_audit_log', False)

        if self.instance:
            user = self.instance
            if password:
                user.set_password(password)
                user.save()
        else:
            user = User.objects.create_user(
                username=username,
                password=password
            )

        user_acl, created = UserAcl.objects.update_or_create(
            user=user,
            defaults={
                'user_level': user_level,
                'enable_console': enable_console,
                'enable_reload': enable_reload,
                'enable_restart': enable_restart,
                'enable_enhanced_filter': enable_enhanced_filter,
                'enable_audit_log': enable_audit_log
            }
        )
        
        user_acl.peer_groups.set(peer_groups)

        return user


class UserMfaSetupForm(forms.Form):
    totp_pin = forms.CharField(
        label=_('認証コード'),
        max_length=6,
        min_length=6,
        help_text=_('認証アプリに表示された6桁のコードを入力してください。'),
    )


class UserMfaDisableForm(forms.Form):
    confirm = forms.BooleanField(
        label=_('MFAを無効化します'),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'confirm',
            Row(
                Column(
                    Submit('submit', _('無効化'), css_class='btn btn-danger'),
                    HTML(' <a class="btn btn-secondary" href="/user/mfa/setup/">' + str(_('戻る')) + '</a>'),
                    css_class='col-md-12'
                ),
                css_class='form-row'
            )
        )


class PeerMfaUnlockForm(forms.Form):
    totp_pin = forms.CharField(
        label=_('認証コード'),
        max_length=6,
        min_length=6,
    )

    def __init__(self, *args, **kwargs):
        peer = kwargs.pop('peer', None)
        back_url = kwargs.pop('back_url', None)
        super().__init__(*args, **kwargs)
        if not back_url:
            back_url = f'/peer/manage/?peer={peer.uuid}' if peer else '/peer/list/'
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'totp_pin',
            Row(
                Column(
                    Submit('submit', _('VPN接続を有効化'), css_class='btn btn-primary'),
                    HTML(f' <a class="btn btn-secondary" href="{back_url}">{_("戻る")}</a>'),
                    css_class='col-md-12'
                ),
                css_class='form-row'
            )
        )



class PeerGroupForm(forms.ModelForm):
    class Meta:
        model = PeerGroup
        fields = ['name', 'peer', 'server_instance']

    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id', None)
        super().__init__(*args, **kwargs)
        self.fields['name'].label = _("Name")
        self.fields['peer'].label = _("Peer")
        self.fields['server_instance'].label = _("Server Instance")
        back_label = _("Back")
        delete_label = _("Delete")
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        
        if self.instance.pk:
            delete_html = f"<a href='javascript:void(0)' class='btn btn-outline-danger' data-command='delete' onclick='openCommandDialog(this)'>{delete_label}</a>"
        else:
            delete_html = ''
            
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('peer', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('server_instance', css_class='form-group col-md-12 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column(
                    Submit('submit', _('Save'), css_class='btn btn-success'),
                    HTML(f' <a class="btn btn-secondary" href="/user/peer-group/list/">{back_label}</a> '),
                    HTML(delete_html),
                    css_class='col-md-12'),
                css_class='form-row'
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        peers = cleaned_data.get('peer')
        server_instances = cleaned_data.get('server_instance')

        if PeerGroup.objects.filter(name=name).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError(_("A peer group with that name already exists."))

        return cleaned_data
    
    def save(self, commit=True):
        peer_group = super().save(commit=False)
        
        if commit:
            peer_group.save()

        return peer_group
