# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
import re

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
    def __init__(self, sourceName):
        self.sourceName = sourceName
    def __str__(self):
        return "The abbreviation or source name %s does not exist." % (
                self.sourceName)
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
            validation = self.source.getPageVal()
        elif self.what == 'volume':
            validation = self.source.getVolVal()
        elif self.what == 'page range':
            return "The second number in a range must be larger than the first."

        val = "The %s %s does not meet the validation parameters for %s, " \
              "which state that %ss must be between %i and %i." % (
                      self.what, self.value, self.source.getName(), self.what,
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
        eid, vid, self._ref, self._type, self._de, self._da = \
                d.cursor.fetchall()[0]
        self._entry = db.entries.Entry(eid)
        self._volume = db.volumes.Volume(vid)
        self._da = dateDeserializer(self._da)
        self._de = dateDeserializer(self._de)
        self._oid = oid

    @classmethod
    def makeNew(cls, entry, volume, ref, type):
        dAdded = dateSerializer(datetime.date.today())
        dEdited = dAdded
        eid = entry.getEid()
        vid = volume.getVid()

        # check for dupes
        raiseDupeIfExists(eid, vid, ref, type)

        # create
        q = '''INSERT INTO occurrences
               (oid, eid, vid, ref, type, dEdited, dAdded)
               VALUES (null, ?,?,?,?,?,?)'''
        d.cursor.execute(q, (eid, vid, ref, type, dEdited, dAdded))
        d.checkAutosave()
        oid = d.cursor.lastrowid
        return cls(oid)

    def __eq__(self, other):
        return (self._entry == other._entry and self._ref == other._ref and
                self._volume == other._volume and self._oid == other._oid and
                self._de == other._de and self._da == other._da and
                self._type == other._type)
    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        if self._type == refTypes['num'] or self._type == refTypes['range']:
            source = self._volume.getSource()
            if source.isSingleVol():
                return "%s %s" % (source.getAbbrev(), self._ref)
            else:
                return "%s %s.%s" % (source.getAbbrev(),
                                     self._volume.getNum(),
                                     self._ref)
        elif self._type == refTypes['redir']:
            source = self._volume.getSource()
            vol = self._volume.getNum()
            if source.isSingleVol():
                return '%s: see "%s"' % (source.getAbbrev(), self._ref)
            else:
                return '%s %s: see "%s"' % (source.getAbbrev(), vol, self._ref)
        else:
            assert False, "invalid reftype in occurrence"

    def __repr__(self):
        return '<' + self.__str__() + '>'

    def __lt__(self, other):
        if hasattr(other, '_volume') and hasattr(other, '_ref'):
            return (generate_index(self.getOccSortKey()) <
                    generate_index(other.getOccSortKey()))

    def getOccSortKey(self):
        """
        Get the sort key for an occurrence, used in __cmp__.

        We sort occurrences essentially by their __str__ representation, but we
        normalize a few things to avoid weird sorting surprises (e.g., we
        include the volume number even if single-volume). Further, if two
        occurrences have the same source, volume, and reference, they will be
        further sorted in order of their entries (this is nice for, say, the
        simplification view).
        """
        return "%s/%s/%s/%s" % (self._volume.getSource().getAbbrev().lower(),
                                self._volume.getNum(), self._ref,
                                self._entry.getName().lower())

    def getEntry(self):
        return self._entry
    def getVolume(self):
        return self._volume
    def getRef(self):
        """
        Fetch the reference in this occurrence, as a tuple of the reference
        and the type code.
        """
        return (self._ref, self._type)
    def getOid(self):
        return self._oid
    def getAddedDate(self):
        return self._da
    def getEditedDate(self):
        return self._de

    def isRefType(self, reftype):
        return self._type == refTypes[reftype]
    def getStartPage(self):
        if self._type == refTypes['num']:
            return self._ref
        elif self._type == refTypes['range']:
            return self._ref.split('-')[0]
        else:
            return None
    def getEndPage(self):
        if self._type == refTypes['num']:
            return self._ref
        elif self._type == refTypes['range']:
            return self._ref.split('-')[1]
        else:
            return None

    #TODO: error-checking
    def setRef(self, ref, type):
        if ref != self._ref or type != self._type:
            self._ref = ref
            self._type = type
            self.dump()
    def setEntry(self, entry):
        "NOTE: Can raise DuplicateError, caller must handle this."
        raiseDupeIfExists(entry.getEid(), self._volume.getVid(),
                          self._ref, self._type)
        self._entry = entry
        self.dump()
    def setVolume(self, volume):
        self._volume = volume
        self.dump()

    def dump(self):
        dEdited = datetime.date.today()

        query = '''UPDATE occurrences
                   SET eid=?, vid=?, ref=?, type=?, dEdited=?, dAdded=?
                   WHERE oid=?'''
        d.cursor.execute(query, (self._entry.getEid(), self._volume.getVid(),
                self._ref, self._type, dateSerializer(dEdited),
                dateSerializer(self._da), self._oid))
        d.checkAutosave()

    def delete(self):
        d.cursor.execute('DELETE FROM occurrences WHERE oid=?', (self._oid,))
        d.checkAutosave()

    def getOccsOfEntry(self):
        """
        Return a list of all occurrences belonging to this entry (including
        self).
        """
        q = 'SELECT oid FROM occurrences WHERE eid=?'
        d.cursor.execute(q, (self._entry.getEid(),))
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

        if self._type not in (refTypes['num'], refTypes['range']):
            return None

        # Notice that the ranges can go outside volume validation, but this
        # doesn't do any harm, as the numbers aren't used beyond this SELECT.
        page = self._ref
        nearRange = self.getVolume().getSource().getNearbyRange()
        if self._type == refTypes['range']:
            bottom, top = parseRange(page)
            pageStart = bottom - nearRange
            pageEnd = top + nearRange
        else:
            pageStart = int(page) - nearRange
            pageEnd = int(page) + nearRange

        q = '''SELECT oid FROM occurrences
               WHERE vid = ? AND (type = 0 OR type = 1)
                   AND CAST(ref as integer) BETWEEN ? AND ?
                   AND oid != ?'''
        d.cursor.execute(q, (self._volume.getVid(), pageStart,
                             pageEnd, self._oid))
        occs = [Occurrence(i[0]) for i in d.cursor.fetchall()]

        # fetch list of entries nearby
        entries = list(set(i.getEntry() for i in occs))
        entries.sort(key=lambda i: i._sk)

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
    eid = entry.getEid()
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
                         [str(entry.getEid())] + filterParams)
    else:
        d.cursor.execute(queryHead, (str(entry.getEid()),))
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
                vids.append(vol.getVid())
        query.append(' AND vid IN (%s)'
                     % ','.join('?' * len(vids)))
        params.extend(vids)
    if source and not volume:
        vols = [i.getVid() for i in db.volumes.volumesInSource(source)]
        query.append(' AND vid IN (%s)' % ','.join('?' * len(vols)))
        for i in vols:
            params.append(i)
    if (not source) and volume:
        assert False, "Volume without source is not a valid search"

    queryStr = ''.join(query)[5:] # to remove the initial AND
    return queryStr, params

def parseRange(val):
    """
    Return a tuple of bottom, top integers for a range (a string consisting of
    two ints separated by a hyphen). Caller is responsible for making sure the
    string is a range.
    """
    return tuple(int(i) for i in val.split('-'))

def raiseDupeIfExists(eid, vid, ref, type):
    """
    Raise DuplicateError if an occurrence with the given eid, vid, ref, and
    type exists. Used when creating or changing the entry of an occurrence.
    """
    q = '''SELECT oid FROM occurrences
           WHERE eid=? AND vid=? AND ref=? AND type=?'''
    d.cursor.execute(q, (eid, vid, ref, type))
    if d.cursor.fetchall():
        raise DuplicateError

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
        All exceptions raised by parseUnifiedFormat() are not caught by this
        function and will be received by the caller so it can provide an
        appropriate error message.
    """
    uofRets = parseUnifiedFormat(s)
    occs = []
    numDupes = 0
    for i in uofRets:
        source, vol, ref, refType = i
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

    The rules:
    The general format looks like `SOURCE:VOLNUMBER.PAGENUMBER`.

    - There may be spaces or no spaces before or after the colon and period.
    - The volume number and point may be omitted if the source is single-volume
      (or you can write in volume 1, but that's generally silly).
    - The colon may be omitted entirely so long as the source name does not
      contain any numbers or colons. If there are numbers or colons in the
      source name, the parser will be too confused to tell what you mean (even
      if the volume number has been omitted), and you must use the colon or put
      the reference in braces.
    - If the source is not a valid source abbreviation, the parser will try to
      parse it as a full source name; if there is a conflict, the abbreviation
      takes precedence.
    

    Multiple occurrences can be entered at once:

    CB:{1.56, 5.78}
    CB {1.56,5 .78,}
    CB{1.56}
    CB 1.56 | CB 5.78 | CB 12.56
    CB {1.56, 5.78} | CB 12.56
    RT 2378 | The Invisible Man {56, 78}
    The 160th Book: 45 | TB2.162

    Rules:
    - To enter multiple page numbers within the same source and volume, OR
      multiple volumes and page numbers within the same source, place the page
      or volume and page references in braces, separating them with a comma. A
      trailing comma inside the braces may optionally be used. (Braces are also
      legal with a single occurrence.)
    - To place a literal comma within braces (say, in the name of an entry
      you're redirecting to), escape it with a backslash: '{see Doe\, Jane}'.
    - To enter multiple whole sources, or as a more verbose way of entering
      multiple pages within the same source, place a pipe (|) character between
      the references, with optional (but suggested for readability) spaces on
      either side.

    Finally, you may want to enter a range or a redirect. Examples:
    CB 15.45-56
    CB 15.45–6
    CB 15.45--56
    CB 15. see Other Entry
    RT: see Other Entry
    RT see Other. Entry.

    Rules:
    
    - Ranges are specified with '-', '--', or '–' (literal en-dash). There can
      be spaces at the sides, but not between the dashes of the double dash. A
      "collapsed" range, where you leave out the first digit(s) in the second
      half because they're identical to the first digit(s) in the first half, is
      also valid.
    - Redirects are specified with the keyword 'see' followed by a space and
      the entry to redirect to.

    And this is valid UOF, though not a very likely/good way of doing things...
    CB{15.26--7,2    . 18, 4.see    Other Entry} |The 2nd Book of    : 45
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

    # Step 2: Separate the source and reference(s). This is *ugly*.
    source, reference = _splitSourceRef(s)

    # Step 3: Separate the individual references within 'reference' into a list
    #         of references.
    reference = reference.replace('\\,', '<ESCAPEDCOMMA>')
    if reference.startswith('{') and reference.endswith('}'):
        reference = reference[1:-1] # chop out braces
        refs = reference.split(',')
        refs = [i.strip() for i in refs if i] # strip and remove empty strings
    elif '{' in reference:
        if '}' not in reference:
            raise InvalidUOFError()
        outside, inside = re.match(r'(.*){(.*)}', reference).group(1, 2)
        refs = inside.split(',')
        refs = [(outside.strip() + i.strip()) for i in refs if i]
    else:
        # no braces at all, not much to do
        refs = [reference]
    refs = [i.replace('<ESCAPEDCOMMA>', ',') for i in refs]

    # Step 4: Find volume, refnum, and range/redir type from each reference.
    referenceList = []
    for ref in refs:
        refSplit = ref.split('.')
        if len(refSplit) == 1:
            # single-volume source
            volume = 1
            refnum = ref.strip()
        elif len(refSplit) == 2:
            volume = refSplit[0].strip()
            refnum = refSplit[1].strip()
        else:
            if 'see ' in refSplit[1]:
                # This was a "see" entry with a period in it.
                volume = refSplit[0].strip()
                refnum = '.'.join(refSplit[1:]).strip()
            elif 'see ' in refSplit[0]:
                # This was a "see" entry with a period in it, and no volume.
                volume = 1
                refnum = '.'.join(refSplit).strip()
            else:
                raise InvalidUOFError()
        try:
            volume = int(volume)
        except ValueError:
            # Perhaps there are several "sees" and periods in here, and no
            # source? (Dear user: quit screwing with us.)
            if 'see ' in volume:
                # Yep, no volume num was given after all.
                volume = 1
                refnum = '.'.join(refSplit)
            else:
                raise InvalidUOFError()

        # determine entry type and format refnum
        if refnum.startswith('see '):
            # redirect
            reftype = refTypes['redir']
            refnum = re.sub('^see ', '', refnum).strip()
        elif '--' in refnum or '–' in refnum or '-' in refnum:
            # range: normalize delimiter
            reftype = refTypes['range']
            if '--' in refnum:
                refnum = refnum.replace('--', '-')
            elif '–' in refnum:
                refnum = refnum.replace('–', '-')
            # convert both to integers
            first, second = refnum.split('-')
            try:
                first, second = int(first), int(second)
            except ValueError:
                raise InvalidUOFError()
            # "uncollapse" range
            ret = rangeUncollapse(first, second)
            if ret is None:
                # range couldn't be uncollapsed
                raise InvalidReferenceError('page range')
            else:
                first, second = ret
                refnum = "%i-%i" % (first, second)
        else:
            # simple number
            reftype = refTypes['num']
            try:
                refnum = int(refnum)
            except ValueError:
                raise InvalidUOFError()

        referenceList.append((volume, refnum, reftype))

    # Step 5: Fetch source object; raise an error if any references are illegal.
    for i in referenceList:
        if(not db.sources.abbrevUsed(source) and
           not db.sources.sourceExists(source)):
            raise NonexistentSourceError(source)
        else:
            try:
                sourceObj = db.sources.byAbbrev(source)
            except IndexError:
                sourceObj = db.sources.byName(source)
        volume = i[0]
        refnum = i[1]
        reftype = i[2]
        if not sourceObj.isValidVol(volume):
            raise InvalidReferenceError('volume', volume, sourceObj)
        if reftype == refTypes['num']:
            if not sourceObj.isValidPage(refnum):
                raise InvalidReferenceError('page', refnum, sourceObj)
        elif reftype == refTypes['range']:
            first, second = [int(i) for i in refnum.split('-')]
            if first >= second:
                raise InvalidReferenceError('page range')
            for i in (first, second):
                if not sourceObj.isValidPage(i):
                    raise InvalidReferenceError('page', i, sourceObj)
        elif reftype == refTypes['redir']:
            # I've decided checking whether the target of the redirect exists
            # is more bother than it's worth -- if we're simply adding entries
            # in a different order, it would get really irritating. We'll have
            # a Tool for invalid redirect checks to help balance this out, and
            # we just have to remember that it's possible the redirect is
            # invalid when we attempt to follow it.
            pass
        else:
            assert False, "unreachable code reached -- invalid refType"

    # Step 6: Find Volume object and return the tuple.
    finalReferences = []
    for i in referenceList:
        volume = i[0]
        refnum = i[1]
        reftype = i[2]
        volObj = db.volumes.byNumAndSource(sourceObj, volume)
        if volObj is None:
            # volume doesn't actually exist
            raise NonexistentVolumeError(sourceObj.getName(), volume)
        finalReferences.append((sourceObj, volObj, refnum, reftype))
    return finalReferences

def _splitSourceRef(s):
    """
    Component of the parseUnifiedFormat() routine. Given a working string with
    no pipes but all other components, return a source and reference part.

    Raises InvalidUOFError if something doesn't match the parser's assumptions
    (hopefully this means the given string is not in UOF).
    """

    colonSplits = s.split(':')
    if len(colonSplits) >= 2:
        # At least one separating colon was found; split at the *last* colon,
        # since the source name could contain one or more colons.
        source = ':'.join(colonSplits[:-1]).strip()
        reference = colonSplits[-1].strip()
    elif len(colonSplits) == 1:
        if not _isColonlessValid(s):
            #print("dumping str:")
            #print(s)
            raise InvalidUOFError()
        if '{' in s:
            # We have a brace; take that part out and then check for the
            # other reference
            braceSplits = s.split('{')
            if len(braceSplits) > 2:
                #print "dumping:"
                #print braceSplits
                raise InvalidUOFError()

            # maybe we have a volume number that ended up in the first part
            volPart = None
            if braceSplits[0].strip().endswith('.'):
                try:
                    volPart = re.match(r'.*?(\d+)\.$', braceSplits[0].strip()).group(1)
                    #print "my volPart will be: %r" % volPart
                except AttributeError:
                    volPart = re.match(r'.*?(\d+)\.$', braceSplits[0])
                    raise InvalidUOFError()
                    #print(volPart)
                    #print "error will be excepted"
            else:
                #print "I will not run because my braceSplits[0].strip() is:"
                #print "-> %r" % braceSplits[0].strip()
                pass


            if volPart:
                source = braceSplits[0].strip().replace(volPart + '.', '').strip()
                reference = volPart + ".{" + braceSplits[1].strip()
            else:
                source = braceSplits[0].strip()
                reference = "{" + braceSplits[1].strip()
        else:
            # We know the string is valid and has no colon or brace in it;
            # therefore, there must be no number in the title, and we can
            # safely split on the first nonnumber-number sequence.
            result = re.split(r'(\D)(\d)', s)
            #print "my result was: %r" % result
            if len(result) == 4:
                # when space between abbrev and vol num
                source = ''.join(result[0:2]).strip()
                reference = ''.join(result[2:5]).strip()
            elif len(result) == 7 or len(result) == 10:
                # when no space between; latter with range
                source = ''.join(result[0:2]).strip()
                reference = ''.join(result[2:]).strip()
            elif len(result) == 1:
                # perhaps this is a single-volume 'see': e.g. 'RT see foobar'
                newResult = result[0].split(' see ')
                if len(newResult) > 1:
                    source = newResult[0]
                    reference = 'see ' + ' see '.join(newResult[1:]).strip()
                else:
                    raise InvalidUOFError()
            else:
                raise InvalidUOFError()
    else:
        # even splitting an empty string gives a one-element list
        assert False, "unreachable branch reached"

    # in all paths, these should be strip()ed already
    return source, reference

def _isColonlessValid(s):
    """
    Given a string s that does not have a colon to separate the source and
    reference, determine whether the string is valid. This is true if it does
    not have multiple numbers in it that are not separated by volume or range
    markers, for instance a number in the title *and* the reference. (It's okay
    if the numbers are in braces.)
    """
    sNew = re.sub('{.*}', '', s)
    if re.match('.*[0-9]+[^.\-–0-9]+[0-9]+', sNew) is not None:
        return False
    else:
        return True

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
