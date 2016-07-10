
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
import db.database as d

def dateSerializer(obj):
    """
    Convert a datetime.date object into an ISO string for database storage.
    """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    elif obj is None:
        return None
    else:
        raise TypeError('Object of type %s with value of %s is not ' \
                'serializable' % (type(obj), repr(obj)))

def dateDeserializer(yyyymmdd):
    """
    Change a serialized string back into a datetime.date. Or if None was stored,
    return None.
    """
    try:
        y, m, d = yyyymmdd.split('-')
        y, m, d = int(y), int(m), int(d)
    except AttributeError:
        if yyyymmdd == None:
            return None
    except ValueError:
        raise
        assert False, "Invalid date serialized to database!"
    return datetime.date(y, m, d)

def minMaxDatesOccurrenceEnteredModified():
    """
    Return the earliest and latest Dates used for "entered" or "modified"
    dates for any occurrence.
    """
    d.cursor.execute('SELECT MIN(dEdited) FROM occurrences')
    minEdit = d.cursor.fetchall()[0][0]
    d.cursor.execute('SELECT MIN(dAdded) FROM occurrences')
    minAdd = d.cursor.fetchall()[0][0]
    early = minEdit if minEdit < minAdd else minAdd

    d.cursor.execute('SELECT MAX(dEdited) FROM occurrences')
    maxEdit = d.cursor.fetchall()[0][0]
    d.cursor.execute('SELECT MAX(dAdded) FROM occurrences')
    maxAdd = d.cursor.fetchall()[0][0]
    late = maxEdit if maxEdit > maxAdd else maxAdd

    return dateDeserializer(early), dateDeserializer(late)

# I copied this function from somewhere on the Web, but unfortunately I
# neglected to keep track of where I got it from...
def generate_index(str):
    """
    Splits a string into alpha and numeric elements, which
    is used as an index for sorting"
    """
    #
    # the index is built progressively
    # using the _append function
    #
    index = []
    def _append(fragment, alist=index):
        if fragment.isdigit(): fragment = int(fragment)
        alist.append(fragment)

    # initialize loop
    prev_isdigit = str[0].isdigit()
    current_fragment = ''
    # group a string into digit and non-digit parts
    for char in str:
        curr_isdigit = char.isdigit()
        if curr_isdigit == prev_isdigit:
            current_fragment += char
        else:
            _append(current_fragment)
            current_fragment = char
            prev_isdigit = curr_isdigit
    _append(current_fragment)
    return tuple(index)
