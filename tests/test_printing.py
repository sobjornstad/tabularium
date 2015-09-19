import tests.utils as utils
from datetime import date

from db.printing import *
from db.consts import sourceTypes
from db.sources import Source
from db.volumes import Volume
from db.entries import Entry, allEntries
from db.occurrences import Occurrence

class PrintingTests(utils.DbTestCase):
    def testPrint(self):
        s1 = Source.makeNew('Chrono Book', (1,100), (5,80), 25, 'CB',
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
        e8 = Entry.makeNew("Melgreth, Gracie")
        e9 = Entry.makeNew("Melgreth, Maudia, personality of")
        o1 = Occurrence.makeNew(e1, v1, '25', 0)
        o2 = Occurrence.makeNew(e2, v1, '26', 0)
        o3 = Occurrence.makeNew(e3, v1, '24', 0)
        o4 = Occurrence.makeNew(e4, v1, '25-28', 1)
        o5 = Occurrence.makeNew(e5, v1, '29', 0)
        o6 = Occurrence.makeNew(e6, v2, '25', 0)
        o7 = Occurrence.makeNew(e7, v1, '25-27', 1)
        o8 = Occurrence.makeNew(e1, v2, '46', 0)
        o9 = Occurrence.makeNew(e8, v2, '44', 0)
        o10 = Occurrence.makeNew(e9, v1, 'Kathariana', 2)
        o10 = Occurrence.makeNew(e9, v1, '32', 0)

        elist = getFormattedEntriesList(allEntries())
        document = '\n\n'.join([DOC_STARTSTR, '\n'.join(elist), INDEX_ENDSTR])

        #with open('tests/resources/fullindexcompare.tex', 'w') as f:
        #    f.write(document)
        with open('tests/resources/fullindexcompare.tex') as f:
            onDisk = f.read()
        assert onDisk == document

        #TODO: test actually compiling

    def testSimplificationPrint(self):
        s1 = Source.makeNew('Chrono Book', (1,100), (5,80), 25, 'CB',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 1, "This is volume 1.",
                            date(2015, 6, 1), date(2015, 7, 6))
        v2 = Volume.makeNew(s1, 2, "This is volume 2.",
                            date(2015, 7, 7), date(2015, 8, 10))
        e1 = Entry.makeNew("Entry A")
        e2 = Entry.makeNew("Entry B")
        e3 = Entry.makeNew("Entry C")
        e4 = Entry.makeNew("Entry D")
        e5 = Entry.makeNew("Entry E")
        e6 = Entry.makeNew("Entry F")
        e7 = Entry.makeNew("Entry G")
        e8 = Entry.makeNew("Entry H")
        e9 = Entry.makeNew("Entry I")

        o1 = Occurrence.makeNew(e1, v1, '25', 0)
        o2 = Occurrence.makeNew(e2, v1, '26', 0)
        o3 = Occurrence.makeNew(e3, v1, '24', 0)
        o4 = Occurrence.makeNew(e4, v1, '24', 0)

        #o5 = Occurrence.makeNew(e5, v1, '29', 0)
        #o6 = Occurrence.makeNew(e6, v2, '25', 0)
        #o7 = Occurrence.makeNew(e7, v1, '25-27', 1)
        #o8 = Occurrence.makeNew(e1, v2, '46', 0)
        #o9 = Occurrence.makeNew(e8, v2, '44', 0)
        #o10 = Occurrence.makeNew(e9, v1, 'Kathariana', 2)
        #o10 = Occurrence.makeNew(e9, v1, '32', 0)
        makeSimplification()
        assert False
