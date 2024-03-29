"""
main.py

Implementation of the main window for Tabularium, where searches are done and
other functions are started.
"""

# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>
# pylint: disable=too-many-lines


import datetime
import functools
import os
import subprocess
import sqlite3
import sys
import traceback
from typing import Callable, Optional

# for some reason pylint thinks these don't exist, but they work fine
# pylint: disable=no-name-in-module
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QLabel, QListWidget
from PyQt5.QtCore import QObject, Qt, QDateTime

import db.analytics
import db.consts
import db.database
import db.entries
import db.exporting
import db.importing
import db.occurrences
import db.printing
import db.sources

import ui.about
import ui.addentry
import ui.addoccurrence
import ui.editnotes
import ui.editoccurrence
import ui.mergeentry
import ui.names2faces
import ui.opendatabase
import ui.settings
import ui.sourcemanager
import ui.volmanager
import ui.utils
import ui.tools_classification
import ui.tools_brokenredirects

from ui.forms.main import Ui_MainWindow

APPLICATION_VERSION = "0.3.1"

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
        super().__init__()

    def setupFilter(self, mw):
        self.mw = mw

    def eventFilter(self, receiver, event):
        """
        Intercept keypress events, I think: the value of event.type() was
        determined entirely by experimentation!
        """
        if event.type() == 51:
            #print event.key()
            if event.key() in self.actOnKeys and self.mw is not None:
                self.mw.checkAllMenus()
        return super().eventFilter(receiver, event)


def preserveSelectionsDuring(func: Callable) -> Callable:
    """
    Decorator for event handlers and other methods that mutate the database
    but want to preserve the user's selections as much as possible.
    Before calling the function, selections are saved;
    if the handler returns true, the display is updated and selections
    are restored. (If the handler ended up not doing anything, say because
    the user canceled the operation, this lets us save a UI update.)
    """
    def _useQtActionHack(argList):
        """
        For actions triggered by menus, Qt always passes an "isChecked" parameter,
        which is completely useless unless you have a checkable action. Qt is
        smart and silently discards it if your event handler has no arguments,
        but shoving the decorator in the way inhibits this action. This hack
        will silently discard a second boolean parameter if the only argument
        to the function under decoration is 'self'.
        """
        return (
            func.__code__.co_varnames[:func.__code__.co_argcount] == ('self',)
            and len(argList) == 1
            and argList[0] in (True, False))

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        self.saveSelections()
        if _useQtActionHack(args):
            retval = func(self)
        else:
            retval = func(self, *args, **kwargs)
        if retval:
            self.updateAndRestoreSelections()
    return wrapper


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class MainWindow(QMainWindow):
    "Main window class."

    ### Application lifecycle functions ###
    def __init__(self, qfilter):
        # set up form and window
        QMainWindow.__init__(self)
        self.form = Ui_MainWindow()
        self.form.setupUi(self)
        self.qfilter = qfilter
        self.qfilter.setupFilter(self)
        self.nearbySplitterState = None
        self.noInspectsDisplayed = False
        self.currentOccs = None

        # connect buttons and signals
        sf = self.form
        sf.searchGoButton.clicked.connect(self.onSearch)
        sf.searchBox.returnPressed.connect(self.onReturnInSearch)
        sf.searchAddButton.clicked.connect(self.onAddFromSearch)
        sf.entriesList.itemSelectionChanged.connect(self.onEntrySelected)
        sf.occurrencesList.itemSelectionChanged.connect(self.fillInspect)
        sf.entriesList.itemActivated.connect(self.onEditEntry)
        sf.occurrencesList.itemActivated.connect(self.onEditOccurrence)
        sf.nearbyList.itemActivated.connect(self.onInspectFollowNearby)

        # connect menus and check functions (for enable/disable)
        sf.menuGo.aboutToShow.connect(self.checkGoMenu)
        sf.menuEntry.aboutToShow.connect(self.checkEntryMenu)
        sf.menuOccurrence.aboutToShow.connect(self.checkOccurrenceMenu)
        sf.menuInspect.aboutToShow.connect(self.checkInspectMenu)
        self._setupMenus()

        # set up statusbar
        self.matchesWidget = QLabel("")
        self.errorWidget = QLabel("")
        self.form.statusBar.addPermanentWidget(self.errorWidget)
        self.form.statusBar.addPermanentWidget(self.matchesWidget)

        # initialize db and set up searching and entries
        self.search = None
        self.searchStack = []
        self.searchForward = []
        self.savedSelections = None
        self.savedTexts = None
        self.entryCache = []
        self.preferredDateFormat = 'd MMM yyyy'
        self.dbLocation = ui.settings.getDbLocation()
        if not self.dbLocation or not self._initDb(self.dbLocation, False):
            self.onNoDB()

    def onNoDB(self):
        """
        Dialog displayed when the last-used database (stored with QSettings) is
        not available, Tabularium has not yet been used/configured on this
        machine, or the incorrect password to a database was typed.
        """
        dialog = ui.opendatabase.OpenDatabaseWindow(self, self.dbLocation)
        if not dialog.exec_():
            sys.exit(0)
        doWhat = dialog.getResult()
        if doWhat == 'new':
            r = self.onNewDB()
        elif doWhat == 'open':
            r = self.onOpenDB()
        elif doWhat == 'last':
            r = self._initDb(self.dbLocation)
        else:
            assert False, f"Illegal return from OpenDatabaseWindow: {doWhat!r}"
        if not r:
            self.onNoDB()

    def _initDb(self, location: str, yellOnNonexistence=True) -> bool:
        """
        Load a database and set up the window for the settings of that
        database.

        Ideally we would use a try-except block instead of os.path.exists, but
        it doesn't look like SQLite has an option to not create a database if
        it doesn't currently exist through the connect() method, and it's more
        trouble than it's worth to set up our own exception handling for this.
        If there's a particularly unlucky race, then we'll just get an uncaught
        exception and no real harm done.

        Return a boolean indicating success.
        """
        if not os.path.exists(location):
            if yellOnNonexistence:
                ui.utils.warningBox(f"The database '{location}' no longer exists!")
            return False
        conn = db.database.DatabaseConnection(location)
        #db.database.downgradeDatabase(conn, 0, print)
        db.database.upgradeDatabase(conn, print)  # no-op if no upgrade needed
        db.database.installGlobalConnection(conn)
        self.dbLocation = location

        self.search = ""
        self.searchOptions = {}
        self.searchStack = []
        self.searchForward = []
        sf = self.form
        sf.incrementalCheckbox.toggled.connect(self.onChangeSearchOptions)
        sf.regexCheckbox.toggled.connect(self.onChangeSearchOptions)

        # set up configuration
        self.sh = ui.settings.SettingsHandler(self)

        # make sure user is authorized
        if self.sh.get('password'):
            pw, accepted = ui.utils.passwordEntry()
            if not accepted:
                return False
            if not ui.settings.checkPassword(pw, self.sh):
                ui.utils.errorBox("Invalid password.",
                                  "No dice!")
                return False

        # wipe object caches
        db.entries.Entry.invalidateCache()
        db.occurrences.Occurrence.invalidateCache()

        # fill entries
        self.savedTexts = ["", ""]
        self.savedSelections = (-1, -1)
        self.onChangeSearchOptions()

        # set up inspection options
        self.inspectOptions = {}
        items = (sf.showInspectCheck, sf.showSourceNameCheck,
                 sf.showAddedCheck, sf.showEnteredCheck,
                 sf.showNearbyCheck, sf.showDiaryCheck)
        for i in items:
            i.toggled.connect(self.onChangeInspectionOptions)
        self.onChangeInspectionOptions()

        # finally, set up checkboxes etc., and restore state from last run
        self.initialWindowState()
        self.restoreWindowState()
        self.setWindowTitle(f"Tabularium – {os.path.basename(location)}")
        self.onSearch()
        self.form.searchBox.setFocus()
        return True

    def closeEvent(self, _event): # pylint: disable=unused-argument
        "Call quit() for a proper exit on click of the X button, etc."
        self.quit()

    def quit(self):
        "Quit the application in an orderly fashion."
        self.saveWindowState()
        ui.settings.saveDbLocation(self.dbLocation)
        db.database.d().close()
        sys.exit(0)

    def saveWindowState(self):
        """
        Save the state of limit checkboxes, splitter sizes, etc., before
        quitting, so the application will open about the same as it was closed.
        The state is saved to the database and can be restored with
        restoreWindowState.
        """
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
        sh.put('entriesUnclassifiedCheck',
               sf.entriesUnclassifiedCheck.isChecked())
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

    def initialWindowState(self):
        """
        Set up window with defaults, so that if any are missing from config,
        weird things won't happen. This also runs some of the toggled handlers
        for the first time to set up some initial state.
        """
        sf = self.form
        sf.incrementalCheckbox.setChecked(True)
        sf.regexCheckbox.setChecked(False)
        # set up limits: for occurrences
        self.updateSourceCombo()

        # set up state
        for i in (sf.enteredCheck, sf.modifiedCheck,
                  sf.sourceCheck, sf.volumeCheck):
            i.setChecked(False)
        self._occurrenceFilterHandlers()
        # for entries
        for i in (sf.entriesCommonsCheck, sf.entriesNamesCheck,
                  sf.entriesPlacesCheck, sf.entriesQuotationsCheck,
                  sf.entriesTitlesCheck, sf.entriesUnclassifiedCheck):
            i.setChecked(True)
            i.toggled.connect(self.fillEntries)
        # for display
        for i in (sf.showInspectCheck, sf.showSourceNameCheck,
                  sf.showAddedCheck, sf.showEnteredCheck,
                  sf.showDiaryCheck, sf.showNearbyCheck):
            i.setChecked(True)

        # connect signals
        sf.enteredCheck.toggled.connect(lambda: self.onEnteredToggled(True))
        sf.modifiedCheck.toggled.connect(lambda: self.onModifiedToggled(True))
        sf.sourceCheck.toggled.connect(lambda: self.onSourceToggled(True))
        sf.volumeCheck.toggled.connect(lambda: self.onVolumeToggled(True))
        for i in (sf.occurrencesAddedDateSpin1, sf.occurrencesEditedDateSpin1,
                  sf.occurrencesAddedDateSpin2, sf.occurrencesEditedDateSpin2):
            i.dateChanged.connect(self._resetForOccurrenceFilter)
        sf.occurrencesSourceCombo.currentIndexChanged.connect(
            self.onOccurrenceSourceChanged)
        sf.occurrencesVolumeSpin1.valueChanged.connect(
            self._resetForOccurrenceFilter)
        sf.occurrencesVolumeSpin2.valueChanged.connect(
            self._resetForOccurrenceFilter)
        sf.entriesAllButton.clicked.connect(
            lambda: self._setAllEntryCheckboxes(True))
        sf.entriesNoneButton.clicked.connect(
            lambda: self._setAllEntryCheckboxes(False))

    def restoreWindowState(self):
        "Restore state saved by saveWindowState."
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
        def checkWrapper(obj, key, blockSignals=True):
            """
            Like wrapper(), but specifically for check boxes, and it is able to
            block signals on the object before making the change, so that we
            don't have a really slow re-search loop.
            """
            val = sh.get(key)
            if val is not None:
                if blockSignals:
                    oldState = obj.blockSignals(True)
                obj.setChecked(val)
                if blockSignals:
                    obj.blockSignals(oldState)

        # splitters
        wrapper(sf.mainSplitter.restoreState, 'mainSplitterState')
        wrapper(sf.inspectNearbySplitter.restoreState,
                'secondarySplitterState')

        # checkboxes
        checkWrapper(sf.incrementalCheckbox, 'incrementalCheck', False)
        checkWrapper(sf.regexCheckbox, 'regexCheck', False)
        # inspection options
        checkWrapper(sf.showInspectCheck, 'showInspectCheck')
        checkWrapper(sf.showSourceNameCheck, 'showSourceNameCheck')
        checkWrapper(sf.showAddedCheck, 'showAddedCheck')
        checkWrapper(sf.showEnteredCheck, 'showEnteredCheck')
        checkWrapper(sf.showDiaryCheck, 'showDiaryCheck')
        checkWrapper(sf.showNearbyCheck, 'showNearbyCheck')
        # entry types
        checkWrapper(sf.entriesNamesCheck, 'entriesNamesCheck')
        checkWrapper(sf.entriesPlacesCheck, 'entriesPlacesCheck')
        checkWrapper(sf.entriesQuotationsCheck, 'entriesQuotationsCheck')
        checkWrapper(sf.entriesTitlesCheck, 'entriesTitlesCheck')
        checkWrapper(sf.entriesCommonsCheck, 'entriesCommonsCheck')
        checkWrapper(sf.entriesUnclassifiedCheck,
                     'entriesUnclassifiedCheck')
        # occurrence filters
        checkWrapper(sf.enteredCheck, 'enteredCheck')
        checkWrapper(sf.modifiedCheck, 'modifiedCheck')
        checkWrapper(sf.sourceCheck, 'sourceCheck')
        checkWrapper(sf.volumeCheck, 'volumeCheck')
        def setupSourceCombo(value):
            i = sf.occurrencesSourceCombo.findText(value)
            sf.occurrencesSourceCombo.setCurrentIndex(i)
        with ui.utils.blockSignals(sf.occurrencesSourceCombo):
            wrapper(setupSourceCombo, 'sourceCombo')
        wrapper(sf.occurrencesVolumeSpin1.setValue, 'minVolume')
        wrapper(sf.occurrencesVolumeSpin2.setValue, 'maxVolume')
        wrapper(sf.occurrencesAddedDateSpin1.setDate, 'minDateAdded')
        wrapper(sf.occurrencesAddedDateSpin2.setDate, 'maxDateAdded')
        wrapper(sf.occurrencesEditedDateSpin1.setDate, 'minDateEdited')
        wrapper(sf.occurrencesEditedDateSpin2.setDate, 'maxDateEdited')
        wrapper(self._resetDateFormat, 'dateFormat')

        self._occurrenceFilterHandlers()


    ### Custom keyboard handlers ###
    def event(self, event) -> bool:
        "Custom key mappings for the dialog."
        def _listWidgetIsFocusedAndAtTopIndex(listWidget: QListWidget):
            return listWidget.hasFocus() and listWidget.currentRow() == 0

        sf = self.form

        if event.type() == 51:  # keypress
            # Down arrow when the filter box is focused
            # selects item after currently selected in the entriesList.
            if sf.searchBox.hasFocus() and event.key() == Qt.Key_Down:
                sf.entriesList.setFocus()
                # -1: because the down arrow gets applied again and we want to keep it
                # in the same place, or select the top row if nothing selected yet.
                targetRow = sf.entriesList.currentRow() - 1
                sf.entriesList.setCurrentRow(targetRow)
                return True
            # Up arrow when the entriesList or occurrencesList is focused
            # and at the top index selects the search box.
            if (event.key() == Qt.Key_Up
                    and (_listWidgetIsFocusedAndAtTopIndex(sf.entriesList)
                         or _listWidgetIsFocusedAndAtTopIndex(sf.occurrencesList))):
                sf.searchBox.selectAll()
                sf.searchBox.setFocus()
                return True
            # Right arrow when the entriesList is focused selects the occurrencesList.
            if (sf.entriesList.hasFocus()
                    and event.key() == Qt.Key_Right):
                # Highlight the first item if nothing is currently selected
                if sf.occurrencesList.currentRow() == -1:
                    sf.occurrencesList.setCurrentRow(0)
                sf.occurrencesList.setFocus()
                return True
            # Left arrow when the occurrencesList is focused selects the entriesList.
            if (sf.occurrencesList.hasFocus()
                    and event.key() == Qt.Key_Left):
                sf.entriesList.setFocus()
                return True

        return super().event(event)


    ### Setting, resetting, and filling the data windows ###
    def updateMatchesStatus(self) -> None:
        "Update the number of entry/occurrence matches in the status bar."
        entryCount = self.form.entriesList.count()
        entryString = f"E: {entryCount}"
        occCount = self.form.occurrencesList.count()
        occString = f", O: {occCount}"

        whatFilters = []
        # all/none has same effect
        if len(self._getOKClassifications()) not in (0, 6):
            whatFilters.append("Entry")
        if self._getOccurrenceFilters():
            whatFilters.append("Occurrence")
        if whatFilters:
            filterStr = ' and '.join(whatFilters) + ' limits active | '
        else:
            filterStr = ""

        self.matchesWidget.setText(
            filterStr + entryString + ("" if not occCount else occString))

    def fillEntries(self) -> None:
        """
        Fill the Entries list box with all entries that match the current
        search and limit criteria. (Right now limits are ignored.)

        The motivation for running processEvents() before we start searching
        is twofold:
            1) It allows the "searching..." text to appear in the status bar.
            2) It makes incremental searching feel faster: the user's
               keystroke appears as soon as it is entered, rather than not
               until the search is complete.

        We block signals to the entries list so we don't try to auto-select the
        first occurrence and refocus the entries list while we're typing a
        search.
        """
        with ui.utils.blockSignals(self.form.entriesList):
            with ui.utils.temporaryStatusMessage(self.form.statusBar, "Searching..."):
                QApplication.processEvents()
                self._resetForEntry()
                entries = self._getEntriesForSearch()
                self.fillListWidgetWithEntries(self.form.entriesList, entries,
                                               sort=False)
                self.updateMatchesStatus()

    def _getEntriesForSearch(self):
        """
        Return a list of entries that match the current classifications and
        search.
        """
        classification = self._getOKClassifications()
        try:
            entries = db.entries.find(self.search, classification,
                                      self.searchOptions.get('regex', False),
                                      **self._getOccurrenceFilters())
            self.errorWidget.setText("")
            self.form.searchBox.setStyleSheet("")
        except sqlite3.OperationalError:
            # regex in search box is invalid
            self.errorWidget.setText("Search syntax incorrect  |")
            self.form.searchBox.setStyleSheet("background-color: indianred;")
            entries = []
        return entries

    def fillOccurrences(self):
        """
        Fill the Occurrences box with all occurrences of the current entry,
        assuming they match limit criteria.
        """
        self._resetForOccurrence()
        entry = self._fetchCurrentEntry()
        if entry is not None:
            # hold onto objects for reference by _fetchCurrentOccurrence
            self.currentOccs = db.occurrences.fetchForEntryFiltered(
                entry, **self._getOccurrenceFilters())
            self.currentOccs.sort()
            for i in self.currentOccs:
                self.form.occurrencesList.addItem(str(i))
        self.updateMatchesStatus()

    def _getOccurrenceFilters(self):
        """
        Return the current occurrence filters (to be passed to find()) as a
        dictionary.
        """
        filters = {}
        sf = self.form
        if sf.enteredCheck.isChecked():
            start = sf.occurrencesAddedDateSpin1.date().toString(
                'yyyy-MM-dd')
            finish = sf.occurrencesAddedDateSpin2.date().toString(
                'yyyy-MM-dd')
            filters['enteredDateStr'] = (start, finish)
        if sf.modifiedCheck.isChecked():
            start = sf.occurrencesEditedDateSpin1.date().toString(
                'yyyy-MM-dd')
            finish = sf.occurrencesEditedDateSpin2.date().toString(
                'yyyy-MM-dd')
            filters['modifiedDateStr'] = (start, finish)
        if sf.sourceCheck.isChecked():
            source = self._getSourceComboSelection()
            if source:
                filters['source'] = source
        if sf.volumeCheck.isChecked():
            filters['volumeRange'] = (sf.occurrencesVolumeSpin1.value(),
                                      sf.occurrencesVolumeSpin2.value())
        return filters

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
        vol = occ.volume
        source = vol.source
        # the added and edited dates
        daStr = "Entered %s<br>" % QDateTime(occ.dateAdded).toString(
            self.preferredDateFormat)
        deStr = "Modified %s<br>" % QDateTime(occ.dateAdded).toString(
            self.preferredDateFormat)
        # during diary time...
        diaryVolume = db.volumes.findDateInDiary(occ.dateAdded)

        # format
        s = "<center>"
        s += "<b>%s</b><br>" % occ # name of occurrence
        if self.inspectOptions['sn']:
            s += "(<i>%s</i>)<br>" % (source.name)
        if self.inspectOptions['ad']:
            s += daStr # added date
        if self.inspectOptions['ed']:
            s += deStr # edited date
        if self.inspectOptions['diary']:
            if diaryVolume is not None:
                s += "<br>"
                s += "Entered during<br>"
                s += "diary volume %i" % (diaryVolume.num)
            else:
                s += "<br>(no diary volume open<br>"
                s += "when entered)"
        s += ""
        s += "</center>"
        self.form.inspectBox.setHtml(s)

        # fill nearby list
        nearby = occ.getNearby()
        if nearby:
            self.fillListWidgetWithEntries(self.form.nearbyList, nearby)
        else:
            self.form.nearbyList.addItem("(No entries nearby)")


    def _getOKClassifications(self):
        """
        Return a tuple of the values defined in db/consts for the selected
        classification / entry-limiting check boxes.
        """
        sf = self.form
        ec = db.entries.EntryClassification
        trans = {sf.entriesCommonsCheck: ec.ORD,
                 sf.entriesNamesCheck: ec.PERSON,
                 sf.entriesPlacesCheck: ec.PLACE,
                 sf.entriesQuotationsCheck: ec.QUOTE,
                 sf.entriesTitlesCheck: ec.TITLE,
                 sf.entriesUnclassifiedCheck: ec.UNCLASSIFIED
                }
        checked = [clf for box, clf in trans.items() if box.isChecked()]
        return tuple(checked)

    def fillListWidgetWithEntries(self, widget, entries, sort=True):
        """
        Fill an arbitrary list widget (entry, occurrence, or nearby) with entries.
        For speed, sort can be disabled; obviously this is only valid if you know
        that the items were ordered in the SQL query that pulled them from the
        database. This should be true for entries.
        """
        if sort:
            entries.sort(key=lambda i: i.sortKey.lower())
        widget.addItems(i.name for i in entries)
        if widget is self.form.entriesList:
            self.entryCache = entries

    ### Checkbox / options handling ###
    def onChangeInspectionOptions(self):
        "Update window state for changed options in 'display' limit section."""
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
        "Update window state for changed regex/incremental checkboxes."
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

        self.onSearch() # immediately update search based on new options

    def onOccurrenceSourceChanged(self):
        self.onSourceToggled(False)
        self._resetForOccurrenceFilter()

    def onEnteredToggled(self, doReset=True):
        """
        Update window state for entered date occurrence limits. If calling
        several of these functions in a row, set doReset to False, as we don't
        need to refresh the window partway through.
        """
        state = self.form.enteredCheck.isChecked()
        self.form.occurrencesAddedDateSpin1.setEnabled(state)
        self.form.occurrencesAddedDateSpin2.setEnabled(state)
        mind, maxd = db.utils.minMaxOccurrenceDates()
        self.form.occurrencesAddedDateSpin1.setMinimumDate(mind)
        self.form.occurrencesAddedDateSpin1.setMaximumDate(maxd)
        self.form.occurrencesAddedDateSpin2.setMinimumDate(mind)
        self.form.occurrencesAddedDateSpin2.setMaximumDate(maxd)
        self.form.occurrencesAddedDateSpin1.setDate(mind)
        self.form.occurrencesAddedDateSpin2.setDate(maxd)
        if doReset:
            self._resetForOccurrenceFilter()

    def onModifiedToggled(self, doReset=True):
        "Update window state for modified date occurrence limits."
        state = self.form.modifiedCheck.isChecked()
        self.form.occurrencesEditedDateSpin1.setEnabled(state)
        self.form.occurrencesEditedDateSpin2.setEnabled(state)
        mind, maxd = db.utils.minMaxOccurrenceDates()
        if mind is None:
            mind = datetime.date.today()
        if maxd is None:
            maxd = datetime.date.today()
        self.form.occurrencesEditedDateSpin1.setMinimumDate(mind)
        self.form.occurrencesEditedDateSpin1.setMaximumDate(maxd)
        self.form.occurrencesEditedDateSpin2.setMinimumDate(mind)
        self.form.occurrencesEditedDateSpin2.setMaximumDate(maxd)
        self.form.occurrencesEditedDateSpin1.setDate(mind)
        self.form.occurrencesEditedDateSpin2.setDate(maxd)
        if doReset:
            self._resetForOccurrenceFilter()

    def onSourceToggled(self, doReset=True):
        "Update window state for modified source occurrence limits."
        state = self.form.sourceCheck.isChecked()
        self.form.occurrencesSourceCombo.setEnabled(state)
        if state:
            self.updateSourceCombo() # in case sources have changed
            source = self._getSourceComboSelection()
            if source is not None:
                # block signals and call handler manually so it gets called
                # unconditionally, even if already enabled
                with ui.utils.blockSignals(self.form.volumeCheck):
                    self.form.volumeCheck.setEnabled(True)
                self.onVolumeToggled(False)
        else:
            self.form.volumeCheck.setChecked(False)
            self.form.volumeCheck.setEnabled(False)
            self.form.occurrencesVolumeSpin1.setMinimum(1)
            self.form.occurrencesVolumeSpin1.setMaximum(1)
            self.form.occurrencesVolumeSpin2.setMinimum(1)
            self.form.occurrencesVolumeSpin2.setMaximum(1)
            self.form.occurrencesSourceCombo.setCurrentIndex(0) # all
        if doReset:
            self._resetForOccurrenceFilter()

    def onVolumeToggled(self, doReset=True):
        "Update window state for modified volume occurrence limits."
        state = self.form.volumeCheck.isChecked()
        self.form.occurrencesVolumeSpin1.setEnabled(state)
        self.form.occurrencesVolumeSpin2.setEnabled(state)
        source = self._getSourceComboSelection()
        if source is not None:
            # if check fails, then volume will not be displayed anyway
            minv, maxv = source.volVal
            # update volume max/min to match volval
            self.form.occurrencesVolumeSpin1.setMinimum(minv)
            self.form.occurrencesVolumeSpin1.setMaximum(maxv)
            self.form.occurrencesVolumeSpin2.setMinimum(minv)
            self.form.occurrencesVolumeSpin2.setMaximum(maxv)
            self.form.occurrencesVolumeSpin1.setValue(minv)
            self.form.occurrencesVolumeSpin2.setValue(maxv)
        if doReset:
            self._resetForOccurrenceFilter()

    def updateSourceCombo(self):
        combo = self.form.occurrencesSourceCombo
        oldSelection = combo.currentText()
        with ui.utils.blockSignals(combo):
            combo.clear()
            combo.addItem(db.consts.noSourceLimitText)
            for i in db.sources.allSources():
                combo.addItem(i.name)
            # restore old selection if possible
            index = combo.findText(oldSelection)
            if index != -1:
                combo.setCurrentIndex(index)


    def _getSourceComboSelection(self):
        """
        Return the Source currently selected, or None if all sources option
        is selected.
        """
        name = self.form.occurrencesSourceCombo.currentText()
        if name == db.consts.noSourceLimitText:
            return None
        else:
            return db.sources.byName(name)

    def saveSelections(self):
        """
        Keep track of the current row in the entries list and occurrences list
        so that we can restore user selections after another action.
        """
        el = self.form.entriesList
        ol = self.form.occurrencesList
        self.savedSelections = (el.currentRow(), ol.currentRow())
        if el.currentItem():
            self.savedTexts[0] = el.currentItem().text()
        if ol.currentItem():
            self.savedTexts[1] = ol.currentItem().text()

    def updateAndRestoreSelections(self):
        """
        Restore the selections saved by saveSelections().
        """
        self.fillEntries()

        el = self.form.entriesList
        ol = self.form.occurrencesList
        # try for an exact match on the former text; there will be one match or
        # nothing since entry names have to be unique
        matches = el.findItems(self.savedTexts[0], Qt.MatchExactly)
        if matches:
            el.setCurrentItem(matches[0])
            # FIXME: following *should* scroll to the item, but there appears to be some
            # kind of bug, potentially in Qt for all I know, that makes it
            # only work on entries near the top?
            el.scrollToItem(matches[0])
            # Since we've found the exact item, we can also sensibly restore
            # the occurrence selection.
            if self.savedSelections[1] <= ol.count() - 1:
                ol.setCurrentRow(self.savedSelections[1])


    ### Menu callback functions ###
    ## File menu
    def onNewDB(self) -> bool:
        "Get filename for, create, and open a new database."
        # get filename from user
        fname = QFileDialog.getSaveFileName(
            caption="Save New Tabularium Database",
            filter="Tabularium databases (*.tdb);;All files (*)")[0]
        if not fname:
            return False
        fname = ui.utils.forceExtension(fname, 'tdb')
        if fname is None:
            return False

        # close current database, delete db to be overwritten, create new db
        if db.database.d is not None:
            self.saveWindowState()
            db.database.d().close()
        try:
            os.remove(fname)
        except OSError:
            pass
        connection = db.database.makeDatabase(fname)
        connection.close()
        if self._initDb(fname):
            return True
        return False


    def onOpenDB(self) -> bool:
        "Close the current database and open a different one."
        fname = QFileDialog.getOpenFileName(
            caption="Open Tabularium Database",
            filter="Tabularium databases (*.tdb);;All files (*)")[0]
        if not fname:
            return False
        if db.database.d is not None:
            self.saveWindowState()
            db.database.d().close()
        if self._initDb(fname):
            return True
        return False

    # pylint: disable=no-self-use
    def onSaveDB(self) -> None:
        """
        Force a save now. Usually not necessary: autosaves take place as edits
        are made, but crashes could still cause losses.
        """
        db.database.d().forceSave()

    @preserveSelectionsDuring
    def onImportMindex(self) -> None:
        "Import index entries from a Mindex file."
        fname = QFileDialog.getOpenFileName(
            caption="Import Mindex File",
            filter="Mindex files (*.mindex);;All files (*)")[0]
        if not fname:
            return

        with ui.utils.temporaryStatusMessage(
            self.form.statusBar,
            "Importing (this may take some time depending on the size "
            "of the file)..."):
            with ui.utils.hourglass():
                numEntries, errors = db.importing.importMindex(fname)

        successMsg = (
            "%i entr%s added or merged with existing entries.<br>"
            % (numEntries, "y was" if numEntries == 1 else "ies were"))

        if len(errors) == 0:
            ui.utils.informationBox(successMsg, "Import Mindex File")
        else:
            msg = [successMsg,
                   "The following %i entr%s could not be imported:<br>"
                   % (len(errors), "y" if len(errors) == 1 else "ies")]
            for err, line, linenum in errors:
                msg.append("""<div><b>Line %s:</b></div>
                              <div style="margin-left: 24px;">%s</div>
                              <div><b>was not imported because:</b></div>
                              <div style="margin-left: 24px;">%s<br></div>
                           """ % (linenum, line.replace('\t', ' → '), err))
            ui.utils.reportBox(self, ''.join(msg), "Import Mindex File")

    def onExportMindex(self):
        def progressCallback(progress):
            self.form.statusBar.showMessage(progress)
            QApplication.processEvents()

        fname = QFileDialog.getSaveFileName(
            caption="Export Mindex File",
            filter="Mindex files (*.mindex);;All files (*)")[0]
        if not fname:
            return
        fname = ui.utils.forceExtension(fname, 'mindex')
        if fname is None:
            return False

        # pylint: disable=no-member
        with ui.utils.temporaryStatusMessage(self.form.statusBar,
                                             "Exporting entries..."):
            with ui.utils.hourglass():
                entriesToPrint = self._getEntriesForSearch()
                QApplication.processEvents()
                db.exporting.exportMindex(fname, entriesToPrint, progressCallback)

        ui.utils.informationBox(
            "%i entries exported." % len(entriesToPrint),
            "Export Mindex File")

    def onPrintAll(self):
        self._printWrapper(db.printing.printEntriesAsIndex)

    def onPrintVisible(self):
        entries = self._getEntriesForSearch()
        self._printWrapper(db.printing.printEntriesAsIndex, entries)

    def onPrintSimplification(self):
        self._printWrapper(db.printing.makeSimplification)

    def _printWrapper(self, printFunc, *args, **kwargs):
        """
        Call printFunc() to print something, handling progress and error
        reporting.
        """
        def progressCallback(progress):
            self.form.statusBar.showMessage(progress)
            QApplication.processEvents()

        # pylint: disable=no-member
        with ui.utils.temporaryStatusMessage(self.form.statusBar, "Printing..."):
            with ui.utils.hourglass():
                try:
                    QApplication.processEvents()
                    printFunc(callback=progressCallback, *args, **kwargs)
                except db.printing.PrintingError as e:
                    ui.utils.errorBox(str(e), "Printing not successful")


    ## Edit menu
    def onPrefs(self):
        pw = ui.settings.PreferencesWindow(self, self.sh)
        pw.exec_()


    ## Go menu
    def onGoBack(self):
        """
        Go back to the previous search.

        The error handling is needed even though the back/forward options are
        disabled on shortcut keys because one might hold down the alt key and
        press back/forward a few times, and the handler only runs the first
        time the key is depressed. Therefore, we could reach the bottom of
        the stack without the event filter getting a chance to disable the
        option.
        """
        if self.searchOptions['incremental']:
            self._saveSearchToStack()

        try:
            cur = self.searchStack.pop()
        except IndexError:
            return
        try:
            last = self.searchStack.pop()
        except IndexError:
            self.searchStack.append(cur)
            return
        if len(self.searchForward) == 0 or cur != self.searchForward[-1]:
            # if not already on the forward stack
            self.searchForward.append(cur)

        # Block signals as we change the search so that the forward history
        # isn't wiped out by an automatic search here.
        oldBlockSignals = self.form.searchBox.blockSignals(True)
        self.form.searchBox.setText(last)
        self.form.searchBox.blockSignals(oldBlockSignals)
        if self.searchOptions['incremental']:
            # Since onSearch() doesn't push the current search onto the stack
            # if incremental mode is on, we have to do it ourselves first.
            self.searchStack.append(last)
        self.onSearch(wentForwardBack=True)

    def onGoForward(self):
        "Go forward to the next (last back'd) search. See onGoBack() for more."
        try:
            last = self.searchForward.pop()
        except IndexError:
            return
        oldBlockSignals = self.form.searchBox.blockSignals(True)
        self.form.searchBox.setText(last)
        self.form.searchBox.blockSignals(oldBlockSignals)
        if self.searchOptions['incremental']:
            # Since onSearch() doesn't push the current search onto the stack
            # if incremental mode is on, we have to do it ourselves first.
            self.searchStack.append(last)
        self.onSearch(wentForwardBack=True)

    def onGoSearch(self):
        self.form.searchBox.selectAll()
        self.form.searchBox.setFocus()


    ## Entry menu
    @preserveSelectionsDuring
    def onAddEntry(self, entry=None, redirTo=None, edit=False, text=None):
        """
        Add a new entry. This function is called directly by the standard add
        function, and with optional arguments by the callback functions
        associated with each menu choice. See the ui.addentry.AddEntryWindow
        class for details on how this works.
        """
        ae = ui.addentry.AddEntryWindow(self)
        if entry:
            ae.setInitialText(entry.name, entry.sortKey)
            ae.putClassification(entry)
            ae.resetTitle(f"New Entry Based On '{entry.name}'")
        elif text:
            # by leaving the SK blank, we trigger automatic generation thereof
            ae.setInitialText(text)
        elif redirTo:
            ae.putRedirect(redirTo)
            ae.resetTitle(f"New Redirect To '{redirTo.name}'")

        if edit:
            assert entry is not None, "Must specify entry when using edit=True"
            ae.setEditing()
            ae.resetTitle(f"Edit Entry '{entry.name}'")

        return ae.exec_()

    def onAddEntryBasedOn(self):
        entry = self._fetchCurrentEntry()
        self.onAddEntry(entry)

    def onAddRedirect(self):
        entry = self._fetchCurrentEntry()
        self.onAddEntry(redirTo=entry)

    def onEditEntry(self):
        entry = self._fetchCurrentEntry()
        self.onAddEntry(entry, edit=True)

    @preserveSelectionsDuring
    def onMergeEntry(self):
        "Merge the selected entry with one typed in by the user."
        curEntry = self._fetchCurrentEntry()
        dialog = ui.mergeentry.MergeEntryDialog(self)
        dialog.setFrom(curEntry)
        dialog.setTitle("Merge '%s' into..." % curEntry.name)
        return dialog.exec_()

    @preserveSelectionsDuring
    def onDeleteEntry(self):
        "After getting confirmation, delete an entry and its occurrences."
        entry = self._fetchCurrentEntry()
        if not entry:
            # We have to make sure we're actually allowed to take this
            # action because its keyboard shortcut is "Del", which doesn't
            # use a Ctrl, Shift, or Alt, which are what trigger the menu
            # checks.
            return False

        eName = entry.name
        occsAffected = len(db.occurrences.fetchForEntry(entry))
        # at some point, replace this with undo
        r = ui.utils.questionBox(
            "Do you really want to delete the entry '%s' "
            "and its %i occurrence%s?" % (eName, occsAffected,
                                          "" if occsAffected == 1 else "s"),
            "Delete entry?")
        if r:
            entry.delete()
            return True
        else:
            return False


    ## Occurrences menu
    @preserveSelectionsDuring
    def onAddOccurrence(self):
        "Add a new occurrence to the currently selected entry."
        # Anna-Christina's window
        ac = ui.addoccurrence.AddOccWindow(self, self._fetchCurrentEntry(),
                                           self.sh)
        return ac.exec_()

    @preserveSelectionsDuring
    def onEditOccurrence(self, _selectedItem):
        "Edit the volume/reference number of an occurrence."
        occ = self._fetchCurrentOccurrence()
        entry = occ.entry
        dialog = ui.editoccurrence.EditOccurrenceWindow(self, entry, occ)
        return dialog.exec_()

    @preserveSelectionsDuring
    def _extendRetractOccurrence(self, doRetract=False):
        occ = self._fetchCurrentOccurrence()
        try:
            occ.extend(-1 if doRetract else 1)
        except (db.occurrences.InvalidReferenceError,
                db.occurrences.ExtensionError) as e:
            ui.utils.errorBox(str(e))
            return False
        else:
            return True

    #TODO: Decorator to save/restore selections?
    def onExtendOccurrence(self):
        self._extendRetractOccurrence(doRetract=False)

    def onRetractOccurrence(self):
        self._extendRetractOccurrence(doRetract=True)

    @preserveSelectionsDuring
    def onMoveToEntry(self):
        """
        Move an occurrence to a different entry, optionally converting it to
        a redirect to that entry.
        """
        assert self.form.occurrencesList.count() > 0
        if self.form.occurrencesList.count() == 1:
            r = ui.utils.questionBox(
                "Since there is only one occurrence in this "
                "entry, the entry will be moved or converted to a "
                "redirect. Continue?", "Move Occurrence to Entry")
            return self.onMergeEntry() if r else None

        curEntry = self._fetchCurrentEntry()
        curOcc = self._fetchCurrentOccurrence()
        dialog = ui.mergeentry.MergeEntryDialog(self)
        dialog.setFrom(curEntry)
        dialog.setMoveSingleOccurrence(curOcc)
        dialog.setTitle("Move occurrence '%s' to..." % str(curOcc))
        return dialog.exec_()

    @preserveSelectionsDuring
    def onDeleteOccurrence(self):
        """
        Delete the currently selected occurrence, and its entry if this is the
        last occurrence.
        """
        occ = self._fetchCurrentOccurrence()
        qString = "Do you really want to delete the occurrence '%s'?" % (
            str(occ))
        if len(occ.getOccsOfEntry()) == 1:
            qString += " (The entry '%s' will be deleted too.)" % (
                occ.entry.name)
        r = ui.utils.questionBox(qString, "Delete entry?")
        if r:
            occ.delete()
            db.entries.deleteOrphaned()
            return True
        else:
            return False

    def onFollowRedirect(self):
        "Follow a redirect occurrence to the entry it points to."
        occ = self._fetchCurrentOccurrence()
        assert occ is not None, "Follow redirect called with no occ selected!"
        assert occ.isRefType(db.occurrences.ReferenceType.REDIRECT), \
                "Follow redirect called with a non-redirect occurrence!"
        self._changeSearch(occ.ref)

    def onCopyEntryToClipboard(self):
        QApplication.clipboard().setText(self._fetchCurrentEntry().name)

    ## Inspect menu
    def onInspectFollowNearby(self):
        "Search for an entry listed in the nearby window."
        entryName = self.form.nearbyList.currentItem().text()
        self._changeSearch(entryName)

    def onSourceNotes(self):
        "Open the notes for the source of the currently selected occurrence."
        occ = self._fetchCurrentOccurrence()
        volume = occ.volume
        source = volume.source
        nb = ui.editnotes.NotesBrowser(self, jumpToSource=source,
                                       jumpToVolume=volume)
        nb.exec_()

    def onDiaryNotes(self):
        """
        Open the notes for the diary volume that was open at the time this
        occurrence was entered.
        """
        occ = self._fetchCurrentOccurrence()
        diaryVolume = db.volumes.findDateInDiary(occ.dateAdded)
        source = diaryVolume.source
        nb = ui.editnotes.NotesBrowser(self, jumpToSource=source,
                                       jumpToVolume=diaryVolume)
        nb.exec_()


    ## Sources menu
    def onViewNotes(self):
        nb = ui.editnotes.NotesBrowser(self)
        nb.exec_()

    @preserveSelectionsDuring
    def onManageSources(self):
        "Launch source manager."
        ms = ui.sourcemanager.SourceManager(self)
        ms.exec_()
        self.updateSourceCombo()

    def onManageVolumes(self):
        mv = ui.volmanager.VolumeManager(self)
        mv.exec_()


    ## Tools menu
    def onClassify(self):
        "Load the entry classification tool."
        with ui.utils.temporaryStatusMessage(
                self.form.statusBar,
                "Loading entry classification tool, this may take a moment..."):
            QApplication.processEvents()
            cw = ui.tools_classification.ClassificationWindow(self)
        cw.exec_()
        self.onSearch()
        #self.updateAndRestoreSelections()

    def onRepairRedirects(self):
        "Load the redirect repair tool."
        with ui.utils.temporaryStatusMessage(
                self.form.statusBar,
                "Loading redirect repair tool, this may take a moment..."):
            QApplication.processEvents()
            rw = ui.tools_brokenredirects.RedirectsWindow(self)
        rw.exec_()

    def onLetterDistro(self):
        ui.utils.reportBox(self, db.analytics.letterDistribution(),
                           "Letter distribution statistics")

    ## Integrations menu
    def integrationRt(self):
        search = self.form.searchBox.text()
        # pylint: disable=line-too-long
        subprocess.Popen('''gnome-terminal -e "bash -c \\"rtgrep %s /home/soren/random-thoughts.txt ; exec bash\\""''' % search, shell=True)

    def integrationRpfind(self) -> None:
        "Launch rpfind on the UOF of the currently selected occurrence."
        occ = self._fetchCurrentOccurrence()
        if not occ:
            ui.utils.errorBox("Please select an occurrence to locate.")
            return
        if occ.isRefType(db.occurrences.ReferenceType.REDIRECT):
            ui.utils.errorBox("Only occurrences with page numbers or ranges "
                              "can be located with this feature.")
            return
        uof = occ.getUOFRepresentation().replace(' ', '')
        subprocess.Popen(["rpfind", uof])

    ## Help menu
    def onAbout(self):
        "Show the about dialog."
        ui.about.AboutWindow(self, APPLICATION_VERSION).exec_()

    def onNames2Faces(self):
        ui.names2faces.FacesWindow(self).exec_()

    ### Menu implementation ###
    def _setupMenus(self):
        "Connect all menu choices to their respective methods."
        sf = self.form
        sf.actionQuit.triggered.connect(self.quit)
        sf.actionFollow_Nearby_Entry.triggered.connect(
            self.onInspectFollowNearby)
        sf.actionAdd.triggered.connect(self.onAddEntry)
        sf.actionNew_based_on.triggered.connect(self.onAddEntryBasedOn)
        sf.actionAdd_Redirect_To.triggered.connect(self.onAddRedirect)
        sf.actionEdit.triggered.connect(self.onEditEntry)
        sf.actionManage_sources.triggered.connect(self.onManageSources)
        sf.actionManage_volumes.triggered.connect(self.onManageVolumes)
        sf.actionNotes.triggered.connect(self.onViewNotes)
        sf.actionDelete.triggered.connect(self.onDeleteEntry)
        sf.actionAdd_occ.triggered.connect(self.onAddOccurrence)
        sf.actionDelete_occ.triggered.connect(self.onDeleteOccurrence)
        sf.actionSource_notes.triggered.connect(self.onSourceNotes)
        sf.actionDiary_notes.triggered.connect(self.onDiaryNotes)
        sf.actionEntire_index.triggered.connect(self.onPrintAll)
        sf.actionVisible_entries.triggered.connect(self.onPrintVisible)
        sf.action_Simplification.triggered.connect(self.onPrintSimplification)
        sf.actionPreferences.triggered.connect(self.onPrefs)
        sf.actionClassify_Entries.triggered.connect(self.onClassify)
        sf.actionRepair_Broken_Redirects.triggered.connect(self.onRepairRedirects)
        sf.actionEditOcc.triggered.connect(self.onEditOccurrence)
        sf.actionCopyEntryToClipboard.triggered.connect(self.onCopyEntryToClipboard)
        sf.actionExtendOccurrence.triggered.connect(self.onExtendOccurrence)
        sf.actionRetractOccurrence.triggered.connect(self.onRetractOccurrence)
        sf.actionLetter_Distribution_Check.triggered.connect(
            self.onLetterDistro)
        sf.actionFollow_redirect.triggered.connect(self.onFollowRedirect)
        sf.actionGoBack.triggered.connect(self.onGoBack)
        sf.actionGoForward.triggered.connect(self.onGoForward)
        sf.actionMerge_into.triggered.connect(self.onMergeEntry)
        sf.actionGoSearch.triggered.connect(self.onGoSearch)
        sf.actionGoEntries.triggered.connect(
            lambda: selectFirstAndFocus(sf.entriesList))
        sf.actionGoOccurrences.triggered.connect(
            lambda: selectFirstAndFocus(sf.occurrencesList))
        sf.actionGoInspect.triggered.connect(sf.inspectBox.setFocus)
        sf.actionGoNearby.triggered.connect(
            lambda: selectFirstAndFocus(sf.nearbyList))
        sf.actionNew_DB.triggered.connect(self.onNewDB)
        sf.actionSwitch_Database.triggered.connect(self.onOpenDB)
        sf.actionSave_now.triggered.connect(self.onSaveDB)
        sf.actionImport.triggered.connect(self.onImportMindex)
        sf.actionExport.triggered.connect(self.onExportMindex)
        sf.actionMove_to_entry.triggered.connect(self.onMoveToEntry)
        sf.actionAbout_Tabularium.triggered.connect(self.onAbout)
        sf.actionShow_in_cabinet.triggered.connect(self.integrationRpfind)
        sf.actionFind_in_RT.triggered.connect(self.integrationRt)
        sf.actionSearch_Faces.triggered.connect(self.onNames2Faces)

    def checkAllMenus(self):
        """
        Called from the keyboard-press event filter to check whether items need
        to be enabled/disabled before the keyboard shortcut entry is complete.
        Checks all menus.

        The functions below are called individually when clicking on that menu,
        since that's the only one that then needs to be checked.
        """
        try:
            self.checkGoMenu()
            self.checkEntryMenu()
            self.checkOccurrenceMenu()
            self.checkInspectMenu()
        except AttributeError:
            # window not fully loaded; no need to check the menu at all
            pass

    def checkGoMenu(self):
        """
        Check to see if we are allowed to go forward/back.

        We can always go back to an empty search, even beyond the beginning of
        the stack (since we always start with an empty search). The empty
        search is not always placed on the stack, so we can go back either if
        the stack is non-empty or if the search box is non-empty. Thus, the
        only time we *can't* go back is if we've already reached the beginning
        state.
        """
        somethingOnStack = bool([i for i in self.searchStack if len(i)])
        searchIsEmpty = self.form.searchBox.text() == ""
        self.form.actionGoBack.setEnabled(
            somethingOnStack or not searchIsEmpty)
        self.form.actionGoForward.setEnabled(len(self.searchForward))

    def checkEntryMenu(self):
        "Enable/disable items on the Entry menu for the current window state."
        sf = self.form
        ifCondition = sf.entriesList.currentRow() != -1
        sf.actionNew_based_on.setEnabled(ifCondition)
        sf.actionAdd_Redirect_To.setEnabled(ifCondition)
        sf.actionEdit.setEnabled(ifCondition)
        sf.actionMerge_into.setEnabled(ifCondition)
        sf.actionDelete.setEnabled(ifCondition)

    def checkOccurrenceMenu(self):
        "Enable/disable items on Occurrences menu for current window state."
        sf = self.form
        ifNoOccurrence = sf.occurrencesList.currentRow() != -1
        sf.actionEditOcc.setEnabled(ifNoOccurrence)
        sf.actionMove_to_entry.setEnabled(ifNoOccurrence)
        sf.actionDelete_occ.setEnabled(ifNoOccurrence)
        sf.actionExtendOccurrence.setEnabled(ifNoOccurrence)
        sf.actionRetractOccurrence.setEnabled(ifNoOccurrence)
        curOcc = self._fetchCurrentOccurrence()
        if((ifNoOccurrence) and (curOcc is not None) and
           (curOcc.isRefType(db.occurrences.ReferenceType.REDIRECT))):
            sf.actionFollow_redirect.setEnabled(True)
        else:
            sf.actionFollow_redirect.setEnabled(False)
        ifNoEntry = sf.entriesList.currentRow() != -1
        sf.actionAdd_occ.setEnabled(ifNoEntry)

    def checkInspectMenu(self):
        "Enable/disable items on Inspect menu for the current window state."
        sf = self.form
        ifCondition = sf.nearbyList.currentRow() != -1
        sf.actionFollow_Nearby_Entry.setEnabled(ifCondition)
        occSelected = sf.occurrencesList.currentRow() != -1
        sf.actionSource_notes.setEnabled(occSelected)

        if occSelected:
            occ = self._fetchCurrentOccurrence()
            diary = db.volumes.findDateInDiary(occ.dateAdded) is not None
            sf.actionDiary_notes.setEnabled(diary)
        else:
            sf.actionDiary_notes.setEnabled(False)


    ### Other actions ###
    def onEntrySelected(self):
        """
        Fill the occurrences for the current entry.

        We used to also automatically fill the occurrences list, but this
        requires two database hits and as such requires quite a lot of time.
        To improve performance when rapidly paging or scrolling through items,
        you now have to click on the entry manually (or hit Alt-O Space).
        """
        self.fillOccurrences()

    def onSearch(self, _=None, wentForwardBack=False):
        """
        Called when clicking the "go" button, or from other methods when the
        view needs to be updated for a changed search (e.g., after following a
        redirect).

        By default anything in the "forward" stack will be cleared when this
        method is called, but if we just popped an item off the back/forward
        stack, we obviously don't want to do that (or it would never be
        possible to use the forward button). The optional argument
        wentForwardBack will disable this behavior.
        """
        self.search = self.form.searchBox.text().strip()
        isDupe = (len(self.searchStack) != 0
                  and self.search == self.searchStack[-1])
        if not self.searchOptions['incremental'] and not isDupe:
            self.searchStack.append(self.search)
        if not wentForwardBack:
            self.searchForward = []
        self.saveSelections()
        self.updateAndRestoreSelections()
        self.form.searchBox.setFocus()

    def onAddFromSearch(self):
        "Add an entry typed in the search box."
        entryName = self.form.searchBox.text()
        self.onAddEntry(text=entryName)

    def onReturnInSearch(self):
        """
        Adaptive return key in the search box. That's the idea anyway; I need
        to have a think about whether the current behavior really makes sense.
        """
        self.onSearch()
        numResults = self.form.entriesList.count()

        if self.searchOptions['incremental']:
            if numResults > 0:
                selectFirstAndFocus(self.form.entriesList)
            else:
                self.onAddFromSearch()
        else:
            if numResults == 0:
                self.form.searchAddButton.setFocus()



    ### UTILITIES ###
    def _fetchCurrentEntry(self) -> Optional[db.entries.Entry]:
        """
        Get an Entry object for the currently selected entry. Return None if
        nothing is selected or the entry was just deleted.
        """
        # Waiting for byName() every time we pick a new row can make the interface
        # feel sluggish, so we cache a configurable number of Entries by their index
        # in the widget.
        # This differs from the cache in the Entry class, which also caches database
        # objects, but only helps when we know the entry ID.
        currentRow = self.form.entriesList.currentRow()
        if currentRow < len(self.entryCache):
            return self.entryCache[currentRow]

        try:
            search = self.form.entriesList.currentItem().text()
        except AttributeError:
            return None
        else:
            return db.entries.Entry.byName(search)

    def _fetchCurrentOccurrence(self) -> Optional[db.occurrences.Occurrence]:
        """
        Get an Occurrence object for the currently selected occurrence. Return
        None if nothing is selected.
        """
        row = self.form.occurrencesList.currentRow()
        if row == -1: # no occurrence selected
            return None
        return self.currentOccs[row]

    def _changeSearch(self, searchFor: str) -> None:
        """
        Change the text in the search box, rerun search, and select the
        particular item. Used when following redirects.
        """
        self._saveSearchToStack()
        self.form.searchBox.setText(searchFor)
        self.onSearch()
        try:
            item = self.form.entriesList.findItems(searchFor,
                                                   Qt.MatchExactly)[0]
        except IndexError:
            ui.utils.warningBox(
                f"The target of this redirect ('{searchFor}') is "
                f"not visible in the current view. Most likely the current "
                f"limits exclude the target, and adjusting the limits "
                f"will show the item. Otherwise, the redirect may be "
                f"invalid.",
                "Redirect not found")
            return
        self.form.entriesList.setCurrentItem(item)
        self.form.entriesList.setFocus()

    def _saveSearchToStack(self) -> None:
        """
        Fake a focus lost event to save the current search value on the stack
        before going back, so user can go forward to it again. This is only an
        issue when incremental search is in use, but it won't do any harm to
        call if it's not.
        """
        self.searchFocusLost(self.form.searchBox, self.form.searchBox)

    def _setAllEntryCheckboxes(self, state: bool) -> None:
        """
        Enable/disable all of the entry classification checkboxes
        and rerun the search.
        """
        sf = self.form
        for i in (sf.entriesCommonsCheck, sf.entriesNamesCheck,
                  sf.entriesPlacesCheck, sf.entriesQuotationsCheck,
                  sf.entriesTitlesCheck, sf.entriesUnclassifiedCheck):
            oldBlockSignals = i.blockSignals(True)
            i.setChecked(state)
            i.blockSignals(oldBlockSignals)
        self.fillEntries()

    def _occurrenceFilterHandlers(self) -> None:
        """
        To be run after programmatically setting the state of some occurrence
        filters, to make sure that all the spin/calendar/combo boxes are in the
        correct state for the check boxes.
        """
        sf = self.form
        with ui.utils.blockSignals(sf.enteredCheck):
            with ui.utils.blockSignals(sf.modifiedCheck):
                with ui.utils.blockSignals(sf.sourceCheck):
                    with ui.utils.blockSignals(sf.volumeCheck):
                        self.onEnteredToggled(False)
                        self.onModifiedToggled(False)
                        self.onSourceToggled(False)
                        self.onVolumeToggled(False)
        self._resetForOccurrenceFilter()

    def _resetDateFormat(self, fmt):
        self.preferredDateFormat = fmt
        for i in (self.form.occurrencesAddedDateSpin1,
                  self.form.occurrencesAddedDateSpin2,
                  self.form.occurrencesEditedDateSpin1,
                  self.form.occurrencesEditedDateSpin2):
            i.setDisplayFormat(fmt)
        # if inspect is selected, it may use the old date format
        self.saveSelections()
        self.updateAndRestoreSelections()

    # Reset functions: since more or less needs to be reset for each, do a
    # sort of cascade.
    def _resetForEntry(self) -> None:
        self.form.entriesList.clear()
        self._resetForOccurrence()
    def _resetForOccurrence(self) -> None:
        self.form.occurrencesList.clear()
        self._resetForNearby()
    def _resetForNearby(self) -> None:
        self.form.nearbyList.clear()
        self.form.inspectBox.clear()

    def _resetForOccurrenceFilter(self) -> None:
        self.updateMatchesStatus()
        self.saveSelections()
        self.updateAndRestoreSelections()

    def searchFocusLost(self, old, _):
        """
        If incremental search mode is on, store the search in the history
        whenever focus to the search box is lost. (Otherwise, the search is
        stored by onSearch(), when Enter or Go is pressed.)
        """
        if old != self.form.searchBox:
            return
        search = self.form.searchBox.text()
        if len(self.searchStack) == 0 or search != self.searchStack[-1]:
            self.searchStack.append(search)

def selectFirstAndFocus(listWidget):
    """
    If there is no selection in listWidget currently, select the first row.
    Regardless, focus the widget.
    """
    if listWidget.currentRow() == -1:
        listWidget.setCurrentRow(0)
    listWidget.setFocus()

def exceptionHook(exctype, value, tb):
    """
    Global error handler: display information about unhandled exceptions,
    rather than printing it to stderr where it disappears if you're not
    running from the terminal.
    """
    tbText = ("An error occurred, and Tabularium doesn't know "
              "how to deal with it properly. This is likely the result "
              "of a bug in the program – sorry about that.\n\n"
              "Things you can try:\n"
              "* If it looks like what you wanted happened anyway, continue "
              "working.\n"
              "* Restart Tabularium and try again.\n\n"
              "If problems continue, please contact support and include "
              "an explanation of what you were doing when the error occurred "
              "along with the following technical details:\n\n")
    tbText += ''.join(traceback.format_exception(exctype, value, tb))
    ui.utils.reportBox(None, tbText, "Oops!")

def start():
    """
    Initialize the application and main window and run. This function should be
    called from the 'tabularium' executable to start the program.
    """
    sys.excepthook = exceptionHook
    app = QApplication(sys.argv)
    qfilter = MwEventFilter()
    app.installEventFilter(qfilter)
    mw = MainWindow(qfilter)
    app.focusChanged.connect(mw.searchFocusLost)

    mw.show()
    app.exec_()
