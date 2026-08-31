"""The calendar chord mode: reaching it, drawing it, marking days.

Reached by holding one tab and pressing another, which is a mechanic with one
hard requirement -- a single tab press must be no slower than it was, so
nothing may wait to see whether a second press is coming.
"""
import json
import time
import pytest
from lpharness import FakeOut, new_board


def at(y, mo, d, h=12, mi=0):
    return time.mktime((y, mo, d, h, mi, 0, 0, 0, -1))


AUG = at(2026, 8, 27)                      # a Thursday


@pytest.fixture
def cal(board, mod, clock):
    clock.now = AUG
    board.mode = mod.M_CAL
    return board


def chord(board, mod, a, b):
    """Hold tab a, press tab b, let both go."""
    board.press(mod.pad(mod.FUNC_ROW, a))
    board.press(mod.pad(mod.FUNC_ROW, b))
    board.release(mod.pad(mod.FUNC_ROW, b))
    board.release(mod.pad(mod.FUNC_ROW, a))


# ---- getting there --------------------------------------------------------

def test_two_tabs_at_once_reach_a_mode_with_no_tab(board, mod):
    chord(board, mod, mod.M_POMO, mod.M_HAB)
    assert board.mode == mod.M_CAL


def test_either_order_works(board, mod):
    chord(board, mod, mod.M_HAB, mod.M_POMO)
    assert board.mode == mod.M_CAL


def test_a_single_tab_press_still_switches_at_once(board, mod):
    """Nothing waits to see whether a second press is coming, which is the
    whole reason the chord lands on the second press rather than a timeout."""
    board.press(mod.pad(mod.FUNC_ROW, mod.M_MACH))
    assert board.mode == mod.M_MACH, 'switched on the press, not on release'
    board.release(mod.pad(mod.FUNC_ROW, mod.M_MACH))
    assert board.mode == mod.M_MACH


def test_pressing_tabs_one_after_the_other_is_not_a_chord(board, mod):
    """Released in between: two ordinary tab presses."""
    for tab in (mod.M_POMO, mod.M_HAB):
        board.press(mod.pad(mod.FUNC_ROW, tab))
        board.release(mod.pad(mod.FUNC_ROW, tab))
    assert board.mode == mod.M_HAB


def test_a_pair_that_is_not_a_chord_just_switches_tabs(board, mod):
    chord(board, mod, mod.M_SPEC, mod.M_NET)
    assert board.mode == mod.M_NET


def test_a_single_tab_leaves_the_chord_mode(board, mod):
    chord(board, mod, mod.M_POMO, mod.M_HAB)
    board.press(mod.pad(mod.FUNC_ROW, mod.M_SPEC))
    assert board.mode == mod.M_SPEC


def test_both_of_its_tabs_light_and_in_a_colour_no_tab_wears(cal, mod):
    cal.render()
    lit = cal.out.lit()
    for tab in mod.CHORD_TABS[mod.M_CAL]:
        assert lit[mod.pad(mod.FUNC_ROW, tab)] == mod.MAGENTA
    assert mod.MAGENTA != mod.TAB_SELECTED
    others = [c for c in mod.TABS if c not in mod.CHORD_TABS[mod.M_CAL]]
    assert all(lit[mod.pad(mod.FUNC_ROW, c)] == mod.WHITE for c in others)


def test_the_chord_mode_survives_a_restart(mod, seed, out):
    seed(mode=mod.M_CAL, marks=['2026-08-01'])
    b = new_board(mod, out)
    assert b.mode == mod.M_CAL and b.marks == {'2026-08-01'}


# ---- the month ------------------------------------------------------------

def test_the_month_is_laid_out_as_a_calendar(mod):
    """August 2026 starts on a Saturday, so the first week is six blanks and
    the 1st, and Sunday is the first column."""
    weeks = mod.month_weeks(2026, 8)
    assert weeks[0] == [0, 0, 0, 0, 0, 0, 1]
    assert weeks[1][:3] == [2, 3, 4]
    assert max(max(w) for w in weeks) == 31


def test_a_six_week_month_still_fits(mod):
    """Six rows is the most a month can need, and the layout has six."""
    longest = max(len(mod.month_weeks(y, m))
                  for y in range(2024, 2031) for m in range(1, 13))
    assert longest == 6 and len(mod.CAL_ROWS) == 6


def sky_phase(mod, base):
    """A moment in each half of today's alternation, near `base`."""
    lit = next(base + d / 10 for d in range(40)
               if int((base + d / 10) / mod.CAL_TODAY_FLASH) % 2)
    dark = next(base + d / 10 for d in range(40)
                if not int((base + d / 10) / mod.CAL_TODAY_FLASH) % 2)
    return lit, dark


def today_colour(cal, when):
    return next(v[1] for v in cal.calendar_cells(when).values()
                if v[0] == '2026-08-27')


def test_today_alternates_between_sky_and_its_own_state(cal, mod, tmp_path, monkeypatch):
    """Sky says which day it is; the other half says how the day is going, so
    the cell answers both questions without a second pad."""
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    for _ in range(4):
        mod.log_timer('pomodoro', 'claimed', when=AUG, path=mod.LOG_FILE)
    cal._counts_at = None
    lit, dark = sky_phase(mod, AUG)
    assert today_colour(cal, lit) == mod.CAL_TODAY_COL
    assert today_colour(cal, dark) == mod.day_colour(4)


def test_a_day_that_is_not_today_does_not_flash(cal, mod):
    lit, dark = sky_phase(mod, AUG)
    other = lambda when: next(v[1] for v in cal.calendar_cells(when).values()
                              if v[0] == '2026-08-12')
    assert other(lit) == other(dark) == mod.day_colour(0)


def test_days_outside_the_month_are_not_drawn(cal, mod):
    cal.render()
    lit = cal.out.lit()
    assert lit[mod.pad(mod.CAL_ROWS[0], 0)] == mod.OFF, 'the 1st is a Saturday'
    assert lit[mod.pad(mod.CAL_ROWS[0], 6)] != mod.OFF


def test_the_navigation_column_is_the_eighth(cal, mod):
    cal.render()
    lit = cal.out.lit()
    for row, colour in mod.CAL_CTRL.items():
        assert lit[mod.pad(row, mod.CAL_COL)] == colour
    assert all((r, mod.CAL_COL) not in cal.calendar_cells(AUG) for r in mod.CAL_ROWS)


@pytest.mark.parametrize('presses,month', [
    (['CAL_PREV'], (2026, 7)),
    (['CAL_NEXT'], (2026, 9)),
    (['CAL_PREV'] * 8, (2025, 12)),
    (['CAL_NEXT'] * 5, (2027, 1)),
    (['CAL_NEXT', 'CAL_PREV'], (2026, 8)),
])
def test_the_month_can_be_walked(cal, mod, presses, month):
    for name in presses:
        cal.press(mod.pad(getattr(mod, name), mod.CAL_COL))
        cal.release(mod.pad(getattr(mod, name), mod.CAL_COL))
    assert mod.month_at(cal.cal_offset, AUG) == month


@pytest.mark.parametrize('first,second', [('CAL_PREV', 'CAL_NEXT'),
                                          ('CAL_NEXT', 'CAL_PREV')])
def test_both_nav_pads_at_once_come_back_to_this_month(cal, mod, first, second):
    for _ in range(5):                                  # wander off
        cal.press(mod.pad(mod.CAL_PREV, mod.CAL_COL))
        cal.release(mod.pad(mod.CAL_PREV, mod.CAL_COL))
    assert cal.cal_offset != 0
    cal.press(mod.pad(getattr(mod, first), mod.CAL_COL))
    cal.press(mod.pad(getattr(mod, second), mod.CAL_COL))
    assert cal.cal_offset == 0, 'either order, on the second press'
    cal.release(mod.pad(getattr(mod, second), mod.CAL_COL))
    cal.release(mod.pad(getattr(mod, first), mod.CAL_COL))
    assert cal.cal_offset == 0, 'and letting go changes nothing back'


def test_one_nav_pad_still_steps_one_month(cal, mod):
    """Nothing waits to see whether the other is coming: a single press moves
    the month the moment it lands."""
    cal.press(mod.pad(mod.CAL_NEXT, mod.CAL_COL))
    assert mod.month_at(cal.cal_offset, AUG) == (2026, 9)


def test_the_navigation_is_two_pads_and_no_more(cal, mod):
    """A third one sat in the bottom right doing this same job, and a light
    that needs explaining is worse than the gesture it saves."""
    assert set(mod.CAL_CTRL) == {mod.CAL_PREV, mod.CAL_NEXT}
    cal.render()
    lit = cal.out.lit()
    dark = [r for r in mod.CAL_ROWS if r not in mod.CAL_CTRL]
    assert all(lit[mod.pad(r, mod.CAL_COL)] == mod.OFF for r in dark)


def test_a_frame_that_changes_nothing_sends_nothing(cal, mod):
    """The flicker: render_calendar blanked every cell and then painted it, so
    with set() suppressing unchanged pads each one changed twice a frame --
    off, on, off, on, twenty times a second. A still board must be silent."""
    cal.render()
    cal.out.sent.clear()
    cal.render()
    assert cal.out.sent == [], f'{len(cal.out.sent)} messages for an unchanged frame'


def test_and_a_frame_that_changes_one_pad_sends_one_pad(cal, mod):
    row, col = next(rc for rc, v in cal.calendar_cells(AUG).items()
                    if v[0] == '2026-08-12')
    cal.render()
    cal.out.sent.clear()
    cal.marks.add('2026-08-12')
    cal.render()
    assert len(cal.out.sent) == 1
    assert cal.out.lit()[mod.pad(row, col)] == mod.CAL_MARK


def test_walking_months_marks_nothing(cal, mod):
    cal.press(mod.pad(mod.CAL_NEXT, mod.CAL_COL))
    assert cal.marks == set()


# ---- marking --------------------------------------------------------------

def test_a_day_marks_and_unmarks(cal, mod):
    row, col = next(rc for rc, v in cal.calendar_cells(AUG).items()
                    if v[0] == '2026-08-12')
    cal.press(mod.pad(row, col))
    assert cal.marks == {'2026-08-12'}
    assert cal.calendar_cells(AUG)[(row, col)][1] == mod.CAL_MARK
    cal.press(mod.pad(row, col))
    assert cal.marks == set()


def test_a_marked_today_flashes_against_its_mark(cal, mod):
    """Marking is deliberate, so it is what today shows between flashes --
    the mark still outranks the count."""
    row, col = next(rc for rc, v in cal.calendar_cells(AUG).items()
                    if v[0] == '2026-08-27')
    cal.press(mod.pad(row, col))
    lit, dark = sky_phase(mod, AUG)
    assert today_colour(cal, lit) == mod.CAL_TODAY_COL
    assert today_colour(cal, dark) == mod.CAL_MARK


def test_pressing_where_no_day_is_does_nothing(cal, mod):
    cal.press(mod.pad(mod.CAL_ROWS[0], 0))         # before the 1st
    assert cal.marks == set()


def test_marks_are_kept_across_months_and_saved(cal, mod):
    row, col = next(rc for rc, v in cal.calendar_cells(AUG).items()
                    if v[0] == '2026-08-12')
    cal.press(mod.pad(row, col))
    cal.press(mod.pad(mod.CAL_NEXT, mod.CAL_COL))
    assert cal.marks == {'2026-08-12'}, 'still marked, just not on screen'
    cal._flush()
    assert json.load(open(mod.STATE_FILE))['marks'] == ['2026-08-12']


# ---- the count behind the colour -----------------------------------------

def test_a_claimed_pomodoro_is_logged(board, mod, tmp_path, monkeypatch, clock):
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    board.mode = mod.M_POMO
    row = mod.POMO_ROWS[0]
    board.rows[row] = {'state': mod.ELAPSED, 'started': clock.time()}
    board.press(mod.pad(row, mod.CELLS - 1))                  # the green pad
    entries = [json.loads(l) for l in open(mod.LOG_FILE)]
    assert entries[-1]['kind'] == 'pomodoro' and entries[-1]['event'] == 'claimed'
    assert entries[-1]['day'] == time.strftime('%Y-%m-%d', time.localtime(clock.time()))


def test_a_break_is_logged_and_not_counted(mod, tmp_path):
    """Breaks are worth recording and are not what the colour is about."""
    log = str(tmp_path / 'log.jsonl')
    mod.log_timer('break', 'claimed', when=AUG, path=log)
    mod.log_timer('pomodoro', 'claimed', when=AUG, path=log)
    assert mod.read_counts(log) == {'2026-08-27': 1}


@pytest.mark.parametrize('event', ['elapsed', 'written off', 'abandoned'])
def test_only_claiming_counts(mod, tmp_path, event):
    """A timer that ran out is a timer that ran out; the green pad at the end
    of the row is where you say it counted."""
    log = str(tmp_path / 'log.jsonl')
    mod.log_timer('pomodoro', event, when=AUG, path=log)
    assert mod.read_counts(log) == {}


def test_a_torn_line_does_not_lose_the_rest(mod, tmp_path):
    log = tmp_path / 'log.jsonl'
    log.write_text(json.dumps({'kind': 'pomodoro', 'event': 'claimed',
                               'day': '2026-08-27'}) + '\n{"kind": "pomo')
    assert mod.read_counts(str(log)) == {'2026-08-27': 1}


def test_no_log_at_all_is_not_an_error(mod, tmp_path):
    assert mod.read_counts(str(tmp_path / 'nothing')) == {}


# ---- and the colour it becomes -------------------------------------------

def test_a_couple_of_pomodoros_already_look_green(mod):
    """A quarter of the way from white to green is barely off white, so two
    used to read as none. The ramp is curved to spend itself early, where the
    difference is hard to see."""
    r, g, b = mod.day_colour(2)
    assert r / g <= 0.55, f'two pomodoros came out {(r, g, b)}'
    assert mod.day_colour(1)[0] / mod.day_colour(1)[1] <= 0.7, 'and one shows'


def test_the_ramp_is_curved_not_straight(mod):
    """Halfway up the count is more than halfway to green."""
    half = mod.day_colour(mod.CAL_FULL // 2)
    straight = mod.blend(mod.CAL_NONE, mod.CAL_DONE, 0.5)
    assert half[0] < straight[0]


def test_none_is_white_and_a_full_day_is_green(mod):
    assert mod.day_colour(0) == mod.CAL_NONE
    assert mod.day_colour(mod.CAL_FULL) == mod.CAL_DONE


def test_it_greens_all_the_way_up_and_then_goes_magenta(mod):
    """One ramp to a day's worth and a second one past it, so a heavy day is
    distinguishable from a full one rather than both being 'green'."""
    ramp = [mod.day_colour(n) for n in range(0, 2 * mod.CAL_FULL + 1)]
    assert len(set(ramp)) == len(ramp), 'every count looks different'
    reds = [c[0] for c in ramp]
    assert reds[:mod.CAL_FULL + 1] == sorted(reds[:mod.CAL_FULL + 1], reverse=True)
    assert reds[mod.CAL_FULL:] == sorted(reds[mod.CAL_FULL:]), 'and back up to magenta'
    assert mod.day_colour(2 * mod.CAL_FULL) == mod.CAL_OVER


def test_more_than_sixteen_does_not_wrap_back_to_white(mod):
    assert mod.day_colour(40) == mod.CAL_OVER


def test_the_count_reaches_the_pads(cal, mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    for _ in range(mod.CAL_FULL):
        mod.log_timer('pomodoro', 'claimed', when=at(2026, 8, 12), path=mod.LOG_FILE)
    cal._counts_at = None                                  # force a re-read
    row, col = next(rc for rc, v in cal.calendar_cells(AUG).items()
                    if v[0] == '2026-08-12')
    assert cal.calendar_cells(AUG)[(row, col)][1] == mod.CAL_DONE
    cal.render()
    assert cal.out.lit()[mod.pad(row, col)] == mod.CAL_DONE


def test_the_log_is_only_read_again_when_it_changes(cal, mod, tmp_path, monkeypatch):
    """Once a frame is 20 reads a second of a file that only grows."""
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    reads = []
    real = mod.read_counts
    monkeypatch.setattr(mod, 'read_counts', lambda *a: (reads.append(1), real(*a))[1])
    mod.log_timer('pomodoro', 'claimed', when=AUG, path=mod.LOG_FILE)
    cal.counts(); cal.counts(); cal.counts()
    assert len(reads) == 1
    mod.log_timer('pomodoro', 'claimed', when=AUG, path=mod.LOG_FILE)
    cal.counts()
    assert len(reads) == 2, 'but a longer file is read again'


# ---- the tab it does not disturb -----------------------------------------

def test_the_calendar_has_the_day_bar_like_the_other_tabs(mod):
    assert mod.BARS[mod.M_CAL] is mod.DAY
    assert mod.widget_at(mod.M_CAL, mod.BAR_ROW) is mod.Widget.BAR


def test_no_row_of_it_means_two_things(mod):
    mod._check_layout()                                    # raises if it does
    for r in mod.CAL_ROWS:
        assert mod.widget_at(mod.M_CAL, r) is mod.Widget.CALENDAR
