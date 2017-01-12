﻿from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.shortcuts import render
from django.db import transaction
from django.utils.html import format_html, strip_tags, escape
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django.db.models import Sum
from django.contrib.admin.widgets import ForeignKeyRawIdWidget
from django.contrib.admin.helpers import ActionForm
from django.contrib.admin import SimpleListFilter, ListFilter
from django.contrib import messages
from django.contrib.postgres.fields import JSONField
from jsoneditor.widgets import JSONEditor
import administration.models as adminModels
import logsApp.models as logModels
import clients.models as clientsModels
from logic import auth
import json
import re


admin.site.site_header = 'Central Administration'
admin.site.index_title = 'Central Administration'

# Override all json widgets
admin.ModelAdmin.formfield_overrides = {
    JSONField: {'widget': JSONEditor},

}


#region some custom overriden classes

class NullListFilter(SimpleListFilter):
    def lookups(self, request, model_admin):
        return (
            ('1', self.null or 'null', ),
            ('0', self.notNull or 'not null', ),
        )

    def queryset(self, request, queryset):
        if self.value() in ('0', '1'):
            kwargs = { '{0}__isnull'.format(self.parameter_name) : self.value() == '1' }
            return queryset.filter(**kwargs)
        return queryset

def getNullListFilter(field, name = None, nullLabel = None, notNullLabel = None):
    class NullListFieldFilter(NullListFilter):
        parameter_name = field
        title = name or parameter_name
        null = nullLabel
        notNull = notNullLabel

    return NullListFieldFilter

class SingleTextInputFilter(ListFilter):
    """
        Custom filter to allow textbox input filtering.        
    """
    parameter_name = None
    template = "administration/textboxFilter.html"

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
            'display':'All',
        }
        return ({
            'get_query': cl.params,
            'current_value': self.value(),
            'all_choice': all_choice,
            'parameter_name': self.parameter_name
        }, )

def getTextFilter(field, name = None):
    class SingleTextInputFieldFilter(SingleTextInputFilter):
        parameter_name = field
        title = name or parameter_name
        
        def queryset(self, request, queryset):
            if self.value():
                kwargs = { '{0}'.format(self.parameter_name) : self.value()}
                return queryset.filter(**kwargs)
                

    return SingleTextInputFieldFilter

class CustomForeignKeyRawIdWidget(ForeignKeyRawIdWidget):

    def __init__(self, rel, attrs = None, using = None):
        return super(CustomForeignKeyRawIdWidget, self).__init__(rel, admin.site, attrs, using)

    #Override label so it also presents a link rather than a single label
    def label_for_value(self, value):
        key = self.rel.get_related_field().name

        try:
            instance = self.rel.model._default_manager.using(self.db).get(**{key: value})

            label, name = instance._meta.app_label, instance._meta.model_name
            return format_html(
                            u'<a href="{}">{}</a><br/>', 
                            reverse('admin:%s_%s_change' % (label,name),args=(instance.pk,)),
                            instance
                        )             

        except (ValueError, self.rel.model.DoesNotExist):
            return ''

#endreigon


#region administration admin models

class AdministratorChangeForm(forms.ModelForm):
    """
        Custom code to make abstract base user work with django admin
    """

    class Meta:
        model = adminModels.Administrator       
        fields = '__all__'

    password = forms.CharField(label="Password", 
                               help_text="This is the hashed password value, you may change it with a real value, or leave it as it is to keep it unchanged.",
                               required=True,
                               widget=forms.TextInput(attrs={'class':"vTextField"})
                               )   
        
    def __init__(self, *args, **kwargs):
        super(AdministratorChangeForm, self).__init__(*args, **kwargs)
   
    def clean(self):
        cleaned_data = super(AdministratorChangeForm, self).clean()
        
        #If password was changed, set the new password with password hasher. Else remain unchanged.        
        if 'password' in self.changed_data:
            
            #We need to set all attributes on the instance so all password validators can work effectively
            #Skip changed password as old password might be needed.
            
            for k,v in cleaned_data.iteritems():
                if k != 'password':
                    setattr(self.instance,k,v)

            password = cleaned_data.get('password',None)
            if password:
                try:
                    auth.validateAdminPassword(self.instance,password)
                except ValidationError as e:
                    raise ValidationError({'password':e})

                auth.setAdminPassword(self.instance,password)

                #Set hashed password
                cleaned_data['password'] = self.instance.password

    def save(self, commit=True):        
        user = super(AdministratorChangeForm, self).save(commit=False)
        
        if commit:            
            user.save()
            
        return user

class AdministratorAdmin(admin.ModelAdmin):
    form = AdministratorChangeForm
    list_display = ('email', 'firstName', 'lastName', 'last_login')
    search_fields = ('email',)
    

admin.site.register(adminModels.Administrator, AdministratorAdmin)

#region clients models

class UserChangeForm(forms.ModelForm):
    
    class Meta:
        model = clientsModels.User       
        fields = '__all__'

    password = forms.CharField(label="Password", 
                               help_text="This is the hashed password value, you may change it with a real value, or leave it as it is to keep it unchanged.",
                               required=True,
                               widget=forms.TextInput(attrs={'class':"vTextField"})
                               )

    
        
    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
   
   
    def clean(self):
        cleaned_data = super(UserChangeForm, self).clean()
        
        #If password was changed, set the new password with password hasher. Else remain unchanged.        
        if 'password' in self.changed_data:

            #We need to set all attributes on the instance so all password validators can work effectively
            #Skip changed password as old password might be needed.
            
            for k,v in cleaned_data.iteritems():
                if k != 'password':
                    setattr(self.instance,k,v)

            password = cleaned_data.get('password',None)
            if password:
                try:
                    auth.validateUserPassword(self.instance,password)
                except ValidationError as e:
                    raise ValidationError({'password':e})

                auth.setUserPassword(self.instance,password)

                #Set hashed password
                cleaned_data['password'] = self.instance.password


    def save(self, commit=True):        
        user = super(UserChangeForm, self).save(commit=False)
        
        if commit:            
            user.save()

        return user



class UserAdmin(admin.ModelAdmin):
    form = UserChangeForm
    list_display = ('id','email', 'last_login')
   
    def impersonation_token(self, instance):
        if instance.pk: 
            return auth.createUserJWT(instance) 
           
        else:
            return ""
   

    impersonation_token.short_description = "Impersonation Token"

    readonly_fields = ('impersonation_token',)
    search_fields = ('email', )

admin.site.register(clientsModels.User, UserAdmin)

#endregion
#----------------------------------------------------------------

class CentralErrorLogAdmin(admin.ModelAdmin):
    model = logModels.CentralErrorLog
    list_display = ('date','level','logName','message')    

    list_filter = ['level','logName','fileName']

    def formfield_for_dbfield(self, db_field, **kwargs):
        formfield = super(CentralErrorLogAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if db_field.name in ('message','extra'):
            formfield.widget = forms.Textarea(attrs=formfield.widget.attrs)
        return formfield
    
admin.site.register(logModels.CentralErrorLog, CentralErrorLogAdmin)


#Unregister some
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
admin.site.unregister(Group)
admin.site.unregister(Site)