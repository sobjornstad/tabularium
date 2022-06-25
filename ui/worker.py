"""
worker.py - background UI threads
"""

from abc import abstractmethod
import sys
import traceback

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget


class Worker(QThread):
    """
    Using this worker thread:

    1. Subclass Worker and override the process() method to do whatever work you
       need. If it will be running for some time, check `self.exiting` periodically
       so the thread can be canceled by the client by setting this value.
    2. If you need any finally:-style behavior, override the tearDown() method.
    3. Create an instance of the thread.
    4. Connect the 'finished' signal to a handler that will run when the thread
       is complete. (If you need to retrieve data, store it in an instance variable.)
    5. Connect the 'jobFailed' signal to a handler that will run if an exception occurs.
    6. After configuring any other required instance attributes or methods,
       call the start() method to run the job.
    """
    jobFailed = pyqtSignal(Exception, list, name="jobFailed")

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.exiting = False

    def tearDown(self):
        pass

    @abstractmethod
    def process(self):
        ...

    def run(self):
        "Execute the job."
        try:
            self.process()
        except Exception as e:
            _, _, tb = sys.exc_info()
            self.tearDown()
            self.jobFailed.emit(e, traceback.extract_tb(tb))
        else:
            self.tearDown()
            self.finished.emit()
