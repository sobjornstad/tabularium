# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime

from db.consts import refTypes
import db.database as d
import db.entries
import db.volumes
import db.sources
from db.utils import dateSerializer, dateDeserializer, generate_index

class InvalidUOFError(Exception):
    def __init__(self, text="Invalid UOF."):
        self.text = text
    def __str__(self):
        return self.text
class DuplicateError(Exception):
    def __init__(self, text="That occurrence already exists."):
        self.text = text
    def __str__(self):
        return self.text
class NonexistentSourceError(Exception):
    def __init__(self, text):
        self.text = text
    def __str__(self):
        return self.text
class NonexistentVolumeError(Exception):
    def __init__(self, sourceName, volName):
        self.volName = volName
        self.sourceName = sourceName
    def __str__(self):
        return "The volume %s in source %s does not exist." % (
                self.volName, self.sourceName)
class InvalidReferenceError(Exception):
    def __init__(self, what, value=None, source=None):
        self.what = what
        self.value = value
        self.source = source
    def __str__(self):
        if self.what == 'page':
            validation = self.source.pageVal
        elif self.what == 'volume':
            validation = self.source.pageVal
        elif self.what == 'page range':
            return "The second number in a range must be larger than the first."

        val = "The %s %s does not meet the validation parameters for %s, " \
              "which state that %ss must be between %i and %i." % (
                      self.what, self.value, self.source.name, self.what,
                      validation[0], validation[1])
        return val

class Occurrence(object):
    """
    Represents one reference target of an entry.
    """
    def __init__(self, oid):
        query = '''SELECT eid, vid, ref, type, dEdited, dAdded
                   FROM occurrences WHERE oid=?'''
        d.cursor.execute(query, (oid,))
        eid, vid, self._ref, self._reftype, self._dateEdited, \
            self._dateAdded = d.cursor.fetchall()[0]
        self._entry = db.entries.Entry(eid)
        self._volume = db.volumes.Volume(vid)
        self._dateEdited = dateDeserializer(self._dateEdited)
        self._dateAdded = dateDeserializer(self._dateAdded)
        self._oid = oid

    @classmethod
    def makeNew(cls, entry, volume, ref, type):
        dAdded = dateSerializer(datetime.date.today())
        dEdited = dAdded
        eid = entry.eid
        vid = volume.vid

        # check for dupes
        _raiseDupeIfExists(eid, vid, ref, type)

        # create
        q = '''INSERT INTO occurrences
               (oid, eid, vid, ref, type, dEdited, dAdded)
               VALUES (null, ?,?,?,?,?,?)'''
        d.cursor.execute(q, (eid, vid, ref, type, dEdited, dAdded))
        d.checkAutosave()
        oid = d.cursor.lastrowid
        return cls(oid)

    def __eq__(self, other):
        return self._oid == other._oid
    def __ne__(self, other):
        return not self.__eq__(other)
    def __lt__(self, other):
        """
        We sort occurrences essentially by their __str__ representation, but we
        normalize a few things to avoid weird sorting surprises (e.g., we
        include the volume number even if single-volume). Further, if two
        occurrences have the same source, volume, and reference, they will be
        further sorted in order of their entries (this is nice for, say, the
        simplification view).
        """
        def getOccSortKey(occ):
            return "%s/%s/%s/%s" % (
                occ._volume.source.abbrev.lower(),
                occ._volume.num, occ._ref, occ._entry.sortKey.lower())
        if hasattr(other, '_volume') and hasattr(other, '_ref'):
            return (generate_index(getOccSortKey(self)) <
                    generate_index(getOccSortKey(other)))

    def __str__(self):
        return self.getUOFRepresentation(displayFormatting=True)
    def __repr__(self):
        return '<' + self.__str__() + '>'

    #TODO: More error-checking right in here?
    @property
    def entry(self):
        return self._entry
    @entry.setter
    def entry(self, entry):
        "NOTE: Can raise DuplicateError, caller must handle this."
        _raiseDupeIfExists(entry.eid, self._volume.vid,
                          self._ref, self._reftype)
        self._entry = entry
        self.flush()

    @property
    def volume(self):
        return self._volume
    @volume.setter
    def volume(self, volume):
        self._volume = volume
        self.flush()

    @property
    def ref(self):
        return self._ref
    @ref.setter
    def ref(self, ref):
        if ref == self._ref:
            return

        #NOTE: This code is duplicated in the UOF parser.
        # That needs to be refactored, but autoflush
        # makes it a challenge; we should change that.
        source = self.volume.source
        if self.isRefType('num'):
            refnum = int(ref)
            if not self.volume.source.isValidPage(refnum):
                raise InvalidReferenceError('page', refnum, source)
        elif self.isRefType('range'):
            first, second = [int(i) for i in ref.split('-')]
            if first >= second:
                raise InvalidReferenceError('page range')
            for i in (first, second):
                if not source.isValidPage(i):
                    raise InvalidReferenceError('page', i, source)
        elif self.isRefType('redir'):
            # We don't check if redirects are valid, because we might want
            # to add them in an order where one is temporarily invalid.
            pass
        else:
            assert False, "unreachable code reached -- invalid refType"

        self._ref = ref
        self.flush()

    @property
    def reftype(self):
        return self._reftype
    @reftype.setter
    def reftype(self, reftype):
        if reftype != self._reftype:
            self._reftype = reftype
            self.flush()

    @property
    def oid(self):
        return self._oid

    @property
    def dateAdded(self):
        return self._dateAdded

    @property
    def dateEdited(self):
        return self._dateEdited


    def isRefType(self, reftype):
        return self._reftype == refTypes[reftype]
    def getStartPage(self):
        if self._reftype == refTypes['num']:
            return self._ref
        elif self._reftype == refTypes['range']:
            return self._ref.split('-')[0]
        else:
            return None
    def getEndPage(self):
        if self._reftype == refTypes['num']:
            return self._ref
        elif self._reftype == refTypes['range']:
            return self._ref.split('-')[1]
        else:
            return None

    def flush(self):
        dEdited = datetime.date.today()
        query = '''UPDATE occurrences
                   SET eid=?, vid=?, ref=?, type=?, dEdited=?, dAdded=?
                   WHERE oid=?'''
        d.cursor.execute(query, (self._entry.eid, self._volume.vid,
                self._ref, self._reftype, dateSerializer(dEdited),
                dateSerializer(self._dateAdded), self._oid))
        d.checkAutosave()

    def delete(self):
        d.cursor.execute('DELETE FROM occurrences WHERE oid=?', (self._oid,))
        d.checkAutosave()

    def extend(self, amount=1):
        """
        Expand the range (or create a range from a page) by the number of pages
        specified in /amount/. If amount is positive, the upper bound will be
        increased; if amount is negative, the lower bound will be decreased.
        Under no circumstances can an occurrence be extended beyond the page
        validation specified in its source.
        """


    def getUOFRepresentation(self, displayFormatting=False):
        """
        Get a string representation of this occurrence. This will be in strict
        UOF, or if displayFormatting is True, will have a slightly friendlier
        representation for references.

        Results from this function can be strung together with | and remain
        valid UOF, but cannot necessarily be combined cleanly in other ways.
        """
        if self.isRefType('num') or self.isRefType('range'):
            source = self._volume.source
            if source.isSingleVol():
                return "%s %s" % (source.abbrev, self._ref)
            else:
                return "%s %s.%s" % (source.abbrev,
                                     self._volume.num,
                                     self._ref)
        elif self.isRefType('redir'):
            source = self._volume.source
            vol = self._volume.num
            if source.isSingleVol():
                return (('%s: see "%s"' if displayFormatting else '%s.see %s')
                        % (source.abbrev, self._ref))
            else:
                return (('%s %s: see "%s"' if displayFormatting
                         else '%s%s.see %s')
                        % (source.abbrev, vol, self._ref))
        else:
            assert False, "invalid reftype in occurrence"

    def getOccsOfEntry(self):
        """
        Return a list of all occurrences belonging to this entry (including
        self).
        """
        q = 'SELECT oid FROM occurrences WHERE eid=?'
        d.cursor.execute(q, (self._entry.eid,))
        return [Occurrence(oidTuple[0]) for oidTuple in d.cursor.fetchall()]

    def getNearby(self):
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

        if self._reftype not in (refTypes['num'], refTypes['range']):
            return None

        # Notice that the ranges can go outside volume validation, but this
        # doesn't do any harm, as the numbers aren't used beyond this SELECT.
        page = self._ref
        nearRange = self.volume.source.nearbyRange
        if self._reftype == refTypes['range']:
            bottom, top = parseRange(page)
            pageStart = bottom - nearRange
            pageEnd = top + nearRange
        else:
            pageStart, pageEnd = self.volume.source.nearbySpread(int(page))

        q = """SELECT DISTINCT entries.eid FROM entries
               INNER JOIN occurrences ON occurrences.eid = entries.eid
               WHERE vid = ?
                     AND (type = 0 OR type = 1)
                     AND CAST(ref as integer) BETWEEN ? AND ?
                     AND oid != ?
               ORDER BY LOWER(sortkey)"""
        d.cursor.execute(q, (self._volume.vid, pageStart,
                             pageEnd, self._oid))
        entries = [db.entries.Entry(i[0]) for i in d.cursor.fetchall()]
        return entries

def allOccurrences():
    """
    Return a list of all occurrences in the database.
    """
    d.cursor.execute('SELECT oid FROM occurrences')
    return [Occurrence(i[0]) for i in d.cursor.fetchall()]

def fetchForEntry(entry):
    """
    Return a list of all Occurrences for a given Entry.
    """
    eid = entry.eid
    d.cursor.execute('SELECT oid FROM occurrences WHERE eid=?', (eid,))
    return [Occurrence(i[0]) for i in d.cursor.fetchall()]

def fetchForEntryFiltered(entry, enteredDate=None, modifiedDate=None,
                          source=None, volume=None):
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
        enteredDate, modifiedDate, source, volume)
    if filterQuery:
        d.cursor.execute(queryHead + ' AND ' + filterQuery,
                         [str(entry.eid)] + filterParams)
    else:
        d.cursor.execute(queryHead, (str(entry.eid),))
    return [Occurrence(i[0]) for i in d.cursor.fetchall()]

def occurrenceFilterString(enteredDate=None, modifiedDate=None,
                           source=None, volume=None):
    """
    Return a slice of SQL query string and a list of parameters that filter
    occurrences by the provided criteria. This can be used to specifically
    select occurrences or in a JOIN to select entries with existing
    occurrences.
    """
    query = []
    params = []
    if enteredDate:
        query.append(' AND occurrences.dAdded>=? AND occurrences.dAdded<=?')
        assert len(enteredDate) == 2
        assert len(enteredDate[0]) == len(enteredDate[1]) == 10
        assert (len(enteredDate[0].split('-')) ==
                len(enteredDate[1].split('-')) == 3)
        params.append(enteredDate[0])
        params.append(enteredDate[1])
    if modifiedDate:
        query.append(' AND occurrences.dEdited>=? AND occurrences.dEdited<=?')
        assert len(modifiedDate) == 2
        assert len(modifiedDate[0]) == len(modifiedDate[1]) == 10
        assert (len(modifiedDate[0].split('-')) ==
                len(modifiedDate[1].split('-')) == 3)
        params.append(modifiedDate[0])
        params.append(modifiedDate[1])
    if source and volume:
        vids = []
        for volnum in range(volume[0], volume[1]+1):
            vol = db.volumes.byNumAndSource(source, volnum)
            if vol is not None:
                vids.append(vol.vid)
        query.append(' AND vid IN (%s)'
                     % ','.join('?' * len(vids)))
        params.extend(vids)
    if source and not volume:
        vols = [i.vid for i in db.volumes.volumesInSource(source)]
        query.append(' AND vid IN (%s)' % ','.join('?' * len(vols)))
        for i in vols:
            params.append(i)

    #TODO: Commented out because it's causing issues when starting Tabularium
    #when vol/source were both selected before. As we improve the startup
    #sequence I think this will cease to be a problem, and we can add it back.
    #if (not source) and volume:
        #assert False, "Volume without source is not a valid search"

    queryStr = ''.join(query)[5:] # to remove the initial AND
    return queryStr, params

def parseRange(val):
    """
    Return a tuple of bottom, top integers for a range (a string consisting of
    two ints separated by a hyphen). Caller is responsible for making sure the
    string is a range.
    """
    return tuple(int(i) for i in val.split('-'))

def makeOccurrencesFromString(s, entry):
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
    for source, vol, ref, refType in uofRets:
        try:
            occs.append(Occurrence.makeNew(entry, vol, ref, refType))
        except DuplicateError:
            numDupes += 1
    return occs, numDupes

def parseUnifiedFormat(s):
    """
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
        occurrences = []
        for i in uniqueSections:
            occurrences = occurrences + parseUnifiedFormat(i)
        return occurrences

    # Step 2: Find the source and separate it from the references.
    s = s.strip()
    for i in db.sources.allSources():
        # NOTE: in the unlikely case that a source has the same name as the
        # abbreviation of a different source, the abbreviation is prioritized.
        # TODO: The above comment is incorrect, and we need to find a better
        # of checking this, unfortunately, because it would be really nice if
        # that worked correctly.
        # TODO: This could break if a redirect happens to contain the same text
        # as the source name/abbrev: it should only replace the first occurrence.
        if s.startswith(i.abbrev):
            source = i
            refPart = s.replace(i.abbrev, '').strip()
            break
        elif s.startswith(i.name):
            source = i
            refPart = s.replace(i.name, '').strip()
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
        volnum, _, reference = [i.strip() for i in refPart.partition('.')]
        try:
            volnum = int(volnum)
        except ValueError:
            # actually a single-volume source where a redirect contained '.'?
            if source.isSingleVol():
                volnum = 1
                reference = refPart.strip()
            else:
                raise InvalidUOFError(
                    'It looks like you specified the volume "%s", but '
                    "volume numbers have to be integers." % volnum)

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
            reftype = refTypes['redir']
            refnum = refnum[4:].strip() # remove the 'see '
        elif '--' in refnum or '–' in refnum or '-' in refnum:
            # range
            reftype = refTypes['range']
            normalizedRefnum = refnum.replace('–', '-').replace('--', '-')
            #TODO: I think the following should be wrapped in a try, it could
            #potentially wack out with illegal UOF?
            first, second = normalizedRefnum.split('-')
            try:
                first, second = int(first.strip()), int(second.strip())
            except ValueError:
                raise InvalidUOFError(
                    "The provided UOF appears to contain a range of "
                    "references (%s), but one or both sides of the range "
                    "are not integers." % refnum)
            uncollapsed = rangeUncollapse(first, second)
            if uncollapsed is None:
                raise InvalidReferenceError('page range')
            refnum = "%i-%i" % uncollapsed
        else:
            # number
            reftype = refTypes['num']
            try:
                refnum = int(refnum)
            except ValueError:
                raise InvalidUOFError(
                    "The provided UOF appears to contain a reference to a "
                    "single page or location (%s), but that reference is not "
                    "an integer. (If you were trying to enter a redirect, use "
                    'the keyword "see" before the entry to redirect to.)'
                    % refnum)

        # validate the provided reference
        volume = db.volumes.byNumAndSource(source, volnum)
        if volume is None:
            raise NonexistentVolumeError(source.name, volnum)

        #NOTE: This code is duplicated on the code for setting the ref property
        # on the Occurrence class. That needs to be refactored, but autoflush
        # makes it a challenge; we should change that.
        if reftype == refTypes['num']:
            if not source.isValidPage(refnum):
                raise InvalidReferenceError('page', refnum, source)
        elif reftype == refTypes['range']:
            first, second = [int(i) for i in refnum.split('-')]
            if first >= second:
                raise InvalidReferenceError('page range')
            for i in (first, second):
                if not source.isValidPage(i):
                    raise InvalidReferenceError('page', i, source)
        elif reftype == refTypes['redir']:
            # We don't check if redirects are valid, because we might want
            # to add them in an order where one is temporarily invalid.
            pass
        else:
            assert False, "unreachable code reached -- invalid refType"
        parsedRefs.append((source, volume, refnum, reftype))

    return parsedRefs

def rangeUncollapse(first, second):
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
    """
    first, second = str(first), str(second)
    while int(first) > int(second):
        place = len(second)
        if place == len(first): # same number of places and still wrong order
            return None
        second = first[-(place+1)] + second

    return int(first), int(second)


def _raiseDupeIfExists(eid, vid, ref, type):
    """
    Raise DuplicateError if an occurrence with the given eid, vid, ref, and
    type exists. Used when creating or changing the entry of an occurrence.
    """
    q = '''SELECT oid FROM occurrences
           WHERE eid=? AND vid=? AND ref=? AND type=?'''
    d.cursor.execute(q, (eid, vid, ref, type))
    if d.cursor.fetchall():
        raise DuplicateError
