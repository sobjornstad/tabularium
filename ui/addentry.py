# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QDialog, QLineEdit, QFocusEvent
import forms.newentry

import utils
import ui.addoccurrence

import db.entries
import db.consts

class FocusGrabberField(QLineEdit):
    def __init__(self, parent=None):
        super(FocusGrabberField, self).__init__(parent)

    def focusInEvent(self, event):
        #self.window().maybeTransformSortKey()
        QLineEdit.focusInEvent(self, QFocusEvent(QtCore.QEvent.FocusIn))

class AddEntryWindow(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = forms.newentry.Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent

        self.initializeSortKeyCheck()
        self.form.nameBox.textChanged.connect(self.maybeUpdateSortKey)
        self.form.unclassifiedButton.setChecked(True)

        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)
        self.form.copyButton.clicked.connect(self.onCopy)
        self.form.washButton.clicked.connect(self.maybeTransformSortKey)

    def initializeSortKeyCheck(self, value=""):
        """
        Get the stored value of the name/sort key into sync. See
        maybeUpdateSortKey().
        """
        self.oldName = value
        self.form.nameBox.setText(value)
        self.form.sortKeyBox.setText(value)

    def maybeUpdateSortKey(self):
        """
        If name (self.oldName) was previously equivalent to the sort key,
        update the sort key to match, so that user doesn't have to fill in the
        sort key unless it's actually different than the name. Changing the
        sort key will thus break the autofill link.
        """
        currentSort = unicode(self.form.sortKeyBox.text())
        newName = unicode(self.form.nameBox.text())
        if self.oldName == currentSort:
            self.form.sortKeyBox.setText(newName)
        self.oldName = newName # update oldName regardless

    def maybeTransformSortKey(self):
        nameEntered = unicode(self.form.sortKeyBox.text())
        sk = db.entries.sortKeyTransform(nameEntered)
        self.form.sortKeyBox.setText(sk)

    def onCopy(self):
        self.form.sortKeyBox.setText(self.form.nameBox.text())

    def accept(self):
        """
        Add new entry to the database and open the add occurrences window,
        passing in the new Entry. If the entry already exists, indicate as such
        and open the add occurrences window without touching the db, passing in
        the existing Entry.
        """

        newName = unicode(self.form.nameBox.text())
        existingEntry = db.entries.find(newName)
        if existingEntry:
            utils.informationBox("Entry already exists; adding occurrences.",
                    "Entry exists")
            entry = existingEntry
        else:
            newSk = unicode(self.form.sortKeyBox.text())
            classif = self._getSelectedClassif()
            entry = db.entries.Entry.makeNew(newName, newSk, classif)

        super(AddEntryWindow, self).accept()
        ac = ui.addoccurrence.AddOccWindow(self, entry)
        ac.exec_()


    def _getSelectedClassif(self):
        """
        Return the classification number for the radio button that is currently
        selected. Radio buttons use the cKey dynamic property to hold the key
        in the entryTypes dictionary corresponding to the classification number.

        For example, the "Ordinary" radio button has a cKey of 'ord' listed in
        the designer, and 'ord' has a value of 1 in consts.entryTypes, so this
        function will return 1 if the "Ordinary" button is currently selected.

        Raises an AssertionError if no radio button is selected -- unclassified
        should be selected when the dialog box is inited, so this should not be
        possible.
        """

        sf = self.form
        for i in (sf.ordinaryButton, sf.personButton, sf.placeButton,
                  sf.quotationButton, sf.titleButton, sf.unclassifiedButton):
            if i.isChecked() == True:
                return db.consts.entryTypes[unicode(i.property('cKey').toString())]
        assert False, "No radio button selected!"
