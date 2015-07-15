# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QDialog, QLineEdit, QTableWidgetItem
import forms.managesources
import forms.newsource

import ui.utils
import ui.addoccurrence
import db.consts
import db.sources

class SourceManager(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = forms.managesources.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.closeButton.clicked.connect(self.reject)
        self.form.newButton.clicked.connect(self.onNew)
        self.form.editButton.clicked.connect(self.onEdit)
        self.form.deleteButton.clicked.connect(self.onEdit)

        self.renderTable()

    def renderTable(self):
        t = self.form.sourceTable
        t.setColumnCount(4)
        t.setHorizontalHeaderLabels(["Name", "Abbrev", "Type", "Volumes"])

        ss = db.sources.allSources()
        t.setRowCount(len(ss))
        for row in range(len(ss)):
            robj = ss[row]
            t.setItem(row, 0, QTableWidgetItem(robj.getName()))
            t.setItem(row, 1, QTableWidgetItem(robj.getAbbrev()))
            t.setItem(row, 2, QTableWidgetItem(
                    db.consts.sourceTypesFriendlyReversed[robj.getStype()]))
            t.setItem(row, 3, QTableWidgetItem("Not Findable")) # TODO
        t.resizeColumnsToContents()

    def onNew(self):
        nsd = NewSourceDialog(self)
        nsd.exec_()
        self.renderTable()
    def onEdit(self):
        pass
    def onDelete(self):
        pass


class NewSourceDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = forms.newsource.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        for i in db.consts.sourceTypesKeys:
            self.form.typeCombo.addItem(i)
        self.checkVolumeEnable()
        self.form.multVolCheckbox.stateChanged.connect(self.checkVolumeEnable)

        self.form.cancelButton.clicked.connect(self.reject)
        self.form.addButton.clicked.connect(self.accept)


    def checkVolumeEnable(self):
        if self.form.multVolCheckbox.isChecked():
            self.form.valVolStart.setEnabled(True)
            self.form.valVolStop.setEnabled(True)
        else:
            self.form.valVolStart.setEnabled(False)
            self.form.valVolStop.setEnabled(False)

    def accept(self):
        sf = self.form
        try:
            db.sources.Source.makeNew(
              name=unicode(sf.nameBox.text()),
              volval=(sf.valVolStart.value(), sf.valVolStop.value()),
              pageval=(sf.valRefStart.value(), sf.valRefStop.value()),
              nearrange=sf.nearbyRange.value(),
              abbrev=unicode(sf.abbrevBox.text()).strip(),
              stype=db.consts.sourceTypesFriendly[
                    unicode(sf.typeCombo.currentText())]
              )
        except db.sources.DuplicateError as err:
            if 'name' in err:
                ui.utils.errorBox("A source with that name already exists.")
            elif 'abbreviation' in err:
                ui.utils.errorBox("A source with that abbreviation already exists.")
            else:
                assert False, "Unrecognized DuplicateError!"
        else:
            super(NewSourceDialog, self).accept()
