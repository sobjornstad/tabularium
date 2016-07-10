# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4.QtGui import QDialog
import ui.forms.tools_classification

import ui.addoccurrence

import db.entries
import db.consts

class ClassificationWindow(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = ui.forms.tools_classification.Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent

        sf = self.form
        et = db.consts.entryTypes
        self.buttonToVal = {sf.ordinary: et['ord'],
                            sf.person: et['person'],
                            sf.place: et['place'],
                            sf.quotation: et['quote'],
                            sf.title: et['title'],
                            sf.unclassified: et['unclassified']
                            }
        self.valToButton = {v: k for k, v in self.buttonToVal.items()}
        for i in self.buttonToVal.keys():
            i.toggled.connect(self.onSet)

        self.form.closeButton.clicked.connect(self.reject)
        self.form.entryList.itemSelectionChanged.connect(self.onSelect)

        self.entries = None
        self.fillEntries()
        self.form.entryList.setCurrentRow(0)

    def fillEntries(self):
        entries = db.entries.find('%', (db.consts.entryTypes['unclassified'],))
        entries.sort(key=lambda i: i.getSortKey().lower())
        for i in entries:
            self.form.entryList.addItem(i.getName())
        self.entries = entries # save for reference when editing

    def onSelect(self):
        entry = self.entries[self.form.entryList.currentRow()]
        classif = entry.getClassification()
        button = self.valToButton[classif]
        old = button.blockSignals(True)  # don't call onSet again as we're
        button.setChecked(True)          # busy handling this; then it would
        button.blockSignals(old)         # skip down another item.

        remains = self.form.entryList.count() - self.form.entryList.currentRow()
        self.form.countLabel.setText("%i entr%s left to classify." % (remains,
            'y' if remains == 1 else 'ies'))

    def onSet(self, wasSelected):
        if not wasSelected: # this is the deselect (not select) operation; we
            return          # only want to run this func once for a reselect

        row = self.form.entryList.currentRow()
        for button, value in self.buttonToVal.items():
            if button.isChecked():
                self.entries[row].setClassification(value)
                break
        self.form.entryList.setCurrentRow(row + 1)
