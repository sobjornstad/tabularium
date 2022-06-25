"""
Schema upgrades.
"""

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
def upgrade_0_1(connection: DatabaseConnection,
                statusCallback: UpgradeStatusCallback) -> None:
    print("Upgrading database from schema version 0 to 1")

@databaseDowngrade(1, 0)
def downgrade_1_0(connection: DatabaseConnection,
                  statusCallback: UpgradeStatusCallback) -> None:
    print("Downgrading database from schema version 1 to 0")
    