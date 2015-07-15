# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QDialog
import forms.newoccs

class AddOccWindow(QDialog):
    def __init__(self, parent, entry):
        QDialog.__init__(self)
        self.form = forms.newoccs.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent # may be mw or entry dialog
        self.entry = entry

        self.form.entryBox.setText(self.entry.getName())

        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)

    def accept(self):
        # actually write the changes to the db!

        super(AddOccWindow, self).accept()

    def reject(self):
        if not self.entry.getOccurrences():
            # entry was new and had no occurrences; delete so we're not left
            # with a blank entry in the db
            self.entry.delete()
        super(AddOccWindow, self).reject()
