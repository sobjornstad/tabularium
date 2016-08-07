# -*- coding: utf-8 -*-
# Copyright (c) 2016 Soren Bjornstad <contact@sorenbjornstad.com>

"""
A very dumb AboutWindow class that does nothing but display a form created in
the Designer, updating the version number as appropriate.
"""

from PyQt5.QtWidgets import QDialog
from ui.forms.about import Ui_Dialog

class AboutWindow(QDialog):
    def __init__(self, parent, version):
        QDialog.__init__(self)
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.form.versionLabel.setText(
            '<span style="font-size:12pt;">Version %s</span>' % version)

        self.form.okButton.clicked.connect(self.accept)
