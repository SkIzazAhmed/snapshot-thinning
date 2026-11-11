"""Simulate one year of hourly snapshots and plot which ones survive.

    python3 simulate.py            # prints a table, writes simulation.png
"""

import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from thinning import thin

DAY, WEEK, YEAR = 24, 24 * 7, 24 * 365
BLUE, INK, MUTED, GRID, SURFACE = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def run(hours, cleanup_every=1, off=frozenset(), sample_every=2 * DAY, **kw):
    """Returns (kept at the end, [(now, ages of kept snapshots)], worst single cleanup)."""
    snaps, samples, worst = [], [], 0
    for now in range(hours):
        if now in off:
            continue
        snaps.append(now)
        if now % cleanup_every == 0 or now == hours - 1:
            snaps, deleted = thin(snaps, now, **kw)
            worst = max(worst, len(deleted))
        if now % sample_every == 0:
            samples.append((now, [now - s for s in snaps]))
    return snaps, samples, worst


def downtime(seed=1):
    """Six random, non-overlapping off-periods of 3 to 21 days."""
    rng = random.Random(seed)
    while True:
        periods = []
        for start in sorted(rng.sample(range(30 * DAY, 330 * DAY), 6)):
            periods.append((start, start + rng.randint(3 * DAY, 21 * DAY)))
        if all(b + DAY < c for (_, b), (c, _) in zip(periods, periods[1:])):
            break
    off = frozenset(h for a, b in periods for h in range(a, b))
    return off, periods


def table():
    off, _ = downtime()
    rows = [
        ("always on, cleanup hourly", dict()),
        ("always on, cleanup daily", dict(cleanup_every=DAY)),
        ("always on, cleanup weekly", dict(cleanup_every=WEEK)),
        ("always on, one cleanup after a year", dict(cleanup_every=10 * YEAR)),
        ("6 off-periods, cleanup hourly", dict(off=off)),
        ("6 off-periods, keep_newest=10", dict(off=off, keep_newest=10)),
    ]
    print(f"{'scenario':38} {'kept':>4} {'gap > 1 day':>10} {'most deleted at once':>20}")
    for name, kw in rows:
        keep, _, worst = run(YEAR, **kw)
        ages = [YEAR - 1 - s for s in keep if s != YEAR - 1]
        widest = max(o / n for n, o in zip(ages, ages[1:]) if n >= DAY)
        print(f"{name:38} {len(keep):4d} {widest:9.2f}x {worst:20d}")


def plot(path="simulation.png"):
    off, periods = downtime()
    panels = [
        ("Machine always on", run(YEAR)[1], []),
        ("Machine off six times (grey), 3 to 21 days each", run(YEAR, off=off)[1], periods),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True, facecolor=SURFACE)
    for ax, (title, samples, shaded) in zip(axes, panels):
        for a, b in shaded:
            ax.axvspan(a / DAY, b / DAY, color=GRID, lw=0)
        xs = [now / DAY for now, ages in samples for age in ages if age > 0]
        ys = [age for now, ages in samples for age in ages if age > 0]
        ax.scatter(xs, ys, s=5, color=BLUE, linewidths=0)
        ax.set_yscale("log")
        ax.set_yticks([1, DAY, WEEK, 30 * DAY, YEAR])
        ax.set_yticklabels(["1 hour", "1 day", "1 week", "1 month", "1 year"])
        ax.minorticks_off()
        ax.set_xlim(0, 365)
        ax.set_xlabel("Day of simulation", color=MUTED)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, length=0)
        for side in ax.spines.values():
            side.set_visible(False)
    axes[0].set_ylabel("Age of each kept snapshot", color=MUTED)
    fig.suptitle("Kept snapshots stay evenly spread on a log scale as time passes",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)


if __name__ == "__main__":
    table()
    plot()
