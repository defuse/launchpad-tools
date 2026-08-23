"""The line protocol between the daemon and habit-popup, from both ends.

The daemon end is tested against a scripted popup stdout; the window end is
tested in test_grid_tk.py, which needs a display.
"""
import io, json, sys
import pytest
from lpharness import FakeOut, new_board


def feed(board, lines):
    """Run _popup_reader over a canned stdout."""
    board._popup.stdout = iter([l + '\n' for l in lines])
    board._popup_reader()


@pytest.fixture
def hb(board, mod):
    board.mode = board._popup_mode = mod.M_HAB
    board.habit_sets['1'] = {'2,0': {'name': 'medication', 'colour': 37, 'state': 1}}
    return board


# ---- daemon -> window ----------------------------------------------------

def test_startup_sends_the_habit_table_not_an_empty_one(mod, seed):
    seed(habit_sets={'1': {'2,0': {'name': 'a', 'colour': 3, 'state': 0}}, '2': {}})
    b = new_board(mod, FakeOut())
    assert b.mode == mod.M_POMO
    first = b._popup.sent()[0]
    kind, payload = first.split('\t', 1)
    assert kind == 'data'
    assert json.loads(payload)['2,0']['name'] == 'a', \
        'the window used to be handed {} whenever the board booted on another tab'


def test_every_command_is_one_line(hb, mod, clock):
    hb.press(mod.pad(2, 0)); clock.advance(0.1); hb.release(mod.pad(2, 0))
    hb.cycle_state(2, 0)
    hb.press(mod.pad(mod.FUNC_ROW, mod.M_HAB2))
    for line in hb._popup.lines:
        assert line.endswith('\n') and line.count('\n') == 1
        assert line.split('\t')[0] in ('data', 'load', 'edit', 'focus', 'hide')


def test_a_dead_popup_is_respawned(hb, mod):
    hb._popup.alive = False
    hb._popup_cmd('hide')
    from lpharness import FakePopen
    assert len(FakePopen.instances) == 2
    assert FakePopen.instances[-1].sent()[-1] == 'hide'


def test_a_broken_pipe_does_not_raise(hb):
    hb._popup.write_error = BrokenPipeError()
    hb._popup_cmd('hide')                       # must not propagate
    assert hb._popup is None


# ---- window -> daemon ----------------------------------------------------

def test_state_line_applies_to_the_habit(hb):
    feed(hb, ['state\t2\t0\t2'])
    assert hb.habit(2, 0)['state'] == 2
    assert hb._dirty is True


def test_state_line_is_ignored_for_an_empty_cell(hb):
    feed(hb, ['state\t7\t7\t2'])
    assert '7,7' not in hb.habits


def test_set_line_renames_and_recolours_keeping_state(hb):
    feed(hb, ['set\t2\t0\tmeds\t9'])
    assert hb.habit(2, 0) == {'name': 'meds', 'colour': 9, 'state': 1}


def test_set_line_with_an_empty_name_deletes(hb):
    feed(hb, ['set\t2\t0\t\t9'])
    assert '2,0' not in hb.habits


def test_a_placeholder_name_makes_the_habit_real(hb, mod):
    """The window's other half of the empty-cell colour fix: the board has to
    accept the name it invents, and light the pad in the colour that came with
    it."""
    feed(hb, ['set\t4\t4\tSET NAME HERE\t45'])
    assert hb.habit(4, 4) == {'name': 'SET NAME HERE', 'colour': 45, 'state': 0}
    hb.render()
    assert hb.out.lit()[mod.pad(4, 4)] == 45


def test_closed_line_ends_the_edit_session(hb, mod, clock):
    hb.press(mod.pad(2, 0)); clock.advance(0.1); hb.release(mod.pad(2, 0))
    assert hb._editing == (2, 0)
    feed(hb, ['closed'])
    assert hb._editing is None


def test_garbage_lines_do_not_kill_the_reader(hb, capsys):
    feed(hb, ['', 'nonsense', 'set\t2', 'state\tx\ty\tz', 'set\t2\t0\tkept\t9'])
    assert hb.habit(2, 0)['name'] == 'medication', 'reader stops at the first bad line'
    # ...but it must say so rather than dying in silence
    assert 'popup reader stopped' in capsys.readouterr().out


def test_an_edit_lands_on_the_tab_the_window_is_showing(hb, mod):
    """REGRESSION. self.habits follows the SELECTED tab. The reader runs on its
    own thread, so a set/state arriving just after the board changed tab used to
    be written into the wrong table -- or, off a habit tab, into a throwaway
    dict where it vanished without trace."""
    hb.mode = mod.M_POMO                        # board moved on; window still open
    feed(hb, ['set\t2\t0\tstill here\t9'])
    assert hb.habit_sets['1']['2,0']['name'] == 'still here'
    assert hb.habit_sets['2'] == {}
