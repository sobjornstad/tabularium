# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QMessageBox, QDialog
from PyQt4.QtCore import QObject, QEvent
from forms.prefs import Ui_Dialog
from passlib.hash import pbkdf2_sha256 as pbkdf

import pickle
import db.database as d

class PreferencesWindow(QDialog):
    DUMMYPASSWORD = '*' * 8
    def __init__(self, mw, sh):
        QDialog.__init__(self)
        self.mw = mw
        self.sh = sh
        self.form = Ui_Dialog()
        self.form.setupUi(self)

        self.form.okButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)

        self.form.passwordCheck.toggled.connect(self.onPwToggle)
        pw = self.sh.get('password')
        self.form.passwordCheck.setChecked(True if pw else False)
        if pw:
            self.form.passwordBox.setText(self.DUMMYPASSWORD)
        self.onPwToggle()

    def onPwToggle(self):
        self.form.passwordBox.setEnabled(self.form.passwordCheck.isChecked())

    def accept(self):
        if self.form.passwordCheck.isChecked():
            newPw = unicode(self.form.passwordBox.text())
            if newPw != self.DUMMYPASSWORD:
                # i.e., user changed the "password" we put in the box
                newHash = pbkdf.encrypt(newPw, rounds=10000, salt_size=16)
                self.sh.put('password', newHash)
        else:
            self.sh.put('password', '')
        super(PreferencesWindow, self).accept()

    def reject(self):
        super(PreferencesWindow, self).reject()

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
