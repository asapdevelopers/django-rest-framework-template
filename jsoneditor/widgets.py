from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.conf import settings
from django import forms


class JSONEditor(forms.widgets.Widget):
    class Media:
        css = {
            'all': ('jsoneditor/jsoneditor.min.css',),
        }
        js = ('jsoneditor/jsoneditor.min.js',)

    def render(self, name, value, attrs=None, **kwargs):
        field_id = attrs['id']

        context = {
            'field_id': field_id,
            'field': name,
            'value': value or '',
            'STATIC_URL': settings.STATIC_URL,
        }

        widget_html = mark_safe(render_to_string('jsoneditor/jsoneditor_widget.html', context))

        return widget_html
