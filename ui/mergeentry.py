"""
Implementation of selection dialog for Entry -> Merge into... menu choice.
Called from onMergeEntry() in main.
"""

# Copyright (c) 2016-2022 Soren Bjornstad <contact@sorenbjornstad.com>

from typing import Iterable, Optional

from PyQt5.QtWidgets import QDialog, QWidget

import db.consts
import db.entries
import db.occurrences

from ui.forms.mergeentry import Ui_Dialog
import ui.utils

class MergeEntryDialog(QDialog):
    """
    Dialog allowing the user to merge two entries, or if
    setMoveSingleOccurrence() is called, to move a single occurrence from one
    entry to another.

    Before executing the dialog, setFrom() and setTitle() are called, giving
    the entry that occurrences will be moved from; if moving a single
    occurrence, the call to setMoveSingleOccurrence() specifies which
    occurrence is being moved. The dialog then asks the user what entry to move
    to and executes the move.
    """
    def __init__(self, parent: QWidget) -> None:
        QDialog.__init__(self)
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent
        self.form.mergeButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)
        self.curEntry: Optional[db.entries.Entry] = None
        self.moveOcc: Optional[db.occurrences.Occurrence] = None

    ### Configuration ###
    def setFrom(self, entry: db.entries.Entry) -> None:
        "Configure the dialog with an entry from which occurrences will be moved."
        self.curEntry = entry
        self.form.fromBox.setText(entry.name)
        self.form.toBox.setText(entry.name)
        self.form.toBox.selectAll()
        self.form.toBox.setFocus()

    def setTitle(self, title: str) -> None:
        "Configure the dialog with a window title."
        self.setWindowTitle(title)

    def setMoveSingleOccurrence(self, occ: db.occurrences.Occurrence) -> None:
        """
        Configure the dialog so that it moves only one occurrence rather than
        (as default) all of an entry's occurrences.
        """
        self.form.fromLabel.setText("M&ove")
        self.form.toLabel.setText("&To")
        self.form.mergeButton.setText("&Move")
        self.form.leaveRedirectCheck.setToolTip(
            "Add a redirect pointing to the To entry to the From entry.")
        self.moveOcc = occ

    def setTo(self, entryName: str) -> None:
        """
        Configure the dialog with initial text of an entry to which
        occurrences will be moved.
        """
        self.form.toBox.setText(entryName)
        self.form.toBox.selectAll()
        self.form.toBox.setFocus()

    ### Event handlers ###
    def accept(self):
        """
        Carry out the move, either of an entry or an occurrence.
        """
        assert self.curEntry is not None, \
            "Must call setFrom() before allowing user to use this dialog"

        newEntryName = self.form.toBox.text()
        newEntry = db.entries.findOne(newEntryName)
        if not newEntry:
            #TODO: offer a move instead
            ui.utils.errorBox(
                f"You can't merge into the entry '{newEntryName}', because it does "
                f"not exist.")
            return
        # compare case-insensitive because the find functions are case-insensitive
        if newEntryName.casefold() == self.curEntry.name.casefold():
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
        super().accept()


def _mergeOccurrences(occs: Iterable[db.occurrences.Occurrence],
                      curEntry: db.entries.Entry,
                      newEntry: db.entries.Entry,
                      leaveRedirect=False,
                      redirectFromOcc: Optional[db.occurrences.Occurrence] = None
                     ) -> None:
    """
    Move an iterable of occurrences from curEntry to newEntry.
    If leaveRedirect, leave a redirect from curEntry to newEntry, placed
    in the volume of the occurrence redirectFromOcc.
    """
    for occ in occs:
        if (occ.ref == newEntry.name
                and occ.isRefType(db.occurrences.ReferenceType.REDIRECT)):
            # this is a redirect to the entry we're moving it to; ignore it
            occ.delete()
            continue
        try:
            occ.entry = newEntry
        except db.occurrences.DuplicateError:
            # a comparable one is there already
            occ.delete()

    if leaveRedirect:
        assert redirectFromOcc is not None, \
            "leaveRedirect requires redirectFromOcc to be specified"
        db.occurrences.Occurrence.makeNew(
            curEntry, redirectFromOcc.volume, newEntry.name,
            db.occurrences.ReferenceType.REDIRECT
        )
