import tempfile
import time
import unittest

import db.database as database
import db.entries

from . import utils

class DbTests(utils.DbTestCase):
    def test_DbAutosave(self):
        database.saveInterval = 0
        db.entries.Entry.makeNew("Margareta")
        assert database.checkAutosave()

        database.saveInterval = 5000
        db.entries.Entry.makeNew("Maggie")
        assert not database.checkAutosave()

    def test_regex(self):
        for i in ("Katherine", "Kate", "Kaitlyn", "Katelyn", "Jonathan",
                  "John", "BlacKsheep"):
            db.entries.Entry.makeNew(i)

        q = "SELECT * FROM entries WHERE name REGEXP '%s'"
        cur = database.cursor

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
            database.makeDatabase(f.name).close()
            database.connect(f.name)
            e1 = db.entries.Entry.makeNew("Margareta")
            database.close()

            database.connect(f.name)
            ret = db.entries.findOne("Margareta")
            assert ret == e1
