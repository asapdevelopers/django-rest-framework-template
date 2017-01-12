from django.conf.urls import include, url
from django.contrib import admin
from django.views.i18n import javascript_catalog
from django.http import HttpResponse
from django.conf import settings

urlpatterns = []

from clients import urls as clientsUrls
urlpatterns.append(url(r'^api/', include(clientsUrls.urlpatterns)))

from administration import urls as administrationUrls
admin.autodiscover()
urlpatterns.append(url(r'^', include(administrationUrls.urlpatterns))) #Make sure to always have a root url so aws doesn't complain with its internal tests to '/'
    



# Add robots.txt url

robotsRes ="User-agent: *\r\nDisallow: /"
def robotstxt(request):
    return HttpResponse(robotsRes)

urlpatterns.append(url(r'^robots\.txt$', robotstxt))