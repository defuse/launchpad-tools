"""The calendar window: what the board sends it, and what it makes of it.

The board can only ever draw one calendar mode at a time -- eight columns of
pads have no room to say a day had four pomodoros AND that the fast went
badly -- so this window shows both at once, plus the arithmetic pads cannot do.
"""
import json
import time
import pytest
from lpharness import FakePopen, new_board

AUG = time.mktime((2026, 8, 27, 12, 0, 0, 0, 0, -1))       # a Thursday


@pytest.fixture
def cal(board, mod, clock):
    clock.now = AUG
    board.mode = mod.M_CAL
    return board


def window(mod):
    for p in FakePopen.instances:
        if 'cal-popup' in p.argv[0]:
            return p.sent()
    return []


def sent(mod):
    """The last frame the window was given."""
    for line in reversed(window(mod)):
        if line.startswith('data\t'):
            return json.loads(line.split('\t', 1)[1])
    return {}


def log(mod, day, n, tmp_path):
    for _ in range(n):
        mod.log_timer('pomodoro', 'claimed',
                      when=time.mktime((2026, 8, day, 10, 0, 0, 0, 0, -1)),
                      path=mod.LOG_FILE)


# ---- opening and following ------------------------------------------------

def test_the_red_pad_opens_it_on_this_tab(cal, mod, clock):
    cal.press(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
    clock.advance(0.2)
    cal.release(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
    assert cal._window == mod.M_CAL
    assert window(mod)[-1] == 'show'


def test_and_closes_it_again(cal, mod, clock):
    for _ in range(2):
        cal.press(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
        clock.advance(0.2)
        cal.release(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
    assert cal._window is None
    assert window(mod)[-1] == 'hide'


def test_leaving_the_tab_takes_the_window_with_it(cal, mod, clock):
    cal.press(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
    clock.advance(0.2)
    cal.release(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
    cal.press(mod.pad(mod.FUNC_ROW, mod.M_SPEC))
    assert cal._window is None
    assert window(mod)[-1] == 'hide'


def test_the_month_here_follows_the_month_there(cal, mod):
    cal.toggle_window()
    assert sent(mod)['title'] == 'August 2026'
    def step(row):                       # released in between, or the two
        cal.press(mod.pad(row, mod.CAL_COL))     # together are the chord back
        cal.release(mod.pad(row, mod.CAL_COL))   # to this month
        cal.render()
    step(mod.CAL_NEXT)
    assert sent(mod)['title'] == 'September 2026'
    step(mod.CAL_PREV); step(mod.CAL_PREV)
    assert sent(mod)['title'] == 'July 2026'


def test_an_unchanged_month_is_not_sent_twice(cal, mod):
    cal.toggle_window()
    before = len([l for l in window(mod) if l.startswith('data\t')])
    cal.render(); cal.render()
    assert len([l for l in window(mod) if l.startswith('data\t')]) == before


def test_a_closed_window_is_not_written_to(cal, mod):
    cal.render()
    assert not [l for l in window(mod) if l.startswith('data\t')]


# ---- both modes at once ---------------------------------------------------

def test_a_day_carries_its_pomodoros_and_its_fast(cal, mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    log(mod, 12, 4, tmp_path)
    cal._counts_at = None
    cal.fasts['2026-08-12'] = mod.FAST_FAIL
    cal.marks.add('2026-08-12')
    cal.toggle_window()
    day = next(d for wk in sent(mod)['weeks'] for d in wk
               if d and d['iso'] == '2026-08-12')
    assert (day['pomos'], day['fast'], day['mark']) == (4, mod.FAST_FAIL, True)


def test_today_is_named_as_today(cal, mod):
    cal.toggle_window()
    todays = [d for wk in sent(mod)['weeks'] for d in wk if d and d['today']]
    assert [d['iso'] for d in todays] == ['2026-08-27']


def test_padding_days_are_null_not_zero(cal, mod):
    """August 2026 opens on a Saturday: the first week is six holes and a day,
    and a hole is not a day with nothing on it."""
    cal.toggle_window()
    assert [d for d in sent(mod)['weeks'][0]][:6] == [None] * 6
    assert sent(mod)['weeks'][0][6]['day'] == 1


# ---- the arithmetic -------------------------------------------------------

def test_the_month_average_counts_days_that_have_happened(cal, mod, tmp_path, monkeypatch):
    """Three days into a month, the average is over three days -- not over
    thirty-one with twenty-eight zeroes in it."""
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    log(mod, 1, 6, tmp_path)
    log(mod, 2, 4, tmp_path)
    cal._counts_at = None
    cal.toggle_window()
    s = sent(mod)['month']
    assert s['days'] == 27, 'the 1st to the 27th'
    assert s['pomos'] == 10
    assert round(s['avg'], 4) == round(10 / 27, 4)


def test_a_month_gone_by_counts_all_of_it(mod, board, clock):
    clock.now = AUG
    board.mode = mod.M_CAL
    board.cal_offset = -1                                  # July
    board.toggle_window()
    assert sent(mod)['month']['days'] == 31


def test_a_month_not_yet_begun_has_nothing_to_average(mod, board, clock):
    clock.now = AUG
    board.mode = mod.M_CAL
    board.cal_offset = 2                                   # October
    board.toggle_window()
    assert sent(mod)['month']['days'] == 0


def test_the_fasting_split_is_of_those_same_days(cal, mod):
    cal.fasts.update({'2026-08-03': mod.FAST_OK, '2026-08-04': mod.FAST_OK,
                      '2026-08-05': mod.FAST_FAIL,
                      '2026-08-30': mod.FAST_OK})          # after today
    cal.toggle_window()
    s = sent(mod)['month']
    assert (s['green'], s['red']) == (2, 1), 'the 30th has not happened yet'
    assert s['yellow'] == s['days'] - 3


def test_the_last_seven_days_ignore_which_month_is_shown(cal, mod, tmp_path, monkeypatch):
    """What you have been doing lately is not a property of the page."""
    monkeypatch.setattr(mod, 'LOG_FILE', str(tmp_path / 'log.jsonl'))
    log(mod, 25, 7, tmp_path)                              # inside the 7 days
    log(mod, 2, 9, tmp_path)                               # outside them
    cal._counts_at = None
    cal.toggle_window()
    first = sent(mod)['week']
    assert first['days'] == 7 and first['pomos'] == 7
    cal.press(mod.pad(mod.CAL_PREV, mod.CAL_COL))          # go to July
    cal.render()
    assert sent(mod)['week'] == first, 'unchanged by walking the months'


def test_seven_days_means_today_and_the_six_before(mod, clock):
    clock.now = AUG
    days = mod.last_days(7)
    assert days[-1] == '2026-08-27' and days[0] == '2026-08-21'
    assert len(set(days)) == 7


def test_the_day_span_survives_a_daylight_saving_change(mod):
    """Subtracting 86400 seconds repeats a day or skips one twice a year."""
    for when in (time.mktime((2026, 11, 3, 12, 0, 0, 0, 0, -1)),
                 time.mktime((2026, 3, 10, 12, 0, 0, 0, 0, -1))):
        days = mod.last_days(7, when)
        assert len(set(days)) == 7, days


# ---- the window itself ----------------------------------------------------

def test_the_window_reads_what_the_board_writes(mod, popup_mod=None):
    """The two halves have to agree about the shape of a frame."""
    from lpharness import load_popup
    win = load_popup('cal-popup')
    assert win.COLS == mod.CAL_DAYS
    assert win.ROWS == len(mod.CAL_ROWS)
    for state in (mod.FAST_NONE, mod.FAST_OK, mod.FAST_FAIL):
        assert state in win.FAST_BG and state in win.FAST_NAME


def test_the_windows_ramp_agrees_with_the_pads(mod):
    """Both should say the same thing about a day's worth of pomodoros."""
    from lpharness import load_popup
    win = load_popup('cal-popup')
    assert win.ramp(0) != win.ramp(1)
    assert win.ramp(mod.CAL_FULL) == '#00ff00', 'full green at a full day'
    assert win.ramp(2 * mod.CAL_FULL) == '#ff00ff', 'magenta at twice one'
