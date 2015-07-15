# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d
import json

class DuplicateError(Exception):
    def __init__(self, what):
        "Argument /what/: 'name', 'abbreviation'"
        self.msg = "That source %s is already used for a different source." % what
    def __str__(self):
        return self.msg
class InvalidRangeError(Exception):
    def __init__(self, what):
        "Argument /what/: 'reference', 'volume' limit"
        self.msg = "That %s range ends lower than it begins." % what
    def __str__(self):
        return self.msg


class Source(object):
    def __init__(self, sid):
        d.cursor.execute('SELECT name, volval, pageval, nearrange, abbrev, '
                'stype FROM sources WHERE sid=?', (sid,))
        self._name, self._volval, self._pageval, self._nearrange, \
                self._abbrev, self._stype = d.cursor.fetchall()[0]
        self._volval = tuple(json.loads(self._volval))
        self._pageval = tuple(json.loads(self._pageval))
        self._sid = sid

    @classmethod
    def makeNew(cls, name, volval, pageval, nearrange, abbrev, stype):
        """
        Create a new source in the db and return a Source object. If a source
        by this name or with this abbreviation already exists, raise
        DuplicateError and leave db untouched.

        TYPES:
        name      : str
        volval    : int tuple (lower valid, upper valid) [*]
        pageval   : int tuple (lower valid, upper valid)
        nearrange : int
        abbrev    : str
        stype     : int; see consts.py's sourceTypes{}

        [*] A volval of (1,1) indicates this is a single-volume source.
            See self.isSingleVol().
        """

        if sourceExists(name):
            raise DuplicateError('name')
        if abbrevUsed(abbrev):
            raise DuplicateError('abbreviation')
        if volval[0] > volval[1]:
            raise InvalidRangeError('volume')
        if pageval[0] > pageval[1]:
            raise InvalidRangeError('page')

        q = """INSERT INTO sources
               (sid, name, volval, pageval, nearrange, abbrev, stype)
               VALUES (null, ?, ?, ?, ?, ?, ?)"""
        d.cursor.execute(q, (name, json.dumps(volval), json.dumps(pageval),
               nearrange, abbrev, stype))
        d.checkAutosave()
        sid = d.cursor.lastrowid
        return cls(sid)


    def __eq__(self, other):
        return (self._sid == other._sid and self._name == other._name and
                self._volval == other._volval and
                self._pageval == other._pageval and
                self._nearrange == other._nearrange and
                self._abbrev == other._abbrev and self._stype == other._stype)
    def __ne__(self, other):
        return not self.__eq__(other)

    def getName(self):
        return self._name
    def getNearbyRange(self):
        return self._nearrange
    def getAbbrev(self):
        return self._abbrev
    def getStype(self):
        return self._stype
    def getValVol(self):
        return self._volval
    def getValPage(self):
        return self._pageval
    def isSingleVol(self):
        return self._volval == (1,1)

    def nearbySpread(self, num):
        return (num - self._nearrange, num + self._nearrange)
    def isValidVol(self, num):
        return self._volval[0] <= num <= self._volval[1]
    def isValidPage(self, num):
        return self._pageval[0] <= num <= self._pageval[1]

    #TODO: Make sure that we can't trounce on existing valid occurrences by
    # changing valid vols/pages. But occurrences need to be working first!
    def setName(self, name):
        if self._name != name:
            if sourceExists(name):
                raise DuplicateError('name')
            self._name = name
            self.dump()
    def setValidVol(self, tup):
        assert isinstance(tup, tuple) # in case we forget
        if tup[0] > tup[1]:
            raise InvalidRangeError('volume')
        self._volval = tup
        self.dump()
    def setValidPage(self, tup):
        assert isinstance(tup, tuple)
        if tup[0] > tup[1]:
            raise InvalidRangeError('page')
        self._pageval = tup
        self.dump()
    def setNearbyRange(self, r):
        self._nearrange = r
        self.dump()
    def setAbbrev(self, abb):
        if self._abbrev != abb:
            if abbrevUsed(abb):
                raise DuplicateError('abbreviation')
            self._abbrev = abb
            self.dump()
    def setStype(self, stype):
        self._stype = stype
        self.dump()

    def delete(self):
        """
        PSEUDOCODE IMPLEMENTATION: can't do this yet, pending (#TODO) a feature
        to zap any entries with no occurrences, and the changeover of
        occurrences from notebooks to volumes.

        display "here be dragons" warning message
        queries = (
            "DELETE * FROM volumes WHERE sid=?"
            "DELETE * FROM occurrences WHERE sid=?"
            "DELETE * FROM sources WHERE sid=?"
            )
        execute queries
        run orphaned entry cleanup
        """
        pass

    def dump(self):
        q = """UPDATE sources SET name=?, volval=?, pageval=?, nearrange=?,
               abbrev=?, stype=?
               WHERE sid=?"""
        d.cursor.execute(q, (self._name, json.dumps(self._volval),
                         json.dumps(self._pageval), self._nearrange,
                         self._abbrev, self._stype, self._sid))
        d.checkAutosave()


def sourceExists(name):
    q = 'SELECT sid FROM sources WHERE name = ?'
    d.cursor.execute(q, (name,))
    return True if d.cursor.fetchall() else False

def abbrevUsed(name):
    q = 'SELECT sid FROM sources WHERE abbrev = ?'
    d.cursor.execute(q, (name,))
    return True if d.cursor.fetchall() else False

def allSources():
    d.cursor.execute('SELECT sid FROM sources')
    ss = [Source(sid[0]) for sid in d.cursor.fetchall()]
    return ss
