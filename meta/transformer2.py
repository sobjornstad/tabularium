#!/usr/bin/python

iput = \
"""
1 2013-03-08
2 2013-04-06
3 2013-05-01
4 2013-05-28
5 2013-06-10
6 2013-07-01
7 2013-07-25
8 2013-08-23
12 2013-09-17
9 2013-10-27
10 2013-12-04
11 2013-12-31
13 2014-01-21
14 2014-02-16
15 2014-03-18
16 2014-04-18
17 2014-05-19
18 2014-06-21
19 2014-07-24
20 2014-08-16
21 2014-09-12
22 2014-10-13
23 2014-11-03
24 2014-12-01
25 2014-12-24
26 2015-01-18
27 2015-02-14
28 2015-03-20
29 2015-04-12
30 2015-05-02
31 2015-05-26
32 2013-05-30
"""

sql = []
for line in iput.split('\n'):
    try:
        vid, date = line.split(' ')
    except ValueError:
        print "skipping line %r" % line
        continue
    vid = int(vid)
    sql.append(
"UPDATE occurrences SET dAdded='%s', dEdited='%s' WHERE vid=%i;" % (
    date, date, vid))

print ""
print "Here's your SQL:"
print '\n'.join(sql)
