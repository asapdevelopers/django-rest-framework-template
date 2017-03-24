from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied, NotFound, ValidationError, \
    ParseError, NotAuthenticated, MethodNotAllowed, NotAcceptable, Throttled, UnsupportedMediaType
from django.core.exceptions import ValidationError as dValidationError
from django.utils.encoding import force_text
from rest_framework import status

'''
    All 'known' exceptions raised by the code should be APIException for easy handling.
    Some django model exceptions will be wraped into the equivalent APIException
    Unknown exceptions such as database exceptions won't be wrapped and will be handled by the exception handler.
'''


def full_clean(ele, validate_unique=True):
    """
        Calls the full_clean method of a model but wraping any django exception into rest api exception.
        Other model validation and exception conversion can be added here.
    """
    try:
        ele.full_clean(validate_unique=validate_unique)
    except dValidationError as e:
        raise ValidationError(detail=e.message_dict)


def validate_unique(ele):
    """
        Similar to full_clean, but only validate unique constraints
    """

    try:
        ele.validate_unique()
    except dValidationError as e:
        raise ValidationError(detail=e.message_dict)


class ExceptionCodes:
    validationError = 'validationError'
    authenticationError = 'authenticationError'
    permissionError = 'permissionError'
    notFound = 'notFound'
    parseError = 'parseError'
    throttled = 'throttled'

    dbError = 'dbError'
    dataError = 'dataError'
    dataTooBig = 'dataTooBig'

    s3Error = 's3Error'
    emailSendingError = 'emailSendingError'

    unknownError = 'unknownError'
    operationError = 'operationError'


class OperationError(APIException):
    """
        Custom exceptions that can not be served by regular API Exceptions.
        Exceptions will have:
           {
                detail: string, list or dictionary of strings ready.
                code: custom string code to identify the error when needed
                status_code: http status code to return, mostly used by web API, optional
           

           }
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Operation Error"
    code = ExceptionCodes.operationError

    def __init__(self, detail=None, code=None, status_code=None):
        self.detail = _force_text_recursive(detail) if detail else None

        # Add message to base exception
        self.message = self.detail

        if status_code:
            self.status_code = status_code

        if code:
            self.code = code

    def __unicode__(self):
        return unicode(self.detail)


def _force_text_recursive(data):
    """
        Copied from library to also include tuples
    """
    if isinstance(data, (list, tuple)):
        return [_force_text_recursive(item) for item in data]
    elif isinstance(data, dict):
        return dict([(key, _force_text_recursive(value)) for key, value in data.iteritems()])
    return force_text(data, strings_only=False, errors='ignore')
