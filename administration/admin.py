from builtins import object
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter, ListFilter
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.utils.html import format_html

import administration.models as admin_models
import clients.models as clients_models
import logs_app.models as log_models
from core import auth
from jsoneditor.widgets import JSONEditor

# Unregister some
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site

admin.site.site_header = 'Administration'
admin.site.index_title = 'Administration'

# Override all json widgets
admin.ModelAdmin.formfield_overrides = {
    JSONField: {'widget': JSONEditor},
}


# region some custom overriden classes

class NullListFilter(SimpleListFilter):
    def lookups(self, request, model_admin):
        return (
            ('1', self.null or 'null',),
            ('0', self.not_null or 'not null',),
        )

    def queryset(self, request, queryset):
        if self.value() in ('0', '1'):
            kwargs = {'{0}__isnull'.format(self.parameter_name): self.value() == '1'}
            return queryset.filter(**kwargs)
        return queryset


def get_null_list_filter(field, name=None, null_label=None, not_null_label=None):
    class NullListFieldFilter(NullListFilter):
        parameter_name = field
        title = name or parameter_name
        null = null_label
        not_null = not_null_label

    return NullListFieldFilter


class SingleTextInputFilter(ListFilter):
    """
        Custom filter to allow textbox input filtering.        
    """
    parameter_name = None
    template = "administration/textbox_filter.html"

    def __init__(self, request, params, model, model_admin):
        super(SingleTextInputFilter, self).__init__(
            request, params, model, model_admin)
        if self.parameter_name is None:
            raise ImproperlyConfigured(
                "The list filter '%s' does not specify "
                "a 'parameter_name'." % self.__class__.__name__)

        if self.parameter_name in params:
            value = params.pop(self.parameter_name)
            self.used_parameters[self.parameter_name] = value

    def value(self):
        return self.used_parameters.get(self.parameter_name, None)

    def has_output(self):
        return True

    def expected_parameters(self):
        return [self.parameter_name]

    def choices(self, cl):
        all_choice = {
            'selected': self.value() is None,
            'query_string': cl.get_query_string({}, [self.parameter_name]),
            'display': 'All',
        }
        return ({'get_query': cl.params,
                 'current_value': self.value(),
                 'all_choice': all_choice,
                 'parameter_name': self.parameter_name},)


def get_text_filter(field, name=None):
    class SingleTextInputFieldFilter(SingleTextInputFilter):
        parameter_name = field
        title = name or parameter_name

        def queryset(self, request, queryset):
            if self.value():
                kwargs = {'{0}'.format(self.parameter_name): self.value()}
                return queryset.filter(**kwargs)

    return SingleTextInputFieldFilter


class CustomForeignKeyRawIdWidget(ForeignKeyRawIdWidget):
    def __init__(self, rel, attrs=None, using=None):
        return super(CustomForeignKeyRawIdWidget, self).__init__(rel, admin.site, attrs, using)

    # Override label so it also presents a link rather than a single label
    def label_for_value(self, value):
        key = self.rel.get_related_field().name

        try:
            instance = self.rel.model._default_manager.using(self.db).get(**{key: value})

            label, name = instance._meta.app_label, instance._meta.model_name
            return format_html(
                u'<a href="{}">{}</a><br/>',
                reverse('admin:%s_%s_change' % (label, name), args=(instance.pk,)),
                instance
            )

        except (ValueError, self.rel.model.DoesNotExist):
            return ''


# endreigon


# region administration admin models

class AdministratorChangeForm(forms.ModelForm):
    """
        Custom code to make abstract base user work with django admin
    """

    class Meta(object):
        model = admin_models.Administrator
        fields = '__all__'

    password = forms.CharField(label="Password",
                               help_text="This is the hashed password value, you may change it with a real value, "
                                         "or leave it as it is to keep it unchanged.",
                               required=True,
                               widget=forms.TextInput(attrs={'class': "vTextField"})
                               )

    def __init__(self, *args, **kwargs):
        super(AdministratorChangeForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(AdministratorChangeForm, self).clean()

        # If password was changed, set the new password with password hasher. Else remain unchanged.
        if 'password' in self.changed_data:

            # We need to set all attributes on the instance so all password validators can work effectively
            # Skip changed password as old password might be needed.

            for k, v in cleaned_data.items():
                if k != 'password':
                    setattr(self.instance, k, v)

            password = cleaned_data.get('password', None)
            if password:
                try:
                    auth.validate_admin_password(self.instance, password)
                except ValidationError as e:
                    raise ValidationError({'password': e})

                auth.set_admin_password(self.instance, password)

                # Set hashed password
                cleaned_data['password'] = self.instance.password

    def save(self, commit=True):
        user = super(AdministratorChangeForm, self).save(commit=False)

        if commit:
            user.save()

        return user


class AdministratorAdmin(admin.ModelAdmin):
    form = AdministratorChangeForm
    list_display = ('email', 'first_name', 'last_name', 'last_login')
    search_fields = ('email',)


admin.site.register(admin_models.Administrator, AdministratorAdmin)


# region clients models

class UserChangeForm(forms.ModelForm):
    class Meta(object):
        model = clients_models.User
        fields = '__all__'

    password = forms.CharField(label="Password",
                               help_text="This is the hashed password value, you may change it with a real value, "
                                         "or leave it as it is to keep it unchanged.",
                               required=True,
                               widget=forms.TextInput(attrs={'class': "vTextField"})
                               )

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(UserChangeForm, self).clean()

        # If password was changed, set the new password with password hasher. Else remain unchanged.
        if 'password' in self.changed_data:

            # We need to set all attributes on the instance so all password validators can work effectively
            # Skip changed password as old password might be needed.

            for k, v in cleaned_data.items():
                if k != 'password':
                    setattr(self.instance, k, v)

            password = cleaned_data.get('password', None)
            if password:
                try:
                    auth.validate_user_password(self.instance, password)
                except ValidationError as e:
                    raise ValidationError({'password': e})

                auth.set_user_password(self.instance, password)

                # Set hashed password
                cleaned_data['password'] = self.instance.password

    def save(self, commit=True):
        user = super(UserChangeForm, self).save(commit=False)

        if commit:
            user.save()

        return user


class UserAdmin(admin.ModelAdmin):
    form = UserChangeForm
    list_display = ('id', 'email', 'last_login')

    def impersonation_token(self, instance):
        if instance.pk:
            return auth.create_user_jwt(instance)

        else:
            return ""

    impersonation_token.short_description = "Impersonation Token"

    readonly_fields = ('impersonation_token',)
    search_fields = ('email',)


admin.site.register(clients_models.User, UserAdmin)


# endregion
# ----------------------------------------------------------------

class CentralErrorLogAdmin(admin.ModelAdmin):
    model = log_models.CentralErrorLog
    list_display = ('date', 'level', 'log_name', 'message')

    list_filter = ['level', 'log_name', 'file_name']

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super(CentralErrorLogAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if db_field.name in ('message', 'extra'):
            formfield.widget = forms.Textarea(attrs=formfield.widget.attrs)
        return formfield


admin.site.register(log_models.CentralErrorLog, CentralErrorLogAdmin)

admin.site.unregister(Group)
admin.site.unregister(Site)
