# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
import re

from db.consts import refTypes
import db.database as d
import db.entries
import db.volumes
import db.sources
from db.utils import dateSerializer, dateDeserializer

class InvalidUOFError(Exception):
    def __init__(self, text="Invalid UOF."):
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
    def __init__(self, what, value, source):
        self.what = what
        self.value = value
        self.source = source
    def __str__(self):
        if self.what == 'page':
            validation = self.source.getPageVal()
        elif self.what == 'volume':
            validation = self.source.getVolVal()
        #else:
            #assert False, "Invalid invalid thing in instantiating " \
                          #"InvalidReferenceError!"
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
                return "%s: see %s" % (source.getAbbrev, self._ref)
            else:
                return '%s %s: see "%s"' % (source.getAbbrev(), vol, self._ref)
        else:
            assert False, "invalid reftype in occurrence"

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

    #TODO: error-checking
    def setRef(self, ref, type):
        self._ref = ref
        self._type = type
        self.dump()
    def setEntry(self, entry):
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

    def getNearby(self, nearRange=1):
        """
        Find all occurrences that are in the same volume and within /nearRange/
        pages/indices of it. Eventually /nearRange/ should be part of the
        source options; for now this will ordinarily use the default value of
        1.

        If the current occurrence is a redirect and thus has no logical result
        for this operation, or if the range or other data is otherwise invalid
        for this occurrence, or in the very unusual case that there are simply
        no results, return None. #(would we rather several return types?)

        Note that nearby is capable of finding things that are nearby ranges,
        but is not currently always capable of finding ranges themselves in
        nearby queries. (SQL BETWEEN does successfully find the entry when one
        of the top or bottom range numbers is actually in the string.)

        Returns a list of Entry objects.
        """

        if not (self._type == 1 or self._type == 0):
            return None

        page = self._ref
        if self._type == 1:
            retval = parseRange(page)
            if retval is None:
                return None
            else:
                bottom, top = retval
            pageStart = bottom - nearRange
            pageEnd = top + nearRange
        else:
            try:
                pageStart = int(page) - 1
                pageEnd = int(page) + 1
            except ValueError:
                return None

        q = '''SELECT oid FROM occurrences
               WHERE vid = ? AND (type = 0 OR type = 1)
                   AND CAST(ref as integer) BETWEEN ? AND ?'''
        d.cursor.execute(q, (self._volume.getVid(), pageStart, pageEnd))
        occs = [Occurrence(i[0]) for i in d.cursor.fetchall()]

        # fetch list of entries nearby
        entries = [i.getEntry() for i in occs]
        entries.sort(key=lambda i: i._sk)

        return entries


def fetchForEntry(entry):
    """
    Return a list of all Occurrences for a given Entry.
    """

    eid = entry.getEid()
    d.cursor.execute('SELECT oid FROM occurrences WHERE eid=?', (eid,))
    return [Occurrence(i[0]) for i in d.cursor.fetchall()]

def parseRange(val):
    """
    Return a tuple of bottom, top integers for a range (a string consisting of
    two ints separated by a hyphen). Return None if the value was not a range
    in this format.
    """

    try:
        bottom, top = val.split('-')
        bottom, top = int(bottom), int(top)
    except ValueError:
        return None

    return (bottom, top)

def makeOccurrencesFromString(s, entry):
    """
    Try to create occurrences from a UOF string.
    
    Arguments:
        s - the UOF string to parse
        entry - the entry to add the occurrences to

    Return:
        A list of Occurrence objects that were created.

    Raises:
        All exceptions raised by parseUnifiedFormat() are not caught by this
        function and will be received by the caller so it can provide an
        appropriate error message.
    """
    uofRets = parseUnifiedFormat(s)
    occs = []
    for i in uofRets:
        source, vol, ref, refType = i
        occs.append(Occurrence.makeNew(entry, vol, ref, refType))
    return occs

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
      source name, the parser would otherwise be unable to figure out where the
      source name ended and the page number began. If there are multiple
      numbers separated by at least one space or non-numeric character and no
      colon, or a colon in the source but not after it, the string is invalid
      UOF.
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
    - To enter multiple whole sources, or as a more verbose way of entering
      multiple pages within the same source, place a pipe (|) character between
      the references, with optional (but suggested for readability) spaces on
      either side.


    Finally, you may want to enter a range or a redirect. Examples:
    CB 15.45-56
    CB 15.45–6
    CB 15.45--56
    CB 15. see Other Entry

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
    #TODO: Ensure that source names cannot contain pipes or braces

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
            raise InvalidUOFError()
        try:
            volume = int(volume)
        except ValueError:
            raise InvalidUOFError()

        # determine entry type and format refnum
        ENDASH = u'–' # putting it in a variable fixes Unicode error somehow
        if refnum.startswith('see '):
            # redirect
            reftype = refTypes['redir']
            refnum = refnum.replace('see ', '').strip()
        elif '--' in refnum or ENDASH in refnum or '-' in refnum:
            # range: normalize delimiter
            reftype = refTypes['range']
            if '--' in refnum:
                refnum = refnum.replace('--', '-')
            elif ENDASH in refnum:
                refnum = refnum.replace(ENDASH, '-')
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
                raise InvalidUOFError()
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
            pass
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
            print "dumping str:"
            print s
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
                    volPart = re.match(r'.*?(\d+)\.$', braceSplits[0]).group(1)
                    #print "my volPart will be: %r" % volPart
                except AttributeError:
                    #print "error will be excepted"
                    pass
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
    if re.match(u'.*[0-9]+[^.\-–0-9]+[0-9]+', sNew) is not None:
        return False
    else:
        return True

def rangeUncollapse(first, second):
    """
    "Uncollapse" a range that looks like:
       56-7
       720-57
    and so on. The algorithm works for a number of any length (as long as we
    don't exceed max recursion depth, which is platform-dependent but is at
    least 1000). There's no particular reason why this should be a
    (tail-)recursive function except that I felt like writing one. :-)

    I believe the test for whether this is not actually a valid collapsed range
    covers all possible cases in which it's possible to determine empirically
    from the numbers that the user didn't intend it to be a collapsed range,
    but I have not proven it.
    """
    if first <= second: # end of algorithm
        return first, second
    place = len(str(second))
    if place == len(str(first)): # same number of places and still wrong order
        return None
    second = int(str(first)[-(place+1)] + str(second))
    return rangeUncollapse(first, second)
