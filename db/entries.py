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
    """
    Represents a single entry in the database. As entries are quite simple,
    this class is also quite simple!
    """

    def __init__(self, name, eid=None):
        self._name = name
        self._eid = eid
        self.dump()

    def __eq__(self, other):
        return self._eid == other._eid and self._name == other._name
    def __ne__(self, other):
        return not self.__eq__(other)

    def getName(self):
        return self._name
    def getEid(self):
        return self._eid

    def setName(self, name):
        self._name = name
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
        if self._eid:
            d.cursor.execute('UPDATE entries SET name=? WHERE eid=?',
                    (self._name, self._eid))
        else:
            if nameExists(self._name):
                raise DuplicateError()
            d.cursor.execute('INSERT INTO entries (eid, name) VALUES (?,?)',
                    (self._eid, self._name))
            self._eid = d.cursor.lastrowid
        d.checkAutosave()

    @classmethod
    def byId(cls, eid):
        d.cursor.execute('SELECT name FROM entries WHERE eid=?', (eid,))
        name = d.cursor.fetchall()[0][0]
        return cls(name, eid)

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

    query = 'SELECT eid, name FROM entries WHERE name LIKE ?'
    d.cursor.execute(query, (search,))
    results = d.cursor.fetchall()
    return [Entry(r[1], r[0]) for r in results]

def allEntries():
    """
    Return a list of all entries in the database.
    """

    d.cursor.execute('SELECT eid, name FROM entries')
    return [Entry(i[1], i[0]) for i in d.cursor.fetchall()]


def percentageWrap(search):
    return "%" + search + "%"
