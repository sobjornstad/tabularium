# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

from PyQt4 import QtGui, QtCore
from PyQt4.QtGui import QApplication, QMainWindow, QFileDialog
from forms.main import Ui_MainWindow
import sys

import config
import db.database

class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.form = Ui_MainWindow()
        self.form.setupUi(self)

        self.form.actionQuit.triggered.connect(self.quit)

        self.initDb()


    def fillEntries(self):
        pass


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
