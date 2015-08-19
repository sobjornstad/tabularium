# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt4.QtCore import QObject, QEvent, Qt
from forms.main import Ui_MainWindow
import sqlite3
import sys

import config
import db.consts
import db.database
import db.entries
import db.occurrences
import db.sources

import ui.addentry
import ui.addoccurrence
import ui.editnotes
import ui.settings
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
        sf.searchAddButton.clicked.connect(self.onAddFromSearch)
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
        items = (sf.showInspectCheck, sf.showSourceNameCheck, sf.showAddedCheck,
                 sf.showEnteredCheck, sf.showNearbyCheck, sf.showDiaryCheck)
        for i in items:
            i.toggled.connect(self.onChangeInspectionOptions)
        self.onChangeInspectionOptions()

        # set up limits
        self.updateSourceCombo()
        sf.enteredCheck.toggled.connect(self.onEnteredToggled)
        sf.modifiedCheck.toggled.connect(self.onModifiedToggled)
        sf.sourceCheck.toggled.connect(self.onSourceToggled)
        sf.occurrencesSourceCombo.activated.connect(self.onSourceToggled)
        sf.volumeCheck.toggled.connect(self.onVolumeToggled)
        self.onEnteredToggled()
        self.onModifiedToggled()
        self.onSourceToggled()
        self.onVolumeToggled()

        # set up configuration fetch options, and restore options
        self.sh = ui.settings.SettingsHandler(self)
        self.restoreWindowState()

    def initDb(self):
        db.database.connect(config.DATABASE_FILENAME)

    def closeEvent(self, event):
        "Catch click of the X button, etc., and properly quit."
        self.quit()

    def quit(self):
        self.saveWindowState()
        db.database.close()
        sys.exit(0)

    def saveWindowState(self):
        sf = self.form
        sh = self.sh
        sh.put('mainSplitterState', sf.mainSplitter.saveState())
        sh.put('secondarySplitterState', sf.inspectNearbySplitter.saveState())
        sh.put('incrementalCheck', sf.incrementalCheckbox.isChecked())
        sh.put('regexCheck', sf.regexCheckbox.isChecked())
        sh.put('showInspectCheck', sf.showInspectCheck.isChecked())
        sh.put('showSourceNameCheck', sf.showSourceNameCheck.isChecked())
        sh.put('showAddedCheck', sf.showAddedCheck.isChecked())
        sh.put('showEnteredCheck', sf.showEnteredCheck.isChecked())
        sh.put('showDiaryCheck', sf.showDiaryCheck.isChecked())
        sh.put('showNearbyCheck', sf.showNearbyCheck.isChecked())
        sh.put('entriesNamesCheck', sf.entriesNamesCheck.isChecked())
        sh.put('entriesPlacesCheck', sf.entriesPlacesCheck.isChecked())
        sh.put('entriesQuotationsCheck', sf.entriesQuotationsCheck.isChecked())
        sh.put('entriesTitlesCheck', sf.entriesTitlesCheck.isChecked())
        sh.put('entriesCommonsCheck', sf.entriesCommonsCheck.isChecked())
        sh.put('entriesUnclassifiedCheck', sf.entriesUnclassifiedCheck.isChecked())
        sh.put('enteredCheck', sf.enteredCheck.isChecked())
        sh.put('modifiedCheck', sf.modifiedCheck.isChecked())
        sh.put('sourceCheck', sf.sourceCheck.isChecked())
        sh.put('volumeCheck', sf.volumeCheck.isChecked())

        sh.put('sourceCombo', sf.occurrencesSourceCombo.currentText())
        sh.put('minVolume', sf.occurrencesVolumeSpin1.value())
        sh.put('maxVolume', sf.occurrencesVolumeSpin2.value())
        sh.put('minDateAdded', sf.occurrencesAddedDateSpin1.date())
        sh.put('maxDateAdded', sf.occurrencesAddedDateSpin2.date())
        sh.put('minDateEdited', sf.occurrencesEditedDateSpin1.date())
        sh.put('maxDateEdited', sf.occurrencesEditedDateSpin2.date())
        sh.sync()

    def restoreWindowState(self):
        sf = self.form
        sh = self.sh
        def wrapper(func, key):
            """
            Set state to saved value if there is one.
            Arguments:
                func - A function to run with one argument, the value of /key/.
                    func() will not be run at all if there is no saved value.
                key - The key to look for in the configuration and pass as the
                    function argument.
            Return:
                func()'s return value if executed, else 'NotExecuted'.
            """
            val = sh.get(key)
            if val is not None:
                return func(val)
            else:
                return 'NotExecuted'

        # splitters
        wrapper(sf.mainSplitter.restoreState, 'mainSplitterState')
        wrapper(sf.inspectNearbySplitter.restoreState, 'secondarySplitterState')

        # checkboxes
        wrapper(sf.incrementalCheckbox.setChecked, 'incrementalCheck')
        wrapper(sf.regexCheckbox.setChecked, 'regexCheck')
        wrapper(sf.showInspectCheck.setChecked, 'showInspectCheck')
        wrapper(sf.showSourceNameCheck.setChecked, 'showSourceNameCheck')
        wrapper(sf.showAddedCheck.setChecked, 'showAddedCheck')
        wrapper(sf.showEnteredCheck.setChecked, 'showEnteredCheck')
        wrapper(sf.showDiaryCheck.setChecked, 'showDiaryCheck')
        wrapper(sf.showNearbyCheck.setChecked, 'showNearbyCheck')
        wrapper(sf.entriesNamesCheck.setChecked, 'entriesNamesCheck')
        wrapper(sf.entriesPlacesCheck.setChecked, 'entriesPlacesCheck')
        wrapper(sf.entriesQuotationsCheck.setChecked, 'entriesQuotationsCheck')
        wrapper(sf.entriesTitlesCheck.setChecked, 'entriesTitlesCheck')
        wrapper(sf.entriesCommonsCheck.setChecked, 'entriesCommonsCheck')
        wrapper(sf.entriesUnclassifiedCheck.setChecked, 'entriesUnclassifiedCheck')
        wrapper(sf.enteredCheck.setChecked, 'enteredCheck')
        wrapper(sf.modifiedCheck.setChecked, 'modifiedCheck')
        wrapper(sf.sourceCheck.setChecked, 'sourceCheck')
        wrapper(sf.volumeCheck.setChecked, 'volumeCheck')
        def setupSourceCombo(value):
            i = sf.occurrencesSourceCombo.findText(value)
            sf.occurrencesSourceCombo.setCurrentIndex(i)
            self.onSourceToggled() # for whatever reason above doesn't emit
        wrapper(setupSourceCombo, 'sourceCombo')
        wrapper(sf.occurrencesVolumeSpin1.setValue, 'minVolume')
        wrapper(sf.occurrencesVolumeSpin2.setValue, 'maxVolume')
        wrapper(sf.occurrencesAddedDateSpin1.setDate, 'minDateAdded')
        wrapper(sf.occurrencesAddedDateSpin2.setDate, 'maxDateAdded')
        wrapper(sf.occurrencesEditedDateSpin1.setDate, 'minDateEdited')
        wrapper(sf.occurrencesEditedDateSpin2.setDate, 'maxDateEdited')


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
        # hold onto objects for reference by _fetchCurrentOccurrence
        self.currentOccs = entry.getOccurrences()
        for i in self.currentOccs:
            self.form.occurrencesList.addItem(str(i))

    def fillInspect(self):
        """
        Dig up the inspection information and fill the boxes with it.
        """

        self._resetForNearby()

        # fetch inspection info
        # the actual occurrence
        occ = self._fetchCurrentOccurrence()
        if occ is None:
            return
        vol = occ.getVolume()
        source = vol.getSource()
        # the added and edited dates
        daStr = "Entered %s<br>" % occ.getAddedDate()
        deStr = "Modified %s<br>" % occ.getEditedDate()
        # during diary time...
        diaryVolume = db.volumes.findDateInDiary(occ.getAddedDate())

        # format
        s = "<center>"
        s += "<b>%s</b><br>" % occ # name of occurrence
        if self.inspectOptions['sn']:
            s += "(<i>%s</i>)<br>" % (source.getName())
        if self.inspectOptions['ad']:
            s += daStr # added date
        if self.inspectOptions['ed']:
            s += deStr # edited date
        if self.inspectOptions['diary']:
            if diaryVolume is not None:
                s += "<br>"
                s += "Entered during<br>"
                s += "diary volume %i" % (diaryVolume.getNum())
            else:
                s += "(no diary volume open<br>"
                s += "when entered)"
        s += ""
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
        sf = self.form

        doShowNearby = self.form.showNearbyCheck.isChecked()
        self.form.nearbyList.setHidden(not doShowNearby)
        self.form.nearbyLabel.setHidden(not doShowNearby)

        doShowInspect = self.form.showInspectCheck.isChecked()
        self.form.inspectBox.setHidden(not doShowInspect)
        self.form.inspectLabel.setHidden(not doShowInspect)
        for i in (sf.showSourceNameCheck, sf.showAddedCheck,
                  sf.showEnteredCheck, sf.showDiaryCheck):
            i.setEnabled(doShowInspect)

        # When hiding/showing inspect/nearby windows, expand the other to fill
        # the whole screen. This is a bit messy because we have to save the
        # current state (i.e., the size of the splits) if and only if we are
        # moving from a state of both showing to a state of one showing, and we
        # don't have information about which state we were in before.
        try:
            self.nearbySplitterState
        except AttributeError:
            self.nearbySplitterState = None
            self.noInspectsDisplayed = False
        if doShowInspect and doShowNearby:
            if self.nearbySplitterState is not None:
                sf.inspectNearbySplitter.restoreState(self.nearbySplitterState)
        elif doShowInspect and not doShowNearby:
            if not self.noInspectsDisplayed:
                self.nearbySplitterState = sf.inspectNearbySplitter.saveState()
            self.noInspectsDisplayed = False
            sf.inspectNearbySplitter.setSizes([100000, 0])
        elif not doShowInspect and doShowNearby:
            if not self.noInspectsDisplayed:
                self.nearbySplitterState = sf.inspectNearbySplitter.saveState()
            self.noInspectsDisplayed = False
            self.form.inspectNearbySplitter.setSizes([0, 100000])
        elif not doShowInspect and not doShowNearby:
            self.noInspectsDisplayed = True

        self.inspectOptions['sn'] = self.form.showSourceNameCheck.isChecked()
        self.inspectOptions['ed'] = self.form.showEnteredCheck.isChecked()
        self.inspectOptions['ad'] = self.form.showAddedCheck.isChecked()
        self.inspectOptions['diary'] = self.form.showDiaryCheck.isChecked()
        self.fillInspect()

    def onChangeSearchOptions(self):
        doRegex = self.form.regexCheckbox.isChecked()
        doIncremental = self.form.incrementalCheckbox.isChecked()

        self.searchOptions['regex'] = doRegex
        self.searchOptions['incremental'] = doIncremental

        if doIncremental:
            self.form.searchBox.textChanged.connect(self.onSearch)
            #self.form.searchAddButton.setDefault(True)
            #self.onSearch() # immediately update based on current content
        else:
            #self.form.searchAddButton.setDefault(False)
            try:
                self.form.searchBox.textChanged.disconnect()
            except TypeError: # not connected in the first place
                pass

    def onEnteredToggled(self):
        state = self.form.enteredCheck.isChecked()
        self.form.occurrencesAddedDateSpin1.setEnabled(state)
        self.form.occurrencesAddedDateSpin2.setEnabled(state)
        mind, maxd = db.utils.minMaxDatesOccurrenceEnteredModified()
        self.form.occurrencesAddedDateSpin1.setMinimumDate(mind)
        self.form.occurrencesAddedDateSpin1.setMaximumDate(maxd)
        self.form.occurrencesAddedDateSpin2.setMinimumDate(mind)
        self.form.occurrencesAddedDateSpin2.setMaximumDate(maxd)
        self.form.occurrencesAddedDateSpin1.setDate(mind)
        self.form.occurrencesAddedDateSpin2.setDate(maxd)

    def onModifiedToggled(self):
        state = self.form.modifiedCheck.isChecked()
        self.form.occurrencesEditedDateSpin1.setEnabled(state)
        self.form.occurrencesEditedDateSpin2.setEnabled(state)
        mind, maxd = db.utils.minMaxDatesOccurrenceEnteredModified()
        self.form.occurrencesEditedDateSpin1.setMinimumDate(mind)
        self.form.occurrencesEditedDateSpin1.setMaximumDate(maxd)
        self.form.occurrencesEditedDateSpin2.setMinimumDate(mind)
        self.form.occurrencesEditedDateSpin2.setMaximumDate(maxd)
        self.form.occurrencesEditedDateSpin1.setDate(mind)
        self.form.occurrencesEditedDateSpin2.setDate(maxd)

    def onSourceToggled(self):
        state = self.form.sourceCheck.isChecked()
        self.form.occurrencesSourceCombo.setEnabled(state)
        if state:
            source = self._getSourceComboSelection()
            if type(source) != type('all'):
                self.form.volumeCheck.setEnabled(True)
                self.onVolumeToggled() # because if already enabled, above will
                                       # not emit the signal again
        else:
            self.form.volumeCheck.setChecked(False)
            self.form.volumeCheck.setEnabled(False)
            self.form.occurrencesVolumeSpin1.setMinimum(1)
            self.form.occurrencesVolumeSpin1.setMaximum(1)
            self.form.occurrencesVolumeSpin2.setMinimum(1)
            self.form.occurrencesVolumeSpin2.setMaximum(1)
            self.form.occurrencesSourceCombo.setCurrentIndex(0) # all

    def onVolumeToggled(self):
        state = self.form.volumeCheck.isChecked()
        self.form.occurrencesVolumeSpin1.setEnabled(state)
        self.form.occurrencesVolumeSpin2.setEnabled(state)
        source = self._getSourceComboSelection()
        if type(source) != type('all'):
            # if check fails, then volume will not be displayed anyway
            minv, maxv = source.getVolVal()
            # update volume max/min to match volval
            self.form.occurrencesVolumeSpin1.setMinimum(minv)
            self.form.occurrencesVolumeSpin1.setMaximum(maxv)
            self.form.occurrencesVolumeSpin2.setMinimum(minv)
            self.form.occurrencesVolumeSpin2.setMaximum(maxv)
            self.form.occurrencesVolumeSpin1.setValue(minv)
            self.form.occurrencesVolumeSpin2.setValue(maxv)

    def updateSourceCombo(self):
        self.form.occurrencesSourceCombo.clear()
        self.form.occurrencesSourceCombo.addItem(db.consts.noSourceLimitText)
        for i in db.sources.allSources():
            self.form.occurrencesSourceCombo.addItem(i.getName())

    def _getSourceComboSelection(self):
        """
        Return the Source currently selected, or 'all' if all sources option
        is selected.
        """
        name = unicode(self.form.occurrencesSourceCombo.currentText())
        if name == db.consts.noSourceLimitText:
            return 'all'
        else:
            return db.sources.byName(name)


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
        sf.actionDelete_occ.triggered.connect(self.onDeleteOccurrence)
        sf.actionSource_notes.triggered.connect(self.onSourceNotes)
        sf.actionDiary_notes.triggered.connect(self.onDiaryNotes)

    def onInspect_FollowNearby(self):
        entryName = unicode(self.form.nearbyList.currentItem().text())
        self.form.searchBox.setText(entryName)
        self.onSearch()
        item = self.form.entriesList.findItems(entryName, Qt.MatchExactly)[0]
        self.form.entriesList.setCurrentItem(item)
        self.form.entriesList.setFocus()
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
        row = self.form.entriesList.currentRow()
        entry = self._fetchCurrentEntry()
        eName = entry.getName()
        occsAffected = len(db.occurrences.fetchForEntry(entry))
        # at some point, replace this with undo
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
        row = self.form.occurrencesList.currentRow()
        occ = self._fetchCurrentOccurrence()
        r = ui.utils.questionBox("Do you really want to delete the "
                                 "occurrence '%s'?" % str(occ),
                                 "Delete entry?")
        if r == QMessageBox.Yes:
            occ.delete()
            self.form.occurrencesList.takeItem(row)

    def onSourceNotes(self):
        occ = self._fetchCurrentOccurrence()
        volume = occ.getVolume()
        source = volume.getSource()
        nb = ui.editnotes.NotesBrowser(self, jumpToSource=source,
                                       jumpToVolume=volume)
        nb.exec_()
    def onDiaryNotes(self):
        occ = self._fetchCurrentOccurrence()
        diaryVolume = db.volumes.findDateInDiary(occ.getAddedDate())
        source = diaryVolume.getSource()
        nb = ui.editnotes.NotesBrowser(self, jumpToSource=source,
                                       jumpToVolume=diaryVolume)
        nb.exec_()

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
        ifCondition = sf.occurrencesList.currentRow() != -1
        sf.actionSource_notes.setEnabled(ifCondition)
        sf.actionDiary_notes.setEnabled(ifCondition)
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
        self.onSearch()
        numResults = self.form.entriesList.count()

        if self.searchOptions['incremental']:
            if numResults > 0:
                self._selectFirstAndFocus(self.form.entriesList)
            else:
                self.onAddFromSearch()
        else:
            if numResults == 0:
                self.form.searchAddButton.setFocus()

    def onSearch(self):
        self.search = unicode(self.form.searchBox.text())
        self.fillEntries()

    def onAddFromSearch(self):
        entryName = unicode(self.form.searchBox.text())
        self.onAddEntry(entryName)


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
        Get an Occurrence object for the currently selected entry. Return None if
        nothing is selected.
        """
        row = self.form.occurrencesList.currentRow()
        if row == -1: # no occurrence selected
            return None
        return self.currentOccs[row]

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
