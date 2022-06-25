import tempfile
import unittest

from db.database import d, makeDatabase, installGlobalConnection, DatabaseConnection
import db.entries

from . import utils

class DbTests(utils.DbTestCase):
    def test_DbAutosave(self):
        d().saveInterval = 0
        db.entries.Entry.makeNew("Margareta")
        assert d().checkAutosave()

        d().saveInterval = 5000
        db.entries.Entry.makeNew("Maggie")
        assert not d().checkAutosave()

    def test_regex(self):
        for i in ("Katherine", "Kate", "Kaitlyn", "Katelyn", "Jonathan",
                  "John", "BlacKsheep"):
            db.entries.Entry.makeNew(i)

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
            e1 = db.entries.Entry.makeNew("Margareta")
            d().close()

            # check for persistence
            installGlobalConnection(DatabaseConnection(f.name))
            ret = db.entries.findOne("Margareta")
            assert ret == e1
