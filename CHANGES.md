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

