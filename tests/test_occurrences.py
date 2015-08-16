import utils

import db.database as d
from db.entries import Entry
from db.occurrences import *
from db.sources import Source
from db.volumes import Volume
from db.consts import sourceTypes
from datetime import date

class OccTests(utils.DbTestCase):
    def testObject(self):
        e1 = Entry.makeNew("Kathariana")
        e2 = Entry.makeNew("Melgreth, Maudia")

        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(s1, 2, "This is volume 2.",
                            date(2015, 7, 7), date(2015, 8, 10))
        o1 = Occurrence.makeNew(e1, v1, '25', 0)

        assert o1.getEntry() == e1
        assert o1.getVolume() == v1
        assert o1.getRef() == ('25', 0)
        oid = o1.getOid()

        o1.setEntry(e2)
        oNew = Occurrence(oid)
        assert oNew.getEntry() == e2

        o1.setRef('25-27', 1)
        oNew = Occurrence(oid)
        assert oNew.getRef() == ('25-27', 1)

        o1.setVolume(v2)
        oNew = Occurrence(oid)
        assert oNew.getVolume() == v2


        # fetchForEntry
        occs = fetchForEntry(e2)
        assert len(occs) == 1
        assert occs[0] == o1

    def testNearby(self):
        ### Test proper returns and lack thereof.
        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(s1, 2, "This is volume 2.",
                            date(2015, 7, 7), date(2015, 8, 10))

        e1 = Entry.makeNew("Kathariana")
        e2 = Entry.makeNew("Melgreth, Maudia")
        e3 = Entry.makeNew("Vaunder, Salila")
        e4 = Entry.makeNew("Maud")
        e5 = Entry.makeNew("Elibemereth")
        e6 = Entry.makeNew("Whilla, Lianja")
        e7 = Entry.makeNew("Kaitlyn Complex")

        # we want this set to appear on query of e1
        o1 = Occurrence.makeNew(e1, v1, '25', 0)
        o2 = Occurrence.makeNew(e2, v1, '26', 0)
        o3 = Occurrence.makeNew(e3, v1, '24', 0)
        o4 = Occurrence.makeNew(e4, v1, '25-28', 0)

        # but these should not, for various reasons
        o5 = Occurrence.makeNew(e5, v1, '29', 0) # too far away
        o6 = Occurrence.makeNew(e6, v2, '25', 0) # wrong notebook
        o7 = Occurrence.makeNew(e7, v1, '25', 2) # wrong reftype

        r = o1.getNearby()
        assert len(r) == 4, len(r)
        assert e1 in r, 'own occ not in nearby'
        assert e2 in r, 'adjacent occ not in nearby'
        assert e3 in r, 'adjacent occ not in nearby'
        assert e4 in r, 'range on boundary not in nearby'
        assert e5 not in r, 'overly distant occ in nearby'
        assert e6 not in r, 'wrong notebook occ in nearby'
        assert e7 not in r, 'redirect reftype in nearby'

        # sort order (alphabetical)
        order = [o1, o4, o2, o3]
        entryOrder = [i.getEntry() for i in order]
        assert r == entryOrder

        ### test none returns for invalid entries?

    def testUnifiedFormat(self):
        """
        Tests should match the docstring documenting UOF in the
        parseUnifiedFormat() function.
        """
