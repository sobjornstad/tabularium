# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

"""
Add/Edit entry dialog implementation

This dialog allows the user to add entries to her database, or to edit existing
ones. The developer is referred to the documentation for the AddEntryWindow
class, which is the entire contents of this module.
"""

from PyQt5.QtWidgets import QDialog

import ui.addoccurrence
import ui.forms.newentry
import ui.utils as utils
from db.consts import entryTypes
import db.entries

class AddEntryWindow(QDialog):
    """
    Implementation of the add entry dialog. There are a number of ways this
    dialog can be used:

    * Adding a completely new entry freeform. This is the default and requires
      only instantiating the window before calling exec_().

    * Editing an existing entry. Before calling exec_(), run .setEditing(). You
      may also want to use .resetTitle() so the dialog title doesn't say "add
      entry".

    * Creating a redirect to an existing entry. This actually has no impact on
      the add entry dialog, but it does have an impact on the add *occurrence*
      dialog, which is automatically started when the add entry dialog is
      accepted. Therefore, you can use .putRedirect() to store the entry that
      the redirect is to, and this dialog will pass that through to the
      AddOccurrence dialog. Again, you may want to use .resetTitle() as well.

    * Basing a new entry on an existing entry. This is the most complicated:
      - Create an instance of AddEntryWindow.
      - Manually call .initializeSortKeyCheck() (normally handled by the
        constructor) with the /value/ and /skvalue/ optional arguments.
      - Call .putClassification() with the classification type of the entry
        that's being based on.
      - Optionally, change the dialog title with .resetTitle().

    As noted in the above, if the user accepts the add entry dialog, the add
    occurrence dialog will be opened to add some occurrences to the new entry.
    It is the add occurrence dialog's responsibility to delete the entry if
    that dialog is rejected so we're not left with an entry with no
    occurrences.
    """

    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = ui.forms.newentry.Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent

        self.skManual = False # whether user has manually changed sk
        self.preparedOccurrence = None # see .putRedirect()
        self.beforeEditingName = None # see .setEditing()
        self.isEditing = False # see .setEditing()
        self.initializeSortKeyCheck()

        self.form.nameBox.textEdited.connect(self.maybeUpdateSortKey)
        self.form.sortKeyBox.textEdited.connect(self.sortKeyManuallyChanged)
        self.form.unclassifiedButton.setChecked(True)
        self.form.autoButton.setChecked(True)
        self.form.autoButton.clicked.connect(self.onAuto)

        sf = self.form
        self.allRadios = (sf.ordinaryButton, sf.personButton,
                          sf.placeButton, sf.quotationButton,
                          sf.titleButton, sf.unclassifiedButton)
        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)

    def putClassification(self, entry):
        """
        Called if modifying/basing on an existing entry; finds the
        corresponding entry and determines its classification.
        """
        for i in self.allRadios:
            if entryTypes[i.property('cKey')] == entry.classification:
                i.setChecked(True)

    def putRedirect(self, to):
        """
        Tell the dialog to pass some text through to the add occurrence dialog
        when it is called, so that the user can run an "add entry redirecting
        to" menu choice and have the entry being redirected to automatically
        placed in the add occurrence dialog when it comes up.
        """
        self.putClassification(to)
        name = to.name.replace(';', '\\;')
        self.preparedOccurrence = " see " + name

    def setEditing(self):
        """
        Called prior to exec_() to specify that we want to use this dialog to
        edit an entry rather than creating an entirely new one.
        """
        self.isEditing = True
        # We need beforeEditingName so that we can still find the entry we're
        # editing after its text has changed, as we don't have an Entry
        # object handy.
        self.beforeEditingName = self.form.nameBox.text()
        self.form.addButton.setText("S&ave")

    def resetTitle(self, title):
        "Change the title of the window, prior to exec_()."
        self.setWindowTitle(title)

    def initializeSortKeyCheck(self, value="", skValue=""):
        """
        Get the stored value of the name/sort key into sync. See
        maybeUpdateSortKey().
        """
        self.form.nameBox.setText(value)
        self.form.sortKeyBox.setText(skValue if skValue else value)

    def maybeUpdateSortKey(self):
        """
        If the sort key has not been manually edited, update the sort key to
        match, so that user doesn't have to fill in the sort key unless it's
        actually different than the name. Changing the sort key will break the
        autofill link.
        """
        if not self.skManual:
            self._autoSortKey()

    def sortKeyManuallyChanged(self):
        """
        If the user manually changes the sort key text, deactivate automatic
        sort key generation.
        """
        self.form.autoButton.setChecked(False)
        self.onAuto()

    def onAuto(self):
        if self.form.autoButton.isChecked():
            self.skManual = False
            self.form.autoButton.setChecked(True)
            self._autoSortKey()
        else:
            self.skManual = True
            self.form.autoButton.setChecked(False)

    def _autoSortKey(self):
        """
        Modify the "sort key" textbox to hold a cleaned version of its text.
        See db.entries.sortKeyTransform() for more information about this
        function and the transformation.
        """
        self.form.sortKeyBox.setText(self.form.nameBox.text())
        nameEntered = self.form.sortKeyBox.text()
        if not nameEntered:
            # presumably user meant for the sort key to be the same
            nameEntered = self.form.nameBox.text()
        sk = db.entries.sortKeyTransform(nameEntered)
        self.form.sortKeyBox.setText(sk)
        self.skManual = False

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
        newName = self.form.nameBox.text().strip()
        newSk = self.form.sortKeyBox.text().strip()
        if not newSk:
            # presumably user meant for the sort key to be the same
            newSk = newName
        classif = self._getSelectedClassif()

        if self.isEditing:
            entryToEdit = db.entries.findOne(self.beforeEditingName)
            #TODO: offer option to merge
            if (newName != self.beforeEditingName
                    and db.entries.nameExists(newName)):
                # need both checks because new and old names may differ only in
                # case, but it's fine to not change the name at all
                utils.errorBox(
                    "That entry already exists, or it differs from an "
                    "existing entry only in its capitalization. Please choose "
                    "a different name, or use the Merge feature.",
                    "Entry exists")
                return
            entryToEdit.name = newName
            entryToEdit.sortKey = newSk
            entryToEdit.classification = classif
            super(AddEntryWindow, self).accept()
        else:
            existingEntry = db.entries.findOne(newName)
            if not existingEntry:
                entry = db.entries.Entry.makeNew(newName, newSk, classif)
            else:
                utils.informationBox("Entry already exists; adding "
                                     "occurrences.", "Entry exists")
                entry = existingEntry
            ac = ui.addoccurrence.AddOccWindow(self, entry,
                                               self.preparedOccurrence)
            super(AddEntryWindow, self).accept()
            ac.exec_()

    def _getSelectedClassif(self):
        """
        Return the classification number for the radio button that is currently
        selected. Radio buttons use the cKey dynamic property to hold the key
        in the entryTypes dictionary corresponding to the classification
        number.

        For example, the "Ordinary" radio button has a cKey of 'ord' listed in
        the designer, and 'ord' has a value of 1 in consts.entryTypes, so this
        function will return 1 if the "Ordinary" button is currently selected.

        Raises an AssertionError if no radio button is selected -- unclassified
        should be selected when the dialog box is inited, so this should not be
        possible.
        """

        for i in self.allRadios:
            if i.isChecked():
                return entryTypes[i.property('cKey')]
        assert False, "No radio button selected!"
