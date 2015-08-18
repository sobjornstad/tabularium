# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt4.QtCore import QObject, QEvent
from forms.main import Ui_MainWindow

import pickle
import db.database as d

class SettingsHandler(QObject):
    def __init__(self, mw):
        self.mw = mw
        self.conf = None
        self.loadDb()

    def exists(self, key):
        """Return True if /key/ is defined in the configuration."""
        return self.conf.has_key(key)

    def get(self, key):
        """Return the value of /key/, or None if key doesn't exist."""
        return self.conf.get(key, None)

    def put(self, key, value):
        """
        Update internal configuration model with the new value /value/ for
        /key/. Since many put()s are often called in a row, you must explicitly
        call sync() to update the database with the changes.
        """
        if self.get(key) != value:
            self.conf[key] = value

    def loadDb(self):
        d.cursor.execute('SELECT conf FROM conf')
        try:
            self.conf = pickle.loads(d.cursor.fetchall()[0][0])
        except EOFError:
            # no configuration initialized
            self.conf = {}

    def sync(self):
        """
        Write current dictionary state out to the database.
        """
        d.cursor.execute('UPDATE conf SET conf=?', (pickle.dumps(self.conf),))
        d.checkAutosave()
