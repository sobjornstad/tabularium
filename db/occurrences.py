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

    def __init__(self, entry, page, notebook, oid=None):
        self._entry = entry
        #NOTE: For now page is a STRING, as in the old version; later we may
        # have start/end fields as integers, for ranges.
        self._page = page
        self._notebook = notebook
        self._oid = oid
        self.dump()

    @classmethod
    def byId(cls, oid):
        query = 'SELECT page, nid, eid FROM occurrences WHERE oid=?'
        d.cursor.execute(query, (oid,))
        page, nid, eid = d.cursor.fetchall()[0]

        entry = entries.Entry.byId(eid)
        notebook = notebooks.Notebook.byId(nid)
        return cls(entry, page, notebook, oid)

    def __eq__(self, other):
        return (self._entry == other._entry and self._page == other._page and
                self._notebook == other._notebook and self._oid == other._oid)
    def __ne__(self, other):
        return not self.__eq__(other)

    def getEntry(self):
        return self._entry
    def getPage(self):
        return self._page
    def getNotebook(self):
        return self._notebook
    def getOid(self):
        return self._oid

    #TODO: error-checking
    def setPage(self, page):
        self._page = page
        self.dump()
    def setEntry(self, entry):
        self._entry = entry
        self.dump()
    def setNotebook(self, notebook):
        self._notebook = notebook
        self.dump()

    def dump(self):
        if self._oid:
            query = 'UPDATE occurrences SET page=?, nid=?, eid=? WHERE oid=?'
            d.cursor.execute(query, (self._page, self._notebook.getNid(),
                    self._entry.getEid(), self._oid))
        else:
            query = 'INSERT INTO occurrences VALUES (null, ?, ?, ?)'
            d.cursor.execute(query, (self._page, self._notebook.getNid(),
                    self._entry.getEid()))
            self._oid = d.cursor.lastrowid
        d.checkAutosave()

def fetchForEntry(entry):
    """
    Return a list of all Occurrences for a given Entry.
    """

    eid = entry.getEid()
    d.cursor.execute('SELECT oid FROM occurrences WHERE eid=?', (eid,))
    return [Occurrence.byId(i[0]) for i in d.cursor.fetchall()]
