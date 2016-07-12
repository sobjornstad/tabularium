import db.analytics
from db.entries import Entry

from . import utils

class AnalyticsTests(utils.DbTestCase):
    def testLetterDistro(self):
        e1 = Entry.makeNew("Kathariana")
        e2 = Entry.makeNew("Melgreth, Maudia")
        e3 = Entry.makeNew("Vaunder, Salila")
        e4 = Entry.makeNew("Maud")
        e5 = Entry.makeNew("Elibemereth")
        e6 = Entry.makeNew("Whilla, Lianja")
        e7 = Entry.makeNew("Kaitlyn Complex")
        e8 = Entry.makeNew("Melgreth, Gracie")
        e9 = Entry.makeNew("Melgreth, Maudia, personality of")
        e10 = Entry.makeNew("99 red balloons")
        e11 = Entry.makeNew("#not-sorted-correctly")
        report = db.analytics.letterDistribution()

        #with open('tests/resources/letterDistroCompare.html', 'w') as f:
        #    f.write(report)
        with open('tests/resources/letterDistroCompare.html') as f:
            onDisk = f.read()
        assert onDisk == report
