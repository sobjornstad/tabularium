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
    def __init__(self):
        QMainWindow.__init__(self)
        self.form = Ui_MainWindow()
        self.form.setupUi(self)

        self.form.actionQuit.triggered.connect(self.quit)

        self.form.searchGoButton.clicked.connect(self.onSearch)
        self.form.searchBox.returnPressed.connect(self.onSearch)
        self.form.entriesList.itemSelectionChanged.connect(self.fillOccurrences)

        self.initDb()
        self.search = ""
        self.fillEntries()
        self.fillOccurrences()

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

    def fillEntries(self):
        """
        Fill the Entries list box with all entries that match the current
        search and limit criteria. (Right now limits are ignored.)
        """

        self.form.entriesList.clear()
        self.form.occurrencesList.clear()
        entries = db.entries.find(db.entries.percentageWrap(self.search))
        entries.sort(key=lambda i: i.getSortKey().lower())
        for i in entries:
            self.form.entriesList.addItem(i.getName())

    def fillOccurrences(self):
        """
        Fill the Occurrences box with all occurrences of the current entry,
        assuming they match limit criteria. (Right now limits are ignored.)
        """

        self.form.occurrencesList.clear()
        if not self.form.entriesList.currentItem():
            return

        search = unicode(self.form.entriesList.currentItem().text())
        entry = db.entries.find(search)[0]
        occs = entry.getOccurrences()
        for i in occs:
            nbook = i.getNotebook()
            occStr = "%s%s.%s" % (nbook.getType(), nbook.getNum(), i.getRef()[0])
            self.form.occurrencesList.addItem(occStr)

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


    def onSearch(self):
        self.search = unicode(self.form.searchBox.text())
        self.fillEntries()

    def initDb(self):
        db.database.connect(config.DATABASE_FILENAME)

    def quit(self):
        db.database.close()
        sys.exit(0)

def start():
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    app.exec_()
