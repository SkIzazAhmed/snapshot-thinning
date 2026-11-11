"""Testsuite for the ratio-based thinning rule. Run with: pytest -q"""

import math

import pytest
from hypothesis import given, settings, strategies as st

from thinning import PHI, thin

HOUR, DAY, WEEK, YEAR = 1, 24, 24 * 7, 24 * 365

times_st = st.lists(st.integers(0, 50_000), min_size=0, max_size=300, unique=True)
ratio_st = st.floats(1.1, 4.0)


def ages(snaps, now):
    return [now - s for s in snaps]


def simulate(hours, cleanup_every=1, off=frozenset(), **kw):
    """Hourly snapshots while the machine is on; cleanup every N hours.
    Returns (kept, created, largest number deleted by a single cleanup)."""
    snaps, created, worst = [], [], 0
    for now in range(hours):
        if now in off:
            continue
        snaps.append(now)
        created.append(now)
        if now % cleanup_every == 0 or now == hours - 1:
            snaps, deleted = thin(snaps, now, **kw)
            worst = max(worst, len(deleted))
    return snaps, created, worst


# --- basic safety -----------------------------------------------------------

@given(times_st, ratio_st)
def test_only_deletes_existing_snapshots(times, ratio):
    now = max(times, default=0)
    keep, delete = thin(times, now, ratio)
    assert set(keep) | set(delete) == set(times)
    assert not set(keep) & set(delete)
    assert keep == sorted(keep, reverse=True)


@given(times_st, ratio_st)
def test_newest_and_oldest_are_never_deleted(times, ratio):
    now = max(times, default=0)
    keep, _ = thin(times, now, ratio)
    if times:
        assert max(times) in keep and min(times) in keep


@given(times_st, ratio_st, st.integers(0, 1000))
def test_idempotent(times, ratio, later):
    """A second cleanup at the same moment deletes nothing more."""
    now = max(times, default=0) + later
    keep, _ = thin(times, now, ratio)
    assert thin(keep, now, ratio) == (keep, [])


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        thin([1, 2, 3], now=3, ratio=1.0)
    with pytest.raises(ValueError):
        thin([1, 2, 30], now=3)


# --- shape of the result ----------------------------------------------------

@given(times_st, ratio_st, st.integers(0, 1000))
def test_no_redundant_snapshot_left(times, ratio, later):
    """After cleanup every interior snapshot is needed: removing it would
    open a gap wider than `ratio`."""
    now = max(times, default=0) + later
    keep, _ = thin(times, now, ratio)
    a = ages(keep, now)
    for i in range(1, len(a) - 1):
        assert a[i + 1] > ratio * a[i - 1]


@given(times_st, ratio_st, st.integers(0, 1000))
def test_gap_never_wider_than_ratio(times, ratio, later):
    """Two neighbours after cleanup are either neighbours in the input
    (nothing was deleted between them) or at most `ratio` apart in age."""
    now = max(times, default=0) + later
    keep, _ = thin(times, now, ratio)
    order = sorted(times, reverse=True)
    for newer, older in zip(keep, keep[1:]):
        untouched = order.index(older) == order.index(newer) + 1
        assert untouched or now - older <= ratio * (now - newer)


@given(times_st, ratio_st, st.integers(0, 1000))
def test_count_is_logarithmic(times, ratio, later):
    """At most 2*log_ratio(oldest age / youngest non-zero age) + 4 survive."""
    now = max(times, default=0) + later
    keep, _ = thin(times, now, ratio)
    a = sorted(x for x in ages(keep, now) if x > 0)
    if len(a) >= 2:
        assert len(keep) <= 2 * math.log(a[-1] / a[0]) / math.log(ratio) + 4


@pytest.mark.parametrize("years,expected_max", [(1, 40), (10, 50)])
def test_count_after_years_of_hourly_snapshots(years, expected_max):
    keep, created, _ = simulate(YEAR * years)
    assert len(created) == YEAR * years
    assert math.log2(YEAR * years) <= len(keep) <= expected_max


# --- behaviour over time ----------------------------------------------------

@settings(max_examples=60, deadline=None)
@given(
    st.lists(st.integers(1, 400), min_size=1, max_size=120),   # gaps between snapshots
    st.lists(st.booleans(), min_size=120, max_size=120),       # run cleanup after this one?
    ratio_st,
)
def test_gap_bound_holds_over_whole_history(gaps, cleanup_flags, ratio):
    """Arbitrary creation times (so arbitrary downtime) and an arbitrary
    cleanup schedule: neighbours that are left are either at most `ratio`
    apart, or no snapshot was ever created between them."""
    now, snaps, created = 0, [], []
    for gap, do_cleanup in zip(gaps, cleanup_flags):
        now += gap
        snaps.append(now)
        created.append(now)
        if do_cleanup:
            snaps, _ = thin(snaps, now, ratio)
    snaps, _ = thin(snaps, now, ratio)

    for newer, older in zip(snaps, snaps[1:]):
        never_existed = not any(older < c < newer for c in created)
        assert never_existed or now - older <= ratio * (now - newer)


@pytest.mark.parametrize("cleanup_every", [HOUR, DAY, WEEK, 30 * DAY, 10 * YEAR])
def test_cleanup_frequency_changes_details_not_shape(cleanup_every):
    """Hourly, daily, weekly, monthly or one single cleanup after a year:
    the surviving snapshots differ, the spacing guarantees do not."""
    keep, _, _ = simulate(YEAR, cleanup_every)
    a = [x for x in ages(keep, YEAR - 1) if x > 0]
    ratios = [o / n for n, o in zip(a, a[1:])]
    assert max(ratios) <= 2.0          # hourly input: 1h -> 2h is the widest gap
    assert 20 <= len(keep) <= 30


def test_downtime_keeps_last_snapshot_before_shutdown():
    """On for two weeks, off for three, on again."""
    off = frozenset(range(2 * WEEK, 5 * WEEK))
    keep, _, _ = simulate(5 * WEEK + 1, off=off)
    assert 2 * WEEK - 1 in keep        # last state before shutdown survives
    assert 5 * WEEK in keep            # first snapshot after boot


def test_downtime_causes_mass_deletion_without_keep_newest():
    """Known behaviour, documented rather than hidden: age is wall-clock, so
    after three weeks off the dense recent history is thinned in one go."""
    off = frozenset(range(2 * WEEK, 5 * WEEK))
    before, _, _ = simulate(2 * WEEK)
    after, _, worst = simulate(5 * WEEK + 1, off=off)
    assert len(before) == 19
    assert len(after) == 4 and worst == 16


def test_keep_newest_softens_mass_deletion():
    off = frozenset(range(2 * WEEK, 5 * WEEK))
    keep, _, worst = simulate(5 * WEEK + 1, off=off, keep_newest=10)
    assert len(keep) == 12 and worst == 11
    assert set(range(2 * WEEK - 9, 2 * WEEK)) <= set(keep)   # last 9 hours before shutdown


@given(times_st, st.integers(0, 500))
def test_min_age_protects_young_snapshots(times, min_age):
    now = max(times, default=0)
    _, delete = thin(times, now, min_age=min_age)
    assert all(now - t >= min_age for t in delete)
