# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt5.QtWidgets import QDialog
import ui.forms.tools_classification

import ui.addoccurrence

import db.entries
import db.consts

class ClassificationWindow(QDialog):
    "Allow user to quickly classify unclassified entries."
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = ui.forms.tools_classification.Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent

        sf = self.form
        ec = db.entries.EntryClassification
        self.buttonToVal = {sf.ordinary: ec.ORD,
                            sf.person: ec.PERSON,
                            sf.place: ec.PLACE,
                            sf.quotation: ec.QUOTE,
                            sf.title: ec.TITLE,
                            sf.unclassified: ec.UNCLASSIFIED,
                           }
        self.valToButton = {v: k for k, v in self.buttonToVal.items()}
        # pylint: disable=consider-iterating-dictionary
        for i in self.buttonToVal.keys():
            i.toggled.connect(self.onSet)

        self.form.closeButton.clicked.connect(self.reject)
        self.form.entryList.itemSelectionChanged.connect(self.onSelect)

        self.entries = None
        self.fillEntries()
        self.form.entryList.setCurrentRow(0)
        self._considerEnableDisable()

    def fillEntries(self):
        "Fill box of entries to classify from the database."
        entries = db.entries.find('%', (db.entries.EntryClassification.UNCLASSIFIED,))
        entries.sort(key=lambda i: i.sortKey.lower())
        for i in entries:
            self.form.entryList.addItem(i.name)
        self.entries = entries # save for reference when editing

    def onSelect(self):
        """
        Select a new item (with user intervention or from onSet()). This
        requires updating the radio buttons and the text indicating how many
        items are left to classify.
        """
        self._considerEnableDisable()
        entry = self.entries[self.form.entryList.currentRow()]
        classif = entry.classification
        button = self.valToButton[classif]
        old = button.blockSignals(True)  # don't call onSet again as we're
        button.setChecked(True)          # busy handling this; then it would
        button.blockSignals(old)         # skip down another item.

        curRow = self.form.entryList.currentRow()
        remains = (self.form.entryList.count() - curRow) if curRow != -1 else 0
        self.form.countLabel.setText("%i entr%s left to classify." % (
            remains, 'y' if remains == 1 else 'ies'))

    def onSet(self, wasSelected):
        """
        User clicked an option; save the change and move the cursor to the next
        entry.
        """
        if not wasSelected: # this is the deselect (not select) operation; we
            return          # only want to run this func once for a reselect

        row = self.form.entryList.currentRow()
        for button, value in self.buttonToVal.items():
            if button.isChecked():
                self.entries[row].classification = value
                break
        self.form.entryList.setCurrentRow(row + 1)
        self._considerEnableDisable()

    def _considerEnableDisable(self):
        """
        If nothing is selected anymore, we should uncheck and disable the radio
        buttons.
        """
        enabled = bool(len(self.form.entryList.selectedItems()))
        # pylint: disable=consider-iterating-dictionary
        for i in self.buttonToVal.keys():
            i.setEnabled(enabled)
            if not enabled:
                # http://stackoverflow.com/questions/1731620/
                # is-there-a-way-to-have-all-radion-buttons-be-unchecked
                i.setAutoExclusive(False)
                i.setChecked(False)
                i.setAutoExclusive(True)
