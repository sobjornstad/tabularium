# The Index Model

At the core of Tabularium is a somewhat simplified model of a standard index
(as used in books and other reference works). That it is simplified implies
that the format is not quite as flexible as in an index that one writes by
hand. However, squishing the index into a standard format with definite types
of entries has great advantages as well: it makes it easy to format the index
in many different ways and to work with the entries in automatic ways:
combining them, checking for conflicts, searching through only parts of the
index, and so on.

Indexes in Tabularium are made up of *sources*, *volumes*, *entries*, and
*occurrences*; we will provide a brief overview of each of these in turn.

## Sources

The highest-level object in Tabularium is the *source*. A source usually
represents one book or other work: your journal, Wikipedia, your Rolodex, *War
and Peace*, and a computer file containing anecdotes you’ve collected could all
be sources. A source can have multiple volumes, if appropriate for that source.

Sources have a *name*, used when managing sources; an *abbreviation*, used in
actual entries so that they don’t get horribly long; and a *type*, which is a
predefined vague description of the source, such as “computer file” or “diary.”
To help prevent typos sneaking into your database, for each source you can also
define the valid volume numbers and valid references (more on references in a
moment); if you try to enter a volume or reference number outside of that
range, Tabularium will assume that your entry was incorrect and display an
error. Finally, you can specify a *nearby range*, which tells Tabularium how
widely to look for other nearby entries when inspecting an occurrence.

## Volumes

Many types of sources naturally have multiple volumes: if you keep a paper
journal, for instance, assuming that you keep writing, eventually you will have
to start a second notebook. To simplify organization of these types of sources,
Tabularium supports multi-volume sources. Sources can be flagged as
multi-volume by ticking the appropriate box when editing the source;
thereafter, you can edit the volumes of a source in the Manage Volumes dialog.

Volumes are normally numbered sequentially beginning at 1, but you can use any
scheme that involves only natural numbers.

Volumes have a *notes* text field associated with them (in the case of
single-volume sources, the source has notes associated with it). Notes can be
accessed through the *Notes* option on the Sources menu, or through a number of
other options and dialogs. Notes can be used for anything you find convenient.

## Entries

An *entry* is the basic building block of an index in Tabularium. Entries
roughly correspond to what are normally called entries and subentries in
traditional indexes. In Tabularium, an “entry” is specifically the text
connected with some reference: “computer program”, “Doe, Jane”, or “\_Alice in
Wonderland\_, poetry in”, for example.

An entry does not belong to a particular source and can catalog occurrences
across many different sources.

Entries are listed in the leftmost column of the main window; when you go to
search your database using the search box, you are normally searching your
entries.

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


## Occurrences

Entries are all very nice, but an index isn’t helpful unless it also tells you
where the referenced information can be found. *Occurrences* bridge the gap
between the abstract labels created by entries and the actual source locations.
An occurrence is composed of a reference to a source (and volume, if a
multi-volume source) and a *reference number*. Reference numbers typically
refer to page numbers if these exist for the source being referenced, but they
can also point to sequentially numbered entries, paragraphs, or any other
positive integers that make it easy to find the requested information.

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
do not remember, and so on. UOF will be covered fully later.

Rather than pointing to a specific reference number, an occurrence can be a
*range* of reference numbers (e.g., pages “12-15”) or a *redirect*, which
specifies another entry that the user should look up (e.g., “*see* Other Name
For This Thing”).
