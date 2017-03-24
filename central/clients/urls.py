from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from rest_framework_swagger import urls as docs_urls
from clients.api.user_auth import UserAuth

# Create urls automatically through a router
router = DefaultRouter()

router.register(r'userauth', UserAuth, 'userauth')

urlpatterns = [
    url(r'^docs/', include(docs_urls.urlpatterns)),
    url(r'^', include(router.urls))
]
