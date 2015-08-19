import utils

import db.database as d
from db.consts import sourceTypes
from db.sources import *
from db.volumes import Volume
from db.occurrences import Occurrence
from db.entries import Entry

class SourceTests(utils.DbTestCase):
    def testObject(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['diary'])
        assert s1.getName() == 'Chronic Book'

        s1.setName('Chrono Book')
        #s1.setStype(sourceTypes['diary']) # not implemented
        s1.setAbbrev('CB')
        s1.setValidVol((1, 100))
        s1.setValidPage((4, 80))
        s1.setNearbyRange(2)

        assert s1.getSid() == 1
        assert s1.getVolVal() == (1, 100)
        assert s1.getPageVal() == (4, 80)
        assert s1.getName() == 'Chrono Book'
        assert s1.getStype() == sourceTypes['diary']
        assert s1.getAbbrev() == 'CB'
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

        # resetting sensitive things
        v1 = Volume.makeNew(s1, 50, "")
        v2 = Volume.makeNew(s1, 5, "")
        e1 = Entry.makeNew("Kathariana")
        o1 = Occurrence.makeNew(e1, v1, '25', 0)
        o2 = Occurrence.makeNew(e1, v1, '50', 0)
        assert s1.volExists(50)
        with self.assertRaises(TrouncesError) as e:
            s1.setValidVol((1, 10))
            assert 'would make 1 volume and 2 occurrences invalid' in e
        s1.setValidVol((1, 10), overrideTrounce=True)
        assert not s1.volExists(50)
        assert s1.volExists(5)

        v2 = Volume.makeNew(s1, 10, "")
        e2 = Entry.makeNew("Melgreth, Maudia")
        o1 = Occurrence.makeNew(e2, v2, '25', 0)
        o2 = Occurrence.makeNew(e2, v2, '50', 0)
        assert len(e2.getOccurrences()) == 2
        with self.assertRaises(TrouncesError) as e:
            s1.setValidPage((1, 30))
            assert 'Changing the page max' in e
            assert 'would make 1 occurrence invalid' in e
        s1.setValidPage((1, 30), overrideTrounce=True)
        assert len(e2.getOccurrences()) == 1




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
