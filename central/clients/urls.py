from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from rest_framework_swagger import urls as docsUrls
from clients.api.userAuth import UserAuth


#Create urls automatically through a router
router = DefaultRouter()

router.register(r'userauth', UserAuth, 'userauth')


urlpatterns = [
            
                url(r'^docs/', include(docsUrls.urlpatterns)),                       
                url(r'^', include(router.urls))                       
            ]