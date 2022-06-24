from datetime import date

from db.consts import sourceTypes
from db.entries import Entry
from db.occurrences import Occurrence, ReferenceType
from db.sources import Source
from db.volumes import Volume
import db.importing
import db.entries
import db.occurrences

from . import utils

class ImportTests(utils.DbTestCase):
    MINDEX_FILE = "tests/resources/testImportFile.mindex"

    def testMindexImport(self):
        s1 = Source.makeNew('Books', (1, 1), (1, 100), 2, 'B',
                            sourceTypes['other'])
        s2 = Source.makeNew('People', (1, 2), (1, 100), 2, 'P',
                            sourceTypes['other'])
        v2_1 = Volume.makeNew(s2, 1, "", date(2016, 1, 1), date(2016, 1, 1))
        v2_2 = Volume.makeNew(s2, 2, "", date(2016, 1, 1), date(2016, 1, 1))
        e1 = Entry.makeNew("Alfonzo")                               # Duplicate entry,
        o1 = Occurrence.makeNew(e1, v2_1, "12", ReferenceType.NUM)  # diff occurrence.
        e2 = Entry.makeNew("Xavier")                                # Duplicate entry
        o2 = Occurrence.makeNew(e2, v2_1, "40", ReferenceType.NUM)  # *and* occurrence.

        numOK, errors = db.importing.importMindex(self.MINDEX_FILE)
        assert numOK == 7
        assert len(errors) == 1, len(errors)
        assert len(errors[0]) == 3
        assert 'two tab-separated columns' in errors[0][0]
        assert errors[0][1] == 'This is an invalid line'
        assert errors[0][2] == 11

        assert len(db.entries.allEntries()) == 7
        assert len(db.occurrences.allOccurrences()) == 10
        extraTesting = db.entries.findOne("Greta")
        assert extraTesting.sortKey == "Greta"
        occs = db.occurrences.fetchForEntry(extraTesting)
        assert len(occs) == 2
        assert occs[0].ref == '7'
        assert occs[0].reftype == ReferenceType.NUM
        assert occs[1].ref == '10'
        assert occs[1].reftype == ReferenceType.NUM
        assert db.entries.find("This is an invalid line") == []
