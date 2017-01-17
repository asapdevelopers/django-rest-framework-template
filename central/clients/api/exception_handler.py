from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.http import Http404
from django.core.exceptions import ValidationError as dValidationError
from django.core.exceptions import PermissionDenied as dPermissionDenied    #to not override PermissionDenied from restframework
from rest_framework import status
from django.utils.encoding import force_text
from rest_framework.settings import api_settings
from django.db import Error, IntegrityError, DataError
from django.utils import timezone
from rest_framework import serializers
from logic.exceptions import _force_text_recursive, ExceptionCodes, OperationError, APIException, ValidationError, ParseError, AuthenticationFailed, NotAuthenticated, PermissionDenied, NotFound, MethodNotAllowed, NotAcceptable, UnsupportedMediaType, Throttled
import logging
import traceback


auth_logger = logging.getLogger('clients.api.auth')
validation_logger = logging.getLogger('clients.api.validation')
data_logger = logging.getLogger('clients.api.data')
others_logger = logging.getLogger('clients.api.others')
throttled_logger = logging.getLogger('clients.api.throttled')


NON_FIELDS_KEY = api_settings.NON_FIELD_ERRORS_KEY


#Note: All 401 responses are converted to 403 (automatically by rest framework) if no authentication was attempted
#(no authentication filter used)

#region exception handler

        

# ---------- Custom exception handler ------------

#Associate a code to usually used django rest framework api exception
default_exceptions_dict = {
    ValidationError : ExceptionCodes.validationError,
    AuthenticationFailed : ExceptionCodes.authenticationError,
    NotAuthenticated : ExceptionCodes.authenticationError,
    PermissionDenied : ExceptionCodes.permissionError,
    ParseError : ExceptionCodes.parseError,
    NotFound : ExceptionCodes.notFound,
    Throttled: ExceptionCodes.throttled,    

}

#Map known api exceptions to loggers
api_exc_loggers = {
    ValidationError : validation_logger.info,

    #These two should probably be removed once production because errors related to not being able to
    #authenticate won't go through any throttler.
    AuthenticationFailed : auth_logger.warn,
    NotAuthenticated : auth_logger.warn,

    PermissionDenied : auth_logger.warn,
    ParseError : others_logger.info,
    NotFound : others_logger.info,
    MethodNotAllowed: others_logger.info,
    OperationError: others_logger.error,
    NotAcceptable: others_logger.info,
    UnsupportedMediaType: others_logger.info,
    Throttled: throttled_logger.info

}

def _get_extra(context):
    request = context.get('request',None)
    
    if not request:
        return None

    #remove potential confident data from request data
    data = {}
    try:
        if request.data:
            if hasattr(request.data, 'iteritems'):
                for k,v in request.data.iteritems():
                    if k not in ('password','token'):
                        data[k] = v
                    else:
                        data[k] = '****'
            else:
                data = request.data

    except Exception as e:
        data = u'Failed to get request data: ' + unicode(e)

    #Use a try catch just in case error happened when authenticating user and the framework failed to
    #Set the property
    try:
        user = unicode(request.user)
        user_id = getattr(request.user, 'pk', None)
    except:
        user = "AnonymousUser"
        user_id = None

    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    remote_addr = request.META.get('REMOTE_ADDR')

    return {
        'extra': u"[{}] {}\n{}\n{} - {}\n\n{}".format(request.method,request.path,user,xff,remote_addr, data),
        'user_id':user_id
    }

def custom_exception_handler(exc, context):
    '''

    '''
    result = { }
    res = None

        
    #99% of all exceptions will fall in here.
    if isinstance(exc, APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        
        result['detail'] = exc.detail
        result['code'] = getattr(exc,'code',None)

        #Add special code for validation so we can tell clients easier that the result
        #is an api validation error which includes a dict of key-values for each field
        if not result['code']:
            result['code'] = default_exceptions_dict.get(type(exc),None)

        res = Response(result, status=exc.status_code, headers=headers)

        apilogger = api_exc_loggers.get(type(exc),None)
        if apilogger:
            apilogger(force_text(result), extra=_get_extra(context))

       
                
    #Conver any unhandled django vlaidation error into api validation error
    elif isinstance(exc, dValidationError):
        result['detail'] = exc.message_dict     
        result['code'] = ExceptionCodes.validationError    
        res = Response(result, status=status.HTTP_400_BAD_REQUEST)
        validation_logger.info(force_text(result), extra=_get_extra(context))

    elif isinstance(exc, ValueError):
        #Some unchecked errors that should rarely happen    
        result['detail'] = {NON_FIELDS_KEY:[force_text(exc)]}
        result['code'] = ExceptionCodes.validationError    
        res = Response(result, status=status.HTTP_400_BAD_REQUEST)
        validation_logger.info(force_text(result), extra=_get_extra(context))

    elif isinstance(exc, Http404):
        result['detail'] = u'Not found.'
        result['code'] = ExceptionCodes.notFound          
        res = Response(result, status=status.HTTP_404_NOT_FOUND)
        others_logger.info(force_text(result), extra=_get_extra(context))

    elif isinstance(exc, dPermissionDenied):
        result['detail'] = u'Permission denied.'      
        result['code'] = ExceptionCodes.permissionError
        res = Response(result, status=status.HTTP_403_FORBIDDEN)
        auth_logger.warn(force_text(result), extra=_get_extra(context))

    elif isinstance(exc, (DataError, IntegrityError)):
        result['detail'] = force_text(exc)
        result['code'] = ExceptionCodes.dataError
        res = Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        data_logger.error(force_text(result) + "\n" + traceback.format_exc(), extra=_get_extra(context))
    

    elif isinstance(exc, Error):
        result['detail'] = u"Uncontrolled db error: " + force_text(exc)
        result['code'] = ExceptionCodes.dbError
        res = Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        data_logger.critical(force_text(result) + "\n" + traceback.format_exc(), extra=_get_extra(context))

    else:
        result['detail'] = u"Unknown error: " + force_text(exc)   
        result['code'] = ExceptionCodes.unknownError

        res = Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        others_logger.critical(force_text(result) + "\n"+ traceback.format_exc(), extra=_get_extra(context))        

    return res




#endregion