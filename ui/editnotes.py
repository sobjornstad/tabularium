# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import datetime
import re

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QDialog, QLineEdit, QTreeWidgetItem
from PyQt4.QtCore import QAbstractTableModel, Qt
import forms.editnotes

import ui.utils
import db.consts
import db.sources
import db.volumes

class TreeWidgetItem(QTreeWidgetItem):
    # http://stackoverflow.com/questions/21030719/
    # sort-a-pyside-qtgui-qtreewidget-by-an-alpha-numeric-column
    def __lt__(self, other):
        key1 = self.text(0)
        key2 = other.text(0)
        return self.naturalSortKey(key1) < self.naturalSortKey(key2)

    @staticmethod
    def naturalSortKey(key):
        regex = '(\d*\.\d+|\d+)'
        parts = re.split(regex, key)
        return tuple((e if i % 2 == 0 else float(e))
                      for i, e in enumerate(parts))


class NotesBrowser(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = forms.editnotes.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.fillTreeWidget()

        self.form.closeButton.clicked.connect(self.reject)
        #self.form.newButton.clicked.connect(self.onNew)
        #self.form.editButton.clicked.connect(self.onEdit)
        #self.form.deleteButton.clicked.connect(self.onDelete)
        #self.form.notesButton.clicked.connect(self.onNotes)

        #self.volModel = VolumeTableModel(self)
        #self.form.volTable.setModel(self.volModel)
        #self.sm = self.form.volTable.selectionModel()
        #self.sm.selectionChanged.connect(self.checkButtonEnablement)

        #self.fillSources()
        #self.fillVolumes()
        #self.form.sourceList.itemSelectionChanged.connect(self.fillVolumes)

    def fillTreeWidget(self):
        sources = db.sources.allSources()
        for source in sources:
            sourceItem = TreeWidgetItem([source.getName()])
            self.form.tree.addTopLevelItem(sourceItem)
            if not source.isSingleVol():
                volumes = db.volumes.volumesInSource(source)
                for volume in volumes:
                    TreeWidgetItem(sourceItem,
                                   ["Volume " + str(volume.getNum())])
            sourceItem.sortChildren(0, Qt.AscendingOrder)
        self.form.tree.sortByColumn(0, Qt.AscendingOrder)

    def fillSources(self):
        sources = db.sources.allSources(includeSingleVolSources=False)
        for source in sources:
            self.form.sourceList.addItem(source.getName())
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
        pass

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
                    unicode(self.form.sourceList.currentItem().text()))
        else:
            return None
