# -*- coding: utf-8 -*-
import utils

import db.database as d
from db.entries import Entry
from db.occurrences import *
import db.occurrences
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

        # uses today's date
        assert o1.getAddedDate() == date.today()
        assert o1.getEditedDate() == date.today()

        # dupes
        with self.assertRaises(db.occurrences.DuplicateError):
            o2 = Occurrence.makeNew(e1, v1, '25', 0)
            o3 = Occurrence.makeNew(e1, v1, '25', 0)

        # delete
        o1.delete()
        assert len(fetchForEntry(e2)) == 0


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

        # getOccsOfEntry (similar but more restrictive)
        # same entry as o1 but different occurrence and pagenum
        o8 = Occurrence.makeNew(e1, v1, '27', 0)
        assert o8.getOccsOfEntry() == [o1, o8] or o8.getOccsOfEntry == [o8, o1]


        ### test none returns for invalid entries?

    def testUOFSplitSourceRef(self):
        """
        Tests should include all tests from the docstring documenting UOF in the
        parseUnifiedFormat() function.
        """
        testDict = {
# mentioned in docstring
'CB1.56': ('CB', '1.56'),
'CB 1.56': ('CB', '1.56'),
'CB: 1.56': ('CB', '1.56'),
'CB:1 . 56': ('CB', '1 . 56'),
'RT 2378': ('RT', '2378'),
'RT 1.2378': ('RT', '1.2378'),
'The Invisible Man 58': ('The Invisible Man', '58'),
'The 160th Book: 45': ('The 160th Book', '45'),
'CB:{1.56, 5.78}': ('CB', '{1.56, 5.78}'),
'CB {1.56, 5 .78,}': ('CB', '{1.56, 5 .78,}'),
'CB{1.56}': ('CB', '{1.56}'),
# other tests, trying my best to break the little sucker
'The Invisible Man:234': ('The Invisible Man', '234'),
'The Invisible Man: 235': ('The Invisible Man', '235'),
'The Invisible Man: 1.235': ('The Invisible Man', '1.235'),
'The Invisible Man: {1.235}': ('The Invisible Man', '{1.235}'),
'The Invisible Man: 1.{235}': ('The Invisible Man', '1.{235}'),
'The Invisible Man: 1.{235,334}': ('The Invisible Man', '1.{235,334}'),
'The Invisible Man 588': ('The Invisible Man', '588'),
'The Invisible Man {588, 264}': ('The Invisible Man', '{588, 264}'),
'The Invisible Man 2.588': ('The Invisible Man', '2.588'),
'The Invisible Man 2.{588}': ('The Invisible Man', '2.{588}'),
'The Invisible Man 2.{220,588}': ('The Invisible Man', '2.{220,588}'),'The Invisible Man {2.220, 1.588}': ('The Invisible Man', '{2.220, 1.588}'),
'CB:3.56': ('CB', '3.56'),
'Chrono Book 5.{21,54,16}': ('Chrono Book', '5.{21,54,16}'),
'CB 5.15': ('CB', '5.15'),
'CB5.58': ('CB', '5.58'),
'CB5.{58}': ('CB', '5.{58}'),
'CB 5.{58}': ('CB', '5.{58}'),
'CB5.{58, 79}': ('CB', '5.{58, 79}'),
'CB 5.{58,79}': ('CB', '5.{58,79}'),
'CB {5.58}': ('CB', '{5.58}'),
'CB{5.58}': ('CB', '{5.58}'),
'CB{5.58,6.17,}': ('CB', '{5.58,6.17,}'),
'The 121st Valid String {237, 348}': ('The 121st Valid String', '{237, 348}'),
'The 122nd Valid String {237}': ('The 122nd Valid String', '{237}'),
'The 123rd Valid. String {5.23}': ('The 123rd Valid. String', '{5.23}'),
'The 124th Valid: String: {5.23}': ('The 124th Valid: String', '{5.23}'),
                    }

        for i in testDict.keys():
            assert db.occurrences._splitSourceRef(i) == testDict[i], \
                    "testDict: %r\nreturned:%r\n\n" % (
                    testDict[i], db.occurrences._splitSourceRef(i))

    def testUOFParse(self):
        cbSource = Source.makeNew('Chrono Book', (1,100), (5,80), 2, 'CB',
                sourceTypes['diary'])
        rtSource = Source.makeNew('Random Thoughts', (1,1), (1,20000), 2, 'RT',
                sourceTypes['computerfile'])
        bookSource = Source.makeNew('The Invisible Man', (1,1), (1,200), 3,
                'TIM', sourceTypes['book'])
        bookSource = Source.makeNew('The 160th Book', (1,1), (1,200), 3,
                'T1B', sourceTypes['book'])
        v1 = Volume.makeNew(cbSource, 1, "",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(cbSource, 2, "",
                            date(2015, 7, 7), date(2015, 8, 10))

        testDict = {'CB1.56': 'CB 1.56 (0) == ',
                    'CB 1.56': 'CB 1.56 (0) == ',
                    'CB: 1.56': 'CB 1.56 (0) == ',
                    'Chrono Book 1.77-9': 'CB 1.77-79 (1) == ',
                    'CB:1 . 56': 'CB 1.56 (0) == ',
                    'RT 2378': 'RT 1.2378 (0) == ',
                    'RT 1.2378': 'RT 1.2378 (0) == ',
                    'The Invisible Man 58': 'TIM 1.58 (0) == ',
                    'TIM 58': 'TIM 1.58 (0) == ',
                    'The 160th Book: 45': 'T1B 1.45 (0) == ',
                    'T1B: 45': 'T1B 1.45 (0) == ',
                    'CB:{1.56, 2.78}': 'CB 1.56 (0) == CB 2.78 (0) == ',
                    'CB {1.56,2 .78,}': 'CB 1.56 (0) == CB 2.78 (0) == ',
                    'CB{1.56}': 'CB 1.56 (0) == ',
                    'CB 1.56 | CB 2.78 | CB 2.56': 'CB 1.56 (0) == CB 2.78 (0) == CB 2.56 (0) == ',
                    'CB {1.56, 2.78} | CB 2.56': 'CB 1.56 (0) == CB 2.78 (0) == CB 2.56 (0) == ',
                    'RT 2378 | The Invisible Man {56, 78}': 'RT 1.2378 (0) == TIM 1.56 (0) == TIM 1.78 (0) == ',
                    'The 160th Book: 45 | CB1.62': 'T1B 1.45 (0) == CB 1.62 (0) == ',
                    'CB 2.45-56': 'CB 2.45-56 (1) == ',
                    u'CB 2.45–6': 'CB 2.45-46 (1) == ',
                    'CB 2.45--56': 'CB 2.45-56 (1) == ',
                    'RT 2348-89': 'RT 1.2348-2389 (1) == ',
                    'RT 1279-89': 'RT 1.1279-1289 (1) == ',
                    'RT1.107-8': 'RT 1.107-108 (1) == ',
                    'RT: see Foobar Entry': 'RT 1.Foobar Entry (2) == ',
                    'CB{1.26--7,2    . 18, 2.see    Other Entry} |The 160th Book    : 45': 'CB 1.26-27 (1) == CB 2.18 (0) == CB 2.Other Entry (2) == T1B 1.45 (0) == ',
                    'CB 2. see Mr. Aoeui': 'CB 2.Mr. Aoeui (2) == ',
                    'RT 1. see foobar': 'RT 1.foobar (2) == ',
                    'RT 1. see Mr. Aoeui': 'RT 1.Mr. Aoeui (2) == ',
                    'RT: see foobar': 'RT 1.foobar (2) == ',
                    'RT see foobar': 'RT 1.foobar (2) == ',
                    # hehe -- this didn't work right the first time though :-)
                    'CB 2.see seeing see foo': 'CB 2.seeing see foo (2) == ',
                    'RT see Other. Entry.': 'RT 1.Other. Entry. (2) == ',
                    'RT:see Other. see Entry.': 'RT 1.Other. see Entry. (2) == ',
                    'RT see Other. see E. Entry': 'RT 1.Other. see E. Entry (2) == ',
                    'RT see   Other . see   E. Entry': 'RT 1.Other . see   E. Entry (2) == ',
                    'RT: see "21st century classroom"': 'RT 1."21st century classroom" (2) == ',
                    'RT {see "21st century classroom"}': 'RT 1."21st century classroom" (2) == ',
                    'Random Thoughts {see "21st century classroom",}': 'RT 1."21st century classroom" (2) == ',
                    'CB 2.see King, Heather': 'CB 2.King, Heather (2) == ',
                    'CB 2.{see King\, Heather}': 'CB 2.King, Heather (2) == ',
                    'CB 2.{35, see King\, Heather}': 'CB 2.35 (0) == CB 2.King, Heather (2) == ',
                    'CB 2. {see King\, Heather}': 'CB 2.King, Heather (2) == ',
                   }

        for i in testDict.keys():
            #print "trying %r" % i
            reflist = parseUnifiedFormat(i)
            vals = ""
            for j in reflist:
                source, vol, ref, rtype = j
                vals += "%s %s.%s (%i)" % (
                        source.getAbbrev(), vol.getNum(), str(ref), rtype)
                vals += " == "
            assert vals == testDict[i], \
                    "vals was: %r\ntestDict was: %r" % (vals, testDict[i])

        # For each "raise" statement, hand function some string that fails.
        # Some of these may not fail the way I anticipate owing to earlier
        # checks, but all of these are clearly invalid and should trigger some
        # check.
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB 2.{46, 48')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB:htns.46')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB: 2.46.58')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB: 2.46.58')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB: 2.46--qq')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB 2.gc')
        with self.assertRaises(NonexistentSourceError):
            parseUnifiedFormat('Flibbertygibberty: 2.15')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB: 9000.15')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB: 1.800')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB: 2.16-2000')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB: 2.2000-16')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB: 2.18-16')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB: 2.16-16')
        with self.assertRaises(InvalidReferenceError):
            parseUnifiedFormat('CB 2.45-3')
        with self.assertRaises(NonexistentVolumeError):
            parseUnifiedFormat('CB: 4.48')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('CB: 4.{48{48}}')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('Soren 23789 3.78')
        with self.assertRaises(InvalidUOFError):
            parseUnifiedFormat('')

    def testColonlessValid(self):
        validStrs  =  ('The Invisible Man 588',
                       'The Invisible Man {588, 264}',
                       'Chrono Book 5.{21,54,16}',
                       'The 121st Valid String {237, 348}',
                       'The 122st Valid String {237}'
                      )
        invalidStrs = ('The 120th Invalid String 234',
                      )

        for i in validStrs:
            assert db.occurrences._isColonlessValid(i)
        for i in invalidStrs:
            assert not db.occurrences._isColonlessValid(i)
