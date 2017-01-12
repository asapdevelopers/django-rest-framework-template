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


authLogger = logging.getLogger('clients.api.auth')
validationLogger = logging.getLogger('clients.api.validation')
dataLogger = logging.getLogger('clients.api.data')
othersLogger = logging.getLogger('clients.api.others')
throttledLogger = logging.getLogger('clients.api.throttled')


NON_FIELDS_KEY = api_settings.NON_FIELD_ERRORS_KEY


#Note: All 401 responses are converted to 403 (automatically by rest framework) if no authentication was attempted
#(no authentication filter used)

#region exception handler

        

# ---------- Custom exception handler ------------

#Associate a code to usually used django rest framework api exception
defaultExceptionsDict = {
    ValidationError : ExceptionCodes.validationError,
    AuthenticationFailed : ExceptionCodes.authenticationError,
    NotAuthenticated : ExceptionCodes.authenticationError,
    PermissionDenied : ExceptionCodes.permissionError,
    ParseError : ExceptionCodes.parseError,
    NotFound : ExceptionCodes.notFound,
    Throttled: ExceptionCodes.throttled,    

}

#Map known api exceptions to loggers
apiExcLoggers = {
    ValidationError : validationLogger.info,

    #These two should probably be removed once production because errors related to not being able to
    #authenticate won't go through any throttler.
    AuthenticationFailed : authLogger.warn,
    NotAuthenticated : authLogger.warn,

    PermissionDenied : authLogger.warn,
    ParseError : othersLogger.info,
    NotFound : othersLogger.info,
    MethodNotAllowed: othersLogger.info,
    OperationError: othersLogger.error,
    NotAcceptable: othersLogger.info,
    UnsupportedMediaType: othersLogger.info,
    Throttled: throttledLogger.info

}

def _getExtra(context):
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
        userId = getattr(request.user, 'pk', None)
    except:
        user = "AnonymousUser"
        userId = None

    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    remoteAddr = request.META.get('REMOTE_ADDR')

    return {
        'extra': u"[{}] {}\n{}\n{} - {}\n\n{}".format(request.method,request.path,user,xff,remoteAddr, data),
        'userId':userId
    }

def customExceptionHandler(exc, context):
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
            result['code'] = defaultExceptionsDict.get(type(exc),None)

        res = Response(result, status=exc.status_code, headers=headers)

        apilogger = apiExcLoggers.get(type(exc),None)
        if apilogger:
            apilogger(force_text(result), extra=_getExtra(context))

       
                
    #Conver any unhandled django vlaidation error into api validation error
    elif isinstance(exc, dValidationError):
        result['detail'] = exc.message_dict     
        result['code'] = ExceptionCodes.validationError    
        res = Response(result, status=status.HTTP_400_BAD_REQUEST)
        validationLogger.info(force_text(result), extra=_getExtra(context))

    elif isinstance(exc, ValueError):
        #Some unchecked errors that should rarely happen    
        result['detail'] = {NON_FIELDS_KEY:[force_text(exc)]}
        result['code'] = ExceptionCodes.validationError    
        res = Response(result, status=status.HTTP_400_BAD_REQUEST)
        validationLogger.info(force_text(result), extra=_getExtra(context))

    elif isinstance(exc, Http404):
        result['detail'] = u'Not found.'
        result['code'] = ExceptionCodes.notFound          
        res = Response(result, status=status.HTTP_404_NOT_FOUND)
        othersLogger.info(force_text(result), extra=_getExtra(context))

    elif isinstance(exc, dPermissionDenied):
        result['detail'] = u'Permission denied.'      
        result['code'] = ExceptionCodes.permissionError
        res = Response(result, status=status.HTTP_403_FORBIDDEN)
        authLogger.warn(force_text(result), extra=_getExtra(context))

    elif isinstance(exc, (DataError, IntegrityError)):
        result['detail'] = force_text(exc)
        result['code'] = ExceptionCodes.dataError
        res = Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        dataLogger.error(force_text(result) + "\n" + traceback.format_exc(), extra=_getExtra(context))
    

    elif isinstance(exc, Error):
        result['detail'] = u"Uncontrolled db error: " + force_text(exc)
        result['code'] = ExceptionCodes.dbError
        res = Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        dataLogger.critical(force_text(result) + "\n" + traceback.format_exc(), extra=_getExtra(context))

    else:
        result['detail'] = u"Unknown error: " + force_text(exc)   
        result['code'] = ExceptionCodes.unknownError

        res = Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        othersLogger.critical(force_text(result) + "\n"+ traceback.format_exc(), extra=_getExtra(context))        

    return res




#endregion