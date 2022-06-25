"""
database.py - simple interface to the Tabularium database
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>

from __future__ import annotations
from contextlib import contextmanager
import pathlib

import os
import pickle
import re
import sqlite3 as sqlite
import threading
import time
from typing import Dict, Generator, Optional, overload, Union

# pylint: disable=invalid-name

_globalConnection: Optional[DatabaseConnection] = None
_auxiliaryConnections: Dict[int, DatabaseConnection] = {}

class DatabaseConnection:
    """
    Connection to the Tabularium SQLite database. Wrapper around sqlite3.Connection.
    """
    @overload
    def __init__(self, fnameOrConn: str, autosaveInterval: int = 60) -> None: ...
    @overload
    def __init__(self, fnameOrConn: sqlite.Connection,
                 autosaveInterval: int = 60) -> None: ...
    def __init__(self, fnameOrConn: Union[str, sqlite.Connection],
                 autosaveInterval: int = 60) -> None:
        if isinstance(fnameOrConn, sqlite.Connection):
            self.connection = fnameOrConn
            self.location = None
        else:
            self.connection = sqlite.connect(fnameOrConn)
            self.location = fnameOrConn

        self.cursor: sqlite.Cursor = self.connection.cursor() # type: ignore
        self.lastSavedTime: float = time.time() # type: ignore
        self.saveInterval = autosaveInterval

        self.regexSetup()
        self.editDistSetup()

    def regexSetup(self) -> None:
        """
        Configure SQLite to allow regex queries.

        <http://stackoverflow.com/questions/5071601/how-do-i-use-regex-in-a-sqlite-query>
        """
        def regexMatch(expr, item):
            # note: use .search(), not match, or it searches only at start of str
            return re.search(expr, item) is not None
        self.connection.create_function("REGEXP", 2, regexMatch)

    def editDistSetup(self) -> None:
        """
        Configure SQLite to load bundled edit distance extensions.
        Do nothing if the extensions are not available.

        TODO: We should check for the existence of the extensions when
        calling them elsewhere.
        """
        EXTENSION_PATH = 'distlib/distlib_64.so'
        if os.path.exists(EXTENSION_PATH):
            self.connection.enable_load_extension(True)
            self.connection.load_extension(EXTENSION_PATH)

    def close(self) -> None:
        "Close this connection."
        self.forceSave()
        self.connection.close()

    def checkAutosave(self, thresholdSeconds: int = None) -> bool:
        """
        Check if it's time to autosave and do so if needed. Return True if we saved.
        """
        assert self.connection is not None, \
            "Checked autosave before connection was opened."
        useThreshold: int = (thresholdSeconds
                             if thresholdSeconds is not None
                             else self.saveInterval)

        now = time.time()
        if now - self.lastSavedTime > useThreshold:
            self.connection.commit()
            self.lastSavedTime = time.time()
            return True
        else:
            return False

    def forceSave(self):
        """Force a save now and update last save time."""
        self.connection.commit()
        self.lastSavedTime = time.time()


def installGlobalConnection(conn: DatabaseConnection) -> None:
    """
    Set the global database connection to the database at /fname/.
    """
    global _globalConnection
    _globalConnection = conn


def d() -> DatabaseConnection:
    """
    Return the global database connection, or an auxiliary connectioni
    if one has been configured for the current thread.
    """
    threadId = threading.current_thread().ident
    if threadId in _auxiliaryConnections:
        return _auxiliaryConnections[threadId]
    else:
        assert _globalConnection is not None, \
            "Tried to access database before initialization"
        return _globalConnection


@contextmanager
def auxiliaryConnection(readOnly: bool = True) -> Generator[None, None, None]:
    """
    Create and return a temporary connection to be used in a background thread,
    as a context manager. The connection will be closed once the context is exited,
    but changes will NOT be committed -- you must do that yourself if necessary.

    By default, the auxiliary connection is read-only for safety; you can change
    this with the optional readOnly argument if you need to write within the
    background thread.

    Note that this will not work if the global connection wasn't opened on a
    filename, for instance on in-memory tests, as it's not possible to open
    multiple connections to an in-memory database.  Attempting such a connection
    will raise an AssertionError. (Even if it's not in-memory, we don't know the
    location and hence can't use this function; we could possibly fix this, but
    presently the only time we don't open with a filename is in-memory
    databases, so it doesn't seem worth it right now.)
    """
    assert _globalConnection is not None, \
        "Tried to create auxiliary connection before main connection initialization"
    assert _globalConnection.location is not None, \
        "Cannot create an auxiliary connection to a connection without a filename"
    try:
        fileUri = pathlib.Path(_globalConnection.location).as_uri()
        if readOnly:
            fileUri += '?mode=ro'
        sqliteConn = sqlite.connect(fileUri, uri=True)
        tabulariumConn = DatabaseConnection(sqliteConn)

        threadId = threading.current_thread().ident
        assert threadId is not None, \
             "Impossible: Currently executing thread has not been started"
        _auxiliaryConnections[threadId] = tabulariumConn
        yield
    finally:
        tabulariumConn.close()


#### to be called without a database open ####
def makeDatabase(fname: str) -> sqlite.Connection:
    """
    Create a new Tabularium database at file /fname/.
    """
    conn = sqlite.connect(fname)
    curs = conn.cursor()
    curs.execute('''CREATE TABLE occurrences (
                        oid INTEGER PRIMARY KEY,
                        eid INTEGER,
                        vid INTEGER,
                        ref TEXT,
                        type INTEGER,
                        dEdited TEXT,
                        dAdded TEXT
                    )''')
    curs.execute('''CREATE TABLE entries (
                        eid INTEGER PRIMARY KEY,
                        name TEXT,
                        sortkey TEXT,
                        classification INTEGER,
                        dEdited TEXT,
                        dAdded TEXT,
                        picture BLOB
                   )''')
    curs.execute('''CREATE TABLE sources (
                        sid INTEGER PRIMARY KEY,
                        name TEXT,
                        volval TEXT,
                        pageval TEXT,
                        nearrange INTEGER,
                        abbrev TEXT,
                        stype INTEGER
                    )''')
    curs.execute('''CREATE TABLE volumes (
                        vid INTEGER PRIMARY KEY,
                        sid INTEGER,
                        num INTEGER,
                        notes TEXT,
                        dopened TEXT,
                        dclosed TEXT
                    )''')
    curs.execute('''CREATE TABLE conf (conf TEXT)''')
    curs.execute('''INSERT INTO conf (conf) VALUES (?)''', (pickle.dumps({}),))
    conn.commit()
    return conn


if __name__ == '__main__':
    print("Create New Indexer DB - Interactive Interface")
    DATABASE = input("Type the name of the new DB to init: ")
    makeDatabase(DATABASE)
