# Copyright (c) 2015-2022 Soren Bjornstad <contact@sorenbjornstad.com>

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
