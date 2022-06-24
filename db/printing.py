"""
printing.py - functions for printing indexes and simplifications from the DB
"""
# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>.

import codecs
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Dict, List, Optional

import db.entries
import db.occurrences

class PrintingError(Exception):
    """
    Indicates that a print could not be completed for some reason. The error
    message /msg/ will be returned to the caller, where it is intended to be
    printed directly as an error message to the user.
    """
    def __init__(self, msg):
        super().__init__()
        self.msg = msg
    def __str__(self):
        return self.msg


##### LATEX FULL INDEX OUTPUT #####
ENTRY_STARTSTR = r"\item \theentry{"
ENTRY_ENDSTR = r"}, "

DOC_STARTSTR = """\\documentclass{article}
    \\usepackage[top=0.9in, bottom=0.8in, left=0.5in, right=0.5in, headsep=0in, landscape]{geometry}
    \\usepackage[utf8x]{inputenc}
    \\usepackage[T1]{fontenc}
    \\usepackage{multicol}
    \\usepackage[columns=5, indentunit=0.75em, columnsep=0.5em, font=footnotesize, justific=raggedright, rule=0.5pt]{idxlayout}
    \\usepackage[sc,osf]{mathpazo}
    \\usepackage{lastpage}
    \\usepackage{fancyhdr}
    \\fancyhf{}
    \\pagestyle{fancy}
    \\renewcommand{\\headrulewidth}{0.5pt}
    \\fancyhead[LO,LE]{\\scshape Tabularium -- %s}
    \\fancyhead[CO,CE]{\\thepage\\ / \\pageref{LastPage}}
    \\fancyhead[RO,RE]{\\scshape \\today}
    \\renewcommand{\\indexname}{\\vskip -0.55in}
    \\newcommand{\\theentry}[1]{#1}
    \\usepackage{titlesec}
    \\begin{document}
    \\begin{theindex}\n
"""

INDEX_ENDSTR = """\\end{theindex}\\end{document}"""

PrintingProgressCallback = Optional[Callable[[str], None]]


def printEntriesAsIndex(entries: List[db.entries.Entry] = None,
                        callback: PrintingProgressCallback = None) -> None:
    """
    Given a list of Entries, print it as an index, write it to LaTeX, and open
    in the system PDF viewer. If entries is None (default), use all entries in
    the db.

    As we get the formatted entries list (the slow part), periodically call
    callback function (if supplied) with a progress message.

    No return.
    """
    if entries is None:
        entries = db.entries.allEntries()
        indexTitle = "Complete Index"
    else:
        indexTitle = "Selected Index Entries"

    formatted = getFormattedEntriesList(entries, callback)
    document = '\n\n'.join([DOC_STARTSTR % indexTitle,
                            '\n'.join(formatted), INDEX_ENDSTR])

    if callback:
        callback("Compiling PDF...")
    compileLatex(document)


# pylint: disable=too-many-locals
# pylint: disable=consider-using-f-string
def getFormattedEntriesList(entries: List[db.entries.Entry],
                            callback: PrintingProgressCallback = None):
    """
    Retrieve a list of strings of LaTeX code representing the /entries/,
    calling /callback/ periodically with a progress message.
    """
    entries.sort(key=lambda i: i.sortKey.lower())

    formatted = []
    prevEname = [None]
    lastPercent = 0
    for step, entry in enumerate(entries):
        # update caller on progress, every 50 entries so we don't waste time
        if callback and step % 50:
            percent = step * 100 // len(entries)
            if percent > lastPercent:
                callback(f"Generating PDF ({percent}%)...")
                lastPercent = percent

        # process entry
        eName = entry.name
        eNameList = eName.split(',')
        # update prevEname list, while keeping our own copy
        prevEnameInLoop = prevEname[:]
        prevEname = eNameList[:]

        if (len(prevEnameInLoop) > 1 and len(eNameList) > 1 and
                eNameList[0] == prevEnameInLoop[0] and
                eNameList[1] == prevEnameInLoop[1]):
            eNameList.pop(1)
            eNameList[0] = '------' + eNameList.pop(1)
        elif eNameList[0] == prevEnameInLoop[0]:
            try:
                eNameList[0] = '---' + eNameList.pop(1)
            except IndexError: # due to differing sort keys, the baseline
                pass           # entry is after the first one
        newEname = ','.join(eNameList)

        occs = db.occurrences.fetchForEntry(entry)
        occs.sort()
        occList = []
        for occ in occs:
            vol = occ.volume
            sourceAbbrev = '\\textsc{%s}' % mungeLatex(
                vol.source.abbrev.lower())
            volNum = vol.num
            ref = mungeLatex(occ.ref)
            if occ.isRefType(db.occurrences.ReferenceType.NUM):
                occList.append("%s~%s.%s" % (sourceAbbrev, volNum, ref))
            elif occ.isRefType(db.occurrences.ReferenceType.RANGE):
                occList.append("%s~%s.%s" % (sourceAbbrev, volNum,
                                             ref.replace('-', '--')))
            else: # redirect
                occList.append("%s~%s: \\emph{see} %s" % (
                    sourceAbbrev, volNum, ref))

        entryStr = ''.join([ENTRY_STARTSTR, mungeLatex(newEname), ENTRY_ENDSTR,
                            ', '.join(occList), '\n'])
        formatted.append(entryStr)
    return formatted


##### LATEX SIMPLIFICATION OUTPUT #####
SIMPLIFICATION_HEADER = r"""
\documentclass{article}
\usepackage[top=0.9in, bottom=0.8in, left=0.5in, right=0.5in, headsep=0in, landscape]{geometry}
\usepackage[utf8x]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{multicol}
\usepackage[columns=5, indentunit=0.75em, columnsep=0.5em, font=footnotesize, justific=raggedright, rule=0.5pt]{idxlayout}
\usepackage[sc,osf]{mathpazo}
\usepackage{lastpage}
\usepackage{fancyhdr}
%\usepackage{microtype}
\fancyhf{}
\pagestyle{fancy}
\renewcommand{\headrulewidth}{0.5pt}
\fancyhead[LO,LE]{\scshape Tabularium -- Complete Simplification}
\fancyhead[CO,CE]{\thepage\ / \pageref{LastPage}}
\fancyhead[RO,RE]{\scshape \today}
\renewcommand{\indexname}{\vskip -0.55in}
%\newcommand{\theentry}[1]{#1}
\usepackage{titlesec}

\newcommand{\theoccset}[2]{\textsc{#1}\thinspace #2:\par}
\newcommand{\theoccurrences}[1]{{\leftskip 1.5em #1\par}}

\begin{document}
\begin{theindex}
"""

SIMPLIFICATION_FOOTER = r"""
\end{theindex}
\end{document}
"""

def makeSimplification(callback: PrintingProgressCallback = None):
    """
    Create a "simplification", essentially a reverse index, of all occurrences
    in the database. (In the future we'll make it possible to choose subsets of
    that, just like in the index.)
    """
    def modifiedRangeKey(occ: db.occurrences.Occurrence):
        """
        Return a string representation of provided occurrence that uses only
        its start page if it is a range; if it is a number or redir, return the
        original string repr. This allows ranges to be collated under the place
        they start along with non-range entries.
        """
        if occ.isRefType(db.occurrences.ReferenceType.RANGE):
            # pylint: disable=unused-variable
            start, end = db.occurrences.parseRange(occ.ref)
            key = str(occ).replace(occ.ref, str(start))
            return key
        else:
            return str(occ)

    if callback:
        callback("Fetching occurrences...")
    allOccs = db.occurrences.allOccurrences()

    # Collate all occurrences into a dictionary of lists where the key is the
    # string representation of the occurrence and the value is a list of the
    # actual occurrences that go with it.
    if callback:
        callback("Collating occurrences...")
    occDictionary: Dict[str, List[db.occurrences.Occurrence]] = {}
    for occ in allOccs:
        occDictionary[modifiedRangeKey(occ)] = \
                occDictionary.get(modifiedRangeKey(occ), []) + [occ]

    # Now form a sorted list using the first occurrence of each string repr.
    # We can then pull the appropriate list by getting the str repr of the
    # elements of this list.
    # NOTE: This does have the possibility of pulling a range, which would
    # sort differently--before the unranged refnums with the same start value.
    # However, in all cases the unranged and ranged values with the same start
    # value will be grouped under the same key, so this makes no difference.
    sortList = sorted([i[0] for i in occDictionary.values()])

    if callback:
        callback("Formatting output...")
    latexAccumulator = []
    for occGroup in sortList:
        if occGroup.isRefType(db.occurrences.ReferenceType.REDIRECT):
            continue # ignore redirects as unhelpful in this view

        key = modifiedRangeKey(occGroup)
        occStrs = []
        for occ in occDictionary[key]:
            txt = '\\item ' + mungeLatex(occ.entry.name)
            if occ.isRefType(db.occurrences.ReferenceType.RANGE):
                txt += ' (--%s)' % db.occurrences.parseRange(occ.ref)[1]
            occStrs.append(txt)

        book = occGroup.volume.source.abbrev
        # get the __str__ repr, but without the book part
        ref = ''.join(key.split(book)[1:]).strip()
        latexStr = "\\theoccset{%s}{%s}\n\\theoccurrences{%s}" % (
            book.lower(), ref, '\n'.join(occStrs))
        latexAccumulator.append(latexStr)

    body = '\n\n'.join(latexAccumulator)
    document = SIMPLIFICATION_HEADER + body + SIMPLIFICATION_FOOTER
    if callback:
        callback("Compiling PDF...")
    compileLatex(document)


##### COMMON #####
def mungeLatex(s: str):
    """
    This escapes all special chars listed as catcodes in /The TeXbook/, p.37.
    Note that spacing is not guaranteed correct with things like the tilde
    and caret. However, those are not very likely to come up; we just don't
    want the whole thing to crash if it does.

    It also converts straight quotes to curly quotes and _text underlines_ to
    italics.
    """
    # We leave out _ because we need to handle italics in a moment.
    s = s.replace('\\', '\\textbackslash ')
    s = s.replace('{', '\\{')
    s = s.replace('}', '\\}')
    s = s.replace('$', '\\$')
    s = s.replace('&', '\\&')
    s = s.replace('#', '\\#')
    s = s.replace('^', '\\textasciicircum ')
    s = s.replace('~', '\\textasciitilde ')
    s = s.replace('%', '\\%')

    # Take care of straight quotation marks (single & double). Note that it's
    # not possible to handle single quotation marks correctly, as there's no
    # way to tell if it's an apostrophe or opening single quote. If you want it
    # right with singles, you need to use curlies in the entry.
    s = re.sub(r'"(.*?)"', r"``\1''", s)

    # Attempt italicization, convert to underscore if any left
    s = re.sub(r"_(.*)_(.*)", r"\\emph{\1}\2", s)
    s = s.replace('_', '\\textunderscore ')

    return s

def compileLatex(document: str):
    """
    Given a complete string of LaTeX source /document/, write it, call LaTeX on it,
    and open the system PDF viewer on the results.
    """
    tdir = tempfile.mkdtemp()
    oldcwd = os.getcwd()
    os.chdir(tdir)

    try:
        fnamebase = "index"
        tfile = os.path.join(tdir, '.'.join([fnamebase, 'tex']))
        with codecs.open(tfile, 'w', 'utf-8') as f:
            f.write(document)
        with open(os.devnull, 'w', encoding='utf-8') as fnull:
            for _ in range(2):
                r = subprocess.call(['pdflatex', '-interaction=nonstopmode', tfile],
                                    stdout=fnull, stderr=fnull)
        if r:
            raise PrintingError("Error executing LaTeX!")
        ofile = os.path.join(tdir, '.'.join([fnamebase, 'pdf']))
        if sys.platform.startswith('linux'):
            subprocess.call(["xdg-open", ofile])
        elif sys.platform == "darwin":
            os.system(f"open {ofile}")
        elif sys.platform == "win32":
            os.startfile(ofile)
        else:
            raise PrintingError(
                f"Unable to automatically open the output. Please direct your "
                f"PDF viewer to {ofile}.")
    finally:
        os.chdir(oldcwd)
        shutil.rmtree(tdir)
