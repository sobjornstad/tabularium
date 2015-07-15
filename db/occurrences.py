# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d
import entries
import notebooks

class DuplicateError(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "An occurrence pointing there already exists."

class Occurrence(object):
    """
    Represents one reference target of an entry.
    """

    def __init__(self, oid):
        query = '''SELECT eid, nid, ref, type, dEdited, dAdded
                   FROM occurrences WHERE oid=?'''
        d.cursor.execute(query, (oid,))
        eid, nid, self._ref, self._type, self._de, self._da = \
                d.cursor.fetchall()[0]
        self._entry = entries.Entry(eid)
        self._notebook = notebooks.Notebook.byId(nid)
        self._oid = oid

    @classmethod
    def makeNew(cls, entry, notebook, ref, type):
        dAdded = '2015-01-01' # update this!
        dEdited = dAdded

        eid = entry.getEid()
        nid = notebook.getNid()
        q = '''INSERT INTO occurrences
               (oid, eid, nid, ref, type, dEdited, dAdded)
               VALUES (null, ?,?,?,?,?,?)'''
        d.cursor.execute(q, (eid, nid, ref, type, dEdited, dAdded))
        d.checkAutosave()
        oid = d.cursor.lastrowid
        return cls(oid)

    def __eq__(self, other):
        return (self._entry == other._entry and self._ref == other._ref and
                self._notebook == other._notebook and self._oid == other._oid and
                self._de == other._de and self._da == other._da and
                self._type == other._type)
    def __ne__(self, other):
        return not self.__eq__(other)

    def getEntry(self):
        return self._entry
    def getNotebook(self):
        return self._notebook
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
    def setNotebook(self, notebook):
        self._notebook = notebook
        self.dump()

    def dump(self):
        dEdited = '2015-06-29' # obviously fetch this in future

        query = '''UPDATE occurrences
                   SET eid=?, nid=?, ref=?, type=?, dEdited=?, dAdded=?
                   WHERE oid=?'''
        d.cursor.execute(query, (self._entry.getEid(), self._notebook.getNid(),
                self._ref, self._type, self._de, self._da, self._oid))
        d.checkAutosave()

    def getNearby(self, nearRange=1):
        """
        Find all occurrences that are in the same notebook/source and within
        /nearRange/ pages/indices of it. Eventually /nearRange/ should be part
        of the source options; for now this will ordinarily use the default
        value of 1.

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
               WHERE nid = ? AND (type = 0 OR type = 1)
                   AND CAST(ref as integer) BETWEEN ? AND ?'''
        d.cursor.execute(q, (self._notebook.getNid(), pageStart, pageEnd))
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

def parseUnifiedFormat(s):
    """
    Parse a string in Unified Occurrence Format (UOF) into Occurrence objects
    and return a list thereof. UOF works as follows.

    A simple occurrence in UOF consists of the *source*, *volume* (if
    applicable), and *page* (or index number). Some examples of valid simple
    occurrences in UOF:

    CB1.56
    CB 1.56
    CB: 1.56
    CB:1 . 56
    RT 2378 (if RT is single-volume)
    RT 0.2378
    The Invisible Man 58
    The 160th Book: 45

    The rules:
    The general format looks like `SOURCENAME:VOLNUMBER.PAGENUMBER`.

    * There may be spaces or no spaces before or after the colon and period.
    * The volume number and point may be omitted if the source is single-volume
      (or you can write in volume 0, but that's generally silly).
    * The colon may be omitted entirely so long as the source name does not
      contain any numbers. If there are numbers in the source name, the parser
      would otherwise be unable to figure out where the source name ended and
      the the page number began. If there are multiple numbers separated by at
      least one space and no colon, the string is invalid UOF.
    

    Multiple occurrences can be entered at once:

    CB:{1.56, 5.78}
    CB {1.56,5 .78,}
    CB{1.56}
    CB 1.56 | CB 5.78 | CB 12.56
    CB {1.56, 5.78} | CB 12.56
    RT 2378 | The Invisible Man {56, 78}
    The 160th Book: 45 | TB2.162

    Rules:
    * To enter multiple page numbers within the same source and volume, OR
      multiple volumes and page numbers within the same source, place the page
      or volume and page references in braces, separating them with a comma. A
      trailing comma inside the braces may optionally be used. (Braces are also
      legal with a single occurrence.)
    * To enter multiple whole sources, or as a more verbose way of entering
      multiple pages within the same source, place a pipe (|) character between
      the references, with optional (but suggested for readability) spaces on
      either side.


    Finally, you may want to enter a range or a redirect. Examples:
    CB 15.45-56
    CB 15.45–6
    CB 15.45--56
    CB 15. see Other Entry

    Rules:
    * Ranges are specified with '-', '--', or '–' (literal en-dash). There
      can be spaces at the sides, but not between the dashes of the double
      dash.
    * Redirects are specified with the keyword 'see' followed by a space and
      the entry to redirect to.

    And this is valid UOF, though not a very likely/good way of doing things...
    CB{15.26--7,2    . 18, 4.see    Other Entry} |The 2nd Book of    : 45
    """
    #TODO: Ensure that source names cannot contain pipes or braces

    #TODO: Sources, I'm afraid, need to be implemented before we can do
    # this properly.

    uniqueSections = [i.strip() for i in s.split('|')]
    for i in uniqueSections:
        pass
