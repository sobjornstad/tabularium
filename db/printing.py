# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

import codecs
import os
import re
import subprocess
import sys
import tempfile

from db.consts import refTypes
from db.utils import sortOccs
import db.database as d
import db.entries
import db.occurrences


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
    \\fancyhead[LO,LE]{\\scshape The Complete Records Project Index}
    \\fancyhead[CO,CE]{\\thepage\ / \\pageref{LastPage}}
    \\fancyhead[RO,RE]{\\scshape \\today}
    \\renewcommand{\\indexname}{\\vskip -0.55in}
    \\newcommand{\\theentry}[1]{#1}
    \\usepackage{titlesec}
    \\begin{document}
    \\begin{theindex}\n
"""

INDEX_ENDSTR = """\\end{theindex}\end{document}"""


def printFullIndex():
    formatted = getFormattedEntriesList()
    document = '\n\n'.join([DOC_STARTSTR, '\n'.join(formatted), INDEX_ENDSTR])

    # it would be good to delete the tmpdir we used at some point in the future
    tdir = tempfile.mkdtemp()
    oldcwd = os.getcwd()
    os.chdir(tdir)

    fnamebase = "index"
    tfile = os.path.join(tdir, '.'.join([fnamebase, 'tex']))
    with codecs.open(tfile, 'w', 'utf-8') as f:
        f.write(document)
    r = subprocess.call(['pdflatex', '-interaction=nonstopmode', tfile])
    r = subprocess.call(['pdflatex', '-interaction=nonstopmode', tfile])
    if r:
        #TODO: throw an error for the ui layer
        print "Error executing latex! Please see the error above."
        return
    ofile = os.path.join(tdir, '.'.join([fnamebase, 'pdf']))
    if sys.platform.startswith('linux'):
        subprocess.call(["xdg-open", ofile])
    elif sys.platform == "darwin":
        os.system("open %s" % ofile)
    elif sys.platform == "win32":
        os.startfile(ofile)
    else:
        print("Unable to automatically open the output. Please" \
                "browse manually to %s." % ofile)
    os.chdir(oldcwd)


def getFormattedEntriesList():
    entries = db.entries.allEntries()
    entries.sort(key=lambda i: i.getSortKey().lower())

    formatted = []
    prevEname = [None]
    for entry in entries:
        eName = entry.getName()
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

        occs = entry.getOccurrences()
        occs = sortOccs(occs)
        occList = []
        for occ in occs:
            vol = occ.getVolume()
            sourceAbbrev = '\\textsc{%s}' % mungeLatex(
                    vol.getSource().getAbbrev().lower())
            volNum = vol.getNum()
            ref = mungeLatex(occ.getRef()[0])
            if occ.getRef()[1] == refTypes['num']:
                occList.append("%s~%s.%s" % (sourceAbbrev, volNum, ref))
            elif occ.getRef()[1] == refTypes['range']:
                occList.append("%s~%s.%s" % (sourceAbbrev, volNum,
                                             ref.replace('-', '--')))
            else:
                occList.append("%s~%s: \emph{see} %s" % (
                               sourceAbbrev, volNum, ref))

        entryStr = ''.join([ENTRY_STARTSTR, mungeLatex(newEname), ENTRY_ENDSTR,
                            ', '.join(occList), '\n'])
        formatted.append(entryStr)
    return formatted


def mungeLatex(s):
    # This escapes all special chars listed as catcodes in /The TeXbook/, p.37.
    # Note that spacing is not guaranteed correct with things like the tilde
    # and caret. However, those are not very likely to come up; we just don't
    # want the whole thing to crash if it does. //
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
    s = re.sub('"(.*?)"', "``\\1''", s)

    # Attempt italicization, convert to underscore if any left
    s = re.sub("_(.*)_(.*)", "\\emph{\\1}\\2", s)
    s = s.replace('_', '\\textunderscore ')

    # reformat 'see' entries with smallcaps and colons
    redir = 'see'
    if ''.join(['.', redir]) in s:
        s = re.sub(".%s (.*)" % redir, ": %s{\\\\scshape\ \\1}" % redir, s)
        repl = re.findall(": %s.*" % redir, s)
        repl = repl[0]
        repl.replace(": %s", "")
        s = s.replace(repl, repl.lower())
    return s
