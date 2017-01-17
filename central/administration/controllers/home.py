# Create your views here.
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, StreamingHttpResponse
from django.core.urlresolvers import reverse
import json
from django.utils.translation import ugettext_lazy as _

def _get_template(action):
    return "administration/home/{0}.html".format(action)

def index(request):
    
    return render(request, _get_template('index'), {})
