"""The elapsed-time bars on the top row of each habit tab.

A cell lights when its slice STARTS, so a full bar means the period is in its
last slice. Times are built with mktime so the tests read as wall-clock times
and stay correct in any timezone.
"""
import time
import pytest
from lpharness import FakeOut, new_board


def at(y, mo, d, h, mi, s=0):
    """Local wall-clock time as an epoch. dst=-1 lets mktime work it out."""
    return time.mktime((y, mo, d, h, mi, s, 0, 0, -1))


# 2026-08-16 is a Sunday, so 16..22 August 2026 is one whole week.
SUN, MON, TUE, WED, THU, FRI, SAT = range(16, 23)


# ---- daily: eight three-hour slices ---------------------------------------
@pytest.mark.parametrize('h,mi,lit', [
    (0, 0, 1), (2, 59, 1),          # first slice starts lit
    (3, 0, 2), (5, 59, 2),
    (12, 0, 5),
    (20, 59, 7),
    (21, 0, 8), (23, 59, 8),        # last slice: full for its whole three hours
])
def test_day_bar_lights_a_cell_as_its_slice_begins(mod, h, mi, lit):
    assert mod.day_bar(at(2026, 8, 18, h, mi))[0] == lit


def test_day_bar_counts_down_to_midnight(mod):
    assert mod.day_bar(at(2026, 8, 18, 23, 0))[1] == 3600
    assert mod.day_bar(at(2026, 8, 18, 0, 0))[1] == 24 * 3600


# ---- weekly: one slice per day, Sunday first ------------------------------
@pytest.mark.parametrize('day,lit', [
    (SUN, 1), (MON, 2), (TUE, 3), (WED, 4), (THU, 5), (FRI, 6),
    (SAT, 8),        # seven days, eight cells: the spare one lights with the 7th
])
def test_week_bar_lights_a_cell_per_day(mod, day, lit):
    assert mod.week_bar(at(2026, 8, day, 9, 0))[0] == lit


def test_week_bar_never_stops_at_seven(mod):
    """A permanent one-cell gap on the last day is the thing the mirrored
    eighth cell exists to prevent."""
    lit = {mod.week_bar(at(2026, 8, d, 12, 0))[0] for d in range(SUN, SAT + 1)}
    assert 7 not in lit and 8 in lit


def test_week_bar_counts_down_to_sunday(mod):
    assert mod.week_bar(at(2026, 8, SAT, 23, 0))[1] == 3600
    assert mod.week_bar(at(2026, 8, SUN, 0, 0))[1] == 7 * 86400


# ---- the last hour --------------------------------------------------------
@pytest.mark.parametrize('left,beat', [
    (3 * 3600, None),                   # full but not urgent: 21:00
    (3601, None),
    (3600, (1.5, 0.3)),                 # pomodoro cadence
    (1801, (1.5, 0.3)),
    (1800, (0.75, 0.15)),               # twice as fast
    (901, (0.75, 0.15)),
    (900, (0.15, 0.15)),                # rapid
    (5, (0.15, 0.15)),
])
def test_prog_flash_escalates(mod, left, beat):
    assert mod.prog_flash(left) == beat


def test_flash_cadence_is_chunks_cut_out_of_a_lit_pad(mod):
    """Not a 50% square wave: at pomodoro speed the pad is lit most of the
    time, which reads as 'live' rather than 'error'."""
    on, off = mod.PROG_FLASH[-1][1:]
    assert on / (on + off) > 0.8


# ---- what lands on the pads ----------------------------------------------
def row(out, mod):
    lit = out.lit()
    return [lit.get(mod.pad(mod.PROG_ROW, c)) for c in range(mod.CELLS)]


def paint(mod, out, when, mode=None):
    b = new_board(mod, out)
    b.mode = mode if mode is not None else mod.M_HAB
    mod.clock.now = when
    b.render_progress()
    return row(out, mod)


def test_daily_bar_is_blue_and_partly_lit(mod, out):
    assert paint(mod, out, at(2026, 8, 18, 12, 0)) == \
        [mod.PROG_DAY] * 5 + [mod.OFF] * 3


def test_weekly_bar_is_purple(mod, out):
    assert paint(mod, out, at(2026, 8, WED, 12, 0), mod.M_HAB2) == \
        [mod.PROG_WEEK] * 4 + [mod.OFF] * 4


def test_a_full_bar_turns_red(mod, out):
    assert paint(mod, out, at(2026, 8, 18, 21, 30)) == [mod.PROG_FULL] * 8
    assert paint(mod, out, at(2026, 8, SAT, 12, 0), mod.M_HAB2) == [mod.PROG_FULL] * 8


def test_the_daily_bar_blinks_in_the_last_hour(mod, out):
    """The whole row goes dark together during the off chunk -- one bar
    blinking, not eight pads chasing each other."""
    on, off = mod.PROG_FLASH[-1][1:]
    base = at(2026, 8, 18, 23, 10)
    dark = next(base + d / 100 for d in range(200)
                if (base + d / 100) % (on + off) >= on)
    assert paint(mod, out, dark) == [mod.OFF] * 8
    lit_t = next(base + d / 100 for d in range(200)
                 if (base + d / 100) % (on + off) < on)
    assert paint(mod, out, lit_t) == [mod.PROG_FULL] * 8


def test_the_weekly_bar_never_blinks(mod, out):
    """It is full for a whole day; blinking that long is just noise."""
    on, off = mod.PROG_FLASH[-1][1:]
    base = at(2026, 8, SAT, 23, 10)
    dark = next(base + d / 100 for d in range(200)
                if (base + d / 100) % (on + off) >= on)
    assert paint(mod, out, dark, mod.M_HAB2) == [mod.PROG_FULL] * 8


# ---- the row is not a habit row any more ----------------------------------
def test_progress_row_is_not_a_habit_row(mod):
    assert mod.PROG_ROW not in mod.HAB_ROWS
    assert mod.HAB_ROWS == [2, 3, 4, 5, 6, 7]


def test_pressing_the_bar_does_nothing(mod, out):
    """It used to be a habit row: a press there would open the window on an
    empty cell and a hold would invent a habit the pads no longer show."""
    b = new_board(mod, out)
    b.mode = mod.M_HAB
    b.press(mod.pad(mod.PROG_ROW, 3))
    b.release(mod.pad(mod.PROG_ROW, 3))
    assert b._editing is None
    assert b.habits == {}
