# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtCore
from PyQt4.QtGui import QDialog
from PyQt4.QtCore import QAbstractTableModel
import ui.forms.managesources
import ui.forms.newsource

import ui.utils
import ui.addoccurrence
import db.consts
import db.sources
import db.volumes

# pylint: disable=too-many-public-methods
# (not sure why that counts superclass methods in the first place)
class SourceTableModel(QAbstractTableModel):
    def __init__(self, parent, *args):
        QAbstractTableModel.__init__(self)
        self.parent = parent
        self.headerdata = ["Name", "Abbrev", "Type", "Volumes"]
        self.sources = None
        self.doUpdate()

    def rowCount(self, parent):
        return len(self.sources)
    def columnCount(self, parent):
        return 4

    def doUpdate(self):
        self.beginResetModel()
        self.sources = db.sources.allSources()
        self.endResetModel()
        self.sort(0, QtCore.Qt.AscendingOrder)

    def data(self, index, role):
        if role != QtCore.Qt.DisplayRole:
            return None

        robj = self.sources[index.row()]
        col = index.column()
        if col == 0:
            return robj.getName()
        elif col == 1:
            return robj.getAbbrev()
        elif col == 2:
            return db.consts.sourceTypesFriendlyReversed[robj.getStype()]
        elif col == 3:
            return robj.getNumVolsRepr()
        else:
            assert False, "Invalid column!"
            return None

    def sort(self, column, order=QtCore.Qt.AscendingOrder):
        rev = not order == QtCore.Qt.AscendingOrder

        if column == 0:
            key = lambda i: i.getName().lower()
        elif column == 1:
            key = lambda i: i.getAbbrev().lower()
        elif column == 2:
            key = lambda i: db.consts.sourceTypesFriendlyReversed[i.getStype()]
        elif column == 3:
            key = lambda i: len(db.volumes.volumesInSource(i))

        self.beginResetModel()
        self.sources.sort(key=key, reverse=rev)
        self.endResetModel()

    def headerData(self, col, orientation, role):
        # note: I don't know why, but if this if-statement is left out, the
        # headers silently don't show up
        if role != QtCore.Qt.DisplayRole:
            return None
        return self.headerdata[col]


class SourceManager(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = ui.forms.managesources.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.closeButton.clicked.connect(self.reject)
        self.form.newButton.clicked.connect(self.onNew)
        self.form.editButton.clicked.connect(self.onEdit)
        self.form.deleteButton.clicked.connect(self.onDelete)

        self.model = SourceTableModel(self)
        self.form.sourceTable.setModel(self.model)
        self.form.sourceTable.resizeColumnsToContents()
        self.sm = self.form.sourceTable.selectionModel()
        self.sm.selectionChanged.connect(self.checkButtonEnablement)
        self.model.modelReset.connect(self.checkButtonEnablement)
        self.checkButtonEnablement()

    def checkButtonEnablement(self):
        sf = self.form
        for i in (sf.editButton, sf.deleteButton):
            i.setEnabled(self.sm.hasSelection())

    def onNew(self):
        nsd = NewSourceDialog(self)
        r = nsd.exec_()
        if r:
            self.form.sourceTable.model().doUpdate()
    def onEdit(self):
        index = self.form.sourceTable.selectionModel().selectedRows()[0]
        source = self.form.sourceTable.model().sources[index.row()]
        nsd = NewSourceDialog(self, source)
        r = nsd.exec_()
        if r:
            self.form.sourceTable.model().doUpdate()
    def onDelete(self):
        index = self.form.sourceTable.selectionModel().selectedRows()[0]
        source = self.form.sourceTable.model().sources[index.row()]
        deletedNums = source.deletePreview()
        if deletedNums[0] > 0:
            msg = ("You have chosen to delete the source '%s'. This will "
                   "result in the permanent deletion of %i volume%s and %i "
                   "occurrence%s, along with any entries that are left "
                   "without occurrences.")
            title = "Heads up or heads off!"
            if deletedNums[1] > 30:
                msg += (" You are highly advised to back up your database "
                        "before continuing. Are you sure you want to delete "
                        "this source?")
                check = "I have backed up my database."
            else:
                msg += " Are you sure you want to delete this source?"
                check = "Really delete this source"

            msg = msg % (source.getName(),
                         deletedNums[0], "" if deletedNums[0] == 1 else "s",
                         deletedNums[1], "" if deletedNums[1] == 1 else "s")
            cd = ui.utils.ConfirmationDialog(self, msg, check, title)
            r = cd.exec_()
            if not r:
                return
        source.delete()
        self.form.sourceTable.model().doUpdate()



class NewSourceDialog(QDialog):
    def __init__(self, parent, editSource=None):
        QDialog.__init__(self)
        self.form = ui.forms.newsource.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        for i in db.consts.sourceTypesKeys:
            self.form.typeCombo.addItem(i)

        if not editSource:
            self.isEditing = False
        else:
            self.isEditing = True
            self.source = editSource
            self.fillForEdit()

        self.checkVolumeEnable()
        self.form.multVolCheckbox.stateChanged.connect(self.checkVolumeEnable)

        self.form.cancelButton.clicked.connect(self.reject)
        self.form.addButton.clicked.connect(self.accept)

    def checkVolumeEnable(self):
        sf = self.form
        for i in (sf.valVolStart, sf.valVolStop, sf.valVolLabel):
            i.setEnabled(self.form.multVolCheckbox.isChecked())
        if not self.form.multVolCheckbox.isChecked():
            sf.valVolStart.setValue(1)
            sf.valVolStop.setValue(1)

    def fillForEdit(self):
        source = self.source
        self.setWindowTitle("Edit Source")
        self.form.addButton.setText("&Save")
        self.form.nameBox.setText(source.getName())
        self.form.abbrevBox.setText(source.getAbbrev())
        self.form.typeCombo.setCurrentIndex(
                db.consts.sourceTypesKeys.index(
                db.consts.sourceTypesFriendlyReversed[source.getStype()]))
        self.form.typeCombo.setEnabled(False)
        self.form.multVolCheckbox.setChecked(not source.isSingleVol())
        self.form.valVolStart.setValue(source.getVolVal()[0])
        self.form.valVolStop.setValue(source.getVolVal()[1])
        self.form.valRefStart.setValue(source.getPageVal()[0])
        self.form.valRefStop.setValue(source.getPageVal()[1])
        self.form.nearbyRange.setValue(source.getNearbyRange())
        self.isEditing = True

    def accept(self, overrideTrounce=None):
        sf = self.form

        newName = sf.nameBox.text().strip()
        if not self.form.multVolCheckbox.isChecked():
            newVolval = (1, 1)
        else:
            newVolval = (sf.valVolStart.value(), sf.valVolStop.value())
        newPageval = (sf.valRefStart.value(), sf.valRefStop.value())
        newNearrange = sf.nearbyRange.value()
        newAbbr = sf.abbrevBox.text().strip()
        newStype = db.consts.sourceTypesFriendly[sf.typeCombo.currentText()]

        if newName == '':
            ui.utils.errorBox("Please enter a name.", "No source name given")
            return
        elif newAbbr == '':
            ui.utils.errorBox("Please enter an abbreviation.",
                              "No abbreviation given")
            return

        try:
            if not self.isEditing:
                db.sources.Source.makeNew(newName, newVolval, newPageval,
                                          newNearrange, newAbbr, newStype)
            else:
                self.source.setName(newName)
                self.source.setValidVol(newVolval,
                        True if overrideTrounce == 'volume' else False)
                self.source.setValidPage(newPageval,
                        True if overrideTrounce == 'page' else False)
                self.source.setNearbyRange(newNearrange)
                self.source.setAbbrev(newAbbr)
                # right now, no setting of stype
        except (db.sources.DuplicateError, db.sources.InvalidRangeError,
                db.sources.InvalidNameError, db.sources.DiaryExistsError) as e:
            ui.utils.errorBox(str(e))
        except db.sources.TrouncesError as e:
            whichThing = e.whichThing
            if whichThing == 'volume':
                check = "&Really delete these %i volumes and %i " \
                        "occurrences" % (e.number1, e.number2)
                title = "Delete invalid volumes and occurrences"
            elif whichThing == 'page':
                check = "&Really delete these %i occurrences" % (
                        e.number1)
                title = "Delete invalid occurrences"

            errStr = str(e).replace('would', 'will')
            extra = (" If you continue, they will be permanently deleted from "
                     "your database along with any entries that are left "
                     "without occurrences.")
            cd = ui.utils.ConfirmationDialog(self, errStr+extra, check, title)
            doDelete = cd.exec_()
            if doDelete:
                return self.accept(overrideTrounce=whichThing)
        else:
            super(NewSourceDialog, self).accept()
