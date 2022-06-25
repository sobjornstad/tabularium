import tempfile
import unittest

from db.consts import sourceTypes
from db.database import (d, makeDatabase, installGlobalConnection, DatabaseConnection,
                         upgradeDatabase, downgradeDatabase)
from db.entries import Entry, findOne
from db.occurrences import Occurrence, ReferenceType
from db.sources import Source
from db.volumes import Volume

from . import utils

class DbTests(utils.DbTestCase):
    def test_DbAutosave(self):
        d().saveInterval = 0
        Entry.makeNew("Margareta")
        assert d().checkAutosave()

        d().saveInterval = 5000
        Entry.makeNew("Maggie")
        assert not d().checkAutosave()

    def test_regex(self):
        for i in ("Katherine", "Kate", "Kaitlyn", "Katelyn", "Jonathan",
                  "John", "BlacKsheep"):
            Entry.makeNew(i)

        q = "SELECT * FROM entries WHERE name REGEXP '%s'"
        cur = d().cursor

        cur.execute(q % 'Katherine')
        assert len(cur.fetchall()) == 1
        cur.execute(q % '^K')
        assert len(cur.fetchall()) == 4
        cur.execute(q % 'K')
        assert len(cur.fetchall()) == 5
        cur.execute(q % 'K.*yn')
        assert len(cur.fetchall()) == 2
        cur.execute(q % '^[JK].*n$')
        assert len(cur.fetchall()) == 4

    def test_circular_upgrade(self):
        """
        Not a great test ATM, but as we don't have any actual upgrades yet it's hard to
        do better at the moment! This will at least catch exceptions.
        """
        s1 = Source.makeNew('Chronic Book', (10,100), (44,80), 25, 'CD',
                sourceTypes['diary'])
        v1 = Volume.makeNew(s1, 50, "")
        e1 = Entry.makeNew("Kathariana")
        o1 = Occurrence.makeNew(e1, v1, '25', ReferenceType.NUM)
        o2 = Occurrence.makeNew(e1, v1, '50', ReferenceType.NUM)
        self.conn.forceSave()

        downgradeDatabase(self.conn, 0, print)
        upgradeDatabase(self.conn, print)

        assert Entry(e1.eid).name == 'Kathariana'


class FileDbTest(unittest.TestCase):
    """
    Test creating a database on disk, since other tests do it in memory.

    Out of about 40 tests, this single one takes 4/5 of the time! That's how
    much faster the memory db is.
    """
    def test_fileDb(self):
        with tempfile.NamedTemporaryFile() as f:
            makeDatabase(f.name).close()
            installGlobalConnection(DatabaseConnection(f.name))
            e1 = Entry.makeNew("Margareta")
            d().close()

            # check for persistence
            installGlobalConnection(DatabaseConnection(f.name))
            ret = findOne("Margareta")
            assert ret == e1
