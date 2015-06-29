import utils

import db.database as d
from db.notebooks import *

class NotebookTests(utils.DbTestCase):
    def testObject(self):
        n1 = Notebook('CB', 1, '2014-01-01', '2014-01-02')
        n2 = Notebook('CB', 2, '2015-01-01', '2015-01-02')

        assert n1.getType() == 'CB' == n2.getType()
        assert n1.getDOpened() == '2014-01-01'
        assert n1.getDClosed() == '2014-01-02'
        assert n1.getNum() == 1

        n1.setDOpened('2012-01-01')
        assert n1.getDOpened() == '2012-01-01'

    def testFetchByNid(self):
        n1 = Notebook('CB', 1, '2014-01-01', '2014-01-02')
        n2 = Notebook('CB', 2, '2015-01-01', '2015-01-02')

        theNid = n1.getNid()
        newObj = Notebook.byId(theNid)
        assert n1 == newObj
        assert n1 != n2
