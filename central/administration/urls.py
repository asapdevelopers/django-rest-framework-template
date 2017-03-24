from datetime import datetime
from django.conf.urls import include, url
from django.contrib import admin
from administration.controllers import home

admin.autodiscover()

urlpatterns = [
    url(r'^home/', home.index, name='home/index'),
    url(r'^', include(admin.site.urls))  # Automatic admin pages
]
