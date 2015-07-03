# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QApplication, QMainWindow, QFileDialog
from forms.main import Ui_MainWindow
import sys

import config
import db.database
import db.entries

class MainWindow(QMainWindow):
    ### Application lifecycle functions ###
    def __init__(self):
        QMainWindow.__init__(self)
        self.form = Ui_MainWindow()
        self.form.setupUi(self)

        self.form.actionQuit.triggered.connect(self.quit)

        self.form.searchGoButton.clicked.connect(self.onSearch)
        self.form.searchBox.returnPressed.connect(self.onSearch)
        self.form.entriesList.itemSelectionChanged.connect(self.fillOccurrences)
        self.form.occurrencesList.itemSelectionChanged.connect(self.fillInspect)

        self.initDb()
        self.search = ""
        self.fillEntries()

        self.inspectOptions = {}
        items = [self.form.showAddedCheck, self.form.showEnteredCheck,
                 self.form.showNearbyCheck, self.form.showDiaryCheck]
        for i in items:
            i.setChecked(True)
            i.toggled.connect(self.onChangeInspectionOptions)
        self.onChangeInspectionOptions()

        self.searchOptions = {}
        self.form.incrementalCheckbox.setChecked(True) # later, get from prefs?
        self.form.regexCheckbox.setChecked(False) # ditto
        self.form.incrementalCheckbox.toggled.connect(self.onChangeSearchOptions)
        self.form.regexCheckbox.toggled.connect(self.onChangeSearchOptions)
        self.onChangeSearchOptions()

    def initDb(self):
        db.database.connect(config.DATABASE_FILENAME)

    def quit(self):
        db.database.close()
        sys.exit(0)


    ### Setting, resetting, and filling the data windows ###
    def fillEntries(self):
        """
        Fill the Entries list box with all entries that match the current
        search and limit criteria. (Right now limits are ignored.)
        """

        self._resetForEntry()
        entries = db.entries.find(db.entries.percentageWrap(self.search))
        self._fillListWidgetWithEntries(self.form.entriesList, entries)

    def fillOccurrences(self):
        """
        Fill the Occurrences box with all occurrences of the current entry,
        assuming they match limit criteria. (Right now limits are ignored.)
        """

        self._resetForOccurrence()
        if not self.form.entriesList.currentItem():
            return

        search = unicode(self.form.entriesList.currentItem().text())
        entry = db.entries.find(search)[0]
        self.currentOccs = entry.getOccurrences() # hold onto objects for reference
        for i in self.currentOccs:
            nbook = i.getNotebook()
            occStr = "%s%s.%s" % (nbook.getType(), nbook.getNum(), i.getRef()[0])
            self.form.occurrencesList.addItem(occStr)

    def fillInspect(self):
        """
        Dig up the inspection information and fill the boxes with it.
        """

        self._resetForNearby()

        # fetch inspection info
        # the actual occurrence
        row = self.form.occurrencesList.currentRow()
        occ = self.currentOccs[row]
        nbook = occ.getNotebook()
        occStr = "<b>%s%s.%s</b><br>" % (
                nbook.getType(), nbook.getNum(), occ.getRef()[0])
        # the added and edited dates
        daStr = "Entered %s<br>" % occ.getAddedDate()
        deStr = "Modified %s<br>" % occ.getEditedDate()
        # during diary time...
        # we cannot yet do this, as events are unimplemented. that's the idea.

        s = "<center>"
        s += occStr # name of occurrence
        s += daStr # added date
        s += deStr # edited date
        s += ""
        s += "" # during diary time
        s += "" # dates of diary
        s += "</center>"
        self.form.inspectBox.setHtml(s)

        # fill nearby list
        nearby = occ.getNearby()
        if nearby:
            self._fillListWidgetWithEntries(self.form.nearbyList, nearby)
        else:
            self.form.nearbyList.addItem("(No entries nearby)")

    def _fillListWidgetWithEntries(self, widget, entries):
        entries.sort(key=lambda i: i.getSortKey().lower())
        for i in entries:
            widget.addItem(i.getName())


    ### Checkbox / options handling ###
    def onChangeInspectionOptions(self):
        val = not self.form.showNearbyCheck.isChecked()
        self.form.nearbyList.setHidden(val)
        self.form.nearbyLabel.setHidden(val)

        self.inspectOptions['ed'] = self.form.showEnteredCheck.isChecked()
        self.inspectOptions['ad'] = self.form.showAddedCheck.isChecked()
        self.inspectOptions['diary'] = self.form.showDiaryCheck.isChecked()

    def onChangeSearchOptions(self):
        doRegex = self.form.regexCheckbox.isChecked()
        doIncremental = self.form.incrementalCheckbox.isChecked()

        self.searchOptions['regex'] = doRegex
        self.searchOptions['incremental'] = doIncremental

        if doIncremental:
            self.form.searchBox.textChanged.connect(self.onSearch)
            self.onSearch() # immediately update based on current content
        else:
            self.form.searchBox.textChanged.disconnect()


    ### Other action functions ###
    def onSearch(self):
        self.search = unicode(self.form.searchBox.text())
        self.fillEntries()


    ### UTILITIES ###
    ### Reset functions: since more or less needs to be reset for each, do a
    ### sort of cascade.
    def _resetForEntry(self):
        self.form.entriesList.clear()
        self._resetForOccurrence()
    def _resetForOccurrence(self):
        self.form.occurrencesList.clear()
        self._resetForNearby()
    def _resetForNearby(self):
        self.form.nearbyList.clear()
        self.form.inspectBox.clear()


def start():
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    app.exec_()
