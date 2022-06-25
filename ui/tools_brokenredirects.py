# Copyright (c) 2022 Soren Bjornstad <contact@sorenbjornstad.com>

from enum import Enum
import time
from typing import List
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtWidgets import QDialog, QWidget, QTableWidgetItem, QApplication

import db.entries
import db.occurrences

import ui.addentry
import ui.forms.tools_redirects
from ui.utils import questionBox


class RedirectTableCol(Enum):
    """Names for the columns in the redirect table."""
    ENTRY = 0
    SOURCE = 1
    REF = 2


class RedirectsWindow(QDialog):
    "Allow user to find and repair broken redirects."
    def __init__(self, parent: QWidget) -> None:
        QDialog.__init__(self)
        self.form = ui.forms.tools_redirects.Ui_Dialog()
        self.form.setupUi(self)
        self.mw = parent

        self.onFilterEntries()
        self.fillBrokenRedirects()
        self.populateSourceOccurrences()
        self.populateTargetOccurrences()
        self.checkButtonEnablement()

        sf = self.form
        sf.remapButton.clicked.connect(self.onRemap)
        sf.deleteButton.clicked.connect(self.onDelete)
        sf.createButton.clicked.connect(self.onCreate)
        sf.closeButton.clicked.connect(self.reject)

        sf.redirectTable.itemSelectionChanged.connect(self.checkButtonEnablement)
        sf.redirectTable.itemSelectionChanged.connect(self.populateSourceOccurrences)
        sf.entriesList.itemSelectionChanged.connect(self.checkButtonEnablement)
        sf.entriesList.itemSelectionChanged.connect(self.populateTargetOccurrences)
        sf.entriesFilterBox.textChanged.connect(self.onFilterEntries)

    def event(self, event) -> bool:
        "Custom key mappings for the dialog."
        if event.type() == 51:  # keypress
            # Map Ctrl+F to switch to filter box like in the main window.
            if event.key() == Qt.Key_F:
                self.form.entriesFilterBox.selectAll()
                self.form.entriesFilterBox.setFocus()
                return True
            # Map down arrow when the entriesFilterBox is focused
            # to select the first item in the entriesList.
            if self.form.entriesFilterBox.hasFocus() and event.key() == Qt.Key_Down:
                self.form.entriesList.setFocus()
                # I guess -1 because the down arrow gets applied again?
                # I couldn't get it to not do that
                self.form.entriesList.setCurrentRow(-1)
                return True
        return super().event(event)

    def checkButtonEnablement(self) -> None:
        """
        Check if the "Remap" and "Delete" buttons are available.
        """
        canRemap = bool(self.form.redirectTable.selectedItems()
                        and self.form.entriesList.selectedItems())
        self.form.remapButton.setEnabled(canRemap)

        canCreateDelete = bool(self.form.redirectTable.selectedItems())
        self.form.deleteButton.setEnabled(canCreateDelete)
        self.form.createButton.setEnabled(canCreateDelete)

    def fillBrokenRedirects(self):
        "Fill table of broken redirects to be fixed."
        redirects = db.occurrences.brokenRedirects()
        # add two columns to self.form.redirectTable
        self.form.redirectTable.setColumnCount(3)
        self.form.redirectTable.setHorizontalHeaderLabels(["Entry",
                                                           "Source/Vol",
                                                           "Redirects To"])
        for o in redirects:
            # add (entry name, occurrence ref) pairs to the redirect table
            self.form.redirectTable.insertRow(self.form.redirectTable.rowCount())
            self.form.redirectTable.setItem(self.form.redirectTable.rowCount() - 1,
                                            RedirectTableCol.ENTRY.value,
                                            QTableWidgetItem(o.entry.name))
            self.form.redirectTable.setItem(
                self.form.redirectTable.rowCount() - 1,
                RedirectTableCol.SOURCE.value,
                QTableWidgetItem(o.volume.source.abbrev + ' ' + str(o.volume.num))
            )
            self.form.redirectTable.setItem(self.form.redirectTable.rowCount() - 1,
                                            RedirectTableCol.REF.value,
                                            QTableWidgetItem(str(o.ref)))
        self.form.redirectTable.resizeColumnsToContents()


        self.form.redirectTable.selectRow(0)
        self.form.redirectTable.setFocus()

    def populateSourceOccurrences(self) -> None:
        """
        Populate the occurrences box with the occurrences of the entry
        of the selected broken redirect.
        """
        QApplication.processEvents()
        sf = self.form
        selectedEntryName = sf.redirectTable.item(
            sf.redirectTable.currentRow(),
            RedirectTableCol.ENTRY.value
        ).text()
        entry = db.entries.Entry.byName(selectedEntryName)
        assert entry is not None, "Unable to retrieve entry in entry list"

        sf.sourceOccurrencesList.clear()
        sf.sourceOccurrencesList.addItems(
            o.getUOFRepresentation(displayFormatting=True)
            for o in db.occurrences.db.occurrences.fetchForEntry(entry)
        )

    def populateTargetOccurrences(self) -> None:
        """
        Populate the occurrences box with the occurrences of the selected
        target entry.
        """
        QApplication.processEvents()
        sf = self.form

        if sf.entriesList.currentItem() is not None:
            selectedEntryName = sf.entriesList.currentItem().text()
            entry = db.entries.Entry.byName(selectedEntryName)
            assert entry is not None, "Unable to retrieve entry in entry list"

            sf.targetOccurrencesList.clear()
            sf.targetOccurrencesList.addItems(
                o.getUOFRepresentation(displayFormatting=True)
                for o in db.occurrences.db.occurrences.fetchForEntry(entry)
            )

    def onFilterEntries(self) -> None:
        """
        When the text of the filterBox is changed, change the entries box
        to show only the matching items.
        """
        self.form.entriesList.clear()
        self.form.entriesList.addItems(
            i.name
            for i in db.entries.find(self.form.entriesFilterBox.text())
        )

    def onRemap(self) -> None:
        """
        Change the "ref" of the occurrence selected in the redirectTable to the
        name selected in the entriesList.
        """
        sf = self.form
        selectedRow = sf.redirectTable.currentRow()
        entryToUpdate = db.entries.Entry.byName(
            sf.redirectTable.item(selectedRow, RedirectTableCol.ENTRY.value).text()
        )
        assert entryToUpdate is not None, "Unable to retrieve entry in entry list"
        occurrenceRefToUpdate = sf.redirectTable.item(selectedRow,
                                                      RedirectTableCol.REF.value).text()

        results = db.occurrences.fetchForEntryFiltered(
            entryToUpdate,
            ref=occurrenceRefToUpdate
        )
        assert len(results) == 1, "Didn't find exactly one occurrence to update"
        occurrenceToUpdate = results[0]

        newTargetEntryName = sf.entriesList.currentItem().text()
        occurrenceToUpdate.ref = newTargetEntryName

        for i in range(3):
            sf.redirectTable.item(selectedRow, i).setBackground(Qt.green)
        sf.redirectTable.item(selectedRow,
                              RedirectTableCol.REF.value).setText(newTargetEntryName)

        # select the next row in the table, if there is one to select
        if sf.redirectTable.rowCount() > selectedRow + 1:
            sf.redirectTable.selectRow(selectedRow + 1)
        else:
            sf.redirectTable.clearSelection()

    def onDelete(self):
        """
        Delete the occurrence selected in the redirectTable.  If the occurrence
        has no other entries, ask the user whether they'd like to delete the entry
        and do so if appropriate.
        """
        sf = self.form
        selectedRow = sf.redirectTable.currentRow()
        entry = db.entries.Entry.byName(
            sf.redirectTable.item(selectedRow, RedirectTableCol.ENTRY.value).text()
        )
        assert entry is not None, "Unable to retrieve entry in entry list"
        occurrenceRefToDelete = sf.redirectTable.item(selectedRow,
                                                      RedirectTableCol.REF.value).text()

        results = db.occurrences.fetchForEntryFiltered(
            entry,
            ref=occurrenceRefToDelete
        )
        assert len(results) == 1, "Didn't find exactly one occurrence to delete"
        occurrenceToDelete = results[0]

        if len(db.occurrences.fetchForEntry(entry)) == 1:
            if not questionBox(f"This redirect is the only occurrence of the entry "
                               f"'{entry.name}'. If you continue, the entry will be "
                               f"deleted. Continue?",
                               "Delete Entry?"):
                return
            entry.delete()
        else:
            occurrenceToDelete.delete()

        sf.redirectTable.removeRow(selectedRow)
        if sf.redirectTable.rowCount() > selectedRow:
            sf.redirectTable.selectRow(selectedRow)
        else:
            sf.redirectTable.clearSelection()

    def onCreate(self):
        """
        Create a new entry which matches the ref of the occurrence selected in
        the redirectTable.
        """
        sf = self.form
        selectedRow = sf.redirectTable.currentRow()
        newEntryName = sf.redirectTable.item(selectedRow,
                                             RedirectTableCol.ENTRY.value).text()

        ae = ui.addentry.AddEntryWindow(self, self.mw.sh)
        ae.initializeSortKeyCheck(newEntryName, newEntryName)
        ae.exec_()
