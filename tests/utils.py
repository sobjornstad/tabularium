import unittest

import db.database

# use a test db in memory, which is waaaaaaay faster
TEST_DB_FNAME = ":memory:"

class DbTestCase(unittest.TestCase):
    # common to all database-using test cases
    def dbSetUp(self):
        conn = db.database.makeDatabase(TEST_DB_FNAME)
        db.database.installGlobalConnection(db.database.DatabaseConnection(conn))
        print(db.database.d)

    def dbTearDown(self):
        db.database.d().close()

    # reimplement these if additional setup is needed
    def setUp(self):
        self.dbSetUp()

    def tearDown(self):
        self.dbTearDown()
        db.entries.Entry.invalidateCache()
