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
    def __init__(self, parent, entry, sh, preparedOccurrence=None):
        """
        Arguments:
            parent: The usual.
            entry: The entry to add occurrences to.
            settingsHandler: a SettingsHandler instance which we can use to
                save the last-used source and volume for convenience.
            preparedOccurrence (optional): Text to put in the occurrences box
                after the last-used source/volume.
        """

        QDialog.__init__(self)
        self.form = ui.forms.newoccs.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent # may be mw or entry dialog
        self.entry = entry
        self.sh = sh

        self.form.entryBox.setText(self.entry.name)
        sv = self.sh.get('lastSourceVolInAddOcc')
        if preparedOccurrence:
            # If we have a prepared occurrence, use that as the default,
            # including the last-used volume but highlighting it since it's the
            # part we're most likely to want to change. Note that
            # preparedOccurrence normally already contains a '.', so we don't
            # need to add one here.
            occurrenceString = (sv or '') + preparedOccurrence
            self.form.valueBox.setText(occurrenceString)
            self.form.valueBox.setSelection(0, len(sv)-1)  # no . at end
        else:
            # Otherwise, autofill the field with the last-used volume and
            # place the cursor immediately afterwards.
            if sv is not None:
                self.form.valueBox.setText(sv)

        self.form.valueBox.textChanged.connect(self.onValueBoxEdited)
        self.form.validationHelpButton.clicked.connect(self.onUofHelp)

        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)

        self.onValueBoxEdited()

    def onValueBoxEdited(self):
        "Parse UOF as you type and display the results."
        prefix = ""
        try:
            results = db.occurrences.previewUofString(self.form.valueBox.text())
        except db.occurrences.InvalidUOFError as e:
            self.validationMessage = str(e)
            friendlyError = "Waiting for complete UOF..."
            prefix = "⌨️ "
        except db.occurrences.NonexistentSourceError as e:
            self.validationMessage = str(e)
            friendlyError = "Unknown source"
        except db.occurrences.NonexistentVolumeError as e:
            self.validationMessage = str(e)
            friendlyError = "Volume not created yet"
        except db.occurrences.InvalidReferenceError as e:
            self.validationMessage = str(e)
            friendlyError = "Page number out of range for this source"
        else:
            self.form.validationLabel.setText(
                f"✔️ UOF is valid, press Enter to add:\n{', '.join(results)}"
            )
            self.form.validationHelpButton.setVisible(False)
            return

        self.form.validationHelpButton.setVisible(True)
        self.form.validationLabel.setText(
            (prefix if prefix else "❓ ") + f"{friendlyError}")

    def onUofHelp(self):
        "Show the current validationError."
        ui.utils.informationBox(self.validationMessage, "Current validation issues")

    def accept(self):
        """
        Try to parse the string in the occurrences box; if success, save
        occurrences to database and close. If failure, show error and leave
        dialog open for correction or reject().
        """
        toParse = self.form.valueBox.text()
        try:
            occs, numDupes = db.occurrences.makeOccurrencesFromString(
                toParse, self.entry)
        except db.occurrences.InvalidUOFError as e:
            error = "%s" % e
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
            if occs:
                # Save the first source we added to conveniently recall it on
                # the next add.
                volume = occs[0].volume
                source = volume.source
                if source.isSingleVol():
                    saveSource = source.abbrev + ' '
                else:
                    saveSource = source.abbrev + str(volume.num) + '.'
                self.sh.put('lastSourceVolInAddOcc', saveSource)
                self.sh.sync()
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
