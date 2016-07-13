# -*- coding: utf-8 -*-
# Copyright (c) 2016 Soren Bjornstad <contact@sorenbjornstad.com>
#
# Code written with reference to the documentation and code of Mindex
# <https://github.com/sobjornstad/mindex>, also written by Soren Bjornstad.

"""
Functions for importing data from other file formats into Tabularium.
"""

import db.occurrences
from db.entries import Entry
from db.consts import entryTypes

def importMindex(filename):
    """
    Create entries and occurrences from a file in Mindex format. Mindex format
    consists of three tab-separated columns:
        1: entry name;
        2: UOF for one or more occurrences;
        3: (optionally) a sort key.
    The tab separating columns 2 and 3 is optional if there is no sort key. As
    usual, of course, having no sort key implies that it's the same as the
    entry name itself.

    If a given line is invalid for some reason, an error is recorded in a list,
    that line is skipped, and the following lines are processed.

    If an entry already exists, add occurrences to it; as when adding entries
    through the GUI, the sort key will not be modified even if it is different.

    State change:
        The entries and occurrences specified in the file are added to the
        database.

    Return:
        A tuple:
            [0] The number of entries that did not cause an error (i.e., the
                number of lines that were not blank, comments, or unable to be
                imported; this includes pure duplicates).
            [1] Any errors generated by the process, as a list of tuples:
                [0] an error message;
                [1] the full text of the offending line;
                [2] the line number.

        Warnings for duplicate occurrences (but not duplicate entries) are also
        included.
    """
    errors = []
    entriesTouched = 0
    with open(filename, 'rt') as f:
        lines = f.readlines()
    for linenum, line in enumerate((i.strip() for i in lines), 1):
        # skip past comments and blank lines
        if line.startswith('#') or not len(line):
            continue

        # parse line
        splits = line.split('\t')
        #print(splits)
        if len(splits) < 2 or len(splits) > 3:
            msg = ("At least two tab-separated columns, entries and "
                   "occurrences, are required.")
            errors.append((msg, line, linenum))
            continue
        elif len(splits) == 3 and splits[2].strip():
            entryText, uof, sortKey = (i.strip() for i in splits)
        else:
            entryText, uof = (i.strip() for i in splits)
            sortKey = entryText.strip()

        # create, or find, entry
        existingEntries = db.entries.find(entryText.strip())
        if not existingEntries:
            entry = Entry.makeNew(entryText, sortKey,
                                  entryTypes['unclassified'])
        else:
            entry = existingEntries[0]

        # create occurrence
        try:
            occs, numDupes = db.occurrences.makeOccurrencesFromString(uof,
                                                                      entry)
        except db.occurrences.InvalidUOFError as e:
            msg = ("The occurrence (second) column does not contain valid "
                   "UOF. Please see the UOF section of the manual if you "
                   "are unsure why you're getting this error.")
            errors.append((msg, line, linenum))
            entry.delete()
            continue
        except (db.occurrences.NonexistentSourceError,
                db.occurrences.NonexistentVolumeError,
                db.occurrences.InvalidReferenceError) as e:
            errors.append((str(e), line, linenum))
            entry.delete()
            continue

        entriesTouched += 1

    return entriesTouched, errors