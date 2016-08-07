# -* coding: utf-8 *-
# Copyright 2016 Soren Bjornstad. All rights reserved.

"Implementation of the EditOccurrenceWindow (and helper functions), q.v."

from PyQt5.QtWidgets import QDialog

import db.occurrences
import ui.utils

class EditOccurrenceWindow(QDialog):
    """
    Window that allows the user to edit occurrences. The user can edit the
    volume with a spin box and can enter a new reference in (partial) UOF
    format. The reference is highlighted when the dialog opens, as the most
    common reason one would want to edit an occurrence is a small typo in the
    reference or reference number.
    """
    def __init__(self, parent, entry, occurrence):
        QDialog.__init__(self)
        self.form = ui.forms.editoccurrence.Ui_Dialog()
        self.form.setupUi(self)
        self.form.cancelButton.clicked.connect(self.reject)
        self.form.okButton.clicked.connect(self.accept)

        self.mw = parent
        self.entry = entry
        self.occ = occurrence
        self.vol = occurrence.getVolume()
        self.source = self.vol.getSource()

        self.form.entryBox.setText(self.entry.name)
        startValid, endValid = self.source.getVolVal()
        self.form.volumeSpin.setMinimum(startValid)
        self.form.volumeSpin.setMaximum(endValid)
        self.form.volumeSpin.setValue(self.vol.getNum())
        if self.occ.isRefType('redir'):
            self.form.referenceBox.setText("see " + self.occ.getRef()[0])
        else:
            self.form.referenceBox.setText(self.occ.getRef()[0])

        self.form.referenceBox.selectAll()
        self.form.referenceBox.setFocus()

    def accept(self):
        "Create new occurrences and delete the old ones."
        ref = self.form.referenceBox.text()
        uof = "%s: %s.%s" % (self.source.getAbbrev(),
                             self.form.volumeSpin.value(), ref)
        if referenceOk(uof):
            _, dupe = db.occurrences.makeOccurrencesFromString(uof, self.entry)
            if dupe:
                # otherwise, if we click OK without changing anything, the
                # occurrence is deleted!
                self.reject()
                return
            self.occ.delete()
            super(EditOccurrenceWindow, self).accept()

def referenceOk(uof):
    """
    Determine if a UOF string (compiled by the program from the user's
    edited choices) is valid, so we can provide an error and give the user
    a chance to fix it before exiting.
    """
    try:
        prospectiveOccs = db.occurrences.parseUnifiedFormat(uof)
    except db.occurrences.InvalidReferenceError as e:
        ui.utils.warningBox("%s" % e, "Error editing occurrence")
        return False
    except db.occurrences.NonexistentVolumeError as e:
        # only way to get this is by using a pipe in the reference field,
        # since spinbox is limited to the valid values
        noMultipleOccurrences()
    except db.occurrences.InvalidUOFError as e:
        ui.utils.warningBox(
            "That is not a valid way to specify a reference. This box "
            "should contain the final part of an occurrence in UOF (after "
            "the source and volume): either a page number, a range of page "
            "numbers, or a redirect ('see WhateverOtherEntry'). See the UOF "
            "section of the manual for more information.")
        return False

    if len(prospectiveOccs) > 1:
        noMultipleOccurrences()
        return False

    return True

def noMultipleOccurrences():
    ui.utils.warningBox(
        "Invalid reference: you cannot replace one occurrence with several. "
        "The reference box should not contain braces or pipes.",
        "Invalid reference")
