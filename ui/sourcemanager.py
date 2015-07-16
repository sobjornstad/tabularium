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
        t.clear()
        t.setColumnCount(4)
        t.setHorizontalHeaderLabels(["Name", "Abbrev", "Type", "Volumes"])

        self.sources = db.sources.allSources()
        t.setRowCount(len(self.sources))
        for row in range(len(self.sources)):
            robj = self.sources[row]
            t.setItem(row, 0, QTableWidgetItem(robj.getName()))
            t.setItem(row, 1, QTableWidgetItem(robj.getAbbrev()))
            t.setItem(row, 2, QTableWidgetItem(
                      db.consts.sourceTypesFriendlyReversed[robj.getStype()]))
            t.setItem(row, 3, QTableWidgetItem("Not Implemented")) # TODO
        t.resizeColumnsToContents()
        t.sortItems(0)

    def onNew(self):
        #TODO: fix display getting corrupted if we cancel
        nsd = NewSourceDialog(self)
        nsd.exec_()
        self.renderTable()
    def onEdit(self):
        sourceRow = self.form.sourceTable.currentRow()
        source = self.sources[sourceRow]
        nsd = NewSourceDialog(self, source)
        nsd.exec_()
        self.renderTable()
    def onDelete(self):
        pass


class NewSourceDialog(QDialog):
    def __init__(self, parent, editSource=None):
        QDialog.__init__(self)
        self.form = forms.newsource.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent
        if not editSource:
            self.isEditing = False
        else:
            self.isEditing = True
            self.source = editSource
            self.fillForEdit()

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

    def fillForEdit(self):
        source = self.source
        self.setWindowTitle("Edit Source")
        self.form.addButton.setText("&Save")
        self.form.typeCombo.setEnabled(False)
        self.form.nameBox.setText(source.getName())
        self.form.abbrevBox.setText(source.getAbbrev())
        self.form.typeCombo.setCurrentIndex(
                db.consts.sourceTypesKeys.index(
                db.consts.sourceTypesFriendlyReversed[source.getStype()]))
        self.form.multVolCheckbox.setChecked(not source.isSingleVol())
        self.form.valVolStart.setValue(source.getValVol()[0])
        self.form.valVolStop.setValue(source.getValVol()[1])
        self.form.valRefStart.setValue(source.getValPage()[0])
        self.form.valRefStop.setValue(source.getValPage()[1])
        self.form.nearbyRange.setValue(source.getNearbyRange())
        self.isEditing = True

    def accept(self):
        #TODO: PREVENT BLANK ENTRIES
        sf = self.form

        newName = unicode(sf.nameBox.text()).strip()
        if not self.form.multVolCheckbox.isChecked():
            newVolval = (1,1)
        else:
            newVolval = (sf.valVolStart.value(), sf.valVolStop.value())
        newPageval = (sf.valRefStart.value(), sf.valRefStop.value())
        newNearrange = sf.nearbyRange.value()
        newAbbr = unicode(sf.abbrevBox.text()).strip()
        newStype = db.consts.sourceTypesFriendly[
                        unicode(sf.typeCombo.currentText())]

        try:
            if not self.isEditing:
                db.sources.Source.makeNew(newName, newVolval, newPageval,
                                          newNearrange, newAbbr, newStype)
            else:
                self.source.setName(newName)
                self.source.setValidVol(newVolval)
                self.source.setValidPage(newPageval)
                self.source.setNearbyRange(newNearrange)
                self.source.setAbbrev(newAbbr)
                # right now, no setting of stype
        except db.sources.DuplicateError as e:
            ui.utils.errorBox(str(e))
        except db.sources.InvalidRangeError as e:
            ui.utils.errorBox(str(e))
        except db.sources.DiaryExistsError as e:
            ui.utils.errorBox(str(e))
        else:
            super(NewSourceDialog, self).accept()
