# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime

def dateSerializer(obj):
    """
    Convert a datetime.date object into an ISO string for database storage.
    """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError, 'Object of type %s with value of %s is not JSON ' \
                'serializable' % (type(obj), repr(obj))

def dateDeserializer(yyyymmdd):
    """
    Change a serialized string back into a datetime.date.
    """
    try:
        y, m, d = yyyymmdd.split('-')
        y, m, d = int(y), int(m), int(d)
    except ValueError:
        raise
        assert False, "Invalid date serialized to database!"
    return datetime.date(y, m, d)
