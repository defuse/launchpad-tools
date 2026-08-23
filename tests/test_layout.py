"""Who owns which row, on which tab.

Every tab drives the same 64 pads, so a row means whatever the tab showing it
says it means. TAB_ROWS is that statement; these tests are what stop it from
drifting away from the code that draws and the code that dispatches presses.
"""
import pytest
from lpharness import FakeOut, new_board


def test_the_top_row_is_the_bar_and_the_timers_start_below_it(mod):
    assert mod.BAR_ROW == 1
    assert mod.POMO_ROWS == [2, 3, 4, 5]
    assert mod.BAR_ROW not in mod.TIMERS and mod.BAR_ROW not in mod.HAB_ROWS


def test_the_pomodoro_tab_shows_the_same_day_as_the_daily_habit_tab(mod):
    """Not a copy of it: the same Period, drawn by the same code."""
    assert mod.BARS[mod.M_POMO] is mod.BARS[mod.M_HAB] is mod.DAY
    assert mod.BARS[mod.M_HAB2] is mod.WEEK
    assert mod.M_SYS not in mod.BARS and mod.M_NET not in mod.BARS


@pytest.mark.parametrize('mode,row,widget', [
    ('M_MACH', 'BAR_ROW',  'BAR'),
    ('M_MACH', 'DISK_ROW', 'DISK'),
    ('M_MACH', 'FS_ROW',   'FS'),
    ('M_MACH', 'TEMP_ROW', 'TEMP'),
    ('M_MACH', 'CTRL_ROW', 'CONTROL'),
    ('M_MACH', 'DRIVE_TEMP_ROW', 'TEMP'),
    ('M_MACH', 6, 'BLANK'),
    ('M_POMO', 'BAR_ROW', 'BAR'),
    ('M_POMO', 2, 'TIMER'),
    ('M_POMO', 6, 'TOGGLE'),
    ('M_POMO', 7, 'TIMER'),          # the break row
    ('M_HAB',  'BAR_ROW', 'BAR'),
    ('M_HAB',  2, 'HABIT'),
    ('M_HAB2', 7, 'HABIT'),
    ('M_SPEC', 1, 'SPECTRUM'),
    ('M_SPEC', 7, 'SPECTRUM'),
    ('M_SYS',  1, 'CPU'),
    ('M_SYS',  7, 'MEM'),
    ('M_NET',  1, 'NET'),
])
def test_widget_at_names_what_a_row_means(mod, mode, row, widget):
    r = getattr(mod, row) if isinstance(row, str) else row
    assert mod.widget_at(getattr(mod, mode), r) is getattr(mod.Widget, widget)


def test_a_row_claimed_twice_on_one_tab_is_a_startup_failure(mod, monkeypatch):
    """Two widgets on one row is how a press comes to mean two things at once
    -- the bug this board has had more than any other. It should never get as
    far as running."""
    bad = dict(mod.TAB_ROWS)
    bad[mod.M_POMO] = {mod.Widget.TIMER: [3], mod.Widget.HABIT: [3]}
    monkeypatch.setattr(mod, 'TAB_ROWS', bad)
    with pytest.raises(RuntimeError, match='row 3'):
        mod._check_layout()


def test_the_real_layout_has_no_overlaps(mod):
    mod._check_layout()


# ---- drawing and dispatch agree with the table ---------------------------
def painted(board, mod, out):
    """Which rows one frame actually lights up."""
    board.shown.clear()                 # set() skips unchanged pads
    out.sent.clear()
    board.render()
    return {board.rc(m.note)[0] for m in out.sent if board.rc(m.note)}


TAB_NAMES = ['M_POMO', 'M_HAB', 'M_HAB2', 'M_MACH', 'M_SPEC', 'M_SYS', 'M_NET']


def test_the_drawing_test_below_covers_every_tab(mod):
    """Guards the parametrize list: a new tab that nobody drew a frame of
    would otherwise just not be tested."""
    assert set(mod.TABS) == {getattr(mod, n) for n in TAB_NAMES}


@pytest.mark.parametrize('mode', TAB_NAMES)
def test_a_tab_draws_exactly_the_rows_it_claims(mod, out, mode):
    """A row drawn but not claimed would take presses meant for something else;
    a row claimed but not drawn would keep the previous tab's colours."""
    b = new_board(mod, out)
    b.mode = getattr(mod, mode)
    claimed = {r for rows in mod.TAB_ROWS[b.mode].values() for r in rows}
    assert painted(b, mod, out) == claimed | {mod.FUNC_ROW}


def test_pressing_the_day_bar_on_the_pomodoro_tab_starts_nothing(mod, out):
    """It used to be pomodoro row 1: every pad of it was a live gesture."""
    b = new_board(mod, out)
    b.mode = mod.M_POMO
    for c in range(mod.CELLS):
        b.press(mod.pad(mod.BAR_ROW, c))
        b.release(mod.pad(mod.BAR_ROW, c))
    assert mod.BAR_ROW not in b.rows
    assert all(st['state'] == mod.IDLE for st in b.rows.values())
    assert b.todo == mod.blank_todo()


def test_the_bar_is_read_only_on_every_tab_that_has_one(mod, out):
    for tab in mod.BARS:
        b = new_board(mod, out)
        b.mode = tab
        before = (dict(b.rows), list(b.todo), dict(b.habits))
        b.press(mod.pad(mod.BAR_ROW, 0))
        b.release(mod.pad(mod.BAR_ROW, 0))
        assert (b.rows, list(b.todo), b.habits) == before
        assert b._editing is None
