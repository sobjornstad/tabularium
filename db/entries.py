# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d
import occurrences

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

        dAdded  = '2015-06-01' # obviously fetch the actual ones later
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

    def getName(self):
        return self._name
    def getEid(self):
        return self._eid
    def getSortKey(self):
        return self._sk
    def getClassification(self):
        return self._clf

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
        self._clf = clf
        self.dump()

    def getOccurrences(self):
        """
        Call occurrences.fetchForEntry and return a list of all the occs of
        this entry.
        """
        return occurrences.fetchForEntry(self)

    def delete(self):
        d.cursor.execute('DELETE FROM entries WHERE eid=?', (self._eid,))
        d.checkAutosave()

    def dump(self):
        # no longer need to check if eid exists, initial write handled in makeNew
        dEdited  = '2015-06-29' # obviously fetch the actual ones later

        q = '''UPDATE entries
               SET name=?, sortkey=?, classification=?, dAdded=?, dEdited=?
               WHERE eid=?'''
        d.cursor.execute(q, (self._name, self._sk, self._clf, self._da,
                dEdited, self._eid))
        d.checkAutosave()


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

def find(search):
    """
    Return a list of Entry objects matching the given glob, or empty list if
    there are no matches.
    """

    query = 'SELECT eid FROM entries WHERE name LIKE ?'
    d.cursor.execute(query, (search,))
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
