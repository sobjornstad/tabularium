#!/usr/bin/python
import re
import db.database
import db.entries

db.database.connect('records-editing.db')
allEntries = db.entries.allEntries()
replaces = []
for i in allEntries:
    eid = i.getEid()
    text = i.getName()
    if '__' in text:
        newText = re.sub('(.*)__', '_\\1_', text)
        newSort = re.sub('_', '', text)
        replaces.append((eid, newText, newSort))

conn = db.database.connection
with conn:
    c = conn.cursor()
    for i in replaces:
        eid = i[0]
        name = i[1]
        sortkey = i[2]
        #print "%s - %s - %s" % (eid, name, sortkey)

        q = '''UPDATE entries SET name=?, sortkey=? WHERE eid=?'''
        c.execute(q, (name, sortkey, eid))
