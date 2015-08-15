import tests.utils as utils
from datetime import date

import db.database as d
from db.consts import sourceTypes
from db.volumes import *
from db.sources import Source

class VolumeTests(utils.DbTestCase):
    def testObject(self):
        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        s2 = Source.makeNew('The Complete Otter Language Grammar',
                            (1,1), (5,80), 25, 'COLG', sourceTypes['book'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(s1, 2, "This is volume 2.",
                            date(2015, 7, 7), date(2015, 8, 10))

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
        assert v1.getVid() == 1
        assert v1.getNum() == 1
        assert v2.getNum() == 2
        assert v1.getSource() == s1
        assert v2.getNotes() == "This is volume 2."
        assert v1.getDopened() == date(2015, 6, 1)
        assert v1.getDclosed() == date(2015, 7, 6)

        v1.setDopened(date(2015, 8, 8))
        v1.setDclosed(date(2015, 8, 9))
        v1.setNotes("That was a *very* eventful two days...")
        assert v1.getDopened() == date(2015, 8, 8)
        assert v1.getDclosed() == date(2015, 8, 9)
        assert v1.getNotes() == "That was a *very* eventful two days..."
