# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import db.database as d

class DuplicateError(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "That notebook already exists."

class Notebook(object):
    def __init__(self, ntype, nnum, dopened, dclosed, nid=None):
        self._ntype = ntype
        self._nnum = nnum
        self._dopened = dopened
        self._dclosed = dclosed
        self._nid = nid
        self.dump()

    def __eq__(self, other):
        return (self._ntype == other._ntype and self._nnum == other._nnum and
                self._dopened == other._dopened and
                self._dclosed == other._dclosed and
                self._nid == other._nid)
    def __ne__(self, other):
        return not self.__eq__(other)

    def getType(self):
        return self._ntype
    def getNum(self):
        return self._nnum
    def getDOpened(self):
        return self._dopened
    def getDClosed(self):
        return self._dclosed
    def getNid(self):
        return self._nid

    def setDOpened(self, date):
        #TODO: validate here!
        self._dopened = date
        self.dump()
    def setDClosed(self, date):
        self._dclosed = date
        self.dump()
    # may be reasonable to implement number change, but notebook db structure
    # is likely going to change somewhat before this is over, so I'm not going
    # to bother to do those now.

    def dump(self):
        if self._nid:
            d.cursor.execute('UPDATE notebooks SET ntype=?, nnum=?, ' \
                    'dopened=?, dclosed=? WHERE nid=?',
                    (self._ntype, self._nnum, self._dopened, self._dclosed,
                    self._nid))
        else:
            #TODO: look out for duplicate entries here. Not likely, but bad.
            d.cursor.execute('INSERT INTO notebooks VALUES (null, ?, ?, ?, ?)',
                    (self._ntype, self._nnum, self._dopened, self._dclosed))
            self._nid = d.cursor.lastrowid
        d.checkAutosave()

    # to initialize an object for a notebook we have the nid of already
    @classmethod
    def byId(cls, nid):
        d.cursor.execute('SELECT ntype, nnum, dopened, dclosed FROM notebooks'\
                ' WHERE nid=?', (nid,))
        ntype, nnum, dopened, dclosed = d.cursor.fetchall()[0]
        return cls(ntype, nnum, dopened, dclosed, nid)
