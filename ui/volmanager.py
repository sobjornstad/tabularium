# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import QAbstractTableModel
import ui.forms.managevols
import ui.forms.newsource

import ui.addoccurrence
import ui.editnotes
import ui.utils
import db.consts
import db.sources
import db.volumes

class VolumeTableModel(QAbstractTableModel):
    def __init__(self, parent):
        QAbstractTableModel.__init__(self)
        self.parent = parent
        self.headerdata = ["Number", "Opened", "Closed", "Notes"]
        self.vols = None

        # default sort parameters
        # At this point we don't have the data, so don't actually sort() yet.
        self.curSortColumn = 0
        self.curSortIsReversed = False

    # pylint: disable=unused-argument
    def rowCount(self, parent):
        return len(self.vols) if self.vols is not None else 0
    def columnCount(self, parent):
        return len(self.headerdata)

    def data(self, index, role):
        if role != QtCore.Qt.DisplayRole:
            return None

        robj = self.vols[index.row()]
        col = index.column()
        if col == 0:
            return robj.num
        elif col == 1:
            val = ui.utils.formatDate(robj.dateOpened)
            return val if val is not None else "N/A"
        elif col == 2:
            val = ui.utils.formatDate(robj.dateClosed)
            return val if val is not None else "N/A"
        elif col == 3:
            return "Available" if robj.notes else "None"
        else:
            assert False, "Invalid column!"
            return None

    def sort(self, column, order=QtCore.Qt.AscendingOrder, isReversed=None):
        if isReversed:
            rev = isReversed
        else:
            rev = not order == QtCore.Qt.AscendingOrder
        # Save the column we've chosen for use after replaceData(). isReversed
        # parameter is used to support this, since we can't cleanly negate the
        # constant QtCore.Qt.AscendingOrder.
        self.curSortColumn = column
        self.curSortIsReversed = rev

        if column == 0:
            key = lambda i: i.num
        elif column == 1:
            key = lambda i: i.dateOpened
        elif column == 2:
            key = lambda i: i.dateClosed
        elif column == 3:
            key = lambda i: "Available" if i.notes else "None"

        self.beginResetModel()
        self.vols.sort(key=key, reverse=rev)
        self.endResetModel()

    def headerData(self, col, orientation, role):
        # note: I don't know why, but if this if-statement is left out, the
        # headers silently don't show up
        if role != QtCore.Qt.DisplayRole:
            return None
        return self.headerdata[col]

    def replaceData(self, volList):
        self.beginResetModel()
        self.vols = volList
        self.endResetModel()
        self.sort(self.curSortColumn, isReversed=self.curSortIsReversed)


class VolumeManager(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = ui.forms.managevols.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.closeButton.clicked.connect(self.reject)
        self.form.newButton.clicked.connect(self.onNew)
        self.form.editButton.clicked.connect(self.onEdit)
        self.form.deleteButton.clicked.connect(self.onDelete)
        self.form.notesButton.clicked.connect(self.onNotes)

        self.volModel = VolumeTableModel(self)
        self.form.volTable.setModel(self.volModel)
        self.form.volTable.doubleClicked.connect(self.onEdit)
        self.sm = self.form.volTable.selectionModel()
        self.sm.selectionChanged.connect(self.checkButtonEnablement)

        self.fillSources()
        self.fillVolumes()
        self.form.sourceList.itemSelectionChanged.connect(self.fillVolumes)

    def checkButtonEnablement(self):
        sf = self.form
        for i in (sf.editButton, sf.deleteButton, sf.notesButton):
            i.setEnabled(self.sm.hasSelection())

    def fillSources(self):
        sources = db.sources.allSources(includeSingleVolSources=False)
        for source in sources:
            self.form.sourceList.addItem(source.name)
    def fillVolumes(self):
        source = self._currentSource()
        if source:
            vols = db.volumes.volumesInSource(source)
            self.volModel.replaceData(vols)
        else:
            self.volModel.replaceData([])
        self.checkButtonEnablement()

    def onNew(self):
        nvd = NewVolumeDialog(self, self._currentSource())
        nvd.exec_()
        self.fillVolumes()
    def onEdit(self):
        vol = self._currentVolume()
        if vol is None:
            return
        nvd = NewVolumeDialog(self, self._currentSource(), editVol=vol)
        nvd.exec_()
        self.fillVolumes()
    def onDelete(self):
        pass
    def onNotes(self):
        nd = ui.editnotes.NotesBrowser(self, self._currentSource(),
                                       self._currentVolume())
        nd.exec_()

    def _currentVolume(self):
        """
        Return the Volume currently selected, or None if there is no selection.
        """
        try:
            index = self.form.volTable.selectionModel().selectedRows()[0]
        except IndexError:
            return None
        volume = self.volModel.vols[index.row()]
        return volume

    def _currentSource(self):
        if self.form.sourceList.currentItem():
            return db.sources.byName(
                self.form.sourceList.currentItem().text())
        else:
            return None



class NewVolumeDialog(QDialog):
    def __init__(self, parent, source, editVol=None):
        QDialog.__init__(self)
        self.form = ui.forms.newvol.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent
        self.source = source

        # connect buttons
        self.form.cancelButton.clicked.connect(self.reject)
        self.form.createButton.clicked.connect(self.accept)

        # set up disable/enable
        self.checkUseDates()
        self.form.useDateCheck.stateChanged.connect(self.checkUseDates)

        # set default options
        self.form.sourceName.setText(self.source.name)
        minVolValid, maxVolValid = self.source.volVal
        volSuggestion = db.volumes.findNextOpenVol(self.source)
        self.form.volNumSpin.setMinimum(minVolValid)
        self.form.volNumSpin.setMaximum(maxVolValid)
        self.form.volNumSpin.setValue(volSuggestion)
        defaultDate = db.volumes.findNextDateOpened(self.source)
        self.form.dOpenedEdit.setDate(defaultDate)
        self.form.dClosedEdit.setDate(defaultDate)

        if not editVol:
            self.isEditing = False
        else:
            self.isEditing = True
            self.volume = editVol
            self.fillForEdit()


    def checkUseDates(self):
        for i in (self.form.dOpenedEdit, self.form.dClosedEdit,
                  self.form.dOpenedLabel, self.form.dClosedLabel):
            i.setEnabled(self.form.useDateCheck.isChecked())

    def fillForEdit(self):
        self.setWindowTitle("Edit Volume")
        self.form.createButton.setText("&Save")
        self.form.volNumSpin.setValue(self.volume.num)

        if self.volume.hasDates():
            self.form.useDateCheck.setChecked(True)
            self.form.dOpenedEdit.setDate(self.volume.dateOpened)
            self.form.dClosedEdit.setDate(self.volume.dateClosed)
        else:
            self.form.useDateCheck.setChecked(False)
            self.form.dOpenedEdit.setDate(datetime.date.today())
            self.form.dClosedEdit.setDate(datetime.date.today())

    def accept(self):
        num = self.form.volNumSpin.value()
        # volExists is the only check we need to do, as the other errors
        # (SingleVolume and Validation) should be prevented from occurring
        # by the interface.
        if db.volumes.volExists(self.source, num) and not (
                self.isEditing and num == self.volume.num):
            ui.utils.errorBox("That volume already exists for this source. "
                              "Maybe you mistyped the number or chose the "
                              "wrong source?", "Volume exists")
            return

        if self.form.useDateCheck.isChecked():
            dOpened = self.form.dOpenedEdit.date().toPyDate()
            dClosed = self.form.dClosedEdit.date().toPyDate()
        else:
            dOpened, dClosed = None, None

        try:
            # we start with an empty notes field here
            if self.isEditing:
                self.volume.num = num
                self.volume.dateOpened = dOpened
                self.volume.dateClosed = dClosed
            else:
                db.volumes.Volume.makeNew(self.source, num, "",
                                          dOpened, dClosed)
        except:
            raise
        else:
            super(NewVolumeDialog, self).accept()
