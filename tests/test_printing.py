import tests.utils as utils
from datetime import date

from db.printing import *
from db.consts import sourceTypes
from db.sources import Source
from db.volumes import Volume
from db.entries import Entry, allEntries
from db.occurrences import Occurrence, ReferenceType

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
        o1 = Occurrence.makeNew(e1, v1, '25', ReferenceType.NUM)
        o2 = Occurrence.makeNew(e2, v1, '26', ReferenceType.NUM)
        o3 = Occurrence.makeNew(e3, v1, '24', ReferenceType.NUM)
        o4 = Occurrence.makeNew(e4, v1, '25-28', ReferenceType.RANGE)
        o5 = Occurrence.makeNew(e5, v1, '29', ReferenceType.NUM)
        o6 = Occurrence.makeNew(e6, v2, '25', ReferenceType.NUM)
        o7 = Occurrence.makeNew(e7, v1, '25-27', ReferenceType.RANGE)
        o8 = Occurrence.makeNew(e1, v2, '46', ReferenceType.NUM)
        o9 = Occurrence.makeNew(e8, v2, '44', ReferenceType.NUM)
        o10 = Occurrence.makeNew(e9, v1, 'Kathariana', ReferenceType.REDIRECT)
        o10 = Occurrence.makeNew(e9, v1, '32', ReferenceType.NUM)

        elist = getFormattedEntriesList(allEntries())
        document = '\n\n'.join([DOC_STARTSTR, '\n'.join(elist), INDEX_ENDSTR])

        #with open('tests/resources/fullindexcompare.tex', 'w') as f:
        #    f.write(document)
        with open('tests/resources/fullindexcompare.tex') as f:
            onDisk = f.read()
        assert onDisk == document

        #TODO: test actually compiling

    def testSimplificationPrint(self):
        pass
        # actually test things!
