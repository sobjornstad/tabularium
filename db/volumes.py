# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d
import db.consts
import db.sources
import json
import datetime
from db.utils import dateSerializer, dateDeserializer

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
        d.cursor.execute(q, (vid,))
        sid, self._num, self._notes, dopened, dclosed = d.cursor.fetchall()[0]
        self._dopened = dateDeserializer(dopened)
        self._dclosed = dateDeserializer(dclosed)
        self._source = db.sources.Source(sid)
        self._vid = vid

    @classmethod
    def makeNew(cls, source, num, notes, dopened=None, dclosed=None):
        """
        Create a new volume in the db and return a Volume object. If a volume
        in this source with this number already exists, raise DuplicateError.
        If this is a single-volume source, raise SingleVolumeError. If the
        value otherwise falls outside the volval numbers, raise
        ValidationError.

        Dopened and dclosed are optional, as they only make sense for some
        items. If not specified, they will be filled as None and displayed in
        an appropriate manner later.

        source  : Source
        num     : integer volume number
        notes   : str
        dopened : datetime.date
        dclosed : datetime.date
        """

        if source.isSingleVol():
            raise SingleVolumeError(source.getName())
        if not source.isValidVol(num):
            raise ValidationError(source.getName(), source.getVolVal())
        if source.volExists(num):
            raise DuplicateError(source.getName(), num)

        q = '''INSERT INTO volumes (vid, sid, num, notes, dopened, dclosed)
               VALUES (null, ?, ?, ?, ?, ?)'''
        d.cursor.execute(q, (source.getSid(), num, notes,
                             dateSerializer(dopened),
                             dateSerializer(dclosed)))
        d.checkAutosave()
        vid = d.cursor.lastrowid
        return cls(vid)


    def __eq__(self, other):
        return (self._source == other._source and self._num == other._num and
                self._notes == other._notes and self._vid == other._vid)
    def __ne__(self, other):
        return not self.__eq__(other)

    def getVid(self):
        return self._vid
    def getNum(self):
        return self._num
    def getSource(self):
        return self._source
    def getNotes(self):
        return self._notes
    def getDopened(self):
        return self._dopened
    def getDclosed(self):
        return self._dclosed

    def setDopened(self, date):
        if self._dopened != date:
            self._dopened = date
            self.dump()
    def setDclosed(self, date):
        if self._dclosed != date:
            self._dclosed = date
            self.dump()
    def setNotes(self, notes):
        if self._notes != notes:
            self._notes = notes
            self.dump()

    def delete(self):
        """
        Can't be implemented until occurrences and orphaned-entry deletion are.
        """
        pass

    def dump(self):
        q = """UPDATE volumes
               SET sid=?, num=?, notes=?, dopened=?, dclosed=?
               WHERE vid=?"""
        d.cursor.execute(q, (self._source.getSid(), self._num, self._notes,
                         dateSerializer(self._dopened),
                         dateSerializer(self._dclosed), self._vid))
        d.checkAutosave()
