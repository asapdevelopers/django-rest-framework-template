from rest_framework.renderers import JSONRenderer
from datetime import datetime, time, timedelta, date

from decimal import Decimal
import json
from uuid import UUID
from django.db.models.query import QuerySet
from django.utils import six, timezone
from django.utils.encoding import force_text
from django.utils.functional import Promise


class JSONEncoder(json.JSONEncoder):
    '''
        Slightly faster version compared to the drf one.
    '''

    def default(self, obj):

        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return str(obj.total_seconds())
        elif isinstance(obj, Decimal):
            # Serializers will coerce decimals to strings by default.
            return float(obj)
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, Promise):
            return force_text(obj)
        elif isinstance(obj, QuerySet):
            return tuple(obj)
        elif hasattr(obj, 'tolist'):
            # Numpy arrays and array scalars.
            return obj.tolist()
        elif hasattr(obj, '__getitem__'):
            try:
                return dict(obj)
            except:
                pass
        elif hasattr(obj, '__iter__'):
            return tuple(item for item in obj)
        return super(JSONEncoder, self).default(obj)


class FasterJSONRenderer(JSONRenderer):
    encoder_class = JSONEncoder
