import utils
import time

import db.database as database
import db.entries

class DbTests(utils.DbTestCase):
    def test_DbAutosave(self):
        pass
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
