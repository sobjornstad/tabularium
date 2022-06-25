"""
database.py - simple interface to the Tabularium database
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>

import pickle
import re
import sqlite3 as sqlite
import time

# pylint: disable=invalid-name

connection = None
# Ignoring that these can have type None prior to initialization is a little ugly,
# but it seems excessive to add helper functions to assert these are not None
# and have to call them every time we use them rather than simply using module globals.
cursor: sqlite.Cursor = None # type: ignore
lastSavedTime: float = None # type: ignore
saveInterval: int = 60


def connect(fname: str, autosaveInterval: int = 60):
    """
    Open a connection to a database on disk. This connection will then be used
    throughout the rest of the application.
    """
    global connection, cursor, lastSavedTime, saveInterval
    connection = sqlite.connect(fname)
    cursor = connection.cursor()
    lastSavedTime = time.time()
    saveInterval = autosaveInterval
    regexSetup()
    editDistSetup()


def openDbConnect(conn):
    """
    This function pulls an open connection into the database module's namespace
    for access by other parts of the program. This is useful in cases like
    running tests by creating a database in RAM (such that you can't run
    create_database separately and then reopen the connection).

    It is an alternative to connect().

    Example:
        >>> conn = db.tools.create_database.makeDatabase(':memory:')
        >>> db.database.openDbConnect(conn)
        >>> db.database.connection.commit()
    """
    global connection, cursor, lastSavedTime
    connection = conn
    cursor = connection.cursor()
    lastSavedTime = time.time()
    regexSetup()
    editDistSetup()


def regexSetup():
    """
    Configure SQLite to allow regex queries.

    <http://stackoverflow.com/questions/5071601/how-do-i-use-regex-in-a-sqlite-query>
    """
    def regexMatch(expr, item):
        # note: use .search(), not match, or it searches only at start of str
        return re.search(expr, item) is not None
    connection.create_function("REGEXP", 2, regexMatch)


def editDistSetup():
    print("setting up exetinsons")
    connection.enable_load_extension(True)
    connection.load_extension('distlib/distlib_64.so')


def close():
    forceSave()
    connection.close()


def checkAutosave(thresholdSeconds: int = None):
    "Check if it's time to autosave."
    assert connection is not None, "Checked autosave before connection was opened."
    useThreshold: int = (thresholdSeconds
                         if thresholdSeconds is not None
                         else saveInterval)

    global lastSavedTime
    now = time.time()
    if now - lastSavedTime > useThreshold:
        connection.commit()
        lastSavedTime = time.time()
        return True
    else:
        return False

def forceSave():
    """Force a commit and update last save time."""
    global lastSavedTime
    connection.commit()
    lastSavedTime = time.time()


#### to be called without a database open ####
def makeDatabase(fname: str):
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
