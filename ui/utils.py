# -* coding: utf-8 *-
# Copyright 2015 Soren Bjornstad. All rights reserved.

"""
Personal Indexer UI utility functions

These functions primarily create various kinds of simple dialog boxes.
"""

from PyQt4.QtGui import QDialog, QMessageBox, QInputDialog, QLineEdit
import ui.forms.confirmationwindow

def informationBox(text, title=None):
    """
    Message box with the information icon and an OK button.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Information)
    if title:
        msgBox.setWindowTitle(title)
    msgBox.exec_()

def errorBox(text, title=None):
    """
    Message box with the error icon and an OK button.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Critical)
    if title:
        msgBox.setWindowTitle(title)
    msgBox.exec_()

def warningBox(text, title=None):
    """
    Message box with the warning icon and an OK button.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Warning)
    if title:
        msgBox.setWindowTitle(title)
    msgBox.exec_()

def questionBox(text, title=None):
    """
    Message box with the question icon and Yes and No buttons.

    Returns QMessageBox.Yes if yes was pushed, QMessageBox.No if no was pushed.
    QMessageBox is PyQt4.QtGui.QMessageBox if you need to import it to use
    those constants.
    """
    msgBox = QMessageBox()
    msgBox.setText(text)
    msgBox.setIcon(QMessageBox.Question)
    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msgBox.setDefaultButton(QMessageBox.No)
    if title:
        msgBox.setWindowTitle(title)
    return msgBox.exec_()

def passwordEntry(title="Password required", label="Database password:"):
    """
    Input box for passwords (displays asterisks in the input box).

    Defaults for the title and label represent those needed for the password
    entry box that appears upon starting the program if password protection is
    enabled.

    Returns a tuple:
        [0] The text entered, as a Unicode string.
        [1] True if dialog accepted, False if dialog rejected.
    """
    ret = QInputDialog.getText(None, title, label, QLineEdit.Password)
    return unicode(ret[0]), ret[1]


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
