from django.conf import settings
from rest_framework import renderers, parsers
from rest_framework.exceptions import ParseError

DATA_UPLOAD_MAX_MEMORY_SIZE = settings.DATA_UPLOAD_MAX_MEMORY_SIZE


# We will define a copy/paste versions of drf parsers but that will honor django's DATA_UPLOAD_MAX_MEMORY_SIZE setting
# to help with DoS caused by large objects request


def check_content_length(parser_context):
    if parser_context and DATA_UPLOAD_MAX_MEMORY_SIZE and 'request' in parser_context:

        try:
            content_length = int(parser_context['request'].META.get('CONTENT_LENGTH', 0))
        except (ValueError, TypeError):
            content_length = 0

        if content_length and content_length > DATA_UPLOAD_MAX_MEMORY_SIZE or content_length < 0:
            raise ParseError('Request parse error - Invalid Content')


class LimitedJSONParser(parsers.JSONParser):
    """
    Parses JSON-serialized data.
    This json parser won't allow large file uploads through base64 encoded strings. Use multipart instead
    """
    media_type = 'application/json'
    renderer_class = renderers.JSONRenderer

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as JSON and returns the resulting data.
        """

        check_content_length(parser_context)

        return super(LimitedJSONParser, self).parse(stream, media_type, parser_context)


class LimitedFormParser(parsers.FormParser):
    """
    Parser for form data.
    This parser won't allow large file uploads through urlencoded encoded strings. Use multipart instead
    """
    media_type = 'application/x-www-form-urlencoded'

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as a URL encoded form,
        and returns the resulting QueryDict.
        """

        check_content_length(parser_context)

        return super(LimitedFormParser, self).parse(stream, media_type, parser_context)
