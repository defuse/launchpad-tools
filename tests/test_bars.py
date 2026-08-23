"""The elapsed-time bars on the top row of the pomodoro and habit tabs.

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
    assert mod.DAY.bar(at(2026, 8, 18, h, mi))[0] == lit


def test_day_bar_counts_down_to_midnight(mod):
    assert mod.DAY.bar(at(2026, 8, 18, 23, 0))[1] == 3600
    assert mod.DAY.bar(at(2026, 8, 18, 0, 0))[1] == 24 * 3600


# ---- weekly: one slice per day, Sunday first ------------------------------
@pytest.mark.parametrize('day,lit', [
    (SUN, 1), (MON, 2), (TUE, 3), (WED, 4), (THU, 5), (FRI, 6),
    (SAT, 8),        # seven days, eight cells: the spare one lights with the 7th
])
def test_week_bar_lights_a_cell_per_day(mod, day, lit):
    assert mod.WEEK.bar(at(2026, 8, day, 9, 0))[0] == lit


def test_week_bar_never_stops_at_seven(mod):
    """A permanent one-cell gap on the last day is the thing the mirrored
    eighth cell exists to prevent."""
    lit = {mod.WEEK.bar(at(2026, 8, d, 12, 0))[0] for d in range(SUN, SAT + 1)}
    assert 7 not in lit and 8 in lit


def test_week_bar_counts_down_to_sunday(mod):
    assert mod.WEEK.bar(at(2026, 8, SAT, 23, 0))[1] == 3600
    assert mod.WEEK.bar(at(2026, 8, SUN, 0, 0))[1] == 7 * 86400


# ---- the last hour --------------------------------------------------------
# clock time -> (colour, blink period in seconds; 0 = solid)
@pytest.mark.parametrize('h,mi,colour,period', [
    (21, 0,  'RED',    0),              # full, but three hours still to run
    (22, 59, 'RED',    0),
    (23, 0,  'YELLOW', 3.3),            # heads-up: half the rate, same dark gap
    (23, 29, 'YELLOW', 3.3),
    (23, 30, 'ORANGE', 1.8),            # pomodoro cadence
    (23, 39, 'ORANGE', 1.8),
    (23, 40, 'RED',    0.9),            # twice that
    (23, 49, 'RED',    0.9),
    (23, 50, 'RED',    0.3),            # rapid
    (23, 59, 'RED',    0.3),
])
def test_the_daily_bar_counts_itself_down_through_the_last_hour(mod, h, mi, colour, period):
    _, left = mod.DAY.bar(at(2026, 8, 18, h, mi))
    st = mod.DAY.stage(left)
    assert st.colour == getattr(mod, colour)
    assert round(st.on + st.off, 6) == period


def test_slowing_the_blink_lengthens_the_lit_chunk_not_the_gap(mod):
    """A dark chunk that grows with the period stops reading as a blink and
    starts reading as a pad that is off."""
    fits = [st for st in mod.BAR_STAGES if st.on + st.off >= 1.8]
    assert {st.off for st in fits} == {mod.FLASH_OFF}
    assert all(st.off <= mod.FLASH_OFF for st in mod.BAR_STAGES)


def test_the_last_hour_warms_from_yellow_to_red(mod):
    """Colour escalates with the rate, so the bar reads at a glance and from
    the corner of an eye both."""
    assert [st.colour for st in mod.BAR_STAGES] == \
        [mod.RED, mod.RED, mod.ORANGE, mod.YELLOW]      # shortest-remaining first


def test_each_stage_blinks_faster_than_the_one_before(mod):
    """Ordered shortest-remaining first, and strictly escalating -- a stage
    that blinked slower than its predecessor would read as the deadline
    receding."""
    periods = [st.on + st.off for st in mod.BAR_STAGES]
    assert periods == sorted(periods)
    assert [st.within for st in mod.BAR_STAGES] == sorted(st.within for st in mod.BAR_STAGES)


def test_the_weekly_bar_has_one_stage_and_it_is_solid(mod):
    """Not "a slow blink": the weekly bar is full for a whole day."""
    assert all(mod.WEEK.stage(left) == mod.WEEK.solid
               for left in (7 * 86400, 3600, 60, 0))
    assert mod.WEEK.solid.off == 0


def test_a_full_week_is_pink_and_a_full_day_is_red(mod):
    """The week sits full for a whole day, so it says so quietly."""
    assert mod.WEEK.full == mod.PINK
    assert mod.DAY.full == mod.RED


def test_every_blink_is_chunks_cut_out_of_a_lit_pad(mod):
    """Not a 50% square wave until the very end: a pad that is lit most of the
    time reads as 'live' rather than 'error'."""
    slow = [st for st in mod.BAR_STAGES if st.on + st.off > 0.5]
    assert all(st.on / (st.on + st.off) > 0.8 for st in slow)


# ---- what lands on the pads ----------------------------------------------
def row(out, mod):
    lit = out.lit()
    return [lit.get(mod.pad(mod.BAR_ROW, c)) for c in range(mod.CELLS)]


def paint(mod, out, when, mode=None):
    b = new_board(mod, out)
    b.mode = mode if mode is not None else mod.M_HAB
    mod.clock.now = when
    b.render_bar(mod.BARS[b.mode])
    return row(out, mod)


def test_daily_bar_is_blue_and_partly_lit(mod, out):
    assert paint(mod, out, at(2026, 8, 18, 12, 0)) == \
        [mod.DAY.colour] * 5 + [mod.OFF] * 3


def test_weekly_bar_is_purple(mod, out):
    assert paint(mod, out, at(2026, 8, WED, 12, 0), mod.M_HAB2) == \
        [mod.WEEK.colour] * 4 + [mod.OFF] * 4


def test_a_full_bar_stops_showing_its_own_colour(mod, out):
    assert paint(mod, out, at(2026, 8, 18, 21, 30)) == [mod.RED] * 8
    assert paint(mod, out, at(2026, 8, SAT, 12, 0), mod.M_HAB2) == [mod.PINK] * 8


def when(base, stage, want_dark):
    """A moment near `base` in the lit or dark chunk of `stage`'s blink."""
    period = stage.on + stage.off
    return next(base + d / 100 for d in range(400)
                if ((base + d / 100) % period >= stage.on) == want_dark)


def test_the_daily_bar_blinks_yellow_in_the_first_half_of_the_last_hour(mod, out):
    """The whole row goes dark together during the off chunk -- one bar
    blinking, not eight pads chasing each other."""
    base = at(2026, 8, 18, 23, 10)
    stage = mod.DAY.stage(mod.DAY.bar(base)[1])
    assert paint(mod, out, when(base, stage, True)) == [mod.OFF] * 8
    assert paint(mod, out, when(base, stage, False)) == [mod.YELLOW] * 8


def test_the_daily_bar_blinks_red_once_the_last_twenty_minutes_start(mod, out):
    base = at(2026, 8, 18, 23, 45)
    stage = mod.DAY.stage(mod.DAY.bar(base)[1])
    assert paint(mod, out, when(base, stage, True)) == [mod.OFF] * 8
    assert paint(mod, out, when(base, stage, False)) == [mod.RED] * 8


def test_the_weekly_bar_never_blinks(mod, out):
    """It is full for a whole day; blinking that long is just noise."""
    base = at(2026, 8, SAT, 23, 10)
    stage = mod.DAY.stage(mod.DAY.bar(base)[1])          # when the DAY bar is dark
    assert paint(mod, out, when(base, stage, True), mod.M_HAB2) == [mod.PINK] * 8


# ---- the row is not a habit row any more ----------------------------------
def test_progress_row_is_not_a_habit_row(mod):
    assert mod.BAR_ROW not in mod.HAB_ROWS
    assert mod.HAB_ROWS == [2, 3, 4, 5, 6, 7]


def test_pressing_the_bar_does_nothing(mod, out):
    """It used to be a habit row: a press there would open the window on an
    empty cell and a hold would invent a habit the pads no longer show."""
    b = new_board(mod, out)
    b.mode = mod.M_HAB
    b.press(mod.pad(mod.BAR_ROW, 3))
    b.release(mod.pad(mod.BAR_ROW, 3))
    assert b._editing is None
    assert b.habits == {}
