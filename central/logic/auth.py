import uuid
import jwt
from django.conf import settings
from datetime import timedelta, datetime
from django.utils import timezone
from dateutil import parser, tz
from clients.models import User
from administration.models import Administrator
from logic.exceptions import ExceptionCodes, AuthenticationFailed, PermissionDenied, OperationError
from django.contrib.auth.signals import user_login_failed
from django.contrib.auth.password_validation import validate_password, password_changed, get_default_password_validators, password_validators_help_texts
from django.core.exceptions import ValidationError as DjangoValidationError
import hashlib
import logging
import traceback
import requests

SECRET_KEY = settings.SECRET_KEY

#Use a separate key to avoid any conflicts with JWT.
RESET_TOKEN_SECRET_KEY = settings.RESET_TOKEN_SECRET_KEY

#Settings for JWT authentication
UTC = tz.tzutc()

ALGORITHM = 'HS256'
JWT_DECODE_AGLS = [ALGORITHM]
JWT_OPTIONS = {'require_exp':True}

TOKEN_EXPIRATION_MINS = 60 * 6
PASSWORD_RECOVERY_TOKEN_EXPIRATION_MINS = 10
PASSWORD_RECOVERY_TOKEN_EXPIRATION = timedelta(minutes=PASSWORD_RECOVERY_TOKEN_EXPIRATION_MINS)


AUTH_MESSAGES = {

    #General messages
    'user_locked':'User Locked.',
    'invalid_credentials':"Invalid credentials.",
    'invalid_user_token':"Invalid user token.",
    'invalid_password_recovery_token':"Password recovery token is invalid."
        
}


PASSWORD_RECOVERY_EMAIL_TEXT =\
u"""
Please use the below token on the password recovery form. If you did not request this, ignore this email.

{0}
"""

#WARNING: Unsafe html formatting, only use from known data.
PASSWORD_RECOVERY_EMAIL_TEXT_HTML =\
u"""<html><body>
<p>Please use the below token on the password recovery form. <span style='color:red'>If you did not request this, ignore this email.</span></p><br/>
<b>{0}</b>
</body></html>
"""

def validate_user_auth_status(user, ex_class = AuthenticationFailed):
    '''
        Performs additional user validation such as active and requiresPasswordChange
    '''
    if not user.is_active:
        raise ex_class(AUTH_MESSAGES['user_locked'])    

def authenticate_user(email, password, validate_additional = True, update_last_login = False, ex_class = AuthenticationFailed):
    '''
        Authenticates and returns an user instance or raises ex_class if authentication fails.
        if validate_additional is True, will perform additional user auth validation.
        We use a variable exception class as different calls might require different authentication exceptions.
    '''

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        raise ex_class(AUTH_MESSAGES['invalid_credentials'])

    if not user.check_password(password):
        raise ex_class(AUTH_MESSAGES['invalid_credentials'])

    if validate_additional:
        validate_user_auth_status(user, ex_class)

    if update_last_login:
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

    return user


def create_user_JWT(user, exp=TOKEN_EXPIRATION_MINS):
    '''
        Creates a user JWT with the following, with exp being a time in minutes

        {
            id
            exp
            l
        }

        We will be using password change date as part of the jwt so we can invalidate tokens on password change.
    '''
    
    payload = {
            'id':user.pk,
            'exp':datetime.utcnow() + timedelta(minutes=exp), #utc date + exp, jwt handles unix time translation.
            'l':user.last_password_change.isoformat() if user.last_password_change else ""
        }

    
    return jwt.encode(payload, SECRET_KEY, ALGORITHM)
   


def validate_user_JWT(token, validate_additional = True, ex_class = AuthenticationFailed):
    '''
        Returns a (user, token_data) instance only if the token is valid, has valid data and is not expired
        otherwise raises ex_class.
    '''
    
    if not token:
        raise ex_class(AUTH_MESSAGES['invalid_user_token'])

    try:        
        payload = jwt.decode(token, SECRET_KEY, True, JWT_DECODE_AGLS, options=JWT_OPTIONS)  #Handles exp and signature validation.

    except:
        raise ex_class(AUTH_MESSAGES['invalid_user_token'])

    try:
        user_id = int(payload['id'])          
        last = payload['l']

    except:
        raise ex_class(AUTH_MESSAGES['invalid_user_token'])    

    try:        
        user = User.objects.get(pk=user_id)        
    except User.DoesNotExist:
        raise ex_class(AUTH_MESSAGES['invalid_user_token'])

    user_last = user.last_password_change.isoformat() if user.last_password_change else ""
    if user_last != last:
        raise ex_class(AUTH_MESSAGES['invalid_user_token'])

    if validate_additional:
        validate_user_auth_status(user, ex_class)       

    return (user, payload)
            

#use os.urandom to get entropy from the OS and create cryptographically secure random bytes
#Then encode base64 to have a human readable key
from os import urandom
from base64 import b64encode

def _create_secret_key(length):  
    '''
        Creates a random key of length bytes using os random number generator.
    '''  
    return b64encode(urandom(length))   


admin_auth_logger = logging.getLogger('administration.site.auth')

#Attach login failures event to standard django's auth framework
#This is basically the admin login
#Will be removed once custom login is implemented.
def login_attempt_failure_handler(sender, **kwargs):
    admin_auth_logger.warn("Failed admin login.", extra={'extra':unicode(kwargs.get('credentials',''))})
    
user_login_failed.connect(login_attempt_failure_handler)


#region password validation


def get_user_password_validator_messages():
    '''
        Returns a list of all password requirements.
    '''
    return password_validators_help_texts()

def validate_user_password(user, password):
    '''
        Checks user passwords against settings passwords validators.
        Raises ValidationError (django) if any validator fails, with the associated validator message.        
    '''

    #Validate through default validators
    validate_password(password, user)


def set_user_password(user, password):
    '''
        Sets the user password running password hash algorithms
        No validation is done, call validate_user_password first.        
    '''

    user.set_password(password)
    user.last_password_change = timezone.now()
    

def check_user_password(user, password):
    '''
        Checks if user password is valid, returns True or False
    '''
    return user.check_password(password)


# ---

#For admin create other validation as we might want different kind.

def validate_admin_password(user, password):

    #Validate through default validators
    validate_password(password, user)

def set_admin_password(user, password):    
    user.set_password(password)
  


#endregion

#Region user password recovery

def create_user_password_recovery_token(user):
    '''
        Returns a JWT that can be used to recover a lost password.
    '''
    
    payload = {
            'id':user.pk,
            'last': user.last_password_change.isoformat() if user.last_password_change else "", #Use last password changed date so token is invalidated on change.
            'exp':datetime.utcnow() + PASSWORD_RECOVERY_TOKEN_EXPIRATION
        }

    
    return jwt.encode(payload, RESET_TOKEN_SECRET_KEY, ALGORITHM)


def validate_user_password_recovery_token(token, ex_class=PermissionDenied):
    '''
        Validates a user password recovery token and returns a user instance.
    '''

    if not token:
        raise ex_class(AUTH_MESSAGES['invalid_password_recovery_token'])

    try:        
        payload = jwt.decode(token, RESET_TOKEN_SECRET_KEY, True, JWT_DECODE_AGLS, options=JWT_OPTIONS)
    except:
        raise ex_class(AUTH_MESSAGES['invalid_password_recovery_token'])

    try:
        user_id = int(payload['id'])           
        last = payload['last']

    except:
        raise ex_class(AUTH_MESSAGES['invalid_password_recovery_token'])

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise ex_class(AUTH_MESSAGES['invalid_password_recovery_token'])

   
    user_last = user.last_password_change.isoformat() if user.last_password_change else ""
    if user_last != last:
        raise ex_class(AUTH_MESSAGES['invalid_password_recovery_token'])


    return user

#endregion

