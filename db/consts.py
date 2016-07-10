# -*- coding: utf-8 -*-
# Copyright (c) 2015 Soren Bjornstad <contact@sorenbjornstad.com>

# user preference...
DATE_FORMAT = '%Y-%m-%d'

refTypes = {'num': 0, 'range': 1, 'redir': 2}

entryTypes = {
    'unclassified': 0,
    'ord': 1,
    'person': 2,
    'place': 3,
    'quote': 4,
    'title': 5
    }

sourceTypes = {
    'other': 0,
    'book': 1,
    'notebooktype': 2,
    'computerfile': 3,
    'diary': 4
    }

sourceTypesFriendly = {
    "Other": 0,
    "Book": 1,
    "Computer file": 3,
    "Diary": 4,
    "Notebook type": 2
    }

sourceTypesFriendlyReversed = dict(
        (v, k) for k, v in sourceTypesFriendly.items())

sourceTypesKeys = (
    "Other", "Book", "Computer file", "Diary", "Notebook type")

noSourceLimitText = '(all sources)'
