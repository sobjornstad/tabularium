"""
database.py - simple interface to the Tabularium database
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>

from __future__ import annotations

from contextlib import contextmanager
import os
import pathlib
import pickle
import re
import sqlite3 as sqlite
import threading
import time
from typing import Callable, Dict, Generator, Optional, Sequence, Tuple, overload, Union

CURRENT_SCHEMA_VERSION = 1

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

    @property
    def schemaVersion(self) -> int:
        "Current version of the database schema the current database is using."
        self.cursor.execute('SELECT conf FROM conf')
        conf = pickle.loads(self.cursor.fetchone()[0])
        return conf.get('schemaVersion', 0)
    @schemaVersion.setter
    def schemaVersion(self, version: int) -> None:
        "Set the schema version of the database."
        self.cursor.execute('SELECT conf FROM conf')
        conf = pickle.loads(self.cursor.fetchone()[0])
        conf['schemaVersion'] = version
        self.cursor.execute('UPDATE conf SET conf = ?',
                            (pickle.dumps(conf),))
        self.connection.commit()

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


#### Database creation and upgrade ####
def makeDatabase(fname: str) -> sqlite.Connection:
    """
    Create a new Tabularium database at file /fname/.
    """
    conn = sqlite.connect(fname)
    curs = conn.cursor()
    x = curs.execute

    x('''CREATE TABLE entries (
             eid INTEGER PRIMARY KEY,
             name TEXT,
             sortkey TEXT,
             classification INTEGER,
             dEdited TEXT,
             dAdded TEXT,
             picture BLOB
         )''')
    x('''CREATE INDEX entries_by_name ON entries(name)''')

    x('''CREATE TABLE occurrences (
             oid INTEGER PRIMARY KEY,
             eid INTEGER,
             vid INTEGER,
             ref TEXT,
             type INTEGER,
             dEdited TEXT,
             dAdded TEXT
         )''')
    x('''CREATE INDEX occurrences_by_entry
                   ON occurrences(eid)''')
    x('''CREATE INDEX nearby_occurrences
                   ON occurrences(vid, type)''')

    x('''CREATE TABLE sources (
             sid INTEGER PRIMARY KEY,
             name TEXT,
             volval TEXT,
             pageval TEXT,
             nearrange INTEGER,
             abbrev TEXT,
             stype INTEGER
         )''')

    x('''CREATE TABLE volumes (
             vid INTEGER PRIMARY KEY,
             sid INTEGER,
             num INTEGER,
             notes TEXT,
             dopened TEXT,
             dclosed TEXT
         )''')

    x('''CREATE TABLE conf (conf TEXT)''')
    x('''INSERT INTO conf (conf) VALUES (?)''',
                 (pickle.dumps({'schemaVersion': CURRENT_SCHEMA_VERSION}),))

    x('''CREATE VIRTUAL TABLE entry_fts
         USING fts5(
            name,
            content="entries",
            content_rowid="eid"
        )''')
    x('''CREATE TRIGGER entry_fts_ai AFTER INSERT ON entries
         BEGIN
             INSERT INTO entry_fts (rowid, name)
             VALUES (new.eid, new.name);
         END''')
    x('''CREATE TRIGGER entry_fts_ad AFTER DELETE ON entries
         BEGIN
             INSERT INTO entry_fts (entry_fts, rowid, name)
             VALUES ('delete', old.eid, old.name);
         END''')
    x('''CREATE TRIGGER entry_fts_au AFTER UPDATE ON entries
         BEGIN
             INSERT INTO entry_fts (entry_fts, rowid, name)
             VALUES('delete', old.eid, old.name);
             INSERT INTO entry_fts (rowid, name)
             VALUES (new.eid, new.name);
         END''')

    conn.commit()
    return conn


UpgradeStatusCallback = Callable[[str], None]
Upgrader = Callable[[DatabaseConnection, UpgradeStatusCallback], None]


# pylint: disable=unnecessary-lambda-assignment
def gradePath(
        conn: DatabaseConnection,
        desiredVersion: int,
        statusCallback: UpgradeStatusCallback
    ) -> Sequence[Tuple[Tuple[int, int], Upgrader]]:
    """
    Compute the upgrade or downgrade path from the current version of the connected
    database to the desired version.
    """
    currentVersion = conn.schemaVersion
    if currentVersion == desiredVersion:
        return []
    elif currentVersion < desiredVersion:
        statusCallback(f"Computing upgrade path "
                       f"from {currentVersion} to {desiredVersion}...")
        versionPair = lambda current: (current, current+1)
        searchIn = database_upgrades.UPGRADES
        continueWhile = lambda current, desired: current < desired
        afterStep = lambda current: current + 1
    elif currentVersion > desiredVersion:
        statusCallback(f"Computing downgrade path "
                       f"from {currentVersion} to {desiredVersion}...")
        versionPair = lambda current: (current, current-1)
        searchIn = database_upgrades.DOWNGRADES
        continueWhile = lambda current, desired: current > desired
        afterStep = lambda current: current - 1

    grades = []
    while continueWhile(currentVersion, desiredVersion):
        if upg := searchIn.get(versionPair(currentVersion)):
            grades.append((versionPair(currentVersion), upg))
            currentVersion = afterStep(currentVersion)
    return grades


def upgradeDatabase(conn: DatabaseConnection,
                    statusCallback: UpgradeStatusCallback) -> None:
    """
    Perform all possible upgrades on the database,
    calling statusCallback() with information on each upgrade.
    """
    if path := gradePath(conn, CURRENT_SCHEMA_VERSION, statusCallback):
        statusCallback(f"Database upgrades are required "
                       f"(database is at version {conn.schemaVersion}, "
                       f"application expects version {CURRENT_SCHEMA_VERSION}).")
        for (fromVer, toVer), func in path:
            statusCallback(f"Upgrading schema v{fromVer} -> v{toVer}...")
            func(conn, statusCallback)
            conn.schemaVersion = toVer
        statusCallback(
            f"Database upgrade to version {conn.schemaVersion} complete."
        )


def downgradeDatabase(conn: DatabaseConnection,
                      desiredVersion: int,
                      statusCallback: UpgradeStatusCallback) -> None:
    """
    Downgrade the database to the given version.
    """
    statusCallback(f"A database downgrade to version {desiredVersion} was requested.")
    if path := gradePath(conn, desiredVersion, statusCallback):
        for (fromVer, toVer), func in path:
            statusCallback(f"Downgrading schema v{fromVer} -> v{toVer}...")
            func(conn, statusCallback)
            conn.schemaVersion = toVer
        statusCallback(
            f"Database downgrade to version {conn.schemaVersion} complete."
        )


if __name__ == '__main__':
    import database_upgrades  # pylint: disable=import-error
    print("Create New Indexer DB - Interactive Interface")
    DATABASE = input("Type the name of the new DB to init: ")
    dconn = makeDatabase(DATABASE)
    installGlobalConnection(DatabaseConnection(dconn))
    upgradeDatabase(d(), print)
    downgradeDatabase(d(), 0, print)
else:
    from db import database_upgrades
