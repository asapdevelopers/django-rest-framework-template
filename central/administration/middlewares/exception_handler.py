import json
import logging
import traceback

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseBadRequest, StreamingHttpResponse, Http404, \
    HttpResponseNotFound
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.db import Error

logger = logging.getLogger('administration.site.others')


def _get_extra(request):
    if not request:
        return None

    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    remote_addr = request.META.get('REMOTE_ADDR')

    # Use a try catch just in case error happened when authenticating user and the framework failed to
    # Set the property
    try:
        user = unicode(request.user)
    except:
        user = "AnonymousUser"

    return u"[{}] {}\n{}\n{} - {}\n\n{}".format(request.method, request.path, user, xff, remote_addr,
                                                request.GET or request.POST)


class ExceptionMiddleware(object):
    # Changes 2016-08-26: Added __init__ and __call__ methods to support django 1.10 new style middlewares
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    def process_exception(self, request, exception):

        if not settings.DEBUG:

            # This does not handle not found due to url mismatch, but using it to handle
            # admin page model not found
            if isinstance(exception, Http404):
                msg = unicode(exception)
                logger.warn(u"{0}: \n{1}".format(msg, "Not found"), extra={'extra': _get_extra(request)})

                return HttpResponseNotFound("Not found: " + msg)

            if isinstance(exception, PermissionDenied):
                msg = unicode(exception)
                logger.warn(u"{0}: \n{1}".format(msg, "Not allowed"), extra={'extra': _get_extra(request)})

                return HttpResponseForbidden("Not allowed: " + msg)

            else:
                logger.error(u"{0} ( {1} ) : \n{2}".format(unicode(exception), unicode(exception.args), ''),
                             extra={'extra': _get_extra(request)})

                if not request.is_ajax():
                    # For now return the same.
                    return HttpResponseBadRequest(unicode(exception))
                else:
                    return HttpResponseBadRequest(unicode(exception))

        # If debug, allow exception to flow so we get debug data.
        else:
            return None
