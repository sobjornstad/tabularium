from . import utils
from datetime import date

import db.database as d
import db.entries
import db.occurrences
from db.sources import Source
from db.volumes import Volume
from db.consts import sourceTypes, entryTypes

class DbTests(utils.DbTestCase):
    def testObject(self):
        e1Name = "Maudi (Maudlin)"
        e2Name = "Katerina (Maudlin)"
        e1 = db.entries.Entry.makeNew(e1Name)
        e2 = db.entries.Entry.makeNew(e2Name, "ZKaterina", 5)

        # nothing else in the db yet, so this is quite clear
        assert e1.eid == 1
        assert e2.eid == 2
        assert e1.name == e1Name
        assert e2.name == e2Name
        assert e1.sortKey == e1.name
        assert e2.sortKey == "ZKaterina"
        assert e1.classification == 0
        assert e2.classification == 5

        newName = "Maudia (Maudlin)"
        e1.name = newName
        assert e1.name == newName
        assert e1.sortKey == e1Name # not automatically changed
        e1.sortKey = newName
        assert e1.sortKey == e1.name
        e1.classification = 4
        assert e1.classification == 4

        assert e1 != e2
        anotherE = e1
        assert e1 == anotherE

        # date
        assert e1.dateAdded == date.today()
        assert e1.dateEdited == date.today()

        # sorting
        assert e1 < e2

    def testFind(self):
        e1Name = "Maudi (Maudlin)"
        e2Name = "Katerina (Maudlin)"
        e3Name = "Katharina (Maudlin)"
        e1 = db.entries.Entry.makeNew(e1Name)
        e2 = db.entries.Entry.makeNew(e2Name)
        e3 = db.entries.Entry.makeNew(e2Name)
        assert e3 is None
        e3 = db.entries.Entry.makeNew(e3Name)

        # test find multiple on single entry
        e1eid = e1.eid
        obj = db.entries.find(e1Name)
        assert obj[0].eid == e1eid

        # test findOne on single entry
        obj = db.entries.findOne(e1Name)
        assert obj.eid == e1eid

        # test globbing: should find all, since all have this word
        assert len(db.entries.find("%Maudlin%")) == 3
        assert len(db.entries.find("Maudlin")) != 3 # but not here, ofc

        # test findOne on multiple entries
        with self.assertRaises(db.entries.MultipleResultsUnexpectedError) \
                as context:
            db.entries.findOne("%Maudlin%")
        assert 'should not have returned multiple' in str(context.exception)

        # try changing
        newName = "Kathariana"
        e3.name = newName
        obj = db.entries.findOne(e2Name)
        assert obj.name == e2Name
        obj = db.entries.findOne(newName)
        assert obj.name == newName

        # test fetching by id
        assert db.entries.Entry(e1eid).eid == e1.eid

        # test allEntries
        assert len(db.entries.allEntries()) == 3
        for i in db.entries.allEntries():
            assert i == e1 or i == e2 or i == e3

        # fetching occurrences
        s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        o1 = db.occurrences.Occurrence.makeNew(e1, v1, '25', 0)
        l = db.occurrences.fetchForEntry(e1)
        assert len(l) == 1
        assert l[0].entry == e1

        # test delete
        assert db.entries.Entry(e1eid)

        # occurrence that should be deleted
        e1occs = db.occurrences.fetchForEntry(e1)
        oids = [i.oid for i in e1occs]
        assert db.occurrences.Occurrence(oids[0])
        # occurrence that should NOT be deleted
        o2 = db.occurrences.Occurrence.makeNew(e2, v1, '22', 0)

        e1.delete()
        with self.assertRaises(IndexError):
            db.entries.Entry(e1eid)
        # the occurrence should be deleted too
        d.cursor.execute('SELECT oid FROM occurrences WHERE oid=?', (oids[0],))
        with self.assertRaises(IndexError):
            d.cursor.fetchall()[0]
        assert db.occurrences.Occurrence(o2.oid)

    def testAdvancedFindFeatures(self):
        # globbing
        e1 = db.entries.Entry.makeNew("Melgreth, Maudia (_Maudlin_)",
                classification=entryTypes['person'])
        e2 = db.entries.Entry.makeNew('"the rational animal"',
                classification=entryTypes['quote'])
        e3 = db.entries.Entry.makeNew("_The Art of Computer Programming_",
                classification=entryTypes['title'])

        assert len(db.entries.find("%t%")) == 3
        assert len(db.entries.find("%t%", (entryTypes['person'],
                entryTypes['quote'], entryTypes['title']))) == 3
        assert len(db.entries.find("%t%", (entryTypes['person'],))) == 1

        e4 = db.entries.Entry.makeNew("An entry with a % in it",
                classification=entryTypes['ord'])
        e5 = db.entries.Entry.makeNew("An entry with a something else in it",
                classification=entryTypes['ord'])
        assert len(db.entries.find("An entry with a % in it")) == 1
        assert len(db.entries.find(
            db.entries.percentageWrap("entry with a % in"))) == 1

    def testDupeEntries(self):
        e1 = db.entries.Entry.makeNew("barf")
        assert db.entries.Entry.makeNew("barf") is None

    def testPercentageWrap(self):
        assert db.entries.percentageWrap("foo") == "%foo%"
        assert db.entries.percentageWrap("f%oo") == "%f\%oo%"

    def testSortKeyTransform(self):
        t = db.entries.sortKeyTransform
        assert t('"Soren"') == 'Soren'
        assert t("_Gödel, Escher, Bach_") == "Gödel, Escher, Bach"
        assert t("The Holy Bible") == "Holy Bible"
        assert t("'45") == "45"
        assert t("#sometimeswe") == "sometimeswe"
        assert t("/quit") == "quit"
        assert t('St. Olaf') == "Saint Olaf"

        # Tricky things that have thrown or could throw us
        # we don't escape this hash because it's in the middle
        assert t("_The End of the #Tests_") == "End of the #Tests"
        # not "e We Adore"
        assert t('"Thee We Adore"') == "Thee We Adore"
        # not "Saintats" (to be sure we didn't screw up '.' in our regex)
        assert t('Stats') == "Stats"
