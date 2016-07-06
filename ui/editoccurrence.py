# -* coding: utf-8 *-
# Copyright 2016 Soren Bjornstad. All rights reserved.

from PyQt4.QtGui import QDialog

import db.occurrences
import ui.utils

class EditOccurrenceWindow(QDialog):
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

        self.form.entryBox.setText(self.entry.getName())
        startValid, endValid = self.source.getVolVal()
        self.form.volumeSpin.setMinimum(startValid)
        self.form.volumeSpin.setMaximum(endValid)
        self.form.volumeSpin.setValue(self.vol.getNum())
        self.form.referenceBox.setText(self.occ.getRef()[0])

        self.form.referenceBox.selectAll()
        self.form.referenceBox.setFocus()

    def accept(self):
        ref = unicode(self.form.referenceBox.text())
        uof = "%s: %s.%s" % (self.source.getAbbrev(),
                             self.form.volumeSpin.value(), ref)
        if self._referenceOk(uof):
            db.occurrences.makeOccurrencesFromString(uof, self.entry)
            self.occ.delete()
            super(EditOccurrenceWindow, self).accept()

    def _referenceOk(self, uof):
        try:
            prospectiveOccs = db.occurrences.parseUnifiedFormat(uof)
        except db.occurrences.InvalidReferenceError as e:
            ui.utils.warningBox("%s" % e, "Error editing occurrence")
            return False
        except db.occurrences.NonexistentVolumeError as e:
            # only way to get this is by using a pipe in the reference field
            self._noMultipleOccurrences()
        except db.occurrences.InvalidUOFError as e:
            ui.utils.warningBox("That is not a valid way to specify a "
                    "reference. This box should contain the final part of an "
                    "occurrence in UOF (after the source and volume): either "
                    "a page number, a range of page numbers, or a redirect "
                    "('see WhateverOtherEntry'). See the UOF section of the "
                    "manual for more information.")
            return False

        if len(prospectiveOccs) > 1:
            self._noMultipleOccurrences()
            return False

        return True

    def _noMultipleOccurrences(self):
        ui.utils.warningBox("Invalid reference: you cannot replace one "
                "occurrence with several. The reference box should not "
                "contain braces or pipes.", "Invalid reference")
