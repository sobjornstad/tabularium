# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

#TODO: possibility of a source filter box?

import datetime
import re

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QDialog, QMessageBox, QLineEdit, QTreeWidgetItem
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
    # Ideally we would handle this with a model/view; if I ever really feel
    # like refactoring and hav nothing better to do, we can do it...but I
    # think the widget is a decent way to handle it for now, so I don't have
    # to learn how to write a tree view model for this one thing.
    def __init__(self, parent):
        QDialog.__init__(self)
        self.form = forms.editnotes.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.closeButton.clicked.connect(self.reject)
        self.form.parseButton.clicked.connect(self.onTreeSelectionChanged)
        self.form.clearButton.clicked.connect(self.onClear)
        self.form.tree.itemSelectionChanged.connect(
                self.onTreeSelectionChanged)
        self.editorTextChanged = False
        self.form.editor.textChanged.connect(self.onTextChanged)

        self.fillTreeWidget()
        self.fillNotesWidget()

    def reject(self):
        self.saveIfModified()
        super(NotesBrowser, self).reject()

    def onClear(self):
        r = ui.utils.questionBox("Are you sure you want to clear all "
                "formatting?", "Clear formatting?")
        if r == QMessageBox.Yes:
            self.form.editor.setHtml(self.form.editor.toPlainText())
            self.saveIfModified()

    def onTextChanged(self):
        """
        Note: this method is *not* called when switching between volumes
        without making any actual modifications, as the signal is blocked
        in that method, fillNotesWidget().
        """
        self.editorTextChanged = True

    def onTreeSelectionChanged(self):
        self.saveIfModified()
        self.fillNotesWidget()
        # By the time this function is called, the selection has already been
        # changed, so we hold onto this so that saveIfModified() can have the
        # correct reference when it comes time to run.
        if (self._selectionType() != 'nothing' and
                self._selectionType() != 'sourceWithVols'):
            self.lastVolumeSelected = self._selectedVolume()
        else:
            self.lastVolumeSelected = None

    def saveIfModified(self):
        if self.editorTextChanged:
            # we know selection is a volume because it's not possible to
            # change the editor text in a top-level heading or nothing
            newHtml = unicode(self.form.editor.toHtml())
            newHtml = newHtml.replace('&lt;', '<').replace('&gt;', '>')
            self.lastVolumeSelected.setNotes(newHtml)
        self.editorTextChanged = False

    def fillTreeWidget(self):
        sources = db.sources.allSources()
        for source in sources:
            sourceItem = TreeWidgetItem([source.getName()])
            self.form.tree.addTopLevelItem(sourceItem)
            if not source.isSingleVol():
                volumes = db.volumes.volumesInSource(source)
                for volume in volumes:
                    strList = [source.getAbbrev() + str(volume.getNum())]
                    TreeWidgetItem(sourceItem, strList)
            sourceItem.sortChildren(0, Qt.AscendingOrder)
        self.form.tree.sortByColumn(0, Qt.AscendingOrder)

    def fillNotesWidget(self):
        oldBlockSignals = self.form.editor.blockSignals(True)
        st = self._selectionType()
        if st == 'nothing' or st == 'sourceWithVols':
            html = "Please select a %svolume to view notes." % (
                    "source or " if st == 'nothing' else "")
            self.form.editor.setHtml(html)
            self.form.editor.setReadOnly(True)
        elif st == 'sourceWithoutVols' or st == 'volume':
            html = self._selectedVolume().getNotes()
            self.form.editor.setHtml(html)
            self.form.editor.setReadOnly(False)
        self.form.editor.blockSignals(oldBlockSignals)

    def _selectedVolume(self):
        """
        Fetch the volume corresponding to the current selection. 
        
        It is the caller's responsibility to make sure there is a selection for
        which a volume can be fetched (either a volume or a single-volume
        source).
        """

        selectedItem = self.form.tree.selectedItems()[0]
        if self._selectionType() == 'sourceWithoutVols':
            source = db.sources.byName(unicode(selectedItem.text(0)))
            # there's only one volume, so this will work great
            volume = db.volumes.volumesInSource(source)[0]
        else:
            source = db.sources.byName(unicode(selectedItem.parent().text(0)))
            # cut off the abbreviation to get the volume number
            volumeNum = int(selectedItem.text(0).split(source.getAbbrev())[1])
            volume = db.volumes.byNumAndSource(source, volumeNum)
        return volume


    def _selectionType(self):
        """
        Return a string representing the type of thing that's selected in the
        tree view currently:

        - 'nothing' (no selection)
        - 'sourceWithVols' (a multi-volume source, the top-level item)
        - 'sourceWithoutVols' (a single-volume source)
        - 'volume' (a volume of a multi-volume source)
        """
        try:
            si = self.form.tree.selectedItems()[0]
        except IndexError:
            return 'nothing'

        # We know it's not nothing; now check if it's a source.
        if si.parent() is None:
            # A source of what type?
            source = db.sources.byName(unicode(si.text(0)))
            if source.isSingleVol():
                return 'sourceWithoutVols'
            else:
                return 'sourceWithVols'

        # By elimination, it's a volume.
        return 'volume'
