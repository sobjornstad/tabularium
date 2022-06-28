"""
entries.py - entry functions
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>.

from __future__ import annotations

import datetime
from enum import Enum
import re
import sqlite3
from typing import Any, Iterable, List, Optional, Sequence, TextIO, Tuple, Union

from db.database import d
import db.occurrences
from db.sources import Source
from db.utils import serializeDate, deserializeDate


class MultipleResultsUnexpectedError(Exception):
    def __str__(self):
        return ("A find that should not have returned multiple results "
                "returned multiple results. This is probably due to the "
                "database being in an inconsistent state.")


class EntryClassification(Enum):
    "The type of thing this entry represents."
    UNCLASSIFIED = 0
    ORD = 1
    PERSON = 2
    PLACE = 3
    QUOTE = 4
    TITLE = 5

    @property
    def interfaceKey(self) -> str:
        "Return a key that can be used in the interface."
        return {
            EntryClassification.UNCLASSIFIED: "unclassified",
            EntryClassification.ORD: "ord",
            EntryClassification.PERSON: "person",
            EntryClassification.PLACE: "place",
            EntryClassification.QUOTE: "quote",
            EntryClassification.TITLE: "title"
        }[self]


class Entry:
    """
    An Entry is the fundamental unit of data in Tabularium.

    An Entry has a name and is associated with some set of occurrences,
    along with some metadata.

    Entries should be retrieved using the byEid() or byName() classmethod, or
    one of the search functions in the module, and created using the makeNew()
    or multiConstruct() classmethod.  The constructor should not be called
    directly by client code, as this bypasses the entry cache (see below).

    Entries are cached by ID so that only one instance is maintained in memory;
    when an Entry is constructed through one of the classmethods, it uses a
    cached instance if available and lazy-loads one from the database if not.
    Most of the time this just works, but if you run an UPDATE or DELETE query
    that touches Entries (rather than modifying the objects in Python and
    flushing them), it's important to invalidate the cache, preferably with
    evictFromCache(). If you change databases or perform some kind of bulk
    update or migration, call Entry.invalidateCache() to clear everything (if
    you don't do this on changing databases, everything will go completely
    haywire as the wrong entries are returned everywhere).)
    """
    _instanceCache: dict[int, Entry] = {}

    def __init__(self, eid: int) -> None:
        q = '''SELECT name, sortkey, classification, dEdited, dAdded
                 FROM entries
                WHERE eid=?'''
        d().cursor.execute(q, (eid,))
        self._name, self._sortKey, self._classification, self._dateEdited, \
            self._dateAdded = d().cursor.fetchall()[0]
        self._classification = EntryClassification(self._classification)
        self._dateEdited = deserializeDate(self._dateEdited)
        self._dateAdded = deserializeDate(self._dateAdded)
        self._eid = eid

    @classmethod
    def byEid(cls, eid: int) -> Entry:
        """
        Get an entry by its ID, from the cache if available and from the database
        if not.
        """
        if eid not in cls._instanceCache:
            cls._instanceCache[eid] = Entry(eid)
        return cls._instanceCache[eid]

    @classmethod
    def byName(cls, name: str) -> Optional[Entry]:
        "Get an entry by its name."
        d().cursor.execute('SELECT eid FROM entries WHERE name = ?', (name,))
        results = d().cursor.fetchall()
        assert len(results) < 2, "Multiple results for name: " + name
        eid = results[0][0] if results else None
        return cls.byEid(eid) if eid else None

    @classmethod
    def makeNew(cls, name: str, sortkey: Optional[str] = None,
                classification: EntryClassification = EntryClassification.UNCLASSIFIED
               ) -> Optional[Entry]:
        """
        Create a new entry record in the database, then create and return an
        Entry object from it. Return None and do not touch the database if an
        entry by given name already exists.
        """
        if sortkey is None:
            sortkey = name

        if nameExists(name):
            return None

        dAdded  = serializeDate(datetime.date.today())
        dEdited = dAdded

        q = '''INSERT INTO entries
               (eid, name, sortkey, classification, dAdded, dEdited) 
               VALUES (null, ?, ?, ?, ?, ?)'''
        d().cursor.execute(q, (name, sortkey, classification.value, dAdded, dEdited))
        d().checkAutosave()
        eid = d().cursor.lastrowid

        obj = cls._instanceCache[eid] = cls(eid)
        return obj

    @classmethod
    def multiConstruct(
        cls,
        entryData: Iterable[Tuple[int, str, str, EntryClassification, str, str]]
        ) -> Sequence[Entry]:
        """
        A nasty hack to bypass __init__ and not hit the database while
        constructing many Entries. This is an optimization useful in the case
        that we do a find() and get 9,000 results; at that point it's very slow
        to make 9,000 unnecessary database requests to construct all the
        entries. (We're dealing with searches growing as O(n) either way, but
        the constant time on a database hit is obviously much, much higher than
        1/9000th of the time it takes to make a larger request.)

        A cleaner way would be to make *this* the __init__ method and make the
        version that retrieves the entry from the database by eid be the class
        method, but since that would make the Entry interface inconsistent with
        that of every other Tabularium object, we're taking this approach for
        the time being.

        Arguments:
            entryData: a list of tuples of (eid, name, sortKey, classification,
            dateEdited, dateAdded) -- the order of the fields in the database.
            So with an appropriate query retrieving all the fields, this works:
            Entry.multiConstruct(d().cursor.fetchall()).

        Return:
            A list of Entry objects containing the specified content.
        """
        constructed = []
        for eid, name, sortKey, classification, dateEdited, dateAdded in entryData:
            if eid not in cls._instanceCache:
                entry = cls.__new__(cls)
                entry._name = name
                entry._sortKey = sortKey
                entry._classification = EntryClassification(classification)
                entry._dateEdited = deserializeDate(dateEdited)
                entry._dateAdded = deserializeDate(dateAdded)
                entry._eid = eid
                cls._instanceCache[eid] = entry
            constructed.append(cls._instanceCache[eid])
        return constructed

    @classmethod
    def invalidateCache(cls) -> None:
        """
        Wipe the cache of entries. Required when changing databases.
        """
        cls._instanceCache.clear()

    @classmethod
    def evictFromCache(cls, eid: int) -> None:
        if eid in cls._instanceCache:
            del cls._instanceCache[eid]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entry):
            return NotImplemented
        return self._eid == other._eid

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        "Sort by sort key."
        if not isinstance(other, Entry):
            return NotImplemented
        return self._sortKey.lower() < other._sortKey.lower()

    def __hash__(self) -> int:
        return self._eid

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return "<" + self._name + ">"

    @property
    def name(self) -> str:
        return self._name
    @name.setter
    def name(self, n: str) -> None:
        """
        Change the name of this entry. Note that this does NOT change the sort
        key -- that needs to be done separately!
        """
        if self._name != n:
            self._name = n
            self.flush()

    @property
    def eid(self) -> int:
        return self._eid

    @property
    def sortKey(self) -> str:
        return self._sortKey
    @sortKey.setter
    def sortKey(self, sk: str):
        if self._sortKey != sk:
            self._sortKey = sk
            self.flush()

    @property
    def classification(self) -> EntryClassification:
        return self._classification
    @classification.setter
    def classification(self, clf: EntryClassification) -> None:
        if self._classification != clf:
            self._classification = clf
            self.flush()

    @property
    def dateAdded(self) -> datetime.date:
        return self._dateAdded

    @property
    def dateEdited(self) -> datetime.date:
        return self._dateEdited

    # To avoid filling up the computer's memory if requesting a bunch of
    # entries, images are fetched from the DB on request rather than being
    # stored in the object with other attributes. Note that this means, for
    # optimal performance, you should get the value of 'obj.image' only once in
    # the caller.
    @property
    def image(self):
        "Image associated with a person."
        d().cursor.execute('SELECT picture FROM entries WHERE eid=?', (self._eid,))
        image = d().cursor.fetchall()[0][0]
        return image
    @image.setter
    def image(self, content: Union[None, str, bytes]):
        """
        Set database column to an image. May be set to None (to delete the
        image), or a filename to read from, or raw data.
        """
        if content is None:
            d().cursor.execute('UPDATE entries SET picture=null WHERE eid=?',
                             (self._eid,))
        elif isinstance(content, str):
            path = content
            with open(path, 'rb') as thefile:
                d().cursor.execute(
                    'UPDATE entries SET picture=? WHERE eid=?',
                     (sqlite3.Binary(thefile.read()), self._eid))
        else:
            # raw data
            d().cursor.execute('UPDATE entries SET picture=? WHERE eid=?',
                             (sqlite3.Binary(content), self._eid))
            # No need to refresh the cache as images aren't stored within the object
        d().checkAutosave()

    def writeImage(self, filehandle: TextIO):
        "Write an image in the DB to disk so the user can work with it further."
        image = self.image
        if image is None:
            return False
        else:
            filehandle.write(image)
            return True

    def delete(self):
        "Toast this entry."
        for occ in db.occurrences.fetchForEntry(self):
            occ.delete()
        d().cursor.execute('DELETE FROM entries WHERE eid=?', (self._eid,))
        self.evictFromCache(self._eid)
        d().checkAutosave()

    def flush(self):
        "Write this entry to the database after changes are made."
        dEdited  = datetime.date.today()

        q = '''UPDATE entries
               SET name=?, sortkey=?, classification=?, dAdded=?, dEdited=?
               WHERE eid=?'''
        d().cursor.execute(q, (self._name, self._sortKey, self._classification.value,
                         serializeDate(self._dateAdded),
                         serializeDate(dEdited), self._eid))
        d().checkAutosave()


def deleteOrphaned():
    """
    Find and delete all entries that have no corresponding occurrences. This
    will usually be run after deleting a volume or occurrence. The only way I
    can think of that this situation would happen unintentionally is if someone
    deleted the last occurrence, which should be disallowed, so it should be
    safe to run this function whenever you want for cleanup.

    It's important to retrieve these and then use the .delete() method rather than
    simply running a DELETE FROM query so that deleted entries are evicted from
    the entry instance cache.
    """
    d().cursor.execute('''SELECT eid FROM entries
                           WHERE eid NOT IN (SELECT eid FROM occurrences)''')
    for eid in d().cursor.fetchall():
        Entry(eid[0]).delete()

def nameExists(name):
    """
    Check if an entry with the given /name/ already exists in the database.
    We should not have entries with duplicate names, so this is a useful
    test. Returns a boolean.

    TODO: Should we disallow entries that differ only in case?
    """
    return bool(Entry.byName(name))


def exciseUnquotedCommas(s: str) -> str:
    """
    Remove any commas that aren't inside double quotes from the string /s/.
    This may be desirable because of the dual role of the filter box in the UI
    in both searching for and creating entries -- the user won't want to leave
    out this extremely common punctuation since then they'll have to edit it
    again if they don't find anything, but if they leave it in FTS5 will error
    without this adjustment.

    >>> exciseUnquotedCommas('Bjornstad, Soren')
    'Bjornstad Soren'

    >>> exciseUnquotedCommas('"Bjornstad, Soren"')
    '"Bjornstad, Soren"'

    >>> exciseUnquotedCommas(",")
    ''

    >>> exciseUnquotedCommas('comma, and "comma, quoted"')
    'comma and "comma, quoted"'

    # a classic from Cross's _Indexing Books_
    >>> exciseUnquotedCommas('"diet, anus, artificial, patients with, for"')
    '"diet, anus, artificial, patients with, for"'

    >>> exciseUnquotedCommas('diet, anus, artificial, patients with, for')
    'diet anus artificial patients with for'
    """
    inQuotes = False
    newStringParts = []
    for i in s.split('"'):
        if not inQuotes:
            newStringParts.append(i.replace(',', ''))
        else:
            newStringParts.append(i)
        inQuotes = not inQuotes
    return '"'.join(newStringParts)


# pylint: disable=too-many-arguments, too-many-locals
def find(
    search: str,
    classification: Sequence[EntryClassification] = None,
    regex: bool = False,
    enteredDateStr: str = None,
    modifiedDateStr: str = None,
    source: Optional[Source] = None,
    volumeRange: Optional[Tuple[int, int]] = None
    ) -> Sequence[Entry]:
    """
    Get a list of Entries matching the given criteria.

    Arguments:
        search - a glob to search for, using either SQLite's fts5 or Python
            regex matching
        classification (optional, default all defined values) - a tuple of
            allowable values for the entry's classification
        regex (optional, default False) - use regex match (see arg /search/)
        enteredDate, modifiedDate, source, volume - occurrence limits: entries
            that do not have any occurrences matching these limits will not be
            returned.

    Return:
        A list of entry objects matching the criteria, or an empty list if
        there were no matches. The entries will be returned in sorted order.

    Raises:
        SQLite.OperationalError - if the search is invalid, this error will propagate.

    TODO: An additional optimization for sorting would be to make COLLATE nocase
    an attribute of the column rather than using it here -- some people on SO
    have said that has improved the sort performance nearly by a factor of 10.
    I don't think an index would help here, but I know very little about SQL
    indexes.
    """
    if not classification:
        classification = tuple(i for i in EntryClassification)

    if (enteredDateStr is None and modifiedDateStr is None
            and source is None and volumeRange is None):
        # The last %s is a fake so that the below code works without
        # modification: nothing will ever be substituted there.
        query = """SELECT entries.eid, entries.name, entries.sortkey,
                          entries.classification, entries.dEdited, entries.dAdded
                   FROM entries
                   {join}
                   WHERE {where}
                         AND entries.classification IN ({classifications}){extra}
                   ORDER BY entries.sortkey COLLATE nocase"""
    else:
        query = """SELECT DISTINCT entries.eid, entries.name, entries.sortkey,
                                   entries.classification, entries.dEdited,
                                   entries.dAdded
                   FROM occurrences
                   INNER JOIN entries
                           ON entries.eid = occurrences.eid
                   INNER JOIN entry_fts
                           ON entries.eid = entry_fts.rowid
                   WHERE {where}
                         AND entries.classification IN ({classifications})
                         {extra}
                   ORDER BY sortkey COLLATE nocase"""
    classifPlaceholders = ','.join('?' * len(classification))
    occQuery, occQueryParams = db.occurrences.occurrenceFilterString(
        enteredDateStr, modifiedDateStr, source, volumeRange)

    searchTextParams: List[Any]
    if regex:
        textQuery = 'entries.name REGEXP ?'
        joins = ''
        searchTextParams = [search]
    elif search:
        textQuery = 'entry_fts MATCH ?'
        joins = 'INNER JOIN entry_fts ON entries.eid = entry_fts.rowid'
        searchTextParams = [exciseUnquotedCommas(search)]
    else:
        textQuery = '1=1'
        joins = ''
        searchTextParams = []

    query = query.format(
        join=joins,
        where=textQuery,
        classifications=classifPlaceholders,
        extra=('AND ' + occQuery if occQuery else '')
    )
    params = tuple(
        searchTextParams
        + [i.value for i in classification]
        + occQueryParams
    )

    d().cursor.execute(query, params)
    results = d().cursor.fetchall()
    return Entry.multiConstruct(results)


def findOne(
    search: str,
    classification: Sequence[EntryClassification] = None,
    regex: bool = False,
    enteredDateStr: str = None,
    modifiedDateStr: str = None,
    source: Optional[Source] = None,
    volumeRange: Optional[Tuple[int, int]] = None
    ) -> Optional[Entry]:
    """
    Interface to find() for when no more than one result should be possible.

    If there is one result, return the result as an Entry object. If there are
    no results, return None.

    If there is more than one result, MultipleResultsUnexpectedError is
    raised. Handling this error is typically not required, as it indicates
    we've somehow let the database get in an inconsistent state where there
    are duplicates and shouldn't be, and we'd like to know about that.
    """
    results = find(search, classification, regex,
                   enteredDateStr, modifiedDateStr, source, volumeRange)
    if len(results) == 1:
        return results[0]
    elif not results:
        return None
    else:
        raise MultipleResultsUnexpectedError()


def nonRedirectTopLevelPeople():
    """
    Return a list of all entries marked as 'person' that have at least one
    non-redirect occurrence and are the "top-level" entry (i.e., without
    additional subentries). This is a rough attempt that could use tweaking
    later; in particular, it fails if there is no top-level entry by simply
    including all of the entries.
    """
    q = """SELECT DISTINCT entries.eid, name, sortkey, classification,
                  entries.dEdited, entries.dAdded
           FROM occurrences
           INNER JOIN entries ON entries.eid = occurrences.eid
           WHERE classification = ?
                 AND occurrences.type != ?
           ORDER BY sortkey COLLATE nocase"""
    d().cursor.execute(q, (EntryClassification.PERSON.value,
                         db.occurrences.ReferenceType.REDIRECT.value))
    entries = db.entries.Entry.multiConstruct(d().cursor.fetchall())
    cleanedEntries = []
    for i in entries:
        if (not cleanedEntries
                or not i.name.startswith(cleanedEntries[-1].name)):
            cleanedEntries.append(i)
    return cleanedEntries


def updateRedirectsTo(oldName: str, newName: str):
    """
    When an entry is renamed from oldName to newName, any occurrences in the database
    of type redirect whose ref points to oldName must have their ref updated
    to point to newName instead.

    We retrieve the occurrences and then reset them rather than using an UPDATE
    statement to avoid needing to flush cache.
    """
    q = '''SELECT oid FROM occurrences WHERE type = ? AND ref = ?'''
    d().cursor.execute(q, (db.occurrences.ReferenceType.REDIRECT.value,
                           oldName))
    for oid, in d().cursor.fetchall():
        db.occurrences.Occurrence.byOid(oid).ref = newName
    d().checkAutosave()


WARNED_OF_EDIT_DISTANCE = False
def findPossibleMisspellings(name: str,
                             threshold: float = 0.80) -> List[Tuple[Entry, float]]:
    """
    Compute Levenshtein similarity between /name/ and entries in the database
    and return a tuple (Entry, similarity) where 0 < similarity < 1
    for all entries whose similarity to /name/ exceeds threshold.

    Similar entries are excluded in the following cases:
    * The incoming name is the beginning of the similar entry (indicating the user
      most likely just hasn't finished typing yet).
    * The incoming name is the similar entry with a comma and some additional text
      after it (indicating this is a subentry of the similar name).

    This function is reasonably fast when the name is short, but becomes rather
    slow as it gets longer and the database gets larger, so it should be run in
    a background thread if it's updating as the user types or keystrokes will be
    slow as molasses.

    TODO: The threshold would ideally be adjusted based on the length of the name,
    as the raw similarity score moves proportionally slower with longer names.
    """
    if not d().hasEditDistance:
        global WARNED_OF_EDIT_DISTANCE
        if not WARNED_OF_EDIT_DISTANCE:
            print("Edit-distance library is not available, so Tabularium will not "
                  "warn you of possibly misspelled entries. "
                  "Run 'make' in the Tabularium directory to compile these extensions.")
            WARNED_OF_EDIT_DISTANCE = True
        return []

    d().cursor.execute('''SELECT eid, lsim(?, name) as similarity
                            FROM entries
                           WHERE similarity > ?
                             AND NOT name LIKE (? || '%')
                             AND NOT ? LIKE (name || ',' || '%')''',
                     (name, threshold, name, name))
    return [(Entry.byEid(row[0]), row[1]) for row in d().cursor.fetchall()]


def allEntries():
    """
    Return a list of all entries in the database.
    """
    d().cursor.execute('''SELECT eid, name, sortkey, classification, dEdited,
                               dAdded
                        FROM entries
                        ORDER BY sortkey COLLATE nocase''')
    return Entry.multiConstruct(d().cursor.fetchall())

def sortKeyTransform(e):
    """
    Perform some automatic transformations on an entry name string, which are
    common issues requiring the specification of a sort key. Returns a string
    to serve as the key.

    This could get a lot smarter; for instance, "and" and "of" at the beginning
    of a subentry would ideally be sliced out, and marks of punctuation should
    generally be removed. Indeed, these rules should generally be applied after
    each comma (but this could fail now and again, since we don't rigidly
    separate inversions from subentries in our index model). This also raises
    the question of how badly we should mangle the sort key and people's
    expectations of how things sort on computers to match what would seem to be
    the most sensible index sort. The Principle of Least Astonishment applies,
    but once in a while surprise might be better in the long run.

    Also, should spaces be removed, not presumably when washing but through a
    property access method when retrieving the sort key? Letter-by-letter
    alphabetization is presumably our goal. (Actually, this would seem to
    require an extra column in the database, since sorting is handled at the DB
    level. Probably not worth it.)
    """
    transforms = (
        (r'\"(.*?)\"', r'\1'),       # quotations
        (r'_(.*?)_', r'\1'),         # underlines/"italics"
        (r"^'(.*)", r'\1'),          # apostrophes
        (r"^#(.*)", r'\1'),          # hashes
        (r"^/(.*)", r'\1'),          # slashes
        (r'^[tT]he +(.*)', r'\1'),   # initial "the" is ignored
        (r'^St\.(.*)', r'Saint\1'),  # 'St.' sorts as 'Saint'
        )
    for match, repl in transforms:
        e = re.sub(match, repl, e)
    return e
