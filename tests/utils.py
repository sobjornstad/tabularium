import unittest

import db.database

# use a test db in memory, which is waaaaaaay faster
TEST_DB_FNAME = ":memory:"

class DbTestCase(unittest.TestCase):
    # common to all database-using test cases
    def dbSetUp(self):
        conn = db.database.makeDatabase(TEST_DB_FNAME)
        db.database.openDbConnect(conn)

    def dbTearDown(self):
        db.database.connection.close()

    # reimplement these if additional setup is needed
    def setUp(self):
        self.dbSetUp()

    def tearDown(self):
        self.dbTearDown()
        db.entries.Entry.clearEntryCache()
