# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt4.QtCore import QObject, QEvent
from forms.main import Ui_MainWindow
import sqlite3
import sys

import config
import db.database
import db.entries
import db.occurrences

import ui.addentry
import ui.addoccurrence
import ui.editnotes
import ui.sourcemanager
import ui.volmanager
import ui.utils

class MwEventFilter(QObject):
    """
    In order to keep items in menus properly enabled and disabled based on the
    selection, we use a series of methods connected to the aboutToShow()
    methods of menus. However, this causes keyboard shortcuts to not get
    correctly enabled or disabled when the state changes until you open the
    menu. To rectify this, we install this event filter, which checks the state
    whenever you press a modifier key that begins any shortcut. This doesn't
    appear to cause any noticeable performance degradation.
    """

    def __init__(self):
        self.mw = None
        self.actOnKeys = (16777251, 16777249, 16777248) # ctrl, alt, shift
        super(MwEventFilter, self).__init__()

    def setupFilter(self, mw):
        self.mw = mw

    def eventFilter(self, receiver, event):
       if event.type() == 51:
           #print event.key()
           if event.key() in self.actOnKeys and self.mw is not None:
               self.mw.checkAllMenus()
       return super(MwEventFilter,self).eventFilter(receiver, event)

class MainWindow(QMainWindow):
    ### Application lifecycle functions ###
    def __init__(self, qfilter):
        # set up form and window
        QMainWindow.__init__(self)
        self.form = Ui_MainWindow()
        self.form.setupUi(self)
        sf = self.form
        self.qfilter = qfilter
        self.qfilter.setupFilter(self)

        # connect buttons and signals
        sf.searchGoButton.clicked.connect(self.onSearch)
        sf.searchBox.returnPressed.connect(self.onReturnInSearch)
        sf.entriesList.itemSelectionChanged.connect(self.fillOccurrences)
        sf.occurrencesList.itemSelectionChanged.connect(self.fillInspect)

        # connect menu check functions (for enable/disable)
        sf.menuEntry.aboutToShow.connect(self.checkEntryMenu)
        sf.menuInspect.aboutToShow.connect(self.checkInspectMenu)
        sf.menuOccurrence.aboutToShow.connect(self.checkOccurrenceMenu)

        # connect menu actions
        self._setupMenus()

        # initialize db and set up searching and entries
        self.initDb()
        self.search = ""
        self.searchOptions = {}
        sf.incrementalCheckbox.setChecked(True) # later, get from prefs?
        sf.regexCheckbox.setChecked(False) # ditto
        sf.incrementalCheckbox.toggled.connect(self.onChangeSearchOptions)
        sf.regexCheckbox.toggled.connect(self.onChangeSearchOptions)
        self.onChangeSearchOptions()
        self.fillEntries()

        # set up inspection options
        self.inspectOptions = {}
        items = [sf.showAddedCheck, sf.showEnteredCheck,
                 sf.showNearbyCheck, sf.showDiaryCheck]
        for i in items:
            i.setChecked(True)
            i.toggled.connect(self.onChangeInspectionOptions)
        self.onChangeInspectionOptions()

    def initDb(self):
        db.database.connect(config.DATABASE_FILENAME)

    def closeEvent(self, event):
        "Catch click of the X button, etc., and properly quit."
        self.quit()

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
        if self.searchOptions['regex']:
            try:
                entries = db.entries.find(self.search, True)
            except sqlite3.OperationalError:
                # regex in search box is invalid
                entries = []
        else:
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

        entry = self._fetchCurrentEntry()
        self.currentOccs = entry.getOccurrences() # hold onto objects for reference
        for i in self.currentOccs:
            vol = i.getVolume()
            occStr = "%s%s.%s" % (vol.getSource().getAbbrev(), vol.getNum(),
                                  i.getRef()[0])
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
        vol = occ.getVolume()
        occStr = "<b>%s%s.%s</b><br>" % (
                vol.getSource().getAbbrev(), vol.getNum(), occ.getRef()[0])
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


    ### Functions from the menu ###
    #TODO: When returning from a menu like "add entry," make sure the view is
    # updated. This is harder than just running _resetForEntry(), though, as
    # we don't want to wipe out the user's selection.
    def _setupMenus(self):
        sf = self.form
        sf.actionQuit.triggered.connect(self.quit)
        sf.actionFollow_Nearby_Entry.triggered.connect(self.onInspect_FollowNearby)
        sf.actionAdd.triggered.connect(self.onAddEntry)
        sf.actionNew_based_on.triggered.connect(self.onAddEntryBasedOn)
        sf.actionManage_sources.triggered.connect(self.onManageSources)
        sf.actionManage_volumes.triggered.connect(self.onManageVolumes)
        sf.actionNotes.triggered.connect(self.onViewNotes)
        sf.actionDelete.triggered.connect(self.onDeleteEntry)
        sf.actionAdd_occ.triggered.connect(self.onAddOccurrence)

    def onInspect_FollowNearby(self):
        # NOTE: This can select other, longer, entries, as it %-pads. I'm not
        # sure if this is a problem, as it won't select *shorter* ones, and the
        # shortest one is the top one and will be chosen.
        entryName = unicode(self.form.nearbyList.currentItem().text())
        self.form.searchBox.setText(entryName)
        self.onSearch()
        self._selectFirstAndFocus(self.form.entriesList)
        #TODO: Ideally we would autoselect the occurrence that was nearby,
        #      but that's a LOT more work, so not right away.

    def onAddEntry(self, entryName=None):
        ae = ui.addentry.AddEntryWindow(self)
        if entryName:
            ae.initializeSortKeyCheck(entryName)
        ae.exec_()
    def onAddEntryBasedOn(self):
        #TODO: This doesn't preserve classification
        entry = self._fetchCurrentEntry()
        self.onAddEntry(entry.getName())
    def onDeleteEntry(self):
        # at some point, replace this with undo
        row = self.form.entriesList.currentRow()
        entry = self._fetchCurrentEntry()
        eName = entry.getName()
        occsAffected = len(db.occurrences.fetchForEntry(entry))
        r = ui.utils.questionBox("Do you really want to delete the entry '%s' "
                "and its %i occurrence%s?" % (eName, occsAffected,
                "" if occsAffected == 1 else "s"), "Delete entry?")
        if r == QMessageBox.Yes:
            entry.delete()
            self.form.entriesList.takeItem(row)


    def onAddOccurrence(self):
        # Anna-Christina's window
        ac = ui.addoccurrence.AddOccWindow(self, self._fetchCurrentEntry())
        ac.exec_()
    def onDeleteOccurrence(self):
        #TODO pending freezing of the format for occurrence display
        assert False, "this function is not yet implemented"
        return

        # at some point, replace this with undo
        row = self.form.occurrencesList.currentRow()

        eName = entry.getName()
        occsAffected = len(db.occurrences.fetchForEntry(entry))
        r = ui.utils.questionBox("Do you really want to delete the entry '%s' "
                "and its %i occurrence%s?" % (eName, occsAffected,
                "" if occsAffected == 1 else "s"), "Delete entry?")
        if r == QMessageBox.Yes:
            entry.delete()
            self.form.entriesList.takeItem(row)

    def onManageSources(self):
        ms = ui.sourcemanager.SourceManager(self)
        ms.exec_()
    def onManageVolumes(self):
        mv = ui.volmanager.VolumeManager(self)
        mv.exec_()
    def onViewNotes(self):
        nb = ui.editnotes.NotesBrowser(self)
        nb.exec_()

    ### Menu check functions ###
    def checkAllMenus(self):
        # called from the event filter to check keyboard shortcuts
        self.checkEntryMenu()
        self.checkInspectMenu()
        self.checkOccurrenceMenu()
    def checkEntryMenu(self):
        sf = self.form
        ifCondition = sf.entriesList.currentRow() != -1
        sf.actionNew_based_on.setEnabled(ifCondition)
        sf.actionAdd_Redirect_To.setEnabled(ifCondition)
        sf.actionEdit.setEnabled(ifCondition)
        sf.actionMerge_into.setEnabled(ifCondition)
        sf.actionDelete.setEnabled(ifCondition)
    def checkInspectMenu(self):
        sf = self.form
        ifCondition = sf.nearbyList.currentRow() != -1
        sf.actionFollow_Nearby_Entry.setEnabled(ifCondition)
    def checkOccurrenceMenu(self):
        sf = self.form
        ifNoOccurrence = sf.occurrencesList.currentRow() != -1
        sf.actionChange_page.setEnabled(ifNoOccurrence)
        sf.actionChange_volume.setEnabled(ifNoOccurrence)
        sf.actionDelete_occ.setEnabled(ifNoOccurrence)
        sf.actionMove_to_entry.setEnabled(ifNoOccurrence)
        #TODO: next should actually be enabled only if selection is a redirect
        sf.actionFollow_redirect.setEnabled(ifNoOccurrence)
        ifNoEntry = sf.entriesList.currentRow() != -1
        sf.actionAdd_occ.setEnabled(ifNoEntry)

    ### Other action functions ###
    def onReturnInSearch(self):
        if self.searchOptions['incremental']:
            self._selectFirstAndFocus(self.form.entriesList)
        else:
            self.onSearch()
    def onSearch(self):
        self.search = unicode(self.form.searchBox.text())
        self.fillEntries()


    ### UTILITIES ###
    ### Database access functions
    def _fetchCurrentEntry(self):
        """
        Get an Entry object for the currently selected entry. Return None if
        nothing is selected.
        """
        try:
            search = unicode(self.form.entriesList.currentItem().text())
        except AttributeError:
            return None
        else:
            return db.entries.find(search)[0]
    def _fetchCurrentOccurrence(self):
        """
        As in _fetchCurrentEntry, for the currently selected occurrence.
        """
        try:
            search = unicode(self.form.occurrencesList.currentItem().text())

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

    def _selectFirstAndFocus(self, widget):
        widget.setCurrentRow(0)
        widget.setFocus()


def start():
    app = QApplication(sys.argv)
    qfilter = MwEventFilter()
    app.installEventFilter(qfilter)
    mw = MainWindow(qfilter)
    mw.show()
    app.exec_()
