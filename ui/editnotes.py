# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

"""
Browser and editor for notes on sources

This file contains classes for the dialog itself and for a tree widget item
with a custom sort. See NotesBrowser for general information on the browser
dialog.
"""

import re

from PyQt4.QtGui import QDialog, QMessageBox, QTreeWidgetItem
from PyQt4.QtCore import Qt
import ui.forms.editnotes

import ui.utils
import db.consts
import db.sources
import db.volumes

class TreeWidgetItem(QTreeWidgetItem):
    """
    A tree widget item that sorts numerically on volume names and numbers
    rather than strictly alphabetically.

    See http://stackoverflow.com/questions/21030719/
    sort-a-pyside-qtgui-qtreewidget-by-an-alpha-numeric-column.
    """
    def __lt__(self, other):
        key1 = self.text(0)
        key2 = other.text(0)
        return self.naturalSortKey(key1) < self.naturalSortKey(key2)

    @staticmethod
    def naturalSortKey(key):
        """
        Sort using numerical sort where possible (splitting at letter/number
        boundaries and then sorting the tuples of these fragments).

        e.g., "CB45hc" and "CB4hc" would be sorted as ('CB', 45, 'hc') and
        ('CB', 4, 'hc'), putting the latter first.
        """
        regex = r'(\d*\.\d+|\d+)'
        parts = re.split(regex, key)
        return tuple((e if i % 2 == 0 else float(e))
                      for i, e in enumerate(parts))


class NotesBrowser(QDialog):
    """
    Implements a dialog with a tree structure in the left pane to look through
    sources (top-level nodes) and volumes (second-level nodes), and a rich text
    editor in the right pane to display/edit the notes.
    """
    # Ideally we would handle this with a model/view; if I ever really feel
    # like refactoring and have nothing better to do, we can do it...but I
    # think the widget is a decent way to handle it for now, so I don't have
    # to learn how to write a tree view model for this one thing.
    def __init__(self, parent, jumpToSource=None, jumpToVolume=None):
        QDialog.__init__(self)
        self.form = ui.forms.editnotes.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.closeButton.clicked.connect(self.reject)
        self.form.parseButton.clicked.connect(self.onTreeSelectionChanged)
        self.form.clearButton.clicked.connect(self.onClear)
        self.form.tree.itemSelectionChanged.connect(
                self.onTreeSelectionChanged)
        self.editorTextChanged = False
        self.form.editor.textChanged.connect(self.onTextChanged)

        self.currentlySelectedVolume = None
        self._fillTreeWidget()
        self.fillNotesWidget()

        if jumpToSource and jumpToVolume:
            sourceName = jumpToSource.getName()
            # the following is the way we choose to display volume names, and
            # could change in the future
            volumeName = jumpToSource.getAbbrev() + str(jumpToVolume.getNum())
            item = self.form.tree.findItems(sourceName, Qt.MatchExactly)[0]
            numChildren = item.childCount()
            if numChildren == 0:
                # Either there are no volumes (which is not the case because
                # there's an occurrence), or this is a single-volume source.
                # Thus, select the source.
                found = item
            else:
                found = None
                for childNum in range(numChildren):
                    if unicode(item.child(childNum).text(0)) == volumeName:
                        found = item.child(childNum)
                        break
            if found is not None:
                self.form.tree.setCurrentItem(found)

    def reject(self):
        self.saveIfModified()
        super(NotesBrowser, self).reject()

    def onClear(self):
        "After confirmation, strip all HTML from the notes text."
        r = ui.utils.questionBox("Are you sure you want to clear all "
                "formatting?", "Clear formatting?")
        if r == QMessageBox.Yes:
            self.form.editor.setHtml(self.form.editor.toPlainText())
            self.saveIfModified()

    def onTextChanged(self):
        """
        When the text of the notes pane is edited by the user (we block signals
        when changing the text of the widget by switching volumes), set a flag
        indicating such so that we know it needs to be saved to the database
        when we change the view.
        """
        self.editorTextChanged = True

    def onTreeSelectionChanged(self):
        """
        When a new selection is made in the tree, save notes and change to
        displaying the new notes. Also, set currentlySelectedVolume: it needs
        to be reset anytime the selection changes (but not on a save that
        doesn't change the selection, like "parse HTML" or closing the dialog)
        so that it will always be in sync with the set of notes we're currently
        editing. See saveIfModified() for information on the motivation for
        this variable.
        """
        self.saveIfModified()
        self.fillNotesWidget()

        if (self._selectionType() != 'nothing' and
                self._selectionType() != 'sourceWithVols'):
            self.currentlySelectedVolume = self._selectedVolume()
        else:
            self.currentlySelectedVolume = None

    def saveIfModified(self):
        """
        If onTextChanged() has set the flag, dump the text of the notes pane to
        the database. If the plain text is nothing, save a blank in the
        database instead of a bunch of empty HTML tags (this allows us to see
        that there are no notes in the relevant column of the source manager).

        Because the selection has already been made from the toolkit's
        perspective by the time this function will ever be called, we use a
        variable called self.currentlySelectedVolume to hold the volume that we
        actually want to be modifying. This is set by onTreeSelectionChanged.

        When done, unset the flag (as we've saved).
        """
        if self.editorTextChanged:
            # we know selection is a volume because it's not possible to
            # change the editor text in a top-level heading, or nothing
            if not unicode(self.form.editor.toPlainText()).strip():
                self.currentlySelectedVolume.setNotes('')
            else:
                newHtml = unicode(self.form.editor.toHtml())
                newHtml = newHtml.replace('&lt;', '<').replace('&gt;', '>')
                self.currentlySelectedVolume.setNotes(newHtml)
        self.editorTextChanged = False

    def fillNotesWidget(self):
        """
        Called on tree selection to put the notes in the notes pane. If the
        selection is a source that is not a single-volume (and thus doesn't
        have any notes associated with it), put some boilerplate in and disable
        editing.

        We block signals so that changing the text of the widget (to load up a
        new set of notes) doesn't set the modified bit and require a save.
        """
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

    def _fillTreeWidget(self):
        """
        Fill the tree widget with all existing sources. This is called by the
        constructor and should not be called (or needed) afterwards, as it
        doesn't clear the widget before beginning.
        """
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
