from . import utils

from db.consts import sourceTypes
from db.sources import *
from db.volumes import Volume
from db.occurrences import Occurrence, ReferenceType, fetchForEntry
from db.entries import Entry

class SourceTests(utils.DbTestCase):
    def testObject(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['diary'])
        assert s1.name == 'Chronic Book'

        s1.name = 'Chrono Book'
        #s1.setStype(sourceTypes['diary']) # not implemented
        s1.abbrev = 'CB'
        s1.volVal = (1, 100)
        s1.pageVal = (4, 80)
        s1.nearbyRange = 2

        assert s1.sid == 1
        assert s1.volVal == (1, 100)
        assert s1.pageVal == (4, 80)
        assert s1.name == 'Chrono Book'
        assert s1.sourceType == sourceTypes['diary']
        assert s1.abbrev == 'CB'
        assert s1.nearbySpread(8) == (6,10)
        assert s1.isValidVol(2)
        assert not s1.isValidVol(5000)
        assert s1.isValidPage(26)
        assert not s1.isValidPage(9001)

        # errors
        with self.assertRaises(DiaryExistsError):
            s2 = Source.makeNew('New Diary', (10,100), (44,80), 25, 'CC',
                    sourceTypes['diary'])
        with self.assertRaises(DuplicateError):
            s2 = Source.makeNew('Chronic Books', (10,100), (44,80), 25, 'CH',
                    sourceTypes['book'])
            s3 = Source.makeNew('Chronic Books', (10,100), (44,80), 25, 'CH',
                    sourceTypes['book'])
        with self.assertRaises(InvalidNameError):
            s3 = Source.makeNew('Chronic|Books', (10,100), (44,80), 25, 'CJ',
                    sourceTypes['book'])
        with self.assertRaises(InvalidNameError):
            s3 = Source.makeNew('Chronicality', (10,100), (44,80), 25, 'C|H',
                    sourceTypes['book'])

        # resetting sensitive things
        v1 = Volume.makeNew(s1, 50, "")
        v2 = Volume.makeNew(s1, 5, "")
        e1 = Entry.makeNew("Kathariana")
        o1 = Occurrence.makeNew(e1, v1, '25', ReferenceType.NUM)
        o2 = Occurrence.makeNew(e1, v1, '50', ReferenceType.NUM)
        assert s1.volExists(50)
        with self.assertRaises(TrouncesError) as e:
            s1.volVal = (1, 10)
            assert 'would make 1 volume and 2 occurrences invalid' in e
        with db.sources.bypassTrounceWarnings(s1):
            s1.volVal = (1, 10)
        assert not s1.volExists(50)
        assert s1.volExists(5)

        v2 = Volume.makeNew(s1, 10, "")
        e2 = Entry.makeNew("Melgreth, Maudia")
        o1 = Occurrence.makeNew(e2, v2, '25', ReferenceType.NUM)
        o2 = Occurrence.makeNew(e2, v2, '50', ReferenceType.NUM)
        assert len(fetchForEntry(e2)) == 2
        with self.assertRaises(TrouncesError) as e:
            s1.pageVal = (1, 30)
            assert 'Changing the page max' in e
            assert 'would make 1 occurrence invalid' in e
        with db.sources.bypassTrounceWarnings(s1):
            s1.pageVal = (1, 30)
        assert len(fetchForEntry(e2)) == 1


    def testDelete(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 10, "")
        e1 = Entry.makeNew("foo")
        o1 = Occurrence.makeNew(e1, v1, '25', ReferenceType.NUM)
        o2 = Occurrence.makeNew(e1, v1, '29', ReferenceType.NUM)

        # these things should survive
        s2 = Source.makeNew('The Chronicles', (1,17), (1,240), 2, 'CC',
                sourceTypes['other']) # Lillian & Sylvia reference :-)
        v1n = Volume.makeNew(s2, 5, "")
        v2n = Volume.makeNew(s2, 2, "")
        e1n = Entry.makeNew("Martha")
        o1n = Occurrence.makeNew(e1n, v1n, '25', ReferenceType.NUM)
        o2n = Occurrence.makeNew(e1n, v1n, '50', ReferenceType.NUM)

        assert s1.deletePreview() == (1, 2)
        s1.delete()
        assert len(allSources()) == 1, len(allSources())
        assert db.volumes.volExists(s2, 5)
        assert len(db.entries.allEntries()) == 1
        fetch = fetchForEntry(e1n)
        assert fetch == [o1n, o2n] or fetch == [o2n, o1n]


    def testFetches(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['other'])
        s2 = Source.makeNew('Turticular Book', (1,20), (1,240), 3, 'TB',
                sourceTypes['notebooktype'])
        assert allSources() == [s1, s2]

        assert getDiary() is None
        s3 = Source.makeNew('Chrono Book', (1,100), (5,80), 25, 'CB',
                sourceTypes['diary'])
        assert getDiary() == s3

    def testInvalidData(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['other'])
        s2 = Source.makeNew('Turticular Book', (1,20), (1,240), 3, 'TB',
                sourceTypes['notebooktype'])
        with self.assertRaises(DuplicateError):
            Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CB',
                    sourceTypes['other'])
            Source.makeNew('Foobar Book', (10,100), (44,80), 25, 'HQ',
                    sourceTypes['other'])

        with self.assertRaises(InvalidRangeError):
            Source.makeNew('Mathematical Fool', (10,1), (44,80), 25, 'PX',
                    sourceTypes['other'])
            Source.makeNew('Mathematical Fool', (10,30), (44,2), 25, 'PC',
                    sourceTypes['other'])
