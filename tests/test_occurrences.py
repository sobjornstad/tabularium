# -*- coding: utf-8 -*-
from datetime import date

import db.database as d
from db.entries import Entry, find
from db.occurrences import *
import db.occurrences
from db.sources import Source
from db.volumes import Volume, byNumAndSource
from db.consts import sourceTypes

from . import utils

class UOFTests(utils.DbTestCase):
    def setUp(self):
        self.dbSetUp()
        self.cbSource = Source.makeNew('Chrono Book', (1,100), (5,80), 2, 'CB',
                                       sourceTypes['diary'])
        self.rtSource = Source.makeNew('Random Thoughts', (1,1), (1,20000), 2,
                                       'RT', sourceTypes['computerfile'])
        self.bookSource = Source.makeNew('The Invisible Man', (1,1), (1,200), 3,
                                         'TIM', sourceTypes['book'])
        self.bookSource2 = Source.makeNew('The 160th Book', (1,1), (1,200), 3,
                                          'T1B', sourceTypes['book'])
        self.v1 = Volume.makeNew(self.cbSource, 1, "",
                                 date(2015, 6, 1), date(2015, 7, 6))
        self.v2 = Volume.makeNew(self.cbSource, 2, "",
                                 date(2015, 7, 7), date(2015, 8, 10))

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

    def testUOFSuccesses(self):
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
                    'CB 2.45–6': 'CB 2.45-46 (1) == ',
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

    def testMakeOccurrencesFromStringNormal(self):
        # A little bit of wrapper code around parseUnifiedFormat()
        e1 = Entry.makeNew("Me, Myself, & I")
        occs = makeOccurrencesFromString("CB1.42", e1)
        assert len(occs[0]) == 1 # occs generated
        assert occs[1] == 0      # number of dupes
        occ = occs[0][0]
        assert occ.getEntry() == e1
        assert occ.getRef() == ('42', db.consts.refTypes['num'])
        assert occ.getVolume() == self.v1

    def testMakeOccurrencesFromStringDupe(self):
        e1 = Entry.makeNew("Me, Myself, & I")
        makeOccurrencesFromString("CB1.42", e1)
        occs = makeOccurrencesFromString("CB1.{42, 44}", e1)
        assert len(occs[0]) == 1
        assert occs[1] == 1
        assert occs[0][0].getRef()[0] == '44'

    # For each "raise" statement, hand function some string that fails.
    # Some of these may not fail the way I anticipate owing to earlier
    # checks, but all of these are clearly invalid and should trigger some
    # check.
    def testInvalidUOFError(self):
        # TODO: It would be nice to support more descriptive errors here.
        def duhWrapper(string):
            self._testUOFErr(string, InvalidUOFError, "Invalid UOF.")
        for i in ('CB 2.{46, 48', 'CB:htns.46', 'CB: 2.46.58',
                 'CB: 2.46--qq', 'CB 2.gc'):
            duhWrapper(i)
        duhWrapper('CB: 4.{48{48}}')
        duhWrapper('Soren 23789 3.78')
        duhWrapper('')
        duhWrapper('CB: {2.2')
        duhWrapper('CB {2.2 {2.6}}')
        duhWrapper('CB .{6}')

    def testNonexistentSourceError(self):
        self._testUOFErr('Flibbertygibberty: 2.15', NonexistentSourceError,
                         "The abbreviation or source name Flibbertygibberty "
                         "does not exist.")

    def testInvalidReferenceError(self):
        self._testUOFErr('CB: 9000.15', InvalidReferenceError,
                         "The "
                         'volume 9000'
                         " does not meet the validation parameters for Chrono "
                         "Book, which state that "
                         'volumes'
                         " must be between "
                         '1 and 100.')
        self._testUOFErr('CB: 1.800', InvalidReferenceError,
                         "The "
                         'page 800'
                         " does not meet the validation parameters for Chrono "
                         "Book, which state that "
                         'pages'
                         " must be between "
                         '5 and 80.')
        self._testUOFErr('CB: 2.16-2000', InvalidReferenceError,
                         "The "
                         'page 2000'
                         " does not meet the validation parameters for Chrono "
                         "Book, which state that "
                         'pages'
                         " must be between "
                         '5 and 80.')
        self._testUOFErr('CB: 2.2000-16', InvalidReferenceError,
                         "The "
                         'page 2000'
                         " does not meet the validation parameters for Chrono "
                         "Book, which state that "
                         'pages'
                         " must be between "
                         '5 and 80.')
        self._testUOFErr(
            'CB: 2.18-16', InvalidReferenceError,
            "The second number in a range must be larger than the first.")
        self._testUOFErr(
            'CB: 2.16-16', InvalidReferenceError,
            "The second number in a range must be larger than the first.")
        self._testUOFErr(
            'CB 2.45-3', InvalidReferenceError,
            "The second number in a range must be larger than the first.")

    def testNonexistentVolumeError(self):
        self._testUOFErr('CB: 4.48', NonexistentVolumeError,
                         "The volume 4 in source Chrono Book does not exist.")

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


    def _testUOFErr(self, uof, err, msg):
        with self.assertRaises(err) as context:
            parseUnifiedFormat(uof)
        assert str(context.exception) == msg, "Wrong error, correct error " \
            "message was: " + str(context.exception)


class OccTests(utils.DbTestCase):
    def setUp(self):
        # put in test sources, volumes, and entries we can play with,
        # along with one occurrence (others are added in tests as needed)
        self.dbSetUp()
        self.s1 = Source.makeNew('Chronic Book', (1,100), (5,80), 1, 'CD',
                                 sourceTypes['diary'])
        self.s2 = Source.makeNew('Topic Book', (1,1), (5,240), 2, 'TB',
                                 sourceTypes['other'])
        self.v1 = Volume.makeNew(self.s1, 1, "This is volume 1.",
                                 date(2015, 6, 1), date(2015, 7, 6))
        self.v2 = Volume.makeNew(self.s1, 2, "This is volume 2.",
                                 date(2015, 7, 7), date(2015, 8, 10))
        self.v3 = byNumAndSource(self.s2, 1)



        self.e1 = Entry.makeNew("Kathariana")
        self.e2 = Entry.makeNew("Melgreth, Maudia")
        self.e3 = Entry.makeNew("Vaunder, Salila")
        self.e4 = Entry.makeNew("Maud")
        self.e5 = Entry.makeNew("Elibemereth")
        self.e6 = Entry.makeNew("Whilla, Lianja")
        self.e7 = Entry.makeNew("Kaitlyn Complex")
        self.o1 = Occurrence.makeNew(self.e1, self.v1, '25', 0)

    def testGetters(self):
        assert self.o1.getEntry() == self.e1
        assert self.o1.getVolume() == self.v1
        assert self.o1.getRef() == ('25', 0)

    def testAssociatedEntry(self):
        self.o1.setEntry(self.e2)
        oNew = Occurrence(self.o1.getOid())
        assert oNew.getEntry() == self.e2

    def testAssociatedRef(self):
        self.o1.setRef('25-27', 1)
        oNew = Occurrence(self.o1.getOid())
        assert oNew.getRef() == ('25-27', 1)

    def testAssociatedVolume(self):
        self.o1.setVolume(self.v2)
        oNew = Occurrence(self.o1.getOid())
        assert oNew.getVolume() == self.v2

    def testFetchForEntry(self):
        occs = fetchForEntry(self.e1)
        assert len(occs) == 1
        assert occs[0] == self.o1

        occs = fetchForEntry(self.e2)
        assert len(occs) == 0

    def testDate(self):
        assert self.o1.getAddedDate() == date.today()
        assert self.o1.getEditedDate() == date.today()

    def testDuplicate(self):
        with self.assertRaises(db.occurrences.DuplicateError) as context:
            o2 = Occurrence.makeNew(self.e1, self.v1, '25', 0)
            o3 = Occurrence.makeNew(self.e1, self.v1, '25', 0)
        assert str(context.exception) == "That occurrence already exists."

    def testDelete(self):
        self.o1.delete()
        assert len(fetchForEntry(self.e2)) == 0
        # no need to put it back, automatic teardown


    def testNearby(self):
        o1 = self.o1

        # we want this set to appear on query of e1
        o2 = Occurrence.makeNew(self.e2, self.v1, '26', 0)
        o3 = Occurrence.makeNew(self.e3, self.v1, '24', 0)
        o4 = Occurrence.makeNew(self.e4, self.v1, '25-28', 1)

        # but these should not, for various reasons
        o5 = Occurrence.makeNew(self.e5, self.v1, '29', 0) # too far away
        o6 = Occurrence.makeNew(self.e6, self.v2, '25', 0) # wrong notebook
        o7 = Occurrence.makeNew(self.e7, self.v1, '25', 2) # wrong reftype

        r = o1.getNearby()
        assert len(r) == 3, len(r) # not counting o1 itself
        assert self.e1 not in r, 'own occ in nearby'
        assert self.e2 in r, 'adjacent occ not in nearby'
        assert self.e3 in r, 'adjacent occ not in nearby'
        assert self.e4 in r, 'range on boundary not in nearby'
        assert self.e5 not in r, 'overly distant occ in nearby'
        assert self.e6 not in r, 'wrong notebook occ in nearby'
        assert self.e7 not in r, 'redirect reftype in nearby'

        # but if we do the range, it uses nearby from each end, so the too-far
        # one will be within range
        r = o4.getNearby()
        assert self.e5 in r, 'range nearby not working right'

        assert not o6.getNearby() # only nearby itself

    def testSortOrder(self):
        o1 = self.o1
        o2 = Occurrence.makeNew(self.e2, self.v1, '26', 0)
        o3 = Occurrence.makeNew(self.e3, self.v1, '24', 0)
        o4 = Occurrence.makeNew(self.e4, self.v1, '25-28', 0)
        order = [o4, o2, o3]
        entryOrder = [i.getEntry() for i in order]
        assert o1.getNearby() == entryOrder

    def testGetOccsOfEntry(self):
        # same entry as o1 but different occurrence and pagenum
        o8 = Occurrence.makeNew(self.e1, self.v1, '27', 0)
        assert (o8.getOccsOfEntry() == [self.o1, o8]
                or o8.getOccsOfEntry == [o8, self.o1])
        ### test none returns for invalid entries?

    def testAllOccurrences(self):
        o2 = Occurrence.makeNew(self.e1, self.v2, '24', 0)
        assert sorted(allOccurrences()) == [self.o1, o2]

    def testRepr(self):
        assert "%r" % self.o1 == "<CD 1.25>"

    def testStr(self):
        o2 = Occurrence.makeNew(self.e1, self.v2, '22-24', 1)
        o3 = Occurrence.makeNew(self.e1, self.v3, 'Kathariana', 2)
        o4 = Occurrence.makeNew(self.e1, self.v2, 'Kathariana', 2)
        o5 = Occurrence.makeNew(self.e1, self.v3, '5', 0)
        assert str(self.o1) == "CD 1.25"
        assert str(o2) == "CD 2.22-24"
        assert str(o3) == 'TB: see "Kathariana"'
        assert str(o4) == 'CD 2: see "Kathariana"'
        assert str(o5) == "TB 5"

    def testGetStartEndPage(self):
        # number
        assert self.o1.getStartPage() == self.o1.getRef()[0]
        assert self.o1.getEndPage() == self.o1.getRef()[0]

        # range
        o2 = Occurrence.makeNew(self.e1, self.v2, '22-24', 1)
        assert o2.getStartPage() == '22'
        assert o2.getEndPage() == '24'

        # xref
        o3 = Occurrence.makeNew(self.e1, self.v3, 'Kathariana', 2)
        assert o3.getStartPage() is None
        assert o3.getEndPage() is None

    def testIsRefType(self):
        assert self.o1.isRefType('num')
        assert not self.o1.isRefType('redir')
        assert not self.o1.isRefType('range')
        with self.assertRaises(KeyError):
            self.o1.isRefType('poo')

    def testFetchForEntryFiltered(self):
        # self.o1 = Occurrence.makeNew(self.e1, self.v1, '25', 0)
        o1 = self.o1
        o2 = Occurrence.makeNew(self.e1, self.v1, '6', 0)
        o3 = Occurrence.makeNew(self.e1, self.v2, '7', 0)
        o4 = Occurrence.makeNew(self.e1, self.v3, '8', 0)

        # manually set dates
        d.cursor.execute('''UPDATE occurrences SET dAdded = '2012-01-01'
                            WHERE oid=?''', (o1.getOid(),))
        d.cursor.execute('''UPDATE occurrences SET dEdited = '2012-04-01'
                          WHERE oid=?''', (o2.getOid(),))
        # others using today's date, sometime after 2012

        assert len(fetchForEntryFiltered(self.e1)) == 4
        assert len(fetchForEntryFiltered(
            self.e1, enteredDate=('2011-01-01', '2013-01-01'))) == 1
        assert len(fetchForEntryFiltered(
            self.e1, modifiedDate=('2011-01-01', '2013-01-01'))) == 1
        assert len(fetchForEntryFiltered(self.e1, source=self.s1)) == 3
        assert len(fetchForEntryFiltered(
            self.e1, source=self.s1, volume=(2, 2))) == 1
        assert len(fetchForEntryFiltered(
            self.e1, source=self.s1, volume=(1, 2))) == 3
        with self.assertRaises(AssertionError): # can't search by just volume
            fetchForEntryFiltered(self.e1, volume=(1, 4))
        # combined
        assert (fetchForEntryFiltered(
                    self.e1, source=self.s1, volume=(self.v1.getNum(), 22),
                    modifiedDate=('2011-01-01', '2013-01-01'))[0].getOid()
                    == o2.getOid())
        # FIXME: for some reason direct equality doesn't work and I'm not sure
        # why: does the date get incorrectly updated for some reason?
