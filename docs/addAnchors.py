#!/usr/bin/env python

import re
import sys

def replaceFunc(txt):
    txt = txt.replace(' ', '_')
    txt = txt.replace('&_', '')
    txt = txt.replace('&', '')
    txt = txt.replace(',', '')
    return txt

if len(sys.argv) <= 2:
    print "Usage: addAnchors input.md output.md"
    sys.exit(1)

readname = sys.argv[1]
writename = sys.argv[2]
with open(readname) as f:
    markdownLines = f.readlines()

with open(writename, 'w') as f:
    for line in markdownLines:
        if line.startswith('#'):
            match = re.match(r'^(\#+) (.*)', line)
            hashes, text = match.group(1), match.group(2)
            modtext = replaceFunc(text.lower())
            f.write('<a id="%s"></a>\n%s %s' % (modtext, hashes, text))
        else:
            f.write(line)
