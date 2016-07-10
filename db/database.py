# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import pickle
import re
import sqlite3 as sqlite
import time
import sys

connection = None
cursor = None
lastSavedTime = None
saveInterval = 60


def connect(fname, autosaveInterval=60):
    global connection, cursor, lastSavedTime, saveInterval
    connection = sqlite.connect(fname)
    #connection.text_factory = str # fix for weird Unicode error (not in 3?)
    cursor = connection.cursor()
    lastSavedTime = time.time()
    saveInterval = autosaveInterval
    regexSetup()
def openDbConnect(conn):
    """
    This function pulls an open connection into the database module's namespace
    for access by other parts of the program. This is useful in cases like
    running tests by creating a database in RAM (such that you can't run
    create_database separately and then reopen the connection).

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

def regexSetup():
    # http://stackoverflow.com/questions/5071601/
    # how-do-i-use-regex-in-a-sqlite-query
    def regexMatch(expr, item):
        # note: use .search(), not match, or it searches only at start of str
        return re.search(expr, item) is not None
    connection.create_function("REGEXP", 2, regexMatch)

def close():
    forceSave()
    connection.close()

def checkAutosave(thresholdSeconds=None):
    if thresholdSeconds == None:
        thresholdSeconds = saveInterval

    global lastSavedTime
    now = time.time()
    if now - lastSavedTime > thresholdSeconds:
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
def makeDatabase(fname):
    connection = sqlite.connect(fname)
    cursor = connection.cursor()
    cursor.execute('CREATE TABLE occurrences (oid INTEGER PRIMARY KEY, eid INTEGER, vid INTEGER, ref TEXT, type INTEGER, dEdited TEXT, dAdded TEXT)')
    cursor.execute('CREATE TABLE entries (eid INTEGER PRIMARY KEY, name TEXT, sortkey TEXT, classification INTEGER, dEdited TEXT, dAdded TEXT)')
    cursor.execute('CREATE TABLE sources (sid INTEGER PRIMARY KEY, name TEXT, volval TEXT, pageval TEXT, nearrange INTEGER, abbrev TEXT, stype INTEGER)')
    cursor.execute('CREATE TABLE volumes (vid INTEGER PRIMARY KEY, sid INTEGER, num INTEGER, notes TEXT, dopened TEXT, dclosed TEXT)')
    cursor.execute('CREATE TABLE conf (conf TEXT)')
    cursor.execute('INSERT INTO conf (conf) VALUES (?)', (pickle.dumps({}),))
    connection.commit()
    return connection

if __name__ == "__main__":
    print("Create New Indexer DB - Interactive Interface")
    DATABASE = input("Type the name of the new DB to init: ")
    makeDatabase(DATABASE)
