import utils
from datetime import date

import db.database as d
from db.entries import *
import db.occurrences
from db.sources import Source
from db.volumes import Volume
from db.consts import sourceTypes

class DbTests(utils.DbTestCase):
    def testObject(self):
        e1Name = "Maudi (Maudlin)"
        e2Name = "Katerina (Maudlin)"
        e1 = Entry.makeNew(e1Name)
        e2 = Entry.makeNew(e2Name, "ZKaterina", 5)

        # nothing else in the db yet, so this is quite clear
        assert e1.getEid() == 1
        assert e2.getEid() == 2
        assert e1.getName() == e1Name
        assert e2.getName() == e2Name
        assert e1.getSortKey() == e1.getName()
        assert e2.getSortKey() == "ZKaterina"
        assert e1.getClassification() == 0
        assert e2.getClassification() == 5

        newName = "Maudia (Maudlin)"
        e1.setName(newName)
        assert e1.getName() == newName
        assert e1.getSortKey() == e1Name # not automatically changed
        e1.setSortKey(newName)
        assert e1.getSortKey() == e1.getName()
        e1.setClassification(4)
        assert e1.getClassification() == 4

        assert e1 != e2
        anotherE = e1
        assert e1 == anotherE

    def testFind(self):
        e1Name = "Maudi (Maudlin)"
        e2Name = "Katerina (Maudlin)"
        e3Name = "Katharina (Maudlin)"
        e1 = Entry.makeNew(e1Name)
        e2 = Entry.makeNew(e2Name)
        e3 = Entry.makeNew(e2Name)
        assert e3 is None
        e3 = Entry.makeNew(e3Name)

        # test single entry
        e1eid = e1.getEid()
        obj = find(e1Name)
        assert obj[0].getEid() == e1eid

        # test globbing: should find all, since all have this word
        assert len(find("%Maudlin%")) == 3
        assert len(find("Maudlin")) != 3 # but not here, ofc

        # try changing
        newName = "Kathariana"
        e3.setName(newName)
        obj = find(e2Name)
        assert len(obj) == 1
        assert obj[0].getName() == e2Name
        obj = find(newName)
        assert len(obj) == 1
        assert obj[0].getName() == newName

        # test fetching by id
        assert Entry(e1eid).getEid() == e1.getEid()

        # test allEntries
        assert len(allEntries()) == 3
        for i in allEntries():
            assert i == e1 or i == e2 or i == e3

        # fetching occurrences
        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        o1 = db.occurrences.Occurrence.makeNew(e1, v1, '25', 0)
        l = e1.getOccurrences()
        assert len(l) == 1
        assert l[0].getEntry() == e1

        # test delete
        assert Entry(e1eid)

        # occurrence that should be deleted
        e1occs = e1.getOccurrences()
        oids = [i.getOid() for i in e1occs]
        assert db.occurrences.Occurrence(oids[0])
        # occurrence that should NOT be deleted
        o2 = db.occurrences.Occurrence.makeNew(e2, v1, '22', 0)

        e1.delete()
        with self.assertRaises(IndexError):
            Entry(e1eid)
        # the occurrence should be deleted too
        d.cursor.execute('SELECT oid FROM occurrences WHERE oid=?', (oids[0],))
        with self.assertRaises(IndexError):
            d.cursor.fetchall()[0]
        assert db.occurrences.Occurrence(o2.getOid())
