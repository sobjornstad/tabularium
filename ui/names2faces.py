# -*- coding: utf-8 -*-
# Copyright (c) 2017 Soren Bjornstad <contact@sorenbjornstad.com>

"""
Show names and faces
"""

import tempfile
from urllib import request
from urllib import error as urlerror
from urllib import parse as urlparse


from PyQt5.QtWidgets import QDialog, QFileDialog
from PyQt5.QtGui import QPixmap, QDesktopServices
from PyQt5.QtCore import Qt, QUrl
from ui.forms.names2faces import Ui_Dialog

import magic

import db.consts
import db.entries
import ui.utils

class FacesWindow(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self)
        self.parent = parent
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.form.nameList.itemSelectionChanged.connect(self.onSelectPerson)
        self.form.changeButton.clicked.connect(self.onChangeFace)
        self.form.downloadButton.clicked.connect(self.onDownloadFace)
        self.form.deleteButton.clicked.connect(self.onDeleteFace)
        self.form.saveButton.clicked.connect(self.onSaveFace)
        self.form.searchButton.clicked.connect(self.onSearch)
        self.form.closeButton.clicked.connect(self.reject)

        #TODO: Rather allow the user to add their own options for source
        self.form.findInCombo.addItem("Facebook")
        self.form.findInCombo.addItem("Google")

        ui.utils.longProcess(
            self.parent,
            "Loading Names and Faces, this may take a moment...",
            self._populatePersonNames)

    def _populatePersonNames(self):
        personEntries = db.entries.nonRedirectTopLevelPeople()
        self.form.nameList.addItems(i.name for i in personEntries)

    def onChangeFace(self):
        fname = QFileDialog.getOpenFileName(
            caption="Select Image",
            filter="Image files (*.png *.jpg *.jpeg *.xpm *.bmp *.gif);;All files (*)")[0]
        if not fname:
            return False
        entry = self._fetchCurrentPerson()
        entry.image = fname
        self.onSelectPerson()

    def onDeleteFace(self):
        entry = self._fetchCurrentPerson()
        entry.image = None
        self.onSelectPerson()

    def onSaveFace(self):
        entry = self._fetchCurrentPerson()

        # Work out what the extension should be
        ftype = magic.from_buffer(entry.image, mime=True)
        if 'image/' in ftype:
            extension = ftype.split('image/')[1]
        else:
            extension, ok = ui.utils.inputBox(
                "Whoops! The attachment doesn't appear to be an image! "
                "Tabularium can still try to save it for you if you like. "
                "What should the file's extension be?", "Invalid image")
            if not ok:
                return

        fname = QFileDialog.getSaveFileName(
            caption="Save Image",
            filter=("%s images (*.%s);;All files (*)" % (extension.upper(),
                                                         extension)))[0]
        if not fname:
            return
        fname = ui.utils.forceExtension(fname, extension)
        if fname is None:
            return False
        with open(fname, 'wb') as outfile:
            entry.writeImage(outfile)

    def onSearch(self):
        entry = self._fetchCurrentPerson()
        source = self.form.findInCombo.currentText()

        if source == "Facebook":
            base_url = "https://www.facebook.com/search/top/?q=%s"
            url = base_url % entry.name
        elif source == "Google":
            base_url = "https://www.google.com/search?tbm=isch&q=%s"
            url = base_url % entry.name

        QDesktopServices.openUrl(QUrl(url))

    def onDownloadFace(self):
        entry = self._fetchCurrentPerson()
        url, accepted = ui.utils.inputBox("URL of image to download:",
                                          title="Download Face",
                                          defaultText="http://")
        if not accepted:
            return

        try:
            with request.urlopen(url) as web:
                imageData = web.read()
        except urlerror.URLError:
            ui.utils.errorBox(
                "Could not download from that URL. If it seems correct, "
                "try manually downloading it and using the Import button.")
            return

        #TODO: find a way to give an error message if the pixmap ends up empty
        entry.image = imageData
        self.onSelectPerson()

    def _fetchCurrentPerson(self):
        try:
            selectedName = self.form.nameList.currentItem().text()
        except AttributeError:
            # nothing is selected
            print("Oopsies!")
            return None
        else:
            return db.entries.findOne(selectedName)

    def onSelectPerson(self):
        entry = self._fetchCurrentPerson()
        with tempfile.NamedTemporaryFile() as f:
            r = entry.writeImage(f)
            if not r:
                self.form.imageLabel.setText("(no image available)")
            else:
                pixmap = QPixmap(f.name)
                if pixmap.isNull():
                    self.form.imageLabel.setText("(no image available)")
                    return
                scaled = pixmap.scaled(self.form.imageLabel.size(),
                                       Qt.KeepAspectRatio)
                self.form.imageLabel.setPixmap(scaled)
