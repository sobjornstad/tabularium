# -*- coding: utf-8 -*-
# Copyright (c) 2016 Soren Bjornstad <contact@sorenbjornstad.com>

"""
Implementation of selection dialog for Entry -> Merge into... menu choice.
Called from onMergeEntry() in main.
"""

from PyQt5.QtWidgets import QDialog
from ui.forms.mergeentry import Ui_Dialog

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

    def setFrom(self, entry):
        self.form.fromBox.setText(entry.getName())
        self.setWindowTitle("Merge '%s' into..." % entry.getName())

    def getTo(self):
        return self.form.toBox.text()
