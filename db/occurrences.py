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

def fetchForEntry(entry):
    """
    Return a list of all Occurrences for a given Entry.
    """

    eid = entry.getEid()
    d.cursor.execute('SELECT oid FROM occurrences WHERE eid=?', (eid,))
    return [Occurrence(i[0]) for i in d.cursor.fetchall()]
