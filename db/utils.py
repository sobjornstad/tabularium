"""
utils.py - miscellaneous helper functions
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
from typing import List, Optional, Sequence, Tuple, Union

import db.database as d


def serializeDate(obj: Optional[datetime.date]) -> Optional[str]:
    """
    Convert a datetime.date object into an ISO string for database storage.
    Both input and output are nullable.
    """
    if obj is None:
        return None
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError(
            f"Object of type {type(obj)} with value of {repr(obj)} is not serializable")


def deserializeDate(dateStr: str) -> datetime.date:
    """
    Change a serialized string back into a datetime.date. Or if None was stored,
    return None.
    """
    if dateStr is None:
        return None

    try:
        yearStr, monthStr, dayStr = dateStr.split('-')
        year, month, day = int(yearStr), int(monthStr), int(dayStr)
    except ValueError as e:
        raise ValueError( "Invalid date '{dateStr}' serialized to database!") from e

    return datetime.date(year, month, day)


def minMaxOccurrenceDates() -> Tuple[datetime.date, datetime.date]:
    """
    Return the earliest and latest Dates used for "entered" or "modified"
    dates for any occurrence.
    """
    d.cursor.execute('SELECT MIN(dEdited) FROM occurrences')
    minEdit = d.cursor.fetchall()[0][0]
    d.cursor.execute('SELECT MIN(dAdded) FROM occurrences')
    minAdd = d.cursor.fetchall()[0][0]
    if minEdit is None:
        minEdit = serializeDate(datetime.date.today())
    if minAdd is None:
        minAdd = serializeDate(datetime.date.today())
    early = minEdit if minEdit < minAdd else minAdd

    d.cursor.execute('SELECT MAX(dEdited) FROM occurrences')
    maxEdit = d.cursor.fetchall()[0][0]
    d.cursor.execute('SELECT MAX(dAdded) FROM occurrences')
    maxAdd = d.cursor.fetchall()[0][0]
    if maxEdit is None:
        maxEdit = serializeDate(datetime.date.today())
    if maxAdd is None:
        maxAdd = serializeDate(datetime.date.today())
    late = maxEdit if maxEdit > maxAdd else maxAdd

    return deserializeDate(early), deserializeDate(late)


# Based on:
# http://code.activestate.com/recipes/135435-sort-a-string-using-numeric-order/
# pylint: disable=invalid-name
def generate_index(sourceStr: str) -> Sequence[Union[str, int]]:
    """
    Split a string into alpha and numeric elements, used as an index for
    sorting.
    """
    # the index is built progressively using the _append function
    index: List[Union[str, int]] = []
    def _append(fragment, alist=index): # pylint: disable=dangerous-default-value
        if fragment.isdigit():
            fragment = int(fragment)
        alist.append(fragment)

    # initialize loop
    prev_isdigit = sourceStr[0].isdigit()
    current_fragment = ''
    # group a string into digit and non-digit parts
    for char in sourceStr:
        curr_isdigit = char.isdigit()
        if curr_isdigit == prev_isdigit:
            current_fragment += char
        else:
            _append(current_fragment)
            current_fragment = char
            prev_isdigit = curr_isdigit
    _append(current_fragment)
    return tuple(index)
