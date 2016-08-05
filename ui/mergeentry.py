# -*- coding: utf-8 -*-
# Copyright (c) 2016 Soren Bjornstad <contact@sorenbjornstad.com>

"""
Implementation of selection dialog for Entry -> Merge into... menu choice.
Called from onMergeEntry() in main.
"""

from PyQt5.QtWidgets import QDialog
from ui.forms.mergeentry import Ui_Dialog

import db.consts
import db.entries
import db.occurrences
import ui.utils

class MergeEntryDialog(QDialog):
    """
    Dialog presenting the entry that occurrences are being moved from and
    asking the user to type the name of the entry that occurrences are being
    moved to. getTo() is used to fetch the user's input once the dialog is
    accepted, as suggested here:

    http://stackoverflow.com/questions/5760622/pyqt4-create-a-custom-dialog-that-returns-parameters
    """
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent
        self.form.mergeButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)
        self.moveOcc = None

    def setFrom(self, entry):
        self.curEntry = entry
        self.form.fromBox.setText(entry.getName())

    def setTitle(self, title):
        self.setWindowTitle(title)

    def setMoveSingleOccurrence(self, occ):
        """
        Change the dialog so that it moves only one occurrence occ rather than
        all of an entry's occurrences.
        """
        self.moveOcc = occ

    def accept(self):
        newEntryName = self.form.toBox.text()
        newEntry = db.entries.findOne(newEntryName)
        if not newEntry:
            #TODO: offer a move instead
            ui.utils.errorBox(
                "You can't merge into the entry '%s', because it does not "
                "exist." % newEntryName, "Cannot merge entry")
            return
        if newEntryName == self.curEntry.getName():
            ui.utils.errorBox("You can't merge an entry into itself!",
                              "Cannot merge entry")
            return

        if self.moveOcc:
            occs = (self.moveOcc,)
        else:
            occs = db.occurrences.fetchForEntry(self.curEntry)

        if self.form.leaveRedirectCheck.isChecked():
            _mergeOccurrences(occs, self.curEntry, newEntry, True, occs[0])
        else:
            _mergeOccurrences(occs, self.curEntry, newEntry)
        db.entries.deleteOrphaned()
        super(MergeEntryDialog, self).accept()

def _mergeOccurrences(occs, curEntry, newEntry,
                      leaveRedirect=False, redirectFromOcc=None):
    """
    Move an iterable of occurrences from curEntry to newEntry.
    If leaveRedirect, leave a redirect from curEntry to newEntry, placed
    in the volume of the occurrence redirectFromOcc.
    """
    for occ in occs:
        if occ.getRef() == (newEntry.getName(),
                            db.consts.refTypes['redir']):
            # this is a redirect to the entry we're moving it to; ignore it
            occ.delete()
            continue
        try:
            occ.setEntry(newEntry)
        except db.occurrences.DuplicateError:
            # a comparable one is there already
            occ.delete()

    if leaveRedirect:
        assert redirectFromOcc is not None, \
            "leaveRedirect requires redirectFromOcc to be specified"
        # TODO: If we can have volumeless redirects that would be better
        # than using the last occurrence there now...
        db.occurrences.Occurrence.makeNew(
            curEntry, redirectFromOcc.getVolume(), newEntry.getName(),
            db.consts.refTypes['redir'])

class MoveOccurrenceDialog(MergeEntryDialog):
    """
    Dialog allowing occurrences to be moved between entries. A very similar
    situation, so the same dialog slightly modified is used.
    """
    def __init__(self, parent):
        super(MoveOccurrenceDialog, self).__init__(parent)
        self.form.fromLabel.setText("M&ove")
        self.form.toLabel.setText("&To")
        self.form.mergeButton.setText("&Move")
        self.setWindowTitle("Move Occurrence to Entry")
        self.form.leaveRedirectCheck.setToolTip(
            "Add a redirect pointing to the To entry to the From entry.")
