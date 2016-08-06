# -*- coding: utf-8 -*-
# Copyright (c) 2016 Soren Bjornstad <contact@sorenbjornstad.com>

import db.entries
import db.occurrences

def exportMindex(filename, callback=None):
    """
    Export the main index to a Mindex file; see db.importing for information
    on Mindex format.

    Periodically call callback function (if supplied) with a progress message.
    """
    entries = db.entries.allEntries()
    entries.sort(key=lambda i: i.getSortKey().lower())

    lines = []
    lastPercent = 0
    for step, entry in enumerate(entries):
        if callback and step % 50:
            percent = step * 100 // len(entries)
            if percent > lastPercent:
                callback("Exporting entries (%i%%)..." % percent)
                lastPercent = percent

        occs = db.occurrences.fetchForEntry(entry)
        occStrs = [i.getUOFRepresentation() for i in occs]
        assert '\t' not in entry.getName(), \
                "Your entry has a tab in its name! This is not allowed and " \
                "should not be possible."
        lines.append('%s\t%s\t%s' % (entry.getName(), ' | '.join(occStrs),
                                     entry.getSortKey()))
    callback("Writing file...")
    with open(filename, 'wt') as f:
        f.write('\n'.join(lines))
