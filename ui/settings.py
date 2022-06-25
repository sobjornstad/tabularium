# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

"""
Personal Indexer preferences managers

This module for the Personal Indexer UI contains two classes:

SettingsHandler :: a QObject used as a convenient interface to get and set
    settings stored in the database
PreferencesWindow :: implements the dialog displayed on Edit -> Preferences.

There is also saveDbLocation() and getDbLocation(), which use QSettings to
store the path to the last-used database. Obviously this info can't be stored
in the normal settings handler, since we can't access the settings stored in
the database before we've found the database.
"""

import pickle
from passlib.hash import pbkdf2_sha256 as pbkdf

from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import QObject, QSettings
from ui.forms.prefs import Ui_Dialog

from db.database import d

dateOrder = ('Jun 1, 2016', '1 Jun 2016', '6/1/16', '1/6/16', '2016-06-01')
dateOptions = {'Jun 1, 2016' : 'MMM d, yyyy',
               '1 Jun 2016'  : 'd MMM yyyy',
               '6/1/16'      : 'M/d/yy',
               '1/6/16'      : 'd/M/yy',
               '2016-06-01'  : 'yyyy-MM-dd',
               }
dateOptionsReversed = dict((v, k) for k, v in dateOptions.items())

class PreferencesWindow(QDialog):
    """
    Code to save and retrieve preferences in the preference dialog. Requires an
    instance of SettingsHandler (also in this file) passed to the constructor
    to access the settings; the main window (which launches the preferences
    window) should have one of those handy.

    This class should be quite self-explanatory.
    """
    DUMMYPASSWORD = '*' * 8 # used to fill the pw field if not edited by user
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
        self._fillDateCombo()

    def onPwToggle(self):
        passwordEnabled = self.form.passwordCheck.isChecked()
        self.form.passwordBox.setEnabled(passwordEnabled)
        self.form.passwordlessTpeekCheck.setEnabled(passwordEnabled)

    def _fillDateCombo(self):
        for i in dateOrder:
            self.form.dateCombo.addItem(i)
        curFormat = dateOptionsReversed[self.sh.get('dateFormat')]
        i = self.form.dateCombo.findText(curFormat)
        self.form.dateCombo.setCurrentIndex(i)

    def accept(self):
        "Save the settings back to the db, if changed."
        if self.form.passwordCheck.isChecked():
            newPw = self.form.passwordBox.text()
            if newPw != self.DUMMYPASSWORD:
                # i.e., user changed the "password" we put in the box.
                # Mostly academic note: this prevents the user from using the
                # literal password '********' (which is such a dreadful
                # password anyway that that's maybe a good limitation!).
                newHash = pbkdf.encrypt(newPw, rounds=10000, salt_size=16)
                self.sh.put('password', newHash)
        else:
            self.sh.put('password', '')

        dateOpt = dateOptions[self.form.dateCombo.currentText()]
        self.sh.put('dateFormat', dateOpt)
        self.mw._resetDateFormat(dateOpt)

        super(PreferencesWindow, self).accept()

    def reject(self):
        super(PreferencesWindow, self).reject()


class SettingsHandler(QObject):
    """
    This class, often instantiated as 'sh', can be used to get and set various
    settings. Settings are always key-value pairs, and are stored in a
    dictionary within the class and pickled into the database in the one-cell
    table 'conf', which has one row on database creation so that we can read
    from and write to it.
    """
    def __init__(self, mw):
        QObject.__init__(self)
        self.mw = mw
        self.conf = None
        self.loadDb()

    def exists(self, key):
        """Return True if /key/ is defined in the configuration."""
        return key in self.conf

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
        """
        (Re)load configuration from the database. This method is automatically
        called by the constructor, and it is rare to need to call it manually.
        """
        d().cursor.execute('SELECT conf FROM conf')
        try:
            self.conf = pickle.loads(d().cursor.fetchall()[0][0])
        except (EOFError, TypeError):
            # no configuration initialized
            self.conf = {}

    def sync(self):
        "Write current dictionary state out to the database."
        d().cursor.execute('UPDATE conf SET conf=?', (pickle.dumps(self.conf),))
        d().checkAutosave()


def checkPassword(password, conf):
    """
    Check if the /password/ matches the one in conf; return True if yes, False
    if no. Return True if no password is set in the database.
    """
    if conf.get('password'):
        return pbkdf.verify(password, conf.get('password'))
    else:
        return True

def saveDbLocation(loc):
    "Write path to last-used database to system config area."
    qs = QSettings("562 Software", "Tabularium")
    qs.setValue("lastDatabaseLocation", loc)
    qs.sync()

def getDbLocation():
    "Read path to last-used database from system config area."
    qs = QSettings("562 Software", "Tabularium")
    val = qs.value("lastDatabaseLocation", "None")
    return None if val == "None" else val
