from rest_framework import authentication
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from dateutil import parser, tz
from django.core.cache import cache
from logic.exceptions import AuthenticationFailed
from logic.auth import validate_user_JWT



class JWTUserAuthenticator(authentication.BaseAuthentication):
    '''
        User JWT Authenticator, will set request.user and request.auth where user is the user instance authenticated
        and auth is the token data
    '''   
       
    def authenticate(self, request):
       
        header = request.META.get('HTTP_AUTHORIZATION')
       
        try:
            auth_type, token = header.split(' ')
            if auth_type != "Token" or not token:
                raise Exception()
        except:
            
            return None

        #Check token cache
        cache_key = 'tk_'+token
        exists = cache.get(cache_key)
        if exists:
            return exists
                  
        #Not found, get it
        user, token_data = validate_user_JWT(token)

        #cache results with 15s timeout. Small enough to avoid inconsistencies but strong
        #enough to greatly help on multiple concurrent requests
        res = (user, token_data)
        cache.set(cache_key, res, 15)
        
        #For now just get the first user found
        return res

    def authenticate_header(self, request):
        '''
            Returns auth protocol
        '''
        return "Token"