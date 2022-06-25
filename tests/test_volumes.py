from datetime import date

from db.entries import EntryClassification
from db.consts import sourceTypes
from db.volumes import *
from db.sources import Source
from db.occurrences import Occurrence, ReferenceType, fetchForEntry

from tests import utils

class VolumeTests(utils.DbTestCase):
    def testObject(self):
        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(s1, 2, "This is volume 2.",
                            date(2015, 7, 7), date(2015, 8, 10))
        s2 = Source.makeNew('The Complete Otter Language Grammar',
                            (1,1), (5,80), 25, 'COLG', sourceTypes['book'])

        # creation error-checking
        with self.assertRaises(DuplicateError):
            v3 = Volume.makeNew(s1, 2, "This is volume 2.",
                                date(2015, 7, 7), date(2015, 8, 10))
        with self.assertRaises(ValidationError):
            v3 = Volume.makeNew(s1, 9000, "This is volume 2.",
                                date(2015, 7, 7), date(2015, 8, 10))
        with self.assertRaises(SingleVolumeError):
            v3 = Volume.makeNew(s2, 2, "This is volume 2, but there aren't 2.",
                                date(2015, 7, 7), date(2015, 8, 10))

        # method checking
        assert v1.vid == 1
        assert v1.num == 1
        assert v2.num == 2
        assert v1.source == s1
        assert v2.notes == "This is volume 2."
        assert v1.dateOpened == date(2015, 6, 1)
        assert v1.dateClosed == date(2015, 7, 6)

        v1.dateOpened = date(2015, 8, 8)
        v1.dateClosed = date(2015, 8, 9)
        v1.notes = "That was a *very* eventful two days..."
        with self.assertRaises(DuplicateError):
            v1.num = 2
        v1.num = 3
        reFetchVol = Volume(1)
        assert reFetchVol.dateOpened == date(2015, 8, 8)
        assert reFetchVol.dateClosed == date(2015, 8, 9)
        assert reFetchVol.notes == "That was a *very* eventful two days..."
        assert reFetchVol.num == 3

        assert len(allVolumes()) == 3 # v1 and v2 plus dummy volume for s2
        assert len(volumesInSource(s2)) == 1
        assert volumesInSource(s2)[0].num == 1
        assert volumesInSource(s2)[0].source == s2
        assert volumesInSource(s2)[0].notes == ""

    def testDelete(self):
        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(s1, 2, "This is volume 2.",
                            date(2015, 7, 7), date(2015, 8, 10))
        e1Name = "Maudi (Maudlin)"
        e2Name = "Katerina (Maudlin)"
        e1 = db.entries.Entry.makeNew(e1Name)
        e2 = db.entries.Entry.makeNew(e2Name, "ZKaterina", EntryClassification.TITLE)
        o1 = Occurrence.makeNew(e1, v1, '25', ReferenceType.NUM)
        o2 = Occurrence.makeNew(e2, v1, '27', ReferenceType.NUM)
        o3 = Occurrence.makeNew(e2, v2, '29', ReferenceType.NUM)

        v1.delete()
        # this should preserve v2 and e2, since o3 is part of v*2*, as well as
        # o3, but nothing else.
        with self.assertRaises(IndexError):
            db.entries.Entry.byEid(1)
        assert db.entries.Entry.byEid(2) == e2
        assert len(fetchForEntry(e2)) == 1
        assert fetchForEntry(e2)[0] == o3
        assert not s1.volExists(1)
        assert s1.volExists(2)
