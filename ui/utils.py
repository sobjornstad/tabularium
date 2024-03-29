# -* coding: utf-8 *-
# Copyright 2015-2016 Soren Bjornstad. All rights reserved.

"""
Personal Indexer UI utility functions

These functions primarily create various kinds of simple dialog boxes.
"""

from contextlib import contextmanager
import os
from typing import Generator

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QInputDialog, \
        QLineEdit, QWidget
from PyQt5.QtGui import QCursor

import ui.forms.confirmationwindow
import ui.forms.report

def informationBox(text, title=None):
    """
    Message box with the information icon and an OK button.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Information)
    msgBox.setWindowTitle(title if title else "Tabularium")
    msgBox.exec_()

def errorBox(text, title=None):
    """
    Message box with the error icon and an OK button.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Critical)
    msgBox.setWindowTitle(title if title else "Tabularium")
    msgBox.exec_()

def warningBox(text, title=None):
    """
    Message box with the warning icon and an OK button.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Warning)
    msgBox.setWindowTitle(title if title else "Tabularium")
    msgBox.exec_()

def questionBox(text, title=None):
    """
    Message box with the question icon and Yes and No buttons.

    Returns True if yes was pushed, False if no was pushed.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Question)
    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msgBox.setDefaultButton(QMessageBox.No)
    msgBox.setWindowTitle(title if title else "Tabularium")
    return msgBox.exec_() == QMessageBox.Yes

def moo():
    "A very advanced debug tool."
    print("MOOOOO!")


def inputBox(label, title=None, defaultText=None):
    """
    Basic input box. Returns a tuple:
        [0] The text entered.
        [1] True if dialog accepted, False if rejected.

    See also passwordEntry().
    """
    if defaultText is not None:
        ret = QInputDialog.getText(None, title, label, text=defaultText)
    else:
        ret = QInputDialog.getText(None, title, label)
    return ret[0], ret[1]

def passwordEntry(title="Password required", label="Database password:"):
    """
    Input box for passwords (displays asterisks in the input box).

    Defaults for the title and label represent those needed for the password
    entry box that appears upon starting the program if password protection is
    enabled.

    Returns a tuple:
        [0] The text entered.
        [1] True if dialog accepted, False if dialog rejected.
    """
    ret = QInputDialog.getText(None, title, label, QLineEdit.Password)
    return ret[0], ret[1]

def forceExtension(filename, ext):
    """
    On Linux, a filename extension might not be automatically appended to the
    result of a file open/save box. This means we have to do it ourselves and
    check to be sure we're not overwriting something ourselves.

    This check is not safe from race conditions (if another program wrote a
    file with the same name between this function running and the output
    routine, the other file would be overwritten), but the chance of that
    causing a bad problem are essentially zero in this situation, and
    neither is the normal file-save routine.

    Arguments:
        filename: the path to (or simple name of) the file we're checking
        ext: the extension, without period, you want to ensure is included

    Return:
      - The filename (modified or not) if the file does not exist;
      - None if it does exist and the user said she didn't want to
        overwrite it.
    """
    # on linux, the extension might not be automatically appended
    if not filename.endswith('.%s' % ext):
        filename += ".%s" % ext
        if os.path.exists(filename):
            r = questionBox("%s already exists.\nDo you want to "
                            "replace it?" % filename)
            if r != QMessageBox.Yes: # yes
                return None
    return filename

def formatDate(date):
    """
    Format a datetime using the user's date format preferences.
    """
    #TODO: Actually implement user date format preferences.
    DATE_FORMAT = '%Y-%m-%d'
    if date is None:
        return None
    else:
        return date.strftime(DATE_FORMAT)


class ConfirmationDialog(QDialog):
    """
    Confirmation dialog to be used for scary/dangerous operations. The accept
    button is greyed out until the user ticks the check box.

    The dialog is created in the designer; see confirmationwindow.ui.

    Arguments to the constructor:
        parent :: as usual
        text :: the warning message to present
        checkText :: the label for the "yes, really" check box
        title :: the title of the dialog
    """

    def __init__(self, parent, text, checkText, title):
        QDialog.__init__(self)
        self.form = ui.forms.confirmationwindow.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.dialogText.setText(text)
        self.form.confirmationCheck.setText(checkText)
        self.setWindowTitle(title)

        self.form.acceptButton.setEnabled(False)
        self.form.confirmationCheck.toggled.connect(self.onConfirmChecked)
        self.form.acceptButton.clicked.connect(self.accept)
        self.form.rejectButton.clicked.connect(self.reject)

    def onConfirmChecked(self):
        sf = self.form
        sf.acceptButton.setEnabled(sf.confirmationCheck.isChecked())

@contextmanager
def blockSignals(widget: QWidget) -> Generator[None, None, None]:
    "Context manager to block all Qt signals on a widget for a period of time."
    oldBlockSignals = widget.blockSignals(True)
    try:
        yield
    finally:
        widget.blockSignals(oldBlockSignals)


@contextmanager
def temporaryStatusMessage(bar, text: str) -> Generator[None, None, None]:
    "Context manager to display a message in the status bar while something processes."
    bar.showMessage(text)
    try:
        yield
    finally:
        bar.clearMessage()

@contextmanager
def hourglass() -> Generator[None, None, None]:
    "Context manager to display a hourglass cursor while something processes."
    QApplication.setOverrideCursor(QCursor(QtCore.Qt.WaitCursor))
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


# pylint: disable=too-few-public-methods
class ReportDialog(QDialog):
    """
    Report dialog with a read-only QTextEdit and an OK button, to display
    HTML-formatted reports.
    """
    def __init__(self, parent, text, title):
        QDialog.__init__(self)
        self.form = ui.forms.report.Ui_Dialog()
        self.form.setupUi(self)
        self.parent = parent

        self.form.reportBox.setText(text)
        self.setWindowTitle(title)
        self.form.okButton.clicked.connect(self.accept)

def reportBox(parent, text, title):
    """
    Convenience function to create a ReportDialog that doesn't need to do any
    additional setup.
    """
    rd = ReportDialog(parent, text, title)
    return rd.exec_()


def longProcess(mw, statusmsg, func, *args, **kwargs):
    #"Loading Names and Faces, this may take a moment...")
    try:
        QApplication.processEvents()
        QApplication.setOverrideCursor(QCursor(QtCore.Qt.WaitCursor))
        mw.form.statusBar.showMessage(statusmsg)
        QApplication.processEvents()
        func(*args, **kwargs)
    finally:
        QApplication.restoreOverrideCursor()
        mw.form.statusBar.clearMessage()
