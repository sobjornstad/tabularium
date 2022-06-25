# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
import json

from db.database import d
import db.consts
import db.sources
import db.entries
from db.utils import serializeDate, deserializeDate

class DuplicateError(Exception):
    def __init__(self, sourceName, volNum):
        self.msg = "Volume %i of source %s already exists." % (
                volNum, sourceName)
    def __str__(self):
        return self.msg
class SingleVolumeError(Exception):
    def __init__(self, sourceName):
        self.msg = "The source %s does not have multiple volumes." % sourceName
    def __str__(self):
        return self.msg
class ValidationError(Exception):
    def __init__(self, sourceName, volval):
        self.msg = "The source %s only allows volume numbers between " \
                "%i and %i." % (sourceName, volval[0], volval[1])
    def __str__(self):
        return self.msg

class Volume(object):
    def __init__(self, vid):
        q = 'SELECT sid, num, notes, dopened, dclosed FROM volumes WHERE vid=?'
        d().cursor.execute(q, (vid,))
        sid, self._num, self._notes, dopened, dclosed = d().cursor.fetchall()[0]
        self._dateOpened = deserializeDate(dopened)
        self._dateClosed = deserializeDate(dclosed)
        self._source = db.sources.Source(sid)
        self._vid = vid

    @classmethod
    def makeNew(cls, source, num, notes, dopened=None, dclosed=None,
            creatingDummy=False):
        """
        Create a new volume in the db and return a Volume object. If a volume
        in this source with this number already exists, raise DuplicateError.
        If this is a single-volume source, raise SingleVolumeError. If the
        value otherwise falls outside the volval numbers, raise
        ValidationError.

        Dopened and dclosed are optional, as they only make sense for some
        items. If not specified, they will be filled as None and displayed in
        an appropriate manner later.

        If creatingDummy, override SingleVolumeError as long as we're creating
        volume 1. This parameter should be used only by the makeNew class
        method of Source.

        source  : Source
        num     : integer volume number
        notes   : str
        dopened : datetime.date
        dclosed : datetime.date
        """

        if source.isSingleVol() and not (creatingDummy and num == 1):
            raise SingleVolumeError(source.name)
        if not source.isValidVol(num):
            raise ValidationError(source.name, source.volVal)
        if source.volExists(num):
            raise DuplicateError(source.name, num)

        q = '''INSERT INTO volumes (vid, sid, num, notes, dopened, dclosed)
               VALUES (null, ?, ?, ?, ?, ?)'''
        d().cursor.execute(q, (source.sid, num, notes,
                             serializeDate(dopened),
                             serializeDate(dclosed)))
        d().checkAutosave()
        vid = d().cursor.lastrowid
        return cls(vid)


    def __eq__(self, other):
        return self._vid == other._vid
    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def vid(self):
        return self._vid

    @property
    def num(self):
        return self._num
    @num.setter
    def num(self, num):
        if self._num != num:
            if volExists(self._source, num):
                raise DuplicateError(self._source, num)
            self._num = num
            self._flush()

    @property
    def source(self):
        return self._source

    @property
    def notes(self):
        return self._notes
    @notes.setter
    def notes(self, notes):
        if self._notes != notes:
            self._notes = notes
            self._flush()

    @property
    def dateOpened(self):
        return self._dateOpened
    @dateOpened.setter
    def dateOpened(self, date):
        if self._dateOpened != date:
            self._dateOpened = date
            self._flush()

    @property
    def dateClosed(self):
        return self._dateClosed
    @dateClosed.setter
    def dateClosed(self, date):
        if self._dateClosed != date:
            self._dateClosed = date
            self._flush()

    def hasDates(self):
        return (self._dateOpened is not None and self._dateClosed is not None)

    def delete(self):
        d().cursor.execute('DELETE FROM occurrences WHERE vid=?', (self._vid,))
        db.entries.deleteOrphaned()
        d().cursor.execute('DELETE FROM volumes WHERE vid=?', (self._vid,))
        d().checkAutosave()

    def _flush(self):
        q = """UPDATE volumes
               SET sid=?, num=?, notes=?, dopened=?, dclosed=?
               WHERE vid=?"""
        d().cursor.execute(q, (self._source.sid, self._num, self._notes,
                         serializeDate(self._dateOpened),
                         serializeDate(self._dateClosed), self._vid))
        d().checkAutosave()


def allVolumes():
    d().cursor.execute('SELECT vid FROM volumes')
    vs = [Volume(vid[0]) for vid in d().cursor.fetchall()]
    return vs

def volumesInSource(source):
    sid = source.sid
    d().cursor.execute('SELECT vid FROM volumes WHERE sid=?', (sid,))
    return [Volume(vid[0]) for vid in d().cursor.fetchall()]

def byNumAndSource(source, num):
    sid = source.sid
    q = 'SELECT vid FROM volumes WHERE sid=? AND num=?'
    d().cursor.execute(q, (sid, num))
    try:
        return Volume(d().cursor.fetchall()[0][0])
    except IndexError:
        return None

def volExists(source, num):
    sid = source.sid
    q = 'SELECT vid FROM volumes WHERE sid=? AND num=?'
    d().cursor.execute(q, (sid, num))
    return True if d().cursor.fetchall() else False

def findNextDateOpened(source):
    """
    Try to guess, or at least come close to, the date the user would like a new
    volume of a source to be opened on: we'll find when the last one was closed
    and pick the day after that.

    If there are no volumes of that source yet, return the current date.

    Return value as a datetime.date.
    """
    d().cursor.execute('''SELECT dclosed FROM volumes
                        WHERE num=(SELECT MAX(num) FROM volumes)
                        AND sid=?''', (source.sid,))
    try:
        return (deserializeDate(d().cursor.fetchall()[0][0]) +
                datetime.timedelta(days=1))
    except (IndexError, TypeError):
        # unsupported operand types: NoneType and timedelta
        return datetime.date.today()

def findNextOpenVol(source):
    """
    Return the next volume number that is not used for /source/. If the source
    is not multi-volume, return 0. If no volumes currently exist, return 1.
    """
    if source.isSingleVol():
        return 0
    d().cursor.execute('SELECT MAX(num) FROM volumes WHERE sid=?',
                     (source.sid,))
    try:
        return d().cursor.fetchall()[0][0] + 1
    except (IndexError, TypeError):
        # unsupported operand types: NoneType and int
        return 1

def findDateInDiary(date):
    """
    Given a Date, return the diary Volume that was open during that time, or
    None if there is no diary volume or volume open during that date.
    """
    #TODO: Make sure we can't have several diary volumes open at the same time.
    # Actually, this could be a problem with the other notes functions too.
    diary = db.sources.getDiary()
    if diary is None:
        return None

    q = '''SELECT vid FROM volumes
           WHERE sid=(SELECT sid FROM sources WHERE stype=?)
           AND dopened <= ?
           AND dclosed >= ?'''
    date = serializeDate(date)
    vals = (db.consts.sourceTypes['diary'], date, date)
    d().cursor.execute(q, vals)
    fetch = d().cursor.fetchall()
    if len(fetch) > 1:
        assert False, "Multiple diary volumes open at the same time!"
    elif len(fetch) == 1:
        return Volume(fetch[0][0])
    else:
        return None
