"""
Schema upgrades (and downgrades).
"""

#pylint: disable=missing-function-docstring

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Tuple

if TYPE_CHECKING:
    from .database import DatabaseConnection, Upgrader, UpgradeStatusCallback


UPGRADES: Dict[Tuple[int, int], Upgrader] = {}
DOWNGRADES: Dict[Tuple[int, int], Upgrader] = {}

def databaseUpgrade(from_: int, to: int):
    """
    Mark a function as capable of upgrading the database between schema version
    /from_/ and /to/.
    """
    def decorator(func: Upgrader):
        UPGRADES[(from_, to)] = func
        return func
    return decorator

def databaseDowngrade(from_: int, to: int):
    """
    Mark a function as capable of downgrading the database between schema version
    /from_/ and /to/.
    """
    def decorator(func: Upgrader):
        DOWNGRADES[(from_, to)] = func
        return func
    return decorator


@databaseUpgrade(0, 1)
def upgrade_0_1(d: DatabaseConnection,
                _statusCallback: UpgradeStatusCallback) -> None:
    x = d.cursor.execute
    x('''CREATE INDEX IF NOT EXISTS
         occurrences_by_entry ON occurrences(eid)''')
    x('''CREATE INDEX IF NOT EXISTS
         nearby_occurrences ON occurrences(vid, type)''')

    # TODO: I think we can join on the rowid instead of duplicating the eid column
    x('''CREATE VIRTUAL TABLE entry_fts
         USING fts5(
            name,
            eid UNINDEXED,
            content="entries",
            content_rowid="eid"
        )''')
    x('''CREATE TRIGGER entry_fts_ai AFTER INSERT ON entries
         BEGIN
             INSERT INTO entry_fts (rowid, name, eid)
             VALUES (new.eid, new.name, new.eid);
         END''')
    x('''CREATE TRIGGER entry_fts_ad AFTER DELETE ON entries
         BEGIN
             INSERT INTO entry_fts (entry_fts, rowid, name, eid)
             VALUES ('delete', old.id, old.name, old.eid);
         END''')
    x('''CREATE TRIGGER entry_fts_au AFTER UPDATE ON entries
         BEGIN
             INSERT INTO entry_fts (entry_fts, rowid, name, eid)
             VALUES('delete', old.id, old.name, old.eid);
             INSERT INTO entry_fts (rowid, name, eid)
             VALUES (new.eid, new.name, new.eid);
         END''')
    # Populate entry_fts indexes for all existing entries.
    # NB: Must include 'rowid' in the insert or the db is silently corrupted!
    x('''INSERT INTO entry_fts (rowid, name, eid)
         SELECT eid, name, eid FROM entries''')

    d.connection.commit()

@databaseDowngrade(1, 0)
def downgrade_1_0(d: DatabaseConnection,
                  _statusCallback: UpgradeStatusCallback) -> None:
    x = d.cursor.execute
    x('''DROP INDEX IF EXISTS occurrences_by_entry''')
    x('''DROP INDEX IF EXISTS nearby_occurrences''')

    x('''DROP TABLE IF EXISTS entry_fts''')
    x('''DROP TRIGGER IF EXISTS entry_fts_ai''')
    x('''DROP TRIGGER IF EXISTS entry_fts_au''')
    x('''DROP TRIGGER IF EXISTS entry_fts_ad''')
    d.connection.commit()
    