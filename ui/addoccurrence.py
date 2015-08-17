# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QDialog

import forms.newoccs
import ui.utils

import db.occurrences

class AddOccWindow(QDialog):
    def __init__(self, parent, entry):
        """
        Arguments:
            parent: The usual.
            entry: The entry to add occurrences to.
        """

        QDialog.__init__(self)
        self.form = forms.newoccs.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent # may be mw or entry dialog
        self.entry = entry

        self.form.entryBox.setText(self.entry.getName())

        self.form.addButton.clicked.connect(self.accept)
        self.form.cancelButton.clicked.connect(self.reject)

    def accept(self):
        """
        Try to parse the string in the occurrences box; if success, save
        occurrences to database and close. If failure, show error and leave
        dialog open for correction or reject().
        """
        toParse = unicode(self.form.valueBox.text())
        try:
            occs = db.occurrences.makeOccurrencesFromString(toParse, self.entry)
        except db.occurrences.InvalidUOFError:
            error = u"The occurrence string is invalid – please check your " \
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
            return

        # if we're still here, there was an exception
        ui.utils.errorBox(error, "UOF parsing error")
        return

    def reject(self):
        if not self.entry.getOccurrences():
            # entry was new and had no occurrences; delete so we're not left
            # with a blank entry in the db
            self.entry.delete()
        super(AddOccWindow, self).reject()
