import argparse
import sys

import db.database
import db.entries
import db.occurrences

TEXTWRAP_COL = 72
TEXT_INDENT = ' ' * 4
DATABASE_PATH = '/home/soren/current/tabularium/records.tdb'

def find(args):
    """
    Search the database and print results on the terminal.
    """
    if args.regex:
        entries = db.entries.find(args.search[0], regex=True)
    else:
        entries = db.entries.find(db.entries.percentageWrap(args.search[0]))
    print("%i matches:" % len(entries))
    # Infuriatingly, textwrap can't properly handle non-breaking spaces,
    # although a Google search suggests this was supposedly fixed in 2014
    # (http://bugs.python.org/issue20491).
    # Therefore, we wrap occurrences ourselves.
    for e in entries:
        occs = db.occurrences.fetchForEntry(e)
        occStrs = []
        for o in occs:
            if occStrs:
                occStrs[-1] += ', '
            # handle a *really* long occurrence by breaking before it and just
            # letting it run over
            if len(str(o)) > TEXTWRAP_COL:
                occStrs.append(TEXT_INDENT + str(o))
                continue
            if (not occStrs
                    or len(occStrs[-1] + ', ') + len(str(o)) > TEXTWRAP_COL):
                occStrs.append(TEXT_INDENT + str(o))
            else:
                occStrs[-1] += str(o)
        print(str(e) + '\n' +  '\n'.join(occStrs))

    # indicate whether a match was found with exit status
    sys.exit(0 if len(entries) else 1)

def frobnicate(args):
    print("We are frobnicating!")
    print(args)

def parseArgs():
    parser = argparse.ArgumentParser(prog="MYPROGRAM")
    subparsers = parser.add_subparsers(help="sub-command help")

    # find
    parserFind = subparsers.add_parser('find', help="Finds things")
    parserFind.add_argument(
        'search', type=str, nargs=1,
        help="The string you want to search for, same as in Tabularium")
    parserFind.add_argument(
        '-r', '--regex', action='store_true',
        help="Search using Python regexes rather than substring match.")
    parserFind.set_defaults(func=find)

    # frobnicate
    parserFrobnicate = subparsers.add_parser('frobnicate', help="Frobnicate something")
    parserFrobnicate.add_argument(
        'text', type=str, nargs=1,
        help="The string you want to frobnicate onto stdout.")
    parserFrobnicate.set_defaults(func=frobnicate)

    ### now parse ###
    args = parser.parse_args()
    args.func(args)

def initDb():
    db.database.connect(DATABASE_PATH)

def start():
    initDb()
    parseArgs()
