from datetime import date
import filecmp
import os

from db.consts import sourceTypes
from db.entries import Entry
from db.occurrences import Occurrence, ReferenceType
from db.sources import Source
from db.volumes import Volume
import db.volumes
import db.exporting

from . import utils


class ExportTests(utils.DbTestCase):
    def testMindexExport(self):
        s1 = Source.makeNew('Books', (1, 1), (1, 100), 2, 'B',
                            sourceTypes['other'])
        s2 = Source.makeNew('People', (1, 2), (1, 100), 2, 'P',
                            sourceTypes['other'])
        v1_1 = db.volumes.byNumAndSource(s1, 1)
        v2_1 = Volume.makeNew(s2, 1, "", date(2016, 1, 1), date(2016, 1, 1))
        v2_2 = Volume.makeNew(s2, 2, "", date(2016, 1, 1), date(2016, 1, 1))
        e1 = Entry.makeNew("Alfonzo")
        o1 = Occurrence.makeNew(e1, v2_1, "12-15", ReferenceType.RANGE)
        e2 = Entry.makeNew("Xavier")
        o2 = Occurrence.makeNew(e2, v2_1, "40", ReferenceType.NUM)
        o3 = Occurrence.makeNew(e2, v2_1, "Alfonzo", ReferenceType.REDIRECT)
        o4 = Occurrence.makeNew(e2, v1_1, "53", ReferenceType.NUM)

        #db.exporting.exportMindex("tests/resources/testExportFile.mindex")
        db.exporting.exportMindex("tmp.mindex")
        filecmp.cmp("tmp.mindex", "tests/resources/testExportFile.mindex")
        os.remove("tmp.mindex")
