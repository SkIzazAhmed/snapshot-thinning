"""Ratio-based snapshot thinning ("Fibonacci-like" / logarithmic retention).

Proof of concept for https://github.com/openSUSE/snapper/issues/962.
Independent of snapper: the only input is a list of creation times.

Rule
----
Sort snapshots newest first. Walk from newest to oldest. A snapshot is
redundant, and gets deleted, when its older neighbour is at most RATIO times
as old as its newer (kept) neighbour:

    age(older) <= RATIO * age(newer)

The newest and the oldest snapshot are never deleted.

The rule never looks at absolute ages and never requires a snapshot to exist
at a particular age. It only ever removes snapshots, so it cannot be broken by
snapshots that are "missing" because the machine was switched off.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

PHI = (1 + 5 ** 0.5) / 2  # golden ratio, the growth rate of the Fibonacci sequence


def thin(
    times: Iterable[float],
    now: float,
    ratio: float = PHI,
    min_age: float = 0,
    keep_newest: int = 0,
) -> Tuple[List[float], List[float]]:
    """Decide which snapshots to keep.

    times   -- creation times of the existing snapshots (any order, any unit)
    now     -- current time, same unit; must be >= every creation time
    ratio   -- maximum allowed age ratio across a deleted snapshot (> 1)
    min_age -- snapshots younger than this are never deleted
               (same meaning as snapper's TIMELINE_MIN_AGE)
    keep_newest -- the N newest snapshots are never deleted, whatever their
               age (softens the mass deletion after a long downtime)

    Returns (keep, delete), both sorted newest first.
    """
    if ratio <= 1:
        raise ValueError("ratio must be > 1")

    snaps = sorted(set(times), reverse=True)
    if snaps and snaps[0] > now:
        raise ValueError("snapshot from the future")

    if len(snaps) <= 2:
        return snaps, []

    keep = [snaps[0]]
    delete = []

    for i in range(1, len(snaps) - 1):
        age = now - snaps[i]
        newer_age = now - keep[-1]
        older_age = now - snaps[i + 1]

        if i >= keep_newest and age >= min_age and older_age <= ratio * newer_age:
            delete.append(snaps[i])
        else:
            keep.append(snaps[i])

    keep.append(snaps[-1])
    return keep, delete
