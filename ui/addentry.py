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
    """
    This subclass, used for the sort key box, does nothing at the moment, but I
    may want to add an "autowash" option in the future; that was the original
    motivation.

    I'm very amused that I ended up with 'window().wash()'.
    """

    def __init__(self, parent=None):
        super(FocusGrabberField, self).__init__(parent)

    def focusInEvent(self, event):
        #self.window().wash()
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
        self.preparedOccurrence = None
        self.isEditing = False

        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)
        self.form.copyButton.clicked.connect(self.onCopy)
        self.form.washButton.clicked.connect(self.wash)

    def putClassification(self, entry):
        """
        Called if modifying/basing on an existing entry; finds the
        corresponding entry and determines its classification.
        """
        classification = entry.getClassification()
        sf = self.form
        for i in (sf.ordinaryButton, sf.personButton, sf.placeButton,
                  sf.quotationButton, sf.titleButton, sf.unclassifiedButton):
            if db.consts.entryTypes[unicode(i.property('cKey').toString())] == \
                    classification:
                i.setChecked(True)

    def putRedirect(self, to):
        self.putClassification(to)
        name = to.getName().replace(',', '\\,')
        self.preparedOccurrence = " {see " + name + "}"

    def setEditing(self):
        self.isEditing = True
        self.beforeEditingName = unicode(self.form.nameBox.text())
        self.form.addButton.setText("S&ave")

    def resetTitle(self, title):
        self.setWindowTitle(title)

    def initializeSortKeyCheck(self, value="", skValue=""):
        """
        Get the stored value of the name/sort key into sync. See
        maybeUpdateSortKey().
        """
        self.oldName = value
        self.form.nameBox.setText(value)
        self.form.sortKeyBox.setText(skValue if skValue else value)

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

    def wash(self):
        nameEntered = unicode(self.form.sortKeyBox.text())
        sk = db.entries.sortKeyTransform(nameEntered)
        self.form.sortKeyBox.setText(sk)

    def onCopy(self):
        self.form.sortKeyBox.setText(self.form.nameBox.text())

    def accept(self):
        """
        Add new entry to the database and open the add occurrences window,
        passing in the new Entry.

        If the entry already exists:
            if not self.isEditing - indicate as such and open the add
                occurrences window without touching the db, passing in the
                existing Entry.
            otherwise - update the existing Entry with the new content, and
                do not open the add occurrences window.
        """


        newName = unicode(self.form.nameBox.text()).strip()
        newSk = unicode(self.form.sortKeyBox.text()).strip()
        classif = self._getSelectedClassif()

        if self.isEditing:
            entryToEdit = db.entries.find(self.beforeEditingName)[0]
            entryToEdit.setName(newName)
            entryToEdit.setSortKey(newSk)
            entryToEdit.setClassification(classif)
            super(AddEntryWindow, self).accept()
        else:
            existingEntry = db.entries.find(newName)
            if not existingEntry:
                entry = db.entries.Entry.makeNew(newName, newSk, classif)
            else:
                utils.informationBox("Entry already exists; adding occurrences.",
                        "Entry exists")
                entry = existingEntry[0]
            ac = ui.addoccurrence.AddOccWindow(self, entry,
                                               self.preparedOccurrence)
            super(AddEntryWindow, self).accept()
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
