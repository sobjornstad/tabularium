# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from contextlib import contextmanager
import json
from typing import List

from db.database import d
import db.consts
import db.volumes
import db.occurrences

class DuplicateError(Exception):
    def __init__(self, what):
        "Argument /what/: 'name', 'abbreviation'"
        self.msg = "That %s is already used for a different source." % what
    def __str__(self):
        return self.msg
class InvalidNameError(Exception):
    def __init__(self, name, what):
        self.msg = "The %s %s is invalid: a source %s cannot contain the " \
                   "character '|'." % (what, name, what)
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
        d().cursor.execute('''SELECT name, volval, pageval, nearrange, abbrev, stype
                              FROM sources
                              WHERE sid=?''', (sid,))
        self._name, self._volVal, self._pageVal, self._nearbyRange, \
                self._abbrev, self._sourceType = d().cursor.fetchall()[0]
        self._volVal = tuple(json.loads(self._volVal))
        self._pageVal = tuple(json.loads(self._pageVal))
        self._sid = sid
        # Turn the following option off only temporarily using the
        # bypassTrounceWarnings context manager, for safety.
        self.trounceWarning = True

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
        if '|' in name:
            raise InvalidNameError(name, 'name')
        if '|' in abbrev:
            raise InvalidNameError(abbrev, 'abbreviation')
        if stype == db.consts.sourceTypes['diary']:
            d().cursor.execute("SELECT name FROM sources WHERE stype = ?",
                    (db.consts.sourceTypes['diary'],))
            existing = d().cursor.fetchall()
            if existing:
                raise DiaryExistsError(existing[0][0])

        q = """INSERT INTO sources
               (sid, name, volval, pageval, nearrange, abbrev, stype)
               VALUES (null, ?, ?, ?, ?, ?, ?)"""
        d().cursor.execute(q, (name, json.dumps(volval), json.dumps(pageval),
               nearrange, abbrev, stype))
        d().checkAutosave()
        sid = d().cursor.lastrowid
        sourceObj = cls(sid)

        # before returning, add a dummy volume if this is a single-vol source
        if volval == (1,1):
            db.volumes.Volume.makeNew(sourceObj, 1, "", creatingDummy=True)
        return sourceObj

    def __eq__(self, other):
        return self._sid == other._sid
    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def sid(self):
        return self._sid

    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, name):
        if self._name != name:
            if sourceExists(name):
                raise DuplicateError('name')
            self._name = name
            self._flush()

    @property
    def nearbyRange(self):
        return self._nearbyRange
    @nearbyRange.setter
    def nearbyRange(self, r):
        if self._nearbyRange != r:
            self._nearbyRange = r
            self._flush()

    @property
    def abbrev(self):
        return self._abbrev
    @abbrev.setter
    def abbrev(self, abb):
        if self._abbrev != abb:
            if abbrevUsed(abb):
                raise DuplicateError('abbreviation')
            self._abbrev = abb
            self._flush()

    @property
    def sourceType(self):
        return self._sourceType

    @property
    def volVal(self):
        return self._volVal
    @volVal.setter
    def volVal(self, tup):
        """
        Reset the volume validation to a new tuple (min, max).
        
        Raises:
            TrouncesOccurrencesError - if changing the validation to the new
                values would make some occurrences invalid. After presenting
                a warning to the user and getting their consent, you can
                turn this error off and cause an actual change by wrapping in
                the bypassTrounceWarnings context manager.
        """
        assert len(tup) == 2 and isinstance(tup, tuple)
        if tup != self._volVal:
            if tup[0] > tup[1]:
                raise InvalidRangeError('volume')

            q = '''SELECT vid FROM volumes
                    WHERE sid=? AND (num < ? OR num > ?)'''
            d().cursor.execute(q, (self._sid, tup[0], tup[1]))
            volsAffected = d().cursor.fetchall()
            if volsAffected:
                if self.trounceWarning:
                    q = '''SELECT oid FROM occurrences
                           WHERE vid IN (SELECT vid FROM volumes
                                          WHERE sid=?
                                            AND (num < ? OR num > ?))'''
                    vals = (self._sid, tup[0], tup[1])
                    d().cursor.execute(q, vals)
                    occsAffected = d().cursor.fetchall()
                    raise TrouncesError(tup, 'volume', len(volsAffected),
                                        len(occsAffected))
                else:
                    vols = [db.volumes.Volume(volTuple[0])
                            for volTuple in volsAffected]
                    for vol in vols:
                        vol.delete()
            else:
                self._volVal = tup
                self._flush()

    @property
    def pageVal(self):
        return self._pageVal
    @pageVal.setter
    def pageVal(self, tup):
        """
        Same deal as for setValVol.
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
                  AND (CAST(ref as integer) < ? OR CAST(ref as integer) > ?)
                  AND type IN (0,1)'''
        vals = (self._sid, tup[0], tup[1])
        d().cursor.execute(q, vals)
        occsAffected = d().cursor.fetchall()

        if occsAffected:
            if self.trounceWarning:
                raise TrouncesError(tup, 'page', len(occsAffected))
            else:
                occs = [db.occurrences.Occurrence(occTuple[0])
                        for occTuple in occsAffected]
                for occ in occs:
                    occ.delete()

        self._pageVal = tup
        self._flush()


    def isSingleVol(self):
        return self._volVal == (1,1)
    def nearbySpread(self, num):
        return (num - self._nearbyRange, num + self._nearbyRange)
    def isValidVol(self, num):
        return self._volVal[0] <= num <= self._volVal[1]
    def isValidPage(self, num):
        return self._pageVal[0] <= num <= self._pageVal[1]
    def volExists(self, num: int):
        "Check if a volume with the given number exists in this source."
        q = 'SELECT 1 FROM volumes WHERE sid=? AND num=?'
        d().cursor.execute(q, (self.sid, num))
        return bool(d().cursor.fetchall())
    def getNumVolsRepr(self):
        "Get a friendly representation of how many volumes are in this source."
        if self.isSingleVol():
            return "(single-volume)"
        else:
            return len(db.volumes.volumesInSource(self))

    def delete(self):
        """
        Look out -- this method can cause MASSIVE data loss, as it
        unconditionally deletes all volumes, entries, and occurrences that use
        the source as well as the source itself. Never, ever call this method
        without providing an appropriate warning (perhaps with the details from
        deletePreview()).
        """
        d().cursor.execute('SELECT vid FROM volumes WHERE sid=?', (self._sid,))
        volumes = [db.volumes.Volume(volTuple[0])
                   for volTuple in d().cursor.fetchall()]
        for vol in volumes:
            vol.delete()
        d().cursor.execute('DELETE FROM sources WHERE sid=?', (self._sid,))
        d().checkAutosave()

    def deletePreview(self):
        """
        Return a tuple explaining what will be deleted when self is:
            [0] how many volumes
            [1] how many occurrences.

        (Note that entries may also be deleted, but those are difficult to
        count -- they're the ones that may be orphaned by the occurrence
        deletion.)
        """
        volumes = db.volumes.volumesInSource(self)

        vidList = [i.vid for i in volumes]
        bindings = ','.join('?' * len(volumes))
        q = f'SELECT COUNT(oid) FROM occurrences WHERE vid IN ({bindings})'
        d().cursor.execute(q, vidList)
        occCount = d().cursor.fetchall()[0][0]
        return len(volumes), occCount

    def _flush(self):
        q = '''UPDATE sources
                  SET name=?, volval=?, pageval=?, nearrange=?, abbrev=?, stype=?
                WHERE sid=?'''
        d().cursor.execute(q, (
            self._name, json.dumps(self._volVal), json.dumps(self._pageVal),
            self._nearbyRange, self._abbrev, self._sourceType, self._sid
        ))
        d().checkAutosave()


def byName(name):
    q = 'SELECT sid FROM sources WHERE name = ?'
    d().cursor.execute(q, (name,))
    return Source(d().cursor.fetchall()[0][0])

def byAbbrev(abbrev):
    q = 'SELECT sid FROM sources WHERE abbrev = ?'
    d().cursor.execute(q, (abbrev,))
    return Source(d().cursor.fetchall()[0][0])

def sourceExists(name):
    q = 'SELECT sid FROM sources WHERE name = ?'
    d().cursor.execute(q, (name,))
    return True if d().cursor.fetchall() else False

def abbrevUsed(name):
    q = 'SELECT sid FROM sources WHERE abbrev = ?'
    d().cursor.execute(q, (name,))
    return True if d().cursor.fetchall() else False

def allSources(includeSingleVolSources=True) -> List[Source]:
    """
    Return a list of all sources, sorted by name.
    """
    d().cursor.execute('SELECT sid FROM sources ORDER BY LOWER(name)')
    sources = [Source(sid[0]) for sid in d().cursor.fetchall()]
    if not includeSingleVolSources:
        sources = [source for source in sources if source.volVal != (1,1)]
    return sources

def getDiary():
    """
    Find the diary source, if it exists.

    Return:
        The Source that is the diary, or None if no source has the diary type.
    """
    d().cursor.execute('SELECT sid FROM sources WHERE stype=?',
                       (db.consts.sourceTypes['diary'],))
    fetch = d().cursor.fetchall()
    if fetch:
        return Source(fetch[0][0])
    else:
        return None

@contextmanager
def bypassTrounceWarnings(source):
    """
    Turn off warnings that a source modification will result in lots of invalid
    occurrences being wiped out, for the duration of the context manager.
    """
    source.trounceWarning = False
    try:
        yield
    finally:
        source.trounceWarning = True
