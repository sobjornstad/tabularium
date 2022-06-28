Changes in 0.3.1
================

This release fixes a few bugs introduced in 0.3.0:

* Fix application crash when pressing Enter quickly
  after typing a long entry name in the add box.
  (Qt gets very unhappy if you allow a running thread to be garbage collected.)
* Remove accidentally left-in debug console prints.
* Fix inconsistent wording of the "looks good" message in the entry add dialog.
* Fix entry name box indicating a duplicate when using "add based on".
* Fix sort key being incorrectly set to manual mode when the text and sort key
  were identical while adding or editing an entry in certain ways.
* Fix wrong application version number.

And two small new niceties:

* When searching in full-text mode, commas are ignored in the top bar.
  This makes the workflow of
  "look for an existing entry or add it if it doesn't exist"
  much easier if the entry to be potentially added contains commas.
* The arrow keys can now be used to move among the search box,
  entries list, and occurrences list (in the direction they appear on the screen).
  Up/down arrows in the lists will select different items if possible,
  and select the search box if you reach the top of the list.


Changes in 0.3.0
================

I spent a 24-hour period hacking on things that annoyed me,
and this is the result.

New features
------------

* Tabularium now uses SQLite's full-text search engine
  rather than a simple substring search over the entire database.
  Incremental searches with regex mode off should be noticeably faster now.
  However, the search syntax has changed.
  Important notes:
  - Matching is **whole-word** and case-insensitive,
    so `cat` will find "Cat" and "cat" but not "dedicate".
    (If you need to find an arbitrary part of a word,
     you can still use regex mode for that.)
  - The order of search terms does not matter.
  - To force multiple words to appear together,
    or include punctuation (including commas),
    put your search in `"quotes, double"`.
  - To find words beginning with a string, use `*`:
    `cat*` finds "cat" and "caterwaul".
    (For performance reasons, `*cat` doesn't work as you might expect.
     If you need to find words or entries *ending* in `cat`, do a regex search.)
  - To force a search term to come at the beginning of an entry's name, use `^`:
    `^cat` finds the entries "cat" and "cat food" but not "animals, cat".
  - Use AND, OR, and NOT between search terms for boolean logic.
* When the syntax of your search is invalid in either full-text or regex mode),
  the search box will turn red and a note will appear in the status bar.
  (I wish I could show more details about the problem, but SQLite unfortunately
   does not provide them.)
* When creating or editing entries,
  Tabularium will now search for duplicates
  and entries with similar names that you might be misspelling
  as you type. You will need to run `make` in the Tabularium directory once
  to install some SQLite extensions to get the fuzzy matching.
* When adding occurrences, errors in your UOF are identified as you type.
* If editing an entry and trying to change its name
  to that of an entry that already exists,
  Tabularium will now offer to merge the entries for you.
* When you rename an entry,
  any redirects to it are now automatically renamed to avoid broken links.
* Existing broken redirects can be easily found and corrected using the new
  Broken Redirects Tool (found on the Tools menu).
* You can now double-click on sources and volumes to edit them
  in the source and volume managers.
* Tabularium now shows a note in the status bar when there are entry or occurrence limits active
  so you don't forget.

Bugs fixed
----------

* Don't allow choosing "multiple volumes" checkbox without actually allowing multiple volumes to be selected.
* Fix sort key reverting to the automatic sort key anytime you edited an entry.

Internal
--------

* Implemented entry and occurrence caching, lazy-loading, indexes, and more carefully tuned SQL queries
  for improved performance on large databases.
* Somewhat reduced (but did not resolve) thrashing in the main window
  when searches are repeatedly retriggered on changing filters.
* Tabularium databases will now be upgraded automatically as the schema changes,
  and can be manually downgraded through Python if need be.
* Various under-the-hood refactoring and cleanup tasks.


Changes in 0.2.0
================

This release combines small improvements I’ve made over the past two years of
using Tabularium.


New features
------------

- Add an option to copy the text of the currently selected entry to the
  clipboard.
- Add options to “extend” or “retract” occurrences that are off by
  one page, a fairly common mistake when indexing.
- Add a names-to-faces dialog you can use to keep track of people in your
  database.

Behavior changes
----------------

- Strip leading and trailing space from search text.
- “Export Mindex File” now exports only the visible entries.
- Auto-fill the last-used source and volume when creating a redirect,
  just like for other types of entries.
- Improve error handling when there are UOF parsing errors.
- Improve searching performance.
- Use alternating row colors for many views.
- Improve splitter handle widths.

