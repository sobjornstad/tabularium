# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
import re

import db.database as d
import db.occurrences
from db.utils import dateSerializer, dateDeserializer
from db.consts import entryTypes

class DuplicateError(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "An entry with that name already exists."


class Entry(object):
    "Represents a single entry in the database."

    def __init__(self, eid):
        q = 'SELECT name, sortkey, classification, dEdited, dAdded ' \
                'FROM entries WHERE eid=?'
        d.cursor.execute(q, (eid,))
        self._name, self._sk, self._clf, self._de, self._da = \
                d.cursor.fetchall()[0]
        self._da = dateDeserializer(self._da)
        self._de = dateDeserializer(self._de)
        self._eid = eid

    @classmethod
    def makeNew(cls, name, sortkey=None, classification=0):
        """
        Create a new entry record in the database, then create and return an
        Entry object from it. Return None and do not touch the database if an
        entry by given name already exists.
        """
        if sortkey is None:
            sortkey = name

        if nameExists(name):
            return None

        dAdded  = dateSerializer(datetime.date.today())
        dEdited = dAdded

        q = '''INSERT INTO entries
              (eid, name, sortkey, classification, dAdded, dEdited) 
              VALUES (null, ?, ?, ?, ?, ?)'''
        d.cursor.execute(q, (name, sortkey, classification, dAdded, dEdited))
        d.checkAutosave()
        eid = d.cursor.lastrowid
        return cls(eid)


    def __eq__(self, other):
        return (self._eid == other._eid and self._name == other._name and
                self._clf == other._clf and self._sk == other._sk)
    def __ne__(self, other):
        return not self.__eq__(other)

    def __unicode__(self):
        return u"<" + self._name + u">"
    def __str__(self):
        return unicode(self).encode('utf-8')
    def __repr__(self):
        return self.__unicode__()

    def getName(self):
        return self._name
    def getEid(self):
        return self._eid
    def getSortKey(self):
        return self._sk
    def getClassification(self):
        return self._clf
    def getDadded(self):
        return self._da
    def getDedited(self):
        return self._de

    def setName(self, name):
        """
        Change the name of this entry. Note that this does NOT change the sort
        key -- that needs to be done separately!
        """
        self._name = name
        self.dump()
    def setSortKey(self, sk):
        self._sk = sk
        self.dump()
    def setClassification(self, clf):
        if self._clf != clf:
            self._clf = clf
            self.dump()

    def getOccurrences(self):
        """
        Call occurrences.fetchForEntry and return a list of all the occs of
        this entry.
        """
        return db.occurrences.fetchForEntry(self)

    def delete(self):
        d.cursor.execute('DELETE FROM occurrences WHERE eid=?', (self._eid,))
        d.cursor.execute('DELETE FROM entries WHERE eid=?', (self._eid,))
        d.checkAutosave()

    def dump(self):
        dEdited  = datetime.date.today()

        q = '''UPDATE entries
               SET name=?, sortkey=?, classification=?, dAdded=?, dEdited=?
               WHERE eid=?'''
        d.cursor.execute(q, (self._name, self._sk, self._clf,
                         dateSerializer(self._da), dateSerializer(dEdited),
                         self._eid))
        d.checkAutosave()


def deleteOrphaned():
    """
    Find and delete all entries that have no corresponding occurrences. This
    will usually be run after deleting a volume. The only way I can think of
    that this situation would happen unintentionally is if someone deleted the
    last occurrence, which should be disallowed, so it should be safe to
    run this function whenever you want for cleanup.
    """
    d.cursor.execute('''DELETE FROM entries
                        WHERE eid NOT IN (SELECT eid FROM occurrences)''')

def nameExists(name):
    """
    Check if an entry with the given /name/ already exists in the database.
    We should not have entries with duplicate names, so this is a useful
    test. Returns a boolean.
    """
    if len(find(name)):
        return True
    else:
        return False

def find(search, classification=tuple([i for i in entryTypes.values()]),
         regex=False):
    """
    Get a list of Entries matching the given criteria.

    Arguments:
        search - a glob to search for, using either standard SQLite or Python
            regex matching
        classification (optional, default all values defined in
            db.consts.entryTypes) - a tuple of allowable values for the entry's
            classification
        regex (optional, default False) - use regex match (see arg /search/)

    Return:
        A list of entry objects matching the criteria, or an empty list if
        there were no matches.

    Raises:
        SQLite.OperationalError - if using regex mode and the regex is invalid,
            this error will propagate.
    """

    query = "SELECT eid FROM entries WHERE name %s ? AND classification IN (%s)"
    placeholders = ','.join('?' * len(classification))
    query = query % ('REGEXP' if regex else 'LIKE', placeholders)

    d.cursor.execute(query, (search,) + classification)
    results = d.cursor.fetchall()
    return [Entry(r[0]) for r in results]

def allEntries():
    """
    Return a list of all entries in the database.
    """
    d.cursor.execute('SELECT eid FROM entries')
    return [Entry(i[0]) for i in d.cursor.fetchall()]

def percentageWrap(search):
    return "%" + search + "%"

def sortKeyTransform(e):
    """
    Perform some automatic transformations on an entry name string, which are
    common issues requiring the specification of a sort key. Returns a string
    to serve as the key.
    """

    e = re.sub(r'\"(.*?)\"', r'\1', e)     # quotations
    e = re.sub(r'_(.*?)_', r'\1', e)       # underlines/"italics"
    e = re.sub(r'^[tT]he *(.*)', r'\1', e) # "the"
    e = re.sub(r"^'(.*)", r'\1', e)        # apostrophes
    e = re.sub(r"^#(.*)", r'\1', e)        # hashes
    e = re.sub(r"^/(.*)", r'\1', e)        # slashes

    return e
