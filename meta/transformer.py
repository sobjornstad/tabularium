#!/usr/bin/python

iput = \
"""
Paste the database output here.
"""

sql = []
for line in iput.split('\n'):
    try:
        oid, text = line.split('|')
    except ValueError:
        print "skipping line %r" % line
        continue
    oid = int(oid)
    print "\n:: %s" % text
    newVal = raw_input("? ")
    sql.append("UPDATE occurrences SET ref='%s' WHERE oid=%i;" % (newVal, oid))

print ""
print "Here's your SQL:"
print '\n'.join(sql)
