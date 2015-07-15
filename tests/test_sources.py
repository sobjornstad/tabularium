import utils

import db.database as d
from db.consts import sourceTypes
from db.sources import *

class SourceTests(utils.DbTestCase):
    def testObject(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['other'])
        assert s1.getName() == 'Chronic Book'

        s1.setName('Chrono Book')
        s1.setStype(sourceTypes['diary'])
        s1.setAbbrev('CB')
        s1.setValidVol((1, 100))
        s1.setValidPage((4, 80))
        s1.setNearbyRange(2)

        assert s1.getName() == 'Chrono Book'
        assert s1.getStype() == sourceTypes['diary']
        assert s1.getAbbrev() == 'CB'
        assert s1.nearbySpread(8) == (6,10)
        assert s1.isValidVol(2)
        assert not s1.isValidVol(5000)
        assert s1.isValidPage(26)
        assert not s1.isValidPage(9001)

    def testFetchAll(self):
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['other'])
        s2 = Source.makeNew('Turticular Book', (1,20), (1,240), 3, 'TB',
                sourceTypes['notebooktype'])
        assert allSources() == [s1, s2]
