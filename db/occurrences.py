"""
occurrences.py - places where the information described by an entry is found
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, overload

from db.database import d
import db.entries
import db.volumes
import db.sources
from db.utils import serializeDate, deserializeDate, generate_index

class InvalidUOFError(Exception):
    "The UOF provided could not be parsed."
    def __init__(self, text="Invalid UOF.") -> None:
        super().__init__()
        self.text = text

    def __str__(self):
        return self.text


class DuplicateError(Exception):
    "An occurrence the same as the one we tried to create already exists."
    def __init__(self, text: str = "That occurrence already exists.") -> None:
        super().__init__()
        self.text = text


    def __str__(self):
        return self.text

class NonexistentSourceError(Exception):
    "A source that isn't in the database was referenced."
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def __str__(self):
        return self.text

class NonexistentVolumeError(Exception):
    "A volume that isn't in the database was referenced."
    def __init__(self, sourceName: str, volName: str) -> None:
        super().__init__()
        self.volName = volName
        self.sourceName = sourceName

    def __str__(self):
        return f"The volume {self.volName} in source {self.sourceName} does not exist."


class InvalidReferenceError(Exception):
    "The reference provided doesn't meet the validation defined for the source."
    @overload
    def __init__(self, what: Union[Literal['page'], Literal['volume']], value: int,
                 source: db.sources.Source) -> None: ...
    @overload
    def __init__(self, what: Literal['page range']) -> None: ...
    def __init__(
            self,
            what: Union[Literal['page'], Literal['volume'], Literal['page range']],
            value: int = None,
            source: db.sources.Source = None) -> None:
        super().__init__()
        self.what = what
        self.value = value
        self.source = source

    def __str__(self) -> str:
        if self.what == 'page range':
            return "The second number in a range must be larger than the first."

        assert self.source, \
            "A source must be provided for reference errors on pages or volumes."
        if self.what == 'page':
            validation = self.source.pageVal
        elif self.what == 'volume':
            validation = self.source.pageVal

        return (f"The {self.what} {self.value} does not meet the validation parameters "
                f"for {self.source.name}, which state that {self.what}s "
                f"must be between {validation[0]} and {validation[1]}.")


class ExtensionError(Exception):
    "Attempt to extend or retract an occurrence that isn't numeric."


class ReferenceType(Enum):
    "The type of reference being made by an occurrence."
    NUM = 0
    RANGE = 1
    REDIRECT = 2


# pylint: disable=too-many-instance-attributes
class Occurrence:
    """
    Represents one reference target of an entry.
    """
    _instanceCache: Dict[int, Occurrence] = {}

    def __init__(self, oid: int, eid: int, vid: int, ref: str, reftype: ReferenceType,
                 dateEdited: str, dateAdded: str) -> None:
        self._oid = oid
        self._eid = eid
        self._vid = vid

        # lazy-loaded from _eid / _vid
        self._entry: Optional[db.entries.Entry] = None
        self._volume: Optional[db.volumes.Volume] = None

        self._ref = ref
        self._reftype = ReferenceType(reftype)
        self._dateEdited = deserializeDate(dateEdited)
        self._dateAdded = deserializeDate(dateAdded)

    @classmethod
    def byOid(cls, oid: int) -> Occurrence:
        "Retrieve an occurrence from the cache, or from the database if not cached."
        if oid not in cls._instanceCache:
            query = '''SELECT eid, vid, ref, type, dEdited, dAdded
                        FROM occurrences
                        WHERE oid=?'''
            d().cursor.execute(query, (oid,))
            eid, vid, ref, reftype, dateEdited, dateAdded = d().cursor.fetchall()[0]
            cls._instanceCache[oid] = Occurrence(oid, eid, vid, ref, reftype,
                                                 dateEdited, dateAdded)
        return cls._instanceCache[oid]

    @classmethod
    def makeNew(cls, entry: db.entries.Entry, volume: db.volumes.Volume,
                ref: str, occType: ReferenceType) -> Occurrence:
        """
        Create and return a new occurrence in the given entry and volume,
        adding it to the database along the way.

        Raise a DuplicateError if the occurrence already exists.
        """
        dAdded = serializeDate(datetime.date.today())
        dEdited = dAdded
        eid = entry.eid
        vid = volume.vid

        # check for dupes
        _raiseDupeIfExists(eid, vid, ref, occType)

        # create
        q = '''INSERT INTO occurrences
               (oid, eid, vid, ref, type, dEdited, dAdded)
               VALUES (null, ?,?,?,?,?,?)'''
        d().cursor.execute(q, (eid, vid, ref, occType.value, dEdited, dAdded))
        d().checkAutosave()
        oid = d().cursor.lastrowid
        assert oid is not None, "Insertion of occurrence failed."
        return cls.byOid(oid)

    @classmethod
    def invalidateCache(cls) -> None:
        """
        Wipe the cache of occurrences. Required when changing databases.
        """
        cls._instanceCache.clear()

    @classmethod
    def evictFromCache(cls, oid: int) -> None:
        if oid in cls._instanceCache:
            del cls._instanceCache[oid]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Occurrence):
            return NotImplemented
        return self._oid == other._oid

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        """
        We sort occurrences essentially by their __str__ representation, but we
        normalize a few things to avoid weird sorting surprises (e.g., we
        include the volume number even if single-volume). Further, if two
        occurrences have the same source, volume, and reference, they will be
        further sorted in order of their entries (this is nice for, say, the
        simplification view).
        """
        def getOccSortKey(occ):
            # pylint: disable=consider-using-f-string
            return "%s/%s/%s/%s" % (
                occ.volume.source.abbrev.casefold(),
                occ.volume.num, occ.ref, occ.entry.sortKey.casefold())

        if hasattr(other, 'volume') and hasattr(other, 'ref'):
            # Although this is a mixed-type list,
            # each corresponding element is always of the same type,
            # so comparison is well-defined here.
            return (generate_index(getOccSortKey(self)) < # type: ignore
                    generate_index(getOccSortKey(other)))
        return NotImplemented

    def __str__(self):
        return self.getUOFRepresentation(displayFormatting=True)

    def __repr__(self):
        return '<' + self.__str__() + '>'

    # TODO: More error-checking right in here?
    @property
    def entry(self) -> db.entries.Entry:
        if self._entry is None:
            self._entry = db.entries.Entry.byEid(self._eid)
        return self._entry
    @entry.setter
    def entry(self, entry: db.entries.Entry):
        "NOTE: Can raise DuplicateError, caller must handle this."
        _raiseDupeIfExists(entry.eid, self.volume.vid,
                           self._ref, self._reftype)
        self._entry = entry
        self.flush()

    @property
    def volume(self) -> db.volumes.Volume:
        if self._volume is None:
            self._volume = db.volumes.Volume(self._vid)
        return self._volume
    @volume.setter
    def volume(self, volume: db.volumes.Volume):
        self._volume = volume
        self.flush()

    @property
    def ref(self) -> str:
        return self._ref
    @ref.setter
    def ref(self, ref: str):
        if ref == self._ref:
            return

        #NOTE: This code is duplicated in the UOF parser.
        # That needs to be refactored, but autoflush
        # makes it a challenge; we should change that.
        source = self.volume.source
        if self.isRefType(ReferenceType.NUM):
            refnum = int(ref)
            if not self.volume.source.isValidPage(refnum):
                raise InvalidReferenceError('page', refnum, source)
        elif self.isRefType(ReferenceType.RANGE):
            first, second = [int(i) for i in ref.split('-')]
            if first >= second:
                raise InvalidReferenceError('page range')
            for i in (first, second):
                if not source.isValidPage(i):
                    raise InvalidReferenceError('page', i, source)
        elif self.isRefType(ReferenceType.REDIRECT):
            # We don't check if redirects are valid, because we might want
            # to add them in an order where one is temporarily invalid.
            pass
        else:
            assert False, "unreachable code reached -- invalid refType"

        self._ref = ref
        self.flush()

    @property
    def reftype(self) -> ReferenceType:
        return self._reftype
    @reftype.setter
    def reftype(self, reftype: ReferenceType):
        if reftype != self._reftype:
            self._reftype = reftype
            self.flush()

    @property
    def oid(self):
        return self._oid

    @property
    def dateAdded(self) -> datetime.date:
        return self._dateAdded

    @property
    def dateEdited(self) -> datetime.date:
        return self._dateEdited


    def isRefType(self, reftype: ReferenceType):
        return self._reftype == reftype

    def getStartPage(self) -> Optional[str]:
        """
        For ranges: get the first page.
        For single numbers: get the page number.
        For redirects: return None.
        """
        if self._reftype == ReferenceType.NUM:
            return self._ref
        elif self._reftype == ReferenceType.RANGE:
            return self._ref.split('-')[0]
        else:
            return None

    def getEndPage(self) -> Optional[str]:
        """
        For ranges: get the last page.
        For single numbers: get the page number.
        For redirects: return None.
        """
        if self._reftype == ReferenceType.NUM:
            return self._ref
        elif self._reftype == ReferenceType.RANGE:
            return self._ref.split('-')[1]
        else:
            return None

    def flush(self) -> None:
        "Write changes to this object to the database."
        dEdited = datetime.date.today()
        query = '''UPDATE occurrences
                   SET eid=?, vid=?, ref=?, type=?, dEdited=?, dAdded=?
                   WHERE oid=?'''
        d().cursor.execute(query, (self.entry.eid, self.volume.vid,
                self._ref, self._reftype.value, serializeDate(dEdited),
                serializeDate(self._dateAdded), self._oid))
        d().checkAutosave()

    def delete(self):
        print("deleting occurrence: ", self)
        d().cursor.execute('DELETE FROM occurrences WHERE oid=?', (self._oid,))
        self.evictFromCache(self._oid)
        d().checkAutosave()

    def extend(self, amount: int = 1):
        """
        Expand the range (or create a range from a page) by the number of pages
        specified in /amount/. If amount is positive, the upper bound will be
        increased; if amount is negative, the lower bound will be decreased.
        Under no circumstances can an occurrence be extended beyond the page
        validation specified in its source.
        """
        assert amount != 0, "Amount argument to extend() must be nonzero"

        if self.isRefType(ReferenceType.NUM):
            oldRefType = self.reftype
            self.reftype = ReferenceType.RANGE
            # Yeah, this is why auto-flush is a bad idea!
            try:
                self.ref = f"{self.ref}-{int(self.ref) + amount}"
            except Exception:
                self.reftype = oldRefType
                raise

        elif self.isRefType(ReferenceType.RANGE):
            oldRefType = self.reftype
            sp = int(self.getStartPage() or 0) # never null, as Optional only returned
            ep = int(self.getEndPage() or 0)   # from redirects
            if sp == ep + amount:
                self.reftype = ReferenceType.NUM
                try:
                    self.ref = str(sp)
                except Exception:
                    self.reftype = oldRefType
                    raise
            else:
                self.ref = f"{sp}-{ep + amount}"

        elif self.isRefType(ReferenceType.REDIRECT):
            raise ExtensionError(
                "You cannot extend or retract a redirect, "
                "as it has no page numbers to adjust. Try this operation on "
                "a page or range reference.")

    def getUOFRepresentation(self, displayFormatting=False):
        """
        Get a string representation of this occurrence. This will be in strict
        UOF, or if displayFormatting is True, will have a slightly friendlier
        representation for references.

        Results from this function can be strung together with | and remain
        valid UOF, but cannot necessarily be combined cleanly in other ways.
        """
        if self.isRefType(ReferenceType.NUM) or self.isRefType(ReferenceType.RANGE):
            source = self.volume.source
            if source.isSingleVol():
                return f"{source.abbrev} {self.ref}"
            else:
                return f"{source.abbrev} {self.volume.num}.{self.ref}"
        elif self.isRefType(ReferenceType.REDIRECT):
            source = self.volume.source
            vol = self.volume.num
            if source.isSingleVol():
                return (('%s: see "%s"' if displayFormatting else '%s.see %s')
                        % (source.abbrev, self._ref))
            else:
                return (('%s %s: see "%s"' if displayFormatting
                         else '%s%s.see %s')
                        % (source.abbrev, vol, self._ref))
        else:
            assert False, f"invalid reftype '{self.reftype}' in occurrence"

    def getOccsOfEntry(self) -> List[Occurrence]:
        """
        Return a list of all occurrences belonging to this entry (including
        self).
        """
        q = 'SELECT oid FROM occurrences WHERE eid=?'
        d().cursor.execute(q, (self.entry.eid,))
        return [Occurrence.byOid(oidTuple[0]) for oidTuple in d().cursor.fetchall()]

    def getNearby(self) -> Optional[List[db.entries.Entry]]:
        """
        Find all occurrences that are in the same volume and within some range
        of pages/indices of it, excepting self, and return their entries. The
        range is determined by the source's options.

        Note that nearby is capable of finding things that are nearby ranges,
        but is not currently always capable of finding ranges themselves in
        nearby queries. (SQL BETWEEN does successfully find the entry when one
        of the top or bottom range numbers is actually in the string.)

        Return:
            A list of Entry objects : on success.
            An empty list : If the current occurrence is only nearby to itself.
            None : if the current occurrence is a redirect and thus has no
                logical result for this operation
        """

        if self.reftype not in (ReferenceType.NUM, ReferenceType.RANGE):
            return None

        # Notice that the ranges can go outside volume validation, but this
        # doesn't do any harm, as the numbers aren't used beyond this SELECT.
        page = self._ref
        nearRange = self.volume.source.nearbyRange
        if self.reftype == ReferenceType.RANGE:
            bottom, top = parseRange(page)
            pageStart = bottom - nearRange
            pageEnd = top + nearRange
        else:
            pageStart, pageEnd = self.volume.source.nearbySpread(int(page))

        q = """SELECT DISTINCT entries.eid
                          FROM entries
                    INNER JOIN occurrences
                            ON occurrences.eid = entries.eid
                         WHERE vid = ?
                           AND (type = 0 OR type = 1)
                           AND CAST(ref as integer) BETWEEN ? AND ?
                           AND oid != ?
                      ORDER BY LOWER(sortkey)"""
        d().cursor.execute(q, (self.volume.vid, pageStart,
                               pageEnd, self._oid))
        entries = [db.entries.Entry.byEid(i[0]) for i in d().cursor.fetchall()]
        return entries


def allOccurrences():
    """
    Return a list of all occurrences in the database.
    """
    d().cursor.execute('SELECT oid FROM occurrences')
    return [Occurrence.byOid(i[0]) for i in d().cursor.fetchall()]


def brokenRedirects():
    """
    Return a list of all occurrences which are redirects and whose ref does not
    match the name of any entry currently in the database.

    I benchmarked this one and surprisingly IN is faster than EXISTS here.
    """
    d().cursor.execute('''SELECT oid FROM occurrences
                           WHERE type=?
                             AND ref NOT IN (SELECT name FROM entries)''',
                         (ReferenceType.REDIRECT.value,))
    return [Occurrence.byOid(i[0]) for i in d().cursor.fetchall()]


def fetchForEntry(entry: db.entries.Entry) -> List[Occurrence]:
    """
    Return a list of all Occurrences for a given Entry.
    """
    eid = entry.eid
    d().cursor.execute('SELECT oid FROM occurrences WHERE eid=?', (eid,))
    return [Occurrence.byOid(i[0]) for i in d().cursor.fetchall()]


def fetchForEntryFiltered(entry: db.entries.Entry,
                          enteredDateStr: str = None,
                          modifiedDateStr: str = None,
                          source: Optional[db.sources.Source] = None,
                          volumeRange: Optional[Tuple[int, int]] = None,
                          ref: str = None
                         ) -> List[Occurrence]:
    """
    Return a list of all Occurrences for a given Entry that additionally match
    some criteria.

    enteredDate  : tuple of start/end YYYY-MM-DD date strings
    modifiedDate : tuple of start/end YYYY-MM-DD date strings
    source : Source the occurrence must be in
    volume : tuple of inclusive int volume numbers the occurrence must be in
    """
    queryHead = 'SELECT oid FROM occurrences WHERE eid=?'
    filterQuery, filterParams = occurrenceFilterString(
        enteredDateStr, modifiedDateStr, source, volumeRange, ref)
    if filterQuery:
        d().cursor.execute(queryHead + ' AND ' + filterQuery,
                         [str(entry.eid)] + filterParams)
    else:
        d().cursor.execute(queryHead, (str(entry.eid),))
    return [Occurrence.byOid(i[0]) for i in d().cursor.fetchall()]

def occurrenceFilterString(enteredDateStr: str = None,
                           modifiedDateStr: str = None,
                           source: Optional[db.sources.Source] = None,
                           volumeRange: Optional[Tuple[int, int]] = None,
                           ref: str = None,
                          ) -> Tuple[str, List[Any]]:
    """
    Return a slice of SQL query string and a list of parameters that filter
    occurrences by the provided criteria. This can be used to specifically
    select occurrences or in a JOIN to select entries with existing
    occurrences.
    """
    query = []
    params = []
    if enteredDateStr:
        query.append(' AND occurrences.dAdded>=? AND occurrences.dAdded<=?')
        assert len(enteredDateStr) == 2
        assert len(enteredDateStr[0]) == len(enteredDateStr[1]) == 10
        assert (len(enteredDateStr[0].split('-')) ==
                len(enteredDateStr[1].split('-')) == 3)
        params.append(enteredDateStr[0])
        params.append(enteredDateStr[1])
    if modifiedDateStr:
        query.append(' AND occurrences.dEdited>=? AND occurrences.dEdited<=?')
        assert len(modifiedDateStr) == 2
        assert len(modifiedDateStr[0]) == len(modifiedDateStr[1]) == 10
        assert (len(modifiedDateStr[0].split('-')) ==
                len(modifiedDateStr[1].split('-')) == 3)
        params.append(modifiedDateStr[0])
        params.append(modifiedDateStr[1])
    if source and volumeRange:
        query.append(''' AND vid IN (
                            SELECT vid FROM volumes
                            WHERE volumes.sid = ? AND volumes.num BETWEEN ? AND ?
                         )''')
        params.extend([source.sid, str(volumeRange[0]), str(volumeRange[1]+1)])
        # NOTE: With a large number of volumes, an EXISTS approach may be faster.
        # I don't notice a difference presently, but might be worth checking later
        #query.append(''' AND EXISTS(
        #    SELECT 1 FROM volumes
        #    WHERE occurrences.vid = volumes.vid
        #      AND volumes.sid = ?
        #      AND volumes.num BETWEEN ? AND ?)
        #''')
    if source and not volumeRange:
        query.append(" AND vid IN (SELECT vid FROM volumes WHERE volumes.sid = ?)")
        params.append(source.sid)
    if ref:
        query.append(' AND ref = ?')
        params.append(ref)

    #TODO: Commented out because it's causing issues when starting Tabularium
    #when vol/source were both selected before. As we improve the startup
    #sequence I think this will cease to be a problem, and we can add it back.
    #if (not source) and volume:
        #assert False, "Volume without source is not a valid search"

    queryStr = ''.join(query)[5:] # to remove the initial AND
    return queryStr, params

def parseRange(val: str) -> Tuple[int, int]:
    """
    Return a tuple of bottom, top integers for a range (a string consisting of
    two ints separated by a hyphen). Caller is responsible for making sure the
    string is a range.
    """
    stringSplits = val.split('-')
    assert len(stringSplits) == 2, "More than one hyphen in range!"
    return int(stringSplits[0]), int(stringSplits[1])


def previewUofString(s: str) -> List[str]:
    """
    Get a friendly display of the occurrences this string will create in
    expanded UOF, or raise a validation exception if the string is invalid UOF.
    """
    uofRets = parseUnifiedFormat(s)
    resultsPreview: List[str] = []
    for source, vol, ref, refType in uofRets:
        if refType == ReferenceType.REDIRECT:
            ref = "see " + ref
        if source.isSingleVol():
            resultsPreview.append(f"{source.abbrev} {ref}")
        else:
            resultsPreview.append(f"{source.abbrev} {vol.num}.{ref}")
    return resultsPreview

def makeOccurrencesFromString(s: str,
                              entry: db.entries.Entry) -> Tuple[List[Occurrence], int]:
    """
    Try to create occurrences from a UOF string.

    Arguments:
        s - the UOF string to parse
        entry - the entry to add the occurrences to

    Return:
        A tuple:
            [0] A list of Occurrence objects that were created.
            [1] The number of duplicates specified by /s/ that were skipped.

    Raises:
        All exceptions raised by parseUnifiedFormat() will bubble up to the
        caller so it can provide an appropriate error message.
    """
    uofRets = parseUnifiedFormat(s)
    occs = []
    numDupes = 0
    for _, vol, ref, refType in uofRets:
        try:
            occs.append(Occurrence.makeNew(entry, vol, ref, refType))
        except DuplicateError:
            numDupes += 1
    return occs, numDupes

UofParserReturn = Tuple[db.sources.Source, db.volumes.Volume, str, ReferenceType]

#TODO:
# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=consider-using-f-string
def parseUnifiedFormat(s: str) -> List[UofParserReturn]:
    r"""
    Parse a string /s/ in Unified Occurrence Format (UOF).

    Arguments:
        s - any string, hopefully one in UOF

    Return:
        A list of tuples (Source, Volume, ref, refType). Along with an Entry,
        this is sufficient to uniquely identify an Occurrence, and it can be
        used to create one when appropriate.

    Raises:
        InvalidUOFError - If the string is not in UOF.
        NonexistentSourceError - If the part of the string specifying a source
            does not correspond to any source abbreviation or full name in the
            database.
        NonexistentVolumeError - If the part of the string specifying a volume
            does not correspond to an existing volume in the source given.
        InvalidReferenceError - If the volume or reference/page number provided
            in the string falls outside of the permitted volume/page validation
            parameters for this source type.

    Documentation on UOF is included below.

    UOF
    ----------
    A simple occurrence in UOF consists of the *source*, *volume* (if
    applicable), and *page* (or index number). Some examples of valid simple
    occurrences in UOF:

    CB1.56
    CB 1.56
    CB: 1.56
    CB:1 . 56
    RT 2378 (if RT is single-volume)
    RT 1.2378
    The Invisible Man 58
    The 160th Book: 45

    Rules:
    - The general format looks like `SOURCE:VOLNUMBER.PAGENUMBER`.
    - Spaces before and after the colon and period are optional.
    - The volume number and point may be omitted if the source is single-volume
      (or you can write in volume 1, but that's generally silly).
    - The colon may be omitted entirely.
    - If the source is not a valid source abbreviation, the parser will take it
      as a full source name; if you happen to have a source with the same name
      as the abbreviation of a different source, the abbreviation takes
      precedence.

    Multiple occurrences can be entered at once:
    CB: 1.56; 78
    CB 1.56;78
    CB 1.56 | CB 5.78 | CB 12.56
    CB 1.56; 78 | CB 12.56
    RT 2378 | The Invisible Man 56; 78
    The 160th Book: 45 | TB2.162

    Rules:
    - To enter multiple page numbers within the same source and volume,
      separate them with a semicolon.
    - To enter a literal semicolon (say, in the name of an entry you're
      redirecting to), escape it with a backslash: 'see first\; second'.
    - To enter occurrences for multiple sources and volumes, place a
      pipe (|) character between the references. (Spaces around the pipe are
      optional.)

    Finally, you may want to enter a range or a redirect:
    CB 15.45-56
    CB 15.45–6
    CB 15.45--56
    CB 15. see Other Entry
    RT: see Other Entry
    RT: 25; see Other Entry
    RT see Other. Entry.

    Rules:
    - Ranges are specified with '-', '--', or '–' (literal en-dash). There can
      be spaces at the sides of the dash, but not between the dashes of a
      double dash. A "collapsed" range, where you leave out the first digit(s)
      in the second half because they're identical to the first digit(s) in the
      first half, is also valid.
    - Redirects are specified with the keyword 'see' followed by a space and
      the entry to redirect to.
    ----------
    """
    # Step 1: Recurse for each pipe-separated section, if any.
    # This step is effectively skipped in the second-level calls.
    uniqueSections = [i.strip() for i in s.split('|')]
    if len(uniqueSections) > 1:
        occurrences: List[UofParserReturn] = []
        for i in uniqueSections:
            occurrences = occurrences + parseUnifiedFormat(i)
        return occurrences

    # Step 2: Find the source and separate it from the references.
    s = s.strip()
    for j in db.sources.allSources():
        # NOTE: in the unlikely case that a source has the same name as the
        # abbreviation of a different source, the abbreviation is prioritized.
        # TODO: The above comment is incorrect, and we need to find a better
        # of checking this, unfortunately, because it would be really nice if
        # that worked correctly.
        # TODO: This could break if a redirect happens to contain the same text
        # as the source name/abbrev: it should only replace the first occurrence.
        if s.startswith(j.abbrev):
            source = j
            refPart = s.replace(j.abbrev, '').strip()
            break
        elif s.startswith(j.name):
            source = j
            refPart = s.replace(j.name, '').strip()
            break
    else:
        raise NonexistentSourceError(
            "The provided UOF %s does not begin with a valid source name or "
            "abbreviation." % s)
    if refPart.startswith(':'):
        refPart = refPart[1:].strip()

    # Step 3: Separate volume and reference.
    if '.' not in refPart:
        # single-volume source
        if source.isSingleVol():
            volnum = 1
            reference = refPart.strip()
        else:
            raise InvalidUOFError(
                "The source %s that you specified has multiple volumes, so "
                "you need to say which volume you want to add to, like "
                '"%s 2.12".' % (source.name, source.name))
    else:
        # multi-volume source
        volnum, _, reference = [k.strip() for k in refPart.partition('.')]
        try:
            volnum = int(volnum)
        except ValueError as e:
            # actually a single-volume source where a redirect contained '.'?
            if source.isSingleVol():
                volnum = 1
                reference = refPart.strip()
            else:
                raise InvalidUOFError(
                    'It looks like you specified the volume "%s", but '
                    "volume numbers have to be integers." % volnum) from e

    # Step 4: Split the reference on semicolons to see if there are multiple
    # targets. Pipe is used as a temporary value because it is illegal in
    # input here.
    reference = reference.replace('\\;', '|')
    refStrings = [i.strip().replace('|', ';') for i in reference.split(';')]

    # Step 5: Parse each target, determine its type, and create a list
    # of targets.
    parsedRefs = []
    for refnum in refStrings:
        if refnum.startswith('see '):
            # redirect
            reftype = ReferenceType.REDIRECT
            refnum = refnum[4:].strip() # remove the 'see '
        elif '--' in refnum or '–' in refnum or '-' in refnum:
            # range
            reftype = ReferenceType.RANGE
            normalizedRefnum = refnum.replace('–', '-').replace('--', '-')
            #TODO: I think the following should be wrapped in a try, it could
            #potentially wack out with illegal UOF?
            first, second = normalizedRefnum.split('-')
            try:
                first, second = int(first.strip()), int(second.strip())
            except ValueError as e:
                raise InvalidUOFError(
                    "The provided UOF appears to contain a range of "
                    "references (%s), but one or both sides of the range "
                    "are not integers." % refnum) from e
            uncollapsed = rangeUncollapse(first, second)
            if uncollapsed is None:
                raise InvalidReferenceError('page range')
            refnum = "%i-%i" % uncollapsed
        else:
            # number
            reftype = ReferenceType.NUM
            try:
                refnum = int(refnum)
            except ValueError as e:
                raise InvalidUOFError(
                    "The provided UOF appears to contain a reference to a "
                    "single page or location (%s), but that reference is not "
                    "an integer. (If you were trying to enter a redirect, use "
                    'the keyword "see" before the entry to redirect to.)'
                    % refnum) from e

        # validate the provided reference
        volume = db.volumes.byNumAndSource(source, volnum)
        if volume is None:
            raise NonexistentVolumeError(source.name, volnum)

        #NOTE: This code is duplicated on the code for setting the ref property
        # on the Occurrence class. That needs to be refactored, but autoflush
        # makes it a challenge; we should change that.
        if reftype == ReferenceType.NUM:
            if not source.isValidPage(refnum):
                raise InvalidReferenceError('page', refnum, source)
        elif reftype == ReferenceType.RANGE:
            first, second = [int(i) for i in refnum.split('-')]
            if first >= second:
                raise InvalidReferenceError('page range')
            for i in (first, second):
                if not source.isValidPage(i):
                    raise InvalidReferenceError('page', i, source)
        elif reftype == ReferenceType.REDIRECT:
            # We don't check if redirects are valid, because we might want
            # to add them in an order where one is temporarily invalid.
            pass
        else:
            assert False, "unreachable code reached -- invalid refType"
        parsedRefs.append((source, volume, refnum, reftype))

    return parsedRefs

def rangeUncollapse(first: int, second: int) -> Optional[Tuple[int, int]]:
    """
    "Uncollapse" a range that looks like:
       56-7   => 56-57
       720-57 => 720-757
       107-8  => 107-108
    and so on. The algorithm works for a number of any length (as long as you
    don't run out of memory, I suppose)

    I believe the test for whether this is not actually a valid collapsed range
    covers all possible cases in which it's possible to determine empirically
    from the numbers that the user didn't intend it to be a collapsed range,
    but I have not proven it.

    Return a tuple of the new ranges, or None if the page range is in the wrong order
    (with a higher number as the start than the end).
    """
    firstStr, secondStr = str(first), str(second)
    while int(firstStr) > int(secondStr):
        place = len(secondStr)
        if place == len(firstStr): # same number of places and still wrong order
            return None
        secondStr = firstStr[-(place+1)] + secondStr

    return int(firstStr), int(secondStr)


def _raiseDupeIfExists(eid: int, vid: int, ref: str, reftype: ReferenceType) -> None:
    """
    Raise DuplicateError if an occurrence with the given eid, vid, ref, and
    type exists. Used when creating or changing the entry of an occurrence.
    """
    q = '''SELECT oid FROM occurrences
           WHERE eid=? AND vid=? AND ref=? AND type=?'''
    d().cursor.execute(q, (eid, vid, ref, reftype.value))
    if d().cursor.fetchall():
        raise DuplicateError
