import utils

import db.database as d
from db.entries import *
from db.notebooks import *
from db.occurrences import *

class OccTests(utils.DbTestCase):
    def testObject(self):
        e1 = Entry.makeNew("Kathariana")
        e2 = Entry.makeNew("Melgreth, Maudia")
        n1 = Notebook('CB', 2, '2015-01-01', '2015-02-01')
        o1 = Occurrence(e1, '25', n1)

        assert o1.getEntry() == e1
        assert o1.getNotebook() == n1
        assert o1.getPage() == '25'
        oid = o1.getOid()

        o1.setEntry(e2)
        oNew = Occurrence.byId(oid)
        assert oNew.getEntry() == e2

        # fetchForEntry
        occs = fetchForEntry(e2)
        assert len(occs) == 1
        assert occs[0] == o1

