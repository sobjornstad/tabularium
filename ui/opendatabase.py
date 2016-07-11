# -* coding: utf-8 *-
# Copyright 2016 Soren Bjornstad. All rights reserved.

"""
Implementation of OpenDatabaseWindow (aka "Welcome to Tabularium!"), q.v.
"""

import os
from PyQt5.QtWidgets import QDialog
import ui.forms.opendatabase

class OpenDatabaseWindow(QDialog):
    """
    Window displayed when the program is run for the first time, when opening
    the previously used database fails, or when user mistypes or doesn't know
    the password on opening the program. Provides options for creating a new
    database, opening an existing one, or (if appropriate) trying again to open
    the previously used database.

    This is a dumb dialog that contains no logic except that necessary to
    display appropriate messages; after exec'ing the dialog one calls the
    getResult() method and acts as appropriate for the options 'new', 'open',
    or 'last'.
    """
    def __init__(self, parent, lastUsed=None):
        QDialog.__init__(self)
        self.form = ui.forms.opendatabase.Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent
        self.result = None

        self.form.quitButton.clicked.connect(self.reject)
        self.form.okButton.clicked.connect(self.accept)
        if lastUsed and os.path.exists(lastUsed):
            self.form.openLastRadio.setText("Open last-used database: %s" %
                                            os.path.split(lastUsed)[-1])
            self.form.openLastRadio.setChecked(True)
        else:
            if lastUsed:
                self.form.explanatoryText.setText(
                    "The last database you had open (%s) is not accessible.\n"
                    "What would you like to do?" % os.path.split(lastUsed)[-1])
            self.form.openLastRadio.setEnabled(False)
            self.form.createNewRadio.setChecked(True)

    def getResult(self):
        return self.result

    def accept(self):
        """
        Save user's radio button selection to self.result for retrieval by
        caller.
        """
        if self.form.createNewRadio.isChecked():
            self.result = 'new'
        elif self.form.openExistingRadio.isChecked():
            self.result = 'open'
        elif self.form.openLastRadio.isChecked():
            self.result = 'last'
        super(OpenDatabaseWindow, self).accept()
