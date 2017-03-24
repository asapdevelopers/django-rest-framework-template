from django.utils.translation import activate, deactivate, get_language
from django.utils.translation.trans_real import parse_accept_lang_header


class LocaleMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        lang_found = None
        txt = request.META.get('HTTP_ACCEPT_LANGUAGE', None)

        if txt:
            parsed = parse_accept_lang_header(txt)
            lang_found = parsed[0][0] if parsed else None

        if lang_found:
            activate(lang_found)

        request.LANGUAGE_CODE = get_language()

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        if request.LANGUAGE_CODE and 'Content-Language' not in response:
            response['Content-Language'] = request.LANGUAGE_CODE

        # Restore language
        deactivate()

        return response
