# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d
import db.consts
import db.volumes
import db.occurrences
from db.utils import dateSerializer
import json

class DuplicateError(Exception):
    def __init__(self, what):
        "Argument /what/: 'name', 'abbreviation'"
        self.msg = "That %s is already used for a different source." % what
    def __str__(self):
        return self.msg
class InvalidRangeError(Exception):
    def __init__(self, what):
        "Argument /what/: 'reference', 'volume' limit"
        self.msg = "That %s range ends lower than it begins." % what
    def __str__(self):
        return self.msg
class DiaryExistsError(Exception):
    def __init__(self, conflicting):
        self.conflicts = conflicting
        pass
    def __str__(self):
        return "You can only have one diary source. Yours is named '%s'." % \
                self.conflicts
class TrouncesError(Exception):
    def __init__(self, toWhat, whichThing, number1, number2=None):
        self.toWhat = toWhat
        self.whichThing = whichThing
        self.number1 = number1
        self.number2 = number2
    def __str__(self):
        if self.whichThing == 'volume':
            return "Changing the %s max and min to (%i, %i) would make %i " \
                   "volume%s and %i occurrence%s invalid." % (
                           self.whichThing, self.toWhat[0], self.toWhat[1],
                           self.number1, "s" if self.number1 != 1 else "",
                           self.number2, "s" if self.number2 != 1 else "")
        elif self.whichThing == 'page':
            return "Changing the page max and min to (%i, %i) would make %i " \
                   "occurrence%s invalid." % (self.toWhat[0], self.toWhat[1],
                           self.number1, "s" if self.number1 != 1 else "")

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
        volval    : int tuple inclusive (lower valid, upper valid) [*]
        pageval   : int tuple inclusive (lower valid, upper valid)
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
        if stype == db.consts.sourceTypes['diary']:
            d.cursor.execute("SELECT name FROM sources WHERE stype = ?",
                    (db.consts.sourceTypes['diary'],))
            existing = d.cursor.fetchall()
            if existing:
                raise DiaryExistsError(existing[0][0])

        q = """INSERT INTO sources
               (sid, name, volval, pageval, nearrange, abbrev, stype)
               VALUES (null, ?, ?, ?, ?, ?, ?)"""
        d.cursor.execute(q, (name, json.dumps(volval), json.dumps(pageval),
               nearrange, abbrev, stype))
        d.checkAutosave()
        sid = d.cursor.lastrowid
        sourceObj = cls(sid)

        # before returning, add a dummy volume if this is a single-vol source
        if volval == (1,1):
            db.volumes.Volume.makeNew(sourceObj, 1, "", creatingDummy=True)
        return sourceObj

    def __eq__(self, other):
        return (self._sid == other._sid and self._name == other._name and
                self._volval == other._volval and
                self._pageval == other._pageval and
                self._nearrange == other._nearrange and
                self._abbrev == other._abbrev and self._stype == other._stype)
    def __ne__(self, other):
        return not self.__eq__(other)

    def getSid(self):
        return self._sid
    def getName(self):
        return self._name
    def getNearbyRange(self):
        return self._nearrange
    def getAbbrev(self):
        return self._abbrev
    def getStype(self):
        return self._stype
    def getVolVal(self):
        return self._volval
    def getPageVal(self):
        return self._pageval
    def isSingleVol(self):
        return self._volval == (1,1)

    def nearbySpread(self, num):
        return (num - self._nearrange, num + self._nearrange)
    def isValidVol(self, num):
        return self._volval[0] <= num <= self._volval[1]
    def isValidPage(self, num):
        return self._pageval[0] <= num <= self._pageval[1]
    def volExists(self, num):
        q = 'SELECT vid FROM volumes WHERE sid=? AND num=?'
        d.cursor.execute(q, (self._sid, num))
        return True if d.cursor.fetchall() else False

    def setName(self, name):
        if self._name != name:
            if sourceExists(name):
                raise DuplicateError('name')
            self._name = name
            self.dump()
    def setValidVol(self, tup, overrideTrounce=False):
        """
        Reset the volume validation. 

        Arguments:
            tup - the new volval, (min, max)
            overrideTrounce - see note under TrouncesOccurrencesError
        
        Raises:
            TrouncesOccurrencesError - if changing the validation to the new
                values would make some occurrences invalid. After presenting
                appropriate confirmation to the user, this function may be
                run again with overrideTrounce set to True, which will cause
                those occurrences to be deleted instead.

        """
        assert isinstance(tup, tuple) # in case we forget
        if tup != self._volval:
            if tup[0] > tup[1]:
                raise InvalidRangeError('volume')

            q = '''SELECT vid FROM volumes WHERE sid=?
                   AND (num < ? OR num > ?)'''
            d.cursor.execute(q, (self._sid, tup[0], tup[1]))
            volsAffected = d.cursor.fetchall()
            if volsAffected:
                if overrideTrounce:
                    vols = [db.volumes.Volume(volTuple[0])
                            for volTuple in volsAffected]
                    for vol in vols:
                        vol.delete()
                else:
                    q = '''SELECT oid FROM occurrences
                           WHERE vid IN (SELECT vid FROM volumes
                                         WHERE sid=?
                                         AND (num < ? OR num > ?))'''
                    vals = (self._sid, tup[0], tup[1])
                    d.cursor.execute(q, vals)
                    occsAffected = d.cursor.fetchall()
                    raise TrouncesError(tup, 'volume', len(volsAffected),
                                        len(occsAffected))
            else:
                self._volval = tup
                self.dump()
    def setValidPage(self, tup, overrideTrounce=False):
        """
        Same deal as for setValidVol.
        """
        assert isinstance(tup, tuple)
        if tup[0] > tup[1]:
            raise InvalidRangeError('page')

        # Get occs in this source that are not redirects and are outside the
        # range. (The cast even works for ranges, though I'm not entirely sure
        # how! SQL is awesome.)
        q = '''SELECT oid FROM occurrences
               WHERE vid IN (SELECT vid FROM volumes
                             WHERE sid=?)
               AND (CAST(ref as integer) < ?
                    OR CAST(ref as integer) > ?)
               AND type IN (0,1)'''
        vals = (self._sid, tup[0], tup[1])
        d.cursor.execute(q, vals)
        occsAffected = d.cursor.fetchall()

        if occsAffected:
            if overrideTrounce:
                occs = [db.occurrences.Occurrence(occTuple[0])
                        for occTuple in occsAffected]
                for occ in occs:
                    occ.delete()
            else:
                raise TrouncesError(tup, 'page', len(occsAffected))



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


def byName(name):
    q = 'SELECT sid FROM sources WHERE name = ?'
    d.cursor.execute(q, (name,))
    return Source(d.cursor.fetchall()[0][0])

def byAbbrev(abbrev):
    q = 'SELECT sid FROM sources WHERE abbrev = ?'
    d.cursor.execute(q, (abbrev,))
    return Source(d.cursor.fetchall()[0][0])

def sourceExists(name):
    q = 'SELECT sid FROM sources WHERE name = ?'
    d.cursor.execute(q, (name,))
    return True if d.cursor.fetchall() else False

def abbrevUsed(name):
    q = 'SELECT sid FROM sources WHERE abbrev = ?'
    d.cursor.execute(q, (name,))
    return True if d.cursor.fetchall() else False

def allSources(includeSingleVolSources=True):
    d.cursor.execute('SELECT sid FROM sources')
    sources = [Source(sid[0]) for sid in d.cursor.fetchall()]
    if not includeSingleVolSources:
        sources = [source for source in sources if source.getVolVal() != (1,1)]
    return sources

def getDiary():
    """
    Find the diary source, if it exists.

    Return:
        The Source that is the diary, or None if no source has the diary type.
    """
    d.cursor.execute('SELECT sid FROM sources WHERE stype=?',
                     (db.consts.sourceTypes['diary'],))
    fetch = d.cursor.fetchall()
    if fetch:
        return Source(fetch[0][0])
    else:
        return None
