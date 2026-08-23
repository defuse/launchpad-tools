"""Named regressions. Each one reproduces a bug that was actually observed.

The headline one: pomodoro timers reverting to idle on their own.
"""
import json
import pytest
from lpharness import FakeOut, new_board, load_pomodoro


def col0(mod, row):
    return mod.pad(row, 0)


# --------------------------------------------------------------------------
# The board reverting every timer to idle
# --------------------------------------------------------------------------

def test_habit_column_and_pomodoro_column_are_the_same_pads(mod):
    """The premise of the bug: they collide, by design.

    Both tabs gave their top row to the elapsed-time bar, so the rows that are
    left still overlap exactly as before.
    """
    shared = {mod.pad(r, 0) for r in mod.POMO_ROWS}
    habit  = {mod.pad(r, 0) for r in mod.HAB_ROWS}
    assert shared <= habit
    assert mod.BAR_ROW not in mod.POMO_ROWS + mod.HAB_ROWS


def test_holding_a_habit_then_tapping_the_pomodoro_tab_keeps_the_timers(mod, seed, clock):
    """THE PRIMARY BUG.

    The observed state file had every pomodoro row {state: idle, started: 0.0} after
    a restart that chimed -- so the rows had loaded as running, elapsed
    correctly, and were then wiped. Nobody touched the reset pad.

    self.held was keyed by MIDI note alone. Holding the morning-routine habits
    in column 0 (notes 71/61/51/41/31) and then tapping the pomodoro tab left
    those entries behind, and the very first pomodoro frame read them as
    'hold-to-abandon has been down for two seconds' on every row at once.
    """
    seed(mode=mod.M_HAB,
         rows={str(r): {'state': 'running', 'started': 900_000.0} for r in mod.POMO_ROWS},
         habit_sets={'1': {f'{r},0': {'name': f'h{r}', 'colour': 37, 'state': 0}
                           for r in mod.HAB_ROWS}, '2': {}})
    b = new_board(mod, FakeOut())

    b.tick()                                          # the chime the user hears
    assert [d[1] for d in mod.dings] == ['finish.wav'] * len(mod.POMO_ROWS)
    assert all(b.rows[r]['state'] == mod.ELAPSED for r in mod.POMO_ROWS)

    for r in mod.POMO_ROWS:                           # walk the routine column
        b.press(col0(mod, r))
    clock.advance(2.5)                                # holding cycles the habits
    b.tick()
    b.press(mod.pad(mod.FUNC_ROW, mod.M_POMO))        # ...then tap the pomodoro tab
    assert b.mode == mod.M_POMO

    b.render()
    assert all(b.rows[r]['state'] == mod.ELAPSED for r in mod.POMO_ROWS), \
        'a habit-tab press must never abandon a pomodoro row'

    b._flush()
    saved = json.loads((mod.STATE_FILE and open(mod.STATE_FILE).read()))['rows']
    # only the pomodoro rows were seeded; the break row is legitimately idle
    assert all(saved[str(r)]['state'] == 'elapsed' for r in mod.POMO_ROWS)


def test_one_stale_habit_press_cannot_abandon_one_row(mod, seed, clock):
    """The same bug in its smallest form: a single pad, a single row."""
    seed(mode=mod.M_HAB, rows={'2': {'state': 'running', 'started': 999_990.0}},
         habit_sets={'1': {'2,0': {'name': 'medication', 'colour': 37, 'state': 0}}, '2': {}})
    b = new_board(mod, FakeOut())
    b.press(mod.pad(2, 0))
    clock.advance(mod.RESET_HOLD + 1)
    b.mode = mod.M_POMO                               # tab changed under the finger
    b.render()
    assert b.rows[2]['state'] == mod.RUNNING


def test_a_never_released_habit_press_cannot_abandon_a_row(mod, seed, clock):
    """A dropped note-off leaves the entry in self.held for good. That must be
    harmless on every other tab, not a delayed-action timer killer."""
    seed(mode=mod.M_HAB, rows={'4': {'state': 'running', 'started': 999_990.0}})
    b = new_board(mod, FakeOut())
    b.press(mod.pad(4, 0))                            # note-off never arrives
    clock.advance(3600)
    b.press(mod.pad(mod.FUNC_ROW, mod.M_POMO))
    for _ in range(5):
        b.render(); clock.advance(0.05)
    assert b.rows[4]['state'] == mod.RUNNING


def test_the_reset_pad_cannot_carry_across_a_tab_change(mod, clock):
    """Start the 2 s reset hold on the habit tab, move to pomodoro mid-hold:
    the hold belongs to the tab it started on."""
    b = new_board(mod, FakeOut())
    b.mode = mod.M_HAB
    for r in mod.POMO_ROWS:
        b.rows[r] = {'state': mod.RUNNING, 'started': clock.time()}
    b.press(mod.pad(mod.FUNC_ROW, mod.RESET_COL))
    clock.advance(0.5)
    b.press(mod.pad(mod.FUNC_ROW, mod.M_POMO))
    clock.advance(mod.RESET_HOLD)
    b.render()
    assert all(b.rows[r]['state'] == mod.RUNNING for r in mod.POMO_ROWS)


def test_hold_to_abandon_still_works_on_its_own_tab(mod, clock):
    """The fix must not disable the feature."""
    b = new_board(mod, FakeOut())
    b.rows[3] = {'state': mod.RUNNING, 'started': clock.time()}
    b.press(mod.pad(3, 0))
    clock.advance(mod.RESET_HOLD + 0.1)
    b.render()
    assert b.rows[3] == {'state': mod.IDLE, 'started': 0.0}


def test_the_selected_tab_survives_a_restart(mod, seed, clock):
    """Second way the timers were lost: the tab was not persisted, so a restart
    put the board back on pomodoro while the user believed they were on habits.
    The next press aimed at a habit hit a pomodoro row, and on an elapsed row
    any pad but the last means 'failed' -- straight to idle."""
    seed(mode=mod.M_HAB,
         rows={'2': {'state': 'running', 'started': 900_000.0}},
         habit_sets={'1': {'2,0': {'name': 'medication', 'colour': 37, 'state': 0}}, '2': {}})
    b = new_board(mod, FakeOut())
    assert b.mode == mod.M_HAB
    b.tick()
    b.press(mod.pad(2, 0)); b.release(mod.pad(2, 0))
    assert b.rows[2]['state'] == mod.ELAPSED


def test_a_held_pad_does_not_cycle_habits_on_the_other_habit_tab(mod, clock):
    """Symmetric case: a pad held while switching between the two habit tabs
    must not start walking the states of whatever cell sits there."""
    b = new_board(mod, FakeOut())
    b.mode = b._popup_mode = mod.M_HAB
    b.habit_sets['1'] = {'2,0': {'name': 'daily', 'colour': 3, 'state': 0}}
    b.habit_sets['2'] = {'2,0': {'name': 'weekly', 'colour': 9, 'state': 0}}
    b.press(mod.pad(2, 0))
    b.press(mod.pad(mod.FUNC_ROW, mod.M_HAB2))
    clock.advance(5.0)
    b.tick()
    assert b.habit_sets['2']['2,0']['state'] == 0


# --------------------------------------------------------------------------
# Other regressions
# --------------------------------------------------------------------------

def test_a_frame_that_throws_does_not_stop_the_clock(mod, clock, monkeypatch):
    """main() catches per-frame errors; make sure tick() is what advances state
    so a broken renderer cannot stall a running pomodoro."""
    b = new_board(mod, FakeOut())
    b.rows[mod.POMO_ROWS[0]] = {'state': mod.RUNNING,
                                'started': clock.time() - 99_999}
    monkeypatch.setattr(b, 'render', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    b.tick()
    with pytest.raises(RuntimeError):
        b.render()
    assert b.rows[mod.POMO_ROWS[0]]['state'] == mod.ELAPSED


def test_hold_counter_does_not_leak_across_tabs(mod, clock):
    b = new_board(mod, FakeOut())
    b.mode = mod.M_HAB
    b.habit_sets['1'] = {'2,0': {'name': 'a', 'colour': 3, 'state': 0}}
    b.press(mod.pad(2, 0))
    clock.advance(1.5); b.tick()
    b.mode = mod.M_POMO
    b.release(mod.pad(2, 0))
    assert b._hold_count == {}, 'released on another tab, but still must be cleaned up'
    assert b.held == {}


def test_non_grid_notes_are_harmless(mod):
    b = new_board(mod, FakeOut())
    for note in (0, 9, 10, 19, 89, 99, 127):
        b.press(note); b.release(note)
    assert b.held == {}
