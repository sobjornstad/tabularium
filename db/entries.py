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

import db.database as d
import db.occurrences
from db.sources import Source
from db.utils import serializeDate, deserializeDate
from db.volumes import Volume


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
    """

    def __init__(self, eid: int):
        q = '''SELECT name, sortkey, classification, dEdited, dAdded
               FROM entries WHERE eid=?'''
        d.cursor.execute(q, (eid,))
        self._name, self._sortKey, self._classification, self._dateEdited, \
            self._dateAdded = d.cursor.fetchall()[0]
        self._classification = EntryClassification(self._classification)
        self._dateEdited = deserializeDate(self._dateEdited)
        self._dateAdded = deserializeDate(self._dateAdded)
        self._eid = eid

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
        d.cursor.execute(q, (name, sortkey, classification.value, dAdded, dEdited))
        d.checkAutosave()
        eid = d.cursor.lastrowid
        return cls(eid)

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
            Entry.multiConstruct(d.cursor.fetchall()).

        Return:
            A list of Entry objects containing the specified content.
        """
        constructed = []
        for eid, name, sortKey, classification, dateEdited, dateAdded in entryData:
            entry = cls.__new__(cls)
            entry._name = name
            entry._sortKey = sortKey
            entry._classification = EntryClassification(classification)
            entry._dateEdited = deserializeDate(dateEdited)
            entry._dateAdded = deserializeDate(dateAdded)
            entry._eid = eid
            constructed.append(entry)
        return constructed


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
        d.cursor.execute('SELECT picture FROM entries WHERE eid=?', (self._eid,))
        image = d.cursor.fetchall()[0][0]
        return image
    @image.setter
    def image(self, content: Union[None, str, bytes]):
        """
        Set database column to an image. May be set to None (to delete the
        image), or a filename to read from, or raw data.
        """
        if content is None:
            d.cursor.execute('UPDATE entries SET picture=null WHERE eid=?',
                             (self._eid,))
        elif isinstance(content, str):
            path = content
            with open(path, 'rb') as thefile:
                d.cursor.execute(
                    'UPDATE entries SET picture=? WHERE eid=?',
                     (sqlite3.Binary(thefile.read()), self._eid))
        else:
            # raw data
            d.cursor.execute('UPDATE entries SET picture=? WHERE eid=?',
                             (sqlite3.Binary(content), self._eid))
        d.checkAutosave()

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
        d.cursor.execute('DELETE FROM occurrences WHERE eid=?', (self._eid,))
        d.cursor.execute('DELETE FROM entries WHERE eid=?', (self._eid,))
        d.checkAutosave()

    def flush(self):
        "Write this entry to the database after changes are made."
        dEdited  = datetime.date.today()

        q = '''UPDATE entries
               SET name=?, sortkey=?, classification=?, dAdded=?, dEdited=?
               WHERE eid=?'''
        d.cursor.execute(q, (self._name, self._sortKey, self._classification.value,
                         serializeDate(self._dateAdded),
                         serializeDate(dEdited), self._eid))
        d.checkAutosave()


def deleteOrphaned():
    """
    Find and delete all entries that have no corresponding occurrences. This
    will usually be run after deleting a volume or occurrence. The only way I
    can think of that this situation would happen unintentionally is if someone
    deleted the last occurrence, which should be disallowed, so it should be
    safe to run this function whenever you want for cleanup.
    """
    d.cursor.execute('''DELETE FROM entries
                        WHERE eid NOT IN (SELECT eid FROM occurrences)''')

def nameExists(name):
    """
    Check if an entry with the given /name/ already exists in the database.
    We should not have entries with duplicate names, so this is a useful
    test. Returns a boolean.
    """
    return bool(find(name))


# pylint: disable=too-many-arguments
def find(
    search: str,
    classification: Sequence[EntryClassification] = None,
    regex: bool = False,
    enteredDate: Optional[datetime.date] = None,
    modifiedDate: Optional[datetime.date] = None,
    source: Optional[Source] = None,
    volume: Optional[Volume] = None
    ) -> Sequence[Entry]:
    """
    Get a list of Entries matching the given criteria.

    Arguments:
        search - a glob to search for, using either standard SQLite or Python
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
        SQLite.OperationalError - if using regex mode and the regex is invalid,
            this error will propagate.

    TODO: An additional optimization for sorting would be to make COLLATE nocase
    an attribute of the column rather than using it here -- some people on SO
    have said that has improved the sort performance nearly by a factor of 10.
    I don't think an index would help here, but I know very little about SQL
    indexes.
    """
    if not classification:
        classification = tuple(i for i in EntryClassification)

    if not regex:
        if not (search.startswith('%') and search.endswith('%')):
            # This search is not supposed to be percent-wrapped, but we might
            # need to escape percents inside it. Note that we require both ends
            # for it to be considered percent-wrapped: if we want to specify
            # anything besides a substring search or an exact match, we should
            # use regexes. This ensures we catch, e.g., "100%", as improperly
            # escaped.
            search = search.replace(r'%', r'\%')

    if (enteredDate is None and modifiedDate is None
            and source is None and volume is None):
        # The last %s is a fake so that the below code works without
        # modification: nothing will ever be substituted there.
        query = """SELECT eid, name, sortkey, classification,
                          entries.dEdited, entries.dAdded
                   FROM entries
                   WHERE name %s ? %s
                         AND classification IN (%s)%s
                   ORDER BY sortkey COLLATE nocase"""
    else:
        query = """SELECT DISTINCT entries.eid, name, sortkey, classification,
                                   entries.dEdited, entries.dAdded
                   FROM occurrences
                   INNER JOIN entries
                           ON entries.eid = occurrences.eid
                   WHERE name %s ? %s
                         AND classification IN (%s)
                         %s
                   ORDER BY sortkey COLLATE nocase"""
    classifPlaceholders = ','.join('?' * len(classification))
    occQuery, occQueryParams = db.occurrences.occurrenceFilterString(
        enteredDate, modifiedDate, source, volume)
    query = query % ('REGEXP' if regex else 'LIKE',
                     "ESCAPE '\\'" if not regex else '',
                     classifPlaceholders,
                     'AND ' + occQuery if occQuery else '')

    d.cursor.execute(
        query,
        (search,) + tuple(i.value for i in classification) + tuple(occQueryParams))
    results = d.cursor.fetchall()
    return Entry.multiConstruct(results)


def findOne(
    search: str,
    classification: Sequence[EntryClassification] = None,
    regex: bool = False,
    enteredDate: Optional[datetime.date] = None,
    modifiedDate: Optional[datetime.date] = None,
    source: Optional[Source] = None,
    volume: Optional[Volume] = None
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
                   enteredDate, modifiedDate, source, volume)
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
    d.cursor.execute(q, (EntryClassification.PERSON.value,
                         db.consts.refTypes['redir']))
    entries = db.entries.Entry.multiConstruct(d.cursor.fetchall())
    cleanedEntries = []
    for i in entries:
        if (not cleanedEntries
                or not i.name.startswith(cleanedEntries[-1].name)):
            cleanedEntries.append(i)
    return cleanedEntries

def allEntries():
    """
    Return a list of all entries in the database.
    """
    d.cursor.execute('''SELECT eid, name, sortkey, classification, dEdited,
                               dAdded
                        FROM entries
                        ORDER BY sortkey COLLATE nocase''')
    return Entry.multiConstruct(d.cursor.fetchall())

def percentageWrap(search):
    return "%" + search.replace(r'%', r'\%') + "%"

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
