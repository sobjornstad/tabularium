# The Index Model

At the core of Tabularium is a somewhat simplified model of a standard index
(as used in books and other reference works). That it is simplified implies
that the format is not quite as flexible as in an index that one writes by
hand. However, squishing the index into a standard format with definite types
of entries has great advantages as well. Specifically, it makes it easy to
format the index in many different ways and to work with the entries in
automatic ways: combining them, checking for conflicts, searching through only
parts of the index, and so on.

Indexes in Tabularium are made up of *sources*, *volumes*, *entries*, and
*occurrences*; we will provide a brief overview of each of these in turn.

## Sources

The highest-level object in Tabularium is the *source*. A source usually
represents one book or other work, such as your diary, Wikipedia, your Rolodex,
*War and Peace*, or a computer file containing anecdotes.

Sources have a *name*, used when managing sources; an *abbreviation*, used when
displaying lists of locations so that they don’t get horribly long; and a
*type*, which is a predefined vague description of the source, such as “computer
file” or “diary.” To help prevent typos sneaking into your database, for each
source you can also define the valid volume numbers and valid references (more
on references in a moment); if you try to enter a volume or reference number
outside of that range, Tabularium will assume that your entry was incorrect and
display an error. Finally, you can specify a *nearby range*, which describes how
close related entries are likely to be to each other in this source; see the
sections on the Nearby area and editing sources for more information.

## Volumes

Many types of sources naturally have multiple volumes: for example, if you keep
a paper diary, if you keep writing, eventually you will have to start a second
notebook. To simplify organization of these types of sources, Tabularium
supports multi-volume sources. Sources can be flagged as multi-volume by
ticking the appropriate box when editing the source; thereafter, you can edit
the volumes of a source in the Manage Volumes dialog.

Volumes are normally numbered sequentially beginning at 1, but you can use any
scheme that uses positive integers.

Volumes have a *notes* text field associated with them (in the case of
single-volume sources, the source has notes associated with it). Notes can be
accessed through the *Notes* option on the Sources menu, or through a number of
other options and dialogs. Notes can be used for anything you find convenient.

## Entries

An *entry* is the basic building block of an index in Tabularium. Entries
roughly correspond to what are normally called entries and subentries in
traditional indexes: *computer program*, *Doe, Jane*, or *\_Alice in
Wonderland\_, poetry in*, for example.

An entry does not belong to a particular source and can reference places in
many different sources.

Entries are listed in the leftmost column of the main window; when you go to
search your database using the search box, you are searching your entries.

Tabularium’s index model is not hierarchical; that is, it does not discriminate
between entries and subentries. Traditional indexes often indent subentries
under a larger entry, forming groups of related topics. A “flat”, one-level
model greatly simplifies the interface and data handling and in my experience
works fine even with thousands of entries. In this model, commas serve double
duty as both subentry markers and a way to invert parts of the index entry.

In a few cases, Tabularium will split index entries up by commas for purposes
of grouping – for instance, when printing an index, entries that share a
first-level word or phrase with the entry above them will be abbreviated using
an em-dash, like so:

    bowling, cosmic
    — Dodgeville

...where the second entry began as “bowling, Dodgeville”.

In addition to its name, an entry has a *sort key* and a *classification*. The
sort key is usually identical to the name, but sometimes an entry name begins
with an insignificant word like *the* or a character like *"* that the computer
sorts before all letters, in which case the sort key can be used to specify
exactly how the entry should be alphabetized (e.g., *The Bible* should be
sorted like *Bible*, and *“scare quotes”* should be sorted like *scare
quotes*).

The classification is one of *People*, *Places*, *Quotations*, *Titles*,
*Others*, or *Unclassified*. Classifications are useful to limit complicated
searches to a relevant category or to look at or print only that part of your
index.

## Occurrences

Entries are all very nice, but a list of keywords isn’t helpful unless it also
tells you where the referenced information can be found. *Occurrences* tie
together entries, volumes, and sources, bridging the gap between the abstract
labels created by entries and the actual information they refer to. An
occurrence is composed of a reference to a source (and volume, if a
multi-volume source) and a *reference number*. Reference numbers typically
refer to page numbers if these exist for the source being referenced, but they
can also point to sequentially numbered entries, paragraphs, or any other
positive integers that make it easy to find the specified information.

Occurrences, when displayed in the *Occurrences* column of the main window or
elsewhere in Tabularium, normally take one of the following formats:

    ABBREV REFNUM
    ABBREV VOLUME.REFNUM

For example:

    RT 4571
    CB 27.46

When you need to enter occurrences, you normally specify them in *Unified
Occurrence Format* (UOF). UOF is a simple, flexible language that can be used
to list any number of occurrences with a minimum of typing. Simple UOF looks
just like the examples above; a variety of tricks can be used to refer to
multiple occurrences at the same time, add to a source whose abbreviation you
do not remember, and so on. UOF is covered fully later.

Rather than pointing to a specific reference number, an occurrence can be a
*range* of reference numbers (e.g., pages “12-15”) or a *redirect* (sometimes
called a *blind entry* in traditional indexing), which specifies another entry
that the user should look up (e.g., “*see* Other Name For This Thing”).


# The main window

The main window of Tabularium is used for finding entries. Various other
actions like adding and editing new entries can be taken from the menus.

There are six major sections in the main window.

* **Find area**: At the very top of the window, just under the menus, you can enter a search query. You can also specify whether you want to search *incrementally* (i.e., Tabularium will search as you type, rather than waiting for you to press Enter) and whether you want to search using exact matches or *regex* (regular expression) search.
* **Entries area**: The entries area to the left lists all the entries in your database that match the current search. When you select an entry, the Occurrences area fills with the occurrences of the selected entry.
* **Occurrences area**: The occurrences area lists the occurrences of the entry you’ve selected in the Entries area. When you select an occurrence, the Inspect and Nearby areas fill with information about the selected occurrence.
* **Inspect area**: The Inspect area shows information about the selected occurrence.
* **Nearby area**: The Nearby area shows you other entries that reference the same physical location as the current occurrence, or a very close-by one.
* **Limits area**: At the very bottom of the window is the limits area, where you can add additional constraints on what kinds of entries and occurrences appear when you search.

## The Find area

You can press **Ctrl+F** to focus the Find area.

As mentioned above, there are two search modes: substring search and regex
search. When the **Regex** box is not checked, substring search is used, and
when it is checked, regex search is used.

In substring search, any entry that contains the letters you type is displayed,
and the match is case-insensitive. For instance, a search for `ud` would match
the entries *ud*, *mud*, *MUD*, *stuDio*, and *muddy*.

Regex search is a more powerful and more complex mode. Regular expressions give
special meaning to many symbols, allowing you to specify very precise criteria
with just a few characters. Regex searches are case-sensitive. If you are not
familiar with regular expressions, here are a few useful tricks:

* Use square brackets to specify alternative characters: `[qQzZ]` matches all
  entries containing a Q or a Z.
* Use `.` to match any single character: `[kK].te` matches *Kate* and *kite*.
* Use `.*` to match any number of characters: `com.*slow` matches *computer,
  slow*. `.*` is implied at the beginning and end of a search unless you use
  `^` or `$` (see below).
* In fact, you can repeat *anything* an arbitrary number of times with `*`:
  `[Qq]*p*` searches for entries that contain some number of *q*’s and *Q*’s
  (including none at all) followed immediately by any number of *p*’s.
* Use `|` to specify alternatives: `January|February|March` matches any of the
  first three months.
* Use `^` and `$` to match the beginning and end of entry names: `mud$` matches
  *full of mud* and *mud* but not *muddy*.
* Use `\b` to match the beginning or end of a word: `\bcat\b` matches *cat* and
  *cat food* but not *dedicate*.

To search for an *actual* `.` (or any other character that has special meaning
in a regex), prefix it with a backslash (`\`): `Mr\. Jones` matches *Mr. Jones*
but not *Mrs Jones*.

Tabularium specifically uses Python’s dialect of regular expressions, which is
fully documented [here][redocs]. A complete [tutorial][retutorial] easier to
follow than the full documentation is also available.

[redocs]: https://docs.python.org/3/library/re.html?highlight=re#regular-expression-syntax
[retutorial]: https://docs.python.org/3.5/howto/regex.html

The **Incremental** box does not affect what entries match your search, but it
does affect the behavior of searching. If incremental search is on, Tabularium
will search as you type; if it is off, you will need to press Enter or click
the **Go** button to search. This is primarily a personal preference, although
if you have a very large database, incremental search may feel slower.

If you press Enter when no search results are available, or you click the Add
button or press **Alt+A**, Tabularium will prompt you to create a new entry
with the same name as your search.

## The Entries area

The Entries area displays all entries that match the criteria in the Find area
and have their classification checked in the *show entries for* section of the
limits area. However, any entries that have no occurrences to be displayed
because of occurrence limits currently selected (*limit occurrences by* in the
limits area) are not shown.

This limitation could use an example. Suppose we have an entry *Sarah* with two
occurrences, *A 2.4* and *B 1.32*. If we say we want to see only occurrences
from the source *C*, then neither of these occurrences are from that source, so
*Sarah* must be irrelevant to our search and will not be displayed in the
entries column.

Single-clicking on an entry selects it and fills the Occurrences area with the
occurrences of that entry. Double-clicking on an entry or pressing Enter opens
it for editing.

You can press **Alt+E** to focus the Entries area, and the arrow keys to select
a different entry from the list.

## The Occurrences area

The Occurrences area shows all occurrences belonging to the selected entry that
additionally match the criteria in the *Limit occurrences by* section of the
Limits area.

Single-clicking on an occurrence selects it and fills the Inspect and Nearby
areas with appropriate information. Double-clicking on an occurrence or
pressing Enter opens it for editing.

You can press **Alt+O** to focus the Occurrences area, and the arrow keys to
select a different occurrence from the list.

## The Inspect area

The Inspect area shows the full source name, date entered, and date modified of
the currently selected occurrence. If you have a multi-volume source marked as
*diary* and use open and close dates on its volumes, it will also show what
volume was open at the time the occurrence was entered.

## The Nearby area

The Nearby area shows you other entries that reference the same physical
location as the current occurrence, or a very close-by one. For instance, if
the entries `foo` and `bar` both reference `Metasyntactic Variables 2.25`, when
you have `foo` selected in the entries area and the `Metasyntactic Variables
2.25` occurrence selected in the occurrences area, `bar` appears in the Nearby
list (similarly, `foo` would appear in the nearby list for `bar`).

You can double-click on an entry in the Nearby area, or choose **Inspect → Jump
to Nearby Entry**, to search for it. (If you want to go back to where you were
afterwards, you can choose **Go → Back**.)

You can press **Alt+N** to focus the Nearby area, and the arrow keys to select
a different occurrence from the list.

## The Limits area

At the very bottom of the window is the Limits area. The Limits area
supplements the Find area with additional constraints on what entries and
occurrences appear.

There are two sections, the entry limits (*Show entries for* section) and the
occurrence limits (*Limit occurrences by* section). As described in the section
on the Entries area, the occurrence limits can also limit what entries appear
if they cause an entry to have no matching occurrences.

The entry limits let you limit the displayed entries by classification; entries
whose classification is unchecked will not be displayed. You can click the
**All** button to quickly select all of the checkboxes, or the **None** button
to deselect all of them. Having all of the checkboxes checked means all entries
are displayed.

The occurrence limits let you limit the displayed occurrences by the date they
were entered or modified and/or the source and volume they come from. Note that
you must specify a source to be able to specify volume numbers. Having *none*
of the occurrence limit checkboxes checked means that all occurrences are
displayed (note that this is the opposite of the entry limits).


# Adding to and editing your index

Additions and changes to your index are handled through the functions on the
**Entry** and **Occurrence** menus.

All of these functions have keyboard shortcuts, so in combination with the
choices on the **Go** menu to move to different areas, you can edit your index
entirely with the keyboard if you wish. Note that since many of the occurrence
and entry functions have similar names, all functions relating to occurrences
have the **Shift** key in their keyboard shortcuts.

## Adding an entry

To add an entry, choose **Entry → Add...** or press **Ctrl+A**. You will be
prompted for the entry name. The sort key will automatically update to be the
same as the name unless you change it to something different. You can choose a
classification by clicking the appropriate button or by holding down the Alt
key and pressing the underlined letter.

The **Copy** button copies the contents of the **Name** box into the **Sort Key** box. This is useful if you change the sort key manually so that it no longer matches the name and you then want to change it back.

The **Wash** button tries to automatically create a sort key from the name. For
instance, it removes `_`, `"`, and `the` from the beginning. In most cases
where you need to specify a sort key at all, clicking **Wash** (or pressing
**Alt+W**) will be enough. However, you can manually change the sort key if the
wash button doesn’t do what you want.

After clicking Add, you will be asked to specify some occurrences to finish
adding the entry, as an entry must have at least one occurrence.

## Adding occurrences

You can add occurrences to the currently selected entry by choosing
**Occurrence → Add...** or by pressing **Ctrl+Shift+A**. You will also be asked
to add occurrences automatically when you create a new entry.

Occurrences are specified in *Unified Occurrence Format* (UOF) in the
**Value(s)** box. UOF is slightly more difficult to learn than a form asking
for each part of the occurrence would be, but it is a great deal easier to use
when entering a large number of occurrences.

If you are adding a large number of entries or occurrences to the same source
at once, it may be useful to copy the source (and volume, if applicable) part
to the clipboard (e.g., `CB 2.`) so you can paste it every time you add
occurrences.

### UOF

A single occurrence in UOF consists of the *source*, *volume* (if applicable),
and *page* (or index number). Some examples of valid single occurrences:

    CB1.56
    CB 1.56
    CB: 1.56
    CB:1 . 56
    RT 2378 (if RT is single-volume)
    RT 1.2378
    The Invisible Man 58
    The 160th Book: 45

Rules:

* The general format looks like `SOURCE:VOLNUMBER.PAGENUMBER`.
* Spaces before and after the colon and period are optional.
* The colon is optional.
* The volume number and point may be omitted if the source is single-volume.
* SOURCE may be either the source’s abbreviation (usually the most convenient)
  or its full name. (If you happen to have a source with the same name as the
  abbreviation of a different source, the abbreviation takes precedence.)

Multiple occurrences can be entered at once:

    CB: 1.56; 78
    CB 1.56;78
    CB 1.56 | CB 5.78 | CB 12.56
    CB 1.56; 78 | CB 12.56
    RT 2378 | The Invisible Man 56; 78
    The 160th Book: 45 | TB2.162

Rules:

* To enter multiple page numbers within the same source and volume, separate
  them with a semicolon.
* To enter a literal semicolon (say, in the name of an entry you're redirecting
  to), escape it with a backslash: `see first\; second`.
* To enter occurrences for multiple sources and volumes, place a pipe (`|`)
  character between the references. Spaces around the pipe are optional.

You might also want to enter a range or a redirect:

    CB 15.45-56
    CB 15.45--56
    CB 15.45–6
    CB 15. see Other Entry
    RT: see Other Entry
    RT: 25-6; see Other Entry
    RT see Other. Entry.

Rules:

* Ranges are specified with `-`, `--`, or `–` (en-dash). There can be spaces at
  the sides of the dash, but not between the dashes of a double dash. A
  "collapsed" range, where you leave out the first digit(s) in the second half
  because they're identical to the first digit(s) in the first half, is also
  valid.
* Redirects are specified with the keyword *see* followed by a space and the
  name of the entry to redirect to. Note that, unlike traditional indexes,
  redirects belong to a particular source, since keywords that make sense for
  one of your sources might not make sense for another one.


## Entry addition shortcuts

There are two useful shortcuts on the Entry menu, **Add Based On** and **Add
Redirect To**. **Add Based On** works the same way as **Add**, but the name,
sort key, and classification boxes are pre-filled with the values of the
currently selected entry, useful if you want to add several similar entries in
a row. **Add Redirect To** prompts you for the entry values as normal, but
pre-fills the occurrences box with `see <the currently selected entry>` – just
finish by typing the source and/or volume in which to create the redirect and
press Enter.


## Editing entries and occurrences

You can edit an entry or occurrence to correct a typo or restructure your index
with the appropriate **Edit...** function on the **Entry** or **Occurrence**
menu. Occurrences cannot be moved between sources – if the changes are that
significant, you should delete the old occurrence and create a new one.

## Deleting entries and occurrences

Similarly, you can delete the currently selected entry or occurrence with the
**Delete** function. Deleting an entry will delete all of its occurrences, and
deleting the only occurrence of an entry will delete the entry.

## Merging entries

Sometimes you may find you have inadvertently created several entries which
really say the same thing in slightly different ways: maybe one refers to your
friend Joe as `Smith, Joe` and the other as `Smith, Joseph`. In this case, you
can *merge* the two entries, moving the occurrences of one into the other.

Start by selecting the entry you’d like to get rid of. Then choose **Entry →
Merge Into** and type the name of the entry you want to move the occurrences
into. Optionally, you can choose to *Leave a redirect behind*, which will turn
the selected entry into a redirect to the entry you’re merging into. If you
choose not to leave a redirect, the selected entry will be removed altogether
after moving its occurrences.

In other cases, you may find that you have two similar entries and have
distributed the occurrences wrongly between them; maybe you have two friends
named Joe Smith and you were trying to file one of them under `Smith, Joe` and
the other under `Smith, Joseph`, but in a couple of instances you got it wrong.
Here you can use **Occurrence → Move to Entry**, which will move just one
occurrence, leaving the rest of the occurrences in the original entry. (If you
try to use this function on the only occurrence in an entry, the entries will
instead be merged.)

## Jumping to redirects

If you’re looking at an occurrence and it happens to be a redirect to a
different entry, you may logically want to look up that entry. You can do so by
selecting the occurrence and choosing **Occurrence → Jump to Redirect** (or
pressing **Ctrl+Shift+J**). As with jumping to nearby entries, you can choose
**Go → Back** to return to the previous search if you decide it’s not the right
entry or you’re done looking at it.


# Adding and editing sources and volumes

So far we’ve been largely ignoring sources and volumes, but you can’t actually
add any entries until you have at least one source, and, for multi-volume
sources, at least one volume.

## Creating (or editing) sources

Sources are managed from **Sources → Manage Sources** (go figure). When you
choose New or Edit, your options are as follows:

* **Name**: The full name of the source. This is used in the source manager,
  volume manager, source notes browser, and inspect window.
* **Abbreviation**: A short abbreviation for this source. This is used in
  occurrence displays and is the normal way to specify a source when typing UOF.
* **Type**: The type of the source, chosen from *book*, *computer file*,
  *diary*, *notebook type*, or *other*. This is mostly to help you keep track of
  your sources in the source manager, although the *diary* source is special in
  that Tabularium has several features that look up dates in the diary source
  specifically.
* **Multiple volumes**: If checked, this source can have several volumes.
* **Valid volumes** and **Valid references**: To help you avoid typos, only
  volume or page numbers within this range can be used for this source (at least
  until you change the range again).
* **Nearby range**: When looking for nearby entries to display in the Nearby
  area, consider references this far away from the current occurrence (for
  instance, if the current occurrence is page 24, a nearby range of 2 would
  display entries that referenced pages from 22 to 26 inclusive).

## Creating (or editing) volumes

Managing volumes is very similar to managing sources: go to the volume manager
by choosing **Sources → Volumes**, then select the source you’d like to edit the
volumes of in the left pane (note that single-volume sources are not listed here
to avoid confusion).

Volume options:

* **Source**: The source this volume is attached to; this cannot be changed
  through the editor box.
* **Volume number**: The identifying number of this volume.
* **Use open/close dates**: If checked, you can indicate when you started and
  stopped using this particular volume. The dates are shown in the volumes
  dialog for your reference. Additionally, if this is the diary source, the
  Inspect window will use these dates to show which diary volume was open at
  the time an occurrence was entered.

You can also click the **Notes...** button here to open the notes browser,
described next.

## Browsing notes

Volumes (or sources, for single-volume sources) have a *notes* field associated
with them. You can use this to remind yourself where you can find a source, give
a brief summary of what’s in it, or anything else you find useful.

Source and volume notes are accessed through the *notes browser*, which you can
open by choosing **Sources → Browse Notes** or clicking the **Notes...** button
in the volume manager. There are also two useful options on the **Inspect**
menu: **Source notes** will display the notes for the source of the selected
occurrence, while **Diary notes** will display the notes for the diary volume
open at the time the occurrence was entered (you can see which volume this is in
the Inspect area).

You can select a source and volume in the left pane to see the notes in the
right pane.

Notes are automatically saved when you switch to a different volume’s notes or
close the window.

The editor supports simple HTML – when you click **Parse HTML** or close the
dialog and reopen it, HTML tags will be converted into formatted text. Complex
things may result in odd-looking notes fields, but lists, bold, and so on work
fine. If you do manage to screw up the formatting and deleting the problematic
section doesn’t help, you can use the **Clear Formatting** button to remove all
HTML and try again.

You can also press `*` to create an unordered list (bullet points) automatically.


# Tools

## Importing and exporting

You can import from and export to *Mindex format*, which is a tab-separated
text file with three columns, in order: entry names, UOF for occurrences for
those entries, and sort keys (the sort key is optional if the same as the entry
name). The import and export options are on the **File** menu.

## Switching databases

It is usually best to keep your personal index in a single database so that you
can find everything at once, but if several people want to use Tabularium or you
want to switch between two completely separate domains (say, home and work), you
can create several databases and switch between them using **File → New
Database** and **File → Open Database**.

## Printing indexes

If you have [LaTeX](https://en.wikipedia.org/wiki/LaTeX) installed on your
computer and `pdflatex` available in your system path, you can print your
indexes on letter-size paper by choosing **File → Print**. (Because you
unfortunately have to install LaTeX if you don’t already use it to get this to
work, this is something of an advanced feature for now.) There are three
printing options available:

* **Entire index**: Print an index of all the entries and occurrences in your
  database.
* **Visible entries**: Print an index of only the entries visible, but all their
  occurrences (if you have occurrence limits in effect, entries that have no
  matching occurrences will not be included in the index, but entries that have
  some matching occurrences will be included in their entirety, including even
  occurrences that do not match the criteria).
* **Simplification**: Print a list of all your entries, sorting by the
  *occurrence*. This is sort of like creating a summary or simplified version of
  the source, assuming you’ve indexed it thoroughly, hence the name.

## The entry classification tool

If you have a lot of entries that are “Unclassified” and would like to give
them a more descriptive classification, you can use the entry classification
tool at **Tools → Classify Entries**. The tool is mostly self-explanatory, and
instructions are provided at the top of the window.

## The letter distribution tool

If you write some entries out on paper in your sources before transferring them
into Tabularium, the letter distribution tool (**Tools → Show Letter
Distribution**) is quite useful for knowing how much space each initial letter
should be allocated on paper. It searches through the sort keys of all your
entries, finds how often each letter of the alphabet is used as the initial
character of a sort key, and presents you with a table of the results.

## Preferences

Under **Edit → Preferences**, you have a couple of small options:

* You can choose to password-protect your database. Your database is *not*
  encrypted and your content can be viewed by a skilled and determined user with
  a modified version of Tabularium or an SQLite database browser, but Tabularium
  itself will refuse to open your database if you don’t get the password
  correct, so this may be a useful way to keep out casual snoopers. Your
  password is stored hashed, so nobody will be able to recover your password
  from the database even if they access your data.
* You can choose from several date formats; this is purely cosmetic and affects
  only the way dates are displayed in the occurrence limits and Inspect area.
