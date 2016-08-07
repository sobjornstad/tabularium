# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

"Implementation for the Add Occurrences window class AddOccWindow, q.v."

from PyQt5.QtWidgets import QDialog

import ui.forms.newoccs
import ui.utils

import db.occurrences

class AddOccWindow(QDialog):
    """
    Window that accepts a string of UOF and creates occurrences from it. The
    dialog displays the entry that the occurrences will be created from (this
    is read-only), and may also start with some text already placed in the box
    (for instance, when adding a redirect entry).
    """
    def __init__(self, parent, entry, preparedOccurrence=None):
        """
        Arguments:
            parent: The usual.
            entry: The entry to add occurrences to.
            preparedOccurrence (optional): Text to put in the occurrences box.
        """

        QDialog.__init__(self)
        self.form = ui.forms.newoccs.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent # may be mw or entry dialog
        self.entry = entry

        self.form.entryBox.setText(self.entry.name)
        if preparedOccurrence:
            self.form.valueBox.setText(preparedOccurrence)
            self.form.valueBox.setCursorPosition(0)

        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)

    def accept(self):
        """
        Try to parse the string in the occurrences box; if success, save
        occurrences to database and close. If failure, show error and leave
        dialog open for correction or reject().
        """
        toParse = self.form.valueBox.text()
        try:
            _, numDupes = db.occurrences.makeOccurrencesFromString(
                toParse, self.entry)
        except db.occurrences.InvalidUOFError:
            error = "The occurrence string is invalid – please check your " \
                    "syntax and try again."
            #raise
        except db.occurrences.NonexistentSourceError as e:
            error = "%s" % e
        except db.occurrences.NonexistentVolumeError as e:
            error = "%s" % e
        except db.occurrences.InvalidReferenceError as e:
            error = "%s" % e
        else:
            super(AddOccWindow, self).accept()
            if numDupes > 0:
                ui.utils.informationBox("%i of the occurrences you added were "
                                        "already in the database." % numDupes,
                                        "Duplicate warning")
            return

        # if we're still here, there was an exception
        ui.utils.errorBox(error, "UOF parsing error")
        return

    def reject(self):
        """
        If entry has no occurrences (i.e., if it was new), delete the entry,
        because we can't have entries without occurrences.
        """
        if not db.occurrences.fetchForEntry(self.entry):
            self.entry.delete()
        super(AddOccWindow, self).reject()
