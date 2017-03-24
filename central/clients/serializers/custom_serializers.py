from rest_framework import serializers
import json


class ObjectField(serializers.Field):
    """
        Custom field that serializes the value to a python object
        from JSON if it is a string, or leave it as is if it was already parsed.
    """

    default_error_messages = {
        'invalid': 'Value must be valid JSON.'
    }

    def __init__(self, *args, **kwargs):
        super(ObjectField, self).__init__(*args, **kwargs)

    def to_internal_value(self, data):

        if isinstance(data, (str, unicode)):
            try:
                return json.loads(data)
            except (TypeError, ValueError):
                self.fail('invalid')

        return data

    def to_representation(self, value):
        return value
