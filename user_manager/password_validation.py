import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class CharacterClassPasswordValidator:
    def validate(self, password, user=None):
        errors = []
        if len(password) < 12:
            errors.append(_('パスワードは12文字以上で入力してください。'))
        if not re.search(r'[A-Z]', password):
            errors.append(_('パスワードには英大文字を1文字以上含めてください。'))
        if not re.search(r'[a-z]', password):
            errors.append(_('パスワードには英小文字を1文字以上含めてください。'))
        if not re.search(r'[0-9]', password):
            errors.append(_('パスワードには数字を1文字以上含めてください。'))
        if not re.search(r'[^A-Za-z0-9]', password):
            errors.append(_('パスワードには記号を1文字以上含めてください。'))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _('パスワードは12文字以上で、英大文字・英小文字・数字・記号をそれぞれ1文字以上含めてください。')
