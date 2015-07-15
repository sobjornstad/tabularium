# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d
import json

class DuplicateError(Exception):
    def __init__(self, what):
        "Argument /what/: 'source name', 'source abbreviation'"
        self.msg = "That %s is already used." % what
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

        Types:
        name: str
        volval: int tuple (lower valid, upper valid)
        pageval: int tuple (lower valid, upper valid)
        nearrange: int
        abbrev: str
        stype: int; see consts.py sourceTypes
        """

        if sourceExists(name):
            raise DuplicateError('source name')
        if abbrevUsed(abbrev):
            raise DuplicateError('source abbreviation')

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

    def nearbySpread(self, num):
        return (num - self._nearrange, num + self._nearrange)
    def isValidVol(self, num):
        return self._volval[0] <= num <= self._volval[1]
    def isValidPage(self, num):
        return self._pageval[0] <= num <= self._pageval[1]

    def setName(self, name):
        self._name = name
        self.dump()
    def setValidVol(self, tup):
        assert isinstance(tup, tuple) # in case we forget
        self._volval = tup
        self.dump()
    def setValidPage(self, tup):
        assert isinstance(tup, tuple)
        self._pageval = tup
        self.dump()
    def setNearbyRange(self, r):
        self._nearrange = r
        self.dump()
    def setAbbrev(self, abb):
        self._abbrev = abb
        self.dump()
    def setStype(self, stype):
        self._stype = stype
        self.dump()

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
