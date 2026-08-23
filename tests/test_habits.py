"""Habit tables: cycling, per-tab isolation, and the popup command stream."""
import json
import pytest
from lpharness import FakeOut, new_board


def sent(board):
    return board._popup.sent() if board._popup else []


def cmds(board, kind):
    return [l for l in sent(board) if l.split('\t')[0] == kind]


@pytest.fixture
def hb(board, mod):
    board.mode = mod.M_HAB
    board.habit_sets['1'] = {'2,0': {'name': 'medication', 'colour': 37, 'state': 0},
                             '3,1': {'name': 'shower', 'colour': 13, 'state': 0}}
    board.habit_sets['2'] = {'2,0': {'name': 'gym', 'colour': 33, 'state': 0}}
    board._popup_mode = mod.M_HAB
    return board


def test_habit_lookup_defaults(hb, mod):
    assert hb.habit(9, 9) == {'name': '', 'colour': mod.WHITE, 'state': 0}
    assert hb.habit(2, 0)['name'] == 'medication'


def test_cycle_state_walks_the_three_states(hb, mod):
    for expected in (1, 2, 0, 1):
        hb.cycle_state(2, 0)
        assert hb.habit(2, 0)['state'] == expected
    assert hb._dirty is True


def test_cycle_state_ignores_empty_cells(hb):
    hb.cycle_state(7, 7)
    assert hb.habit(7, 7)['state'] == 0
    assert '7,7' not in hb.habits


def test_set_habit_with_neither_a_name_nor_a_colour_deletes(hb, mod):
    hb.set_habit(2, 0, {'name': '', 'colour': mod.WHITE, 'state': 0})
    assert '2,0' not in hb.habits


def test_a_colour_outlives_the_name(hb, mod):
    """Clearing the name to retype it used to throw the colour away with it,
    so a habit renamed this way came back white."""
    hb.set_habit(2, 0, {'name': '', 'colour': mod.CYAN, 'state': 0})
    assert hb.habits['2,0'] == {'name': '', 'colour': mod.CYAN, 'state': 0}


def test_a_nameless_habit_lights_nothing(hb, mod):
    """It is kept for its colour, not because it is a habit. The pad is dark
    until it has a name -- otherwise a cleared cell would still be lit."""
    hb.set_habit(2, 0, {'name': '', 'colour': mod.CYAN, 'state': 2})
    hb.mode = mod.M_HAB
    hb.shown.clear()
    hb.render()
    assert hb.shown[mod.pad(2, 0)][1] == mod.OFF


def test_clearing_a_name_clears_the_state_with_it(hb, mod):
    """Otherwise the next habit typed into that cell arrives already done."""
    hb.set_habit(2, 0, {'name': '', 'colour': mod.CYAN, 'state': 2})
    assert hb.habits['2,0']['state'] == 0


def test_a_nameless_habit_cannot_be_cycled(hb, mod):
    """There is nothing to be in progress."""
    hb.set_habit(2, 0, {'name': '', 'colour': mod.CYAN, 'state': 0})
    hb.cycle_state(2, 0)
    assert hb.habits['2,0']['state'] == 0


def test_habit_tabs_are_independent(hb, mod):
    hb.cycle_state(2, 0)
    assert hb.habit_sets['1']['2,0']['state'] == 1
    assert hb.habit_sets['2']['2,0']['state'] == 0
    hb.mode = mod.M_HAB2
    assert hb.habit(2, 0)['name'] == 'gym'


def test_habits_is_empty_off_a_habit_tab(hb, mod):
    hb.mode = mod.M_POMO
    assert hb.habits == {}
    hb.mode = mod.M_SYS
    assert hb.habits == {}
    assert set(hb.habit_sets) == {'1', '2'}, 'must not invent a table for a non-habit tab'


def test_hold_cycles_once_per_second(hb, mod, clock):
    note = mod.pad(2, 0)
    hb.press(note)
    for expected in (0, 1, 2, 0):
        hb.tick()
        assert hb.habit(2, 0)['state'] == expected
        clock.advance(mod.HOLD_CYCLE)


def test_a_hold_does_not_also_count_as_a_click(hb, mod, clock):
    note = mod.pad(2, 0)
    hb.press(note)
    clock.advance(mod.HOLD_CYCLE + 0.1)
    hb.tick()
    hb._popup.lines.clear()
    hb.release(note)
    assert cmds(hb, 'edit') == [], 'a hold must not open the window on release'


def test_a_click_opens_the_window_on_that_cell(hb, mod, clock):
    note = mod.pad(2, 0)
    hb.press(note); clock.advance(0.1); hb.release(note)
    assert hb._editing == (2, 0)
    assert cmds(hb, 'edit') == ['edit\t2\t0']


def test_a_click_elsewhere_moves_the_selection(hb, mod, clock):
    hb.press(mod.pad(2, 0)); hb.release(mod.pad(2, 0))
    hb._popup.lines.clear()
    hb.press(mod.pad(3, 1)); hb.release(mod.pad(3, 1))
    assert hb._editing == (3, 1)
    assert cmds(hb, 'focus') == ['focus\t3\t1']


def test_clicking_the_selected_cell_again_leaves_it_alone(hb, mod):
    hb.press(mod.pad(2, 0)); hb.release(mod.pad(2, 0))
    hb._popup.lines.clear()
    hb.press(mod.pad(2, 0)); hb.release(mod.pad(2, 0))
    assert hb._editing == (2, 0)
    assert sent(hb) == []


def test_switching_habit_tabs_reloads_the_window(hb, mod):
    hb.press(mod.pad(2, 0)); hb.release(mod.pad(2, 0))
    hb._popup.lines.clear()
    hb.press(mod.pad(mod.FUNC_ROW, mod.M_HAB2))
    assert hb.mode == mod.M_HAB2 and hb._popup_mode == mod.M_HAB2
    loads = cmds(hb, 'load')
    assert len(loads) == 1
    assert json.loads(loads[0].split('\t', 1)[1])['2,0']['name'] == 'gym'


def test_leaving_the_habit_tabs_hides_the_window(hb, mod):
    hb.press(mod.pad(2, 0)); hb.release(mod.pad(2, 0))
    hb._popup.lines.clear()
    hb.press(mod.pad(mod.FUNC_ROW, mod.M_SYS))
    assert cmds(hb, 'hide') == ['hide']
    assert hb._editing is None


def test_render_colours_by_state(hb, mod, out):
    hb.habit_sets['1']['2,0']['state'] = 0
    hb.habit_sets['1']['3,1']['state'] = 1
    hb.habit_sets['1']['4,2'] = {'name': 'x', 'colour': 9, 'state': 2}
    hb.render()
    lit = out.lit()
    assert lit[mod.pad(2, 0)] == 37          # unstarted: the habit's own colour
    assert lit[mod.pad(3, 1)] == mod.RED     # started
    assert lit[mod.pad(4, 2)] == mod.GREEN   # complete
    assert lit[mod.pad(7, 7)] == mod.OFF     # nameless cells do not exist


def test_reset_repaints_the_window(hb, mod):
    hb.habit_sets['1']['2,0']['state'] = 2
    hb._popup.lines.clear()
    hb.reset()
    payload = json.loads(cmds(hb, 'data')[-1].split('\t', 1)[1])
    assert payload['2,0']['state'] == 0, 'the window must be told about the reset'


def test_in_progress_habit_flashes_between_red_and_its_own_colour(board, mod, clock):
    """State 1 alternates so a started habit is the only thing that moves, and
    still shows which habit it is."""
    board.mode = mod.M_HAB
    board.habit_sets[str(mod.M_HAB)]['2,0'] = {'name': 'x', 'colour': mod.CYAN, 'state': 1}
    seen = set()
    for i in range(8):
        clock.advance(mod.HAB_FLASH)
        board.shown.clear()                      # defeat the paint-once cache
        board.render()
        seen.add(board.shown[mod.pad(2, 0)][1])
    assert seen == {mod.RED, mod.CYAN}


def test_unstarted_and_complete_habits_do_not_flash(board, mod, clock):
    board.mode = mod.M_HAB
    board.habit_sets[str(mod.M_HAB)]['2,0'] = {'name': 'x', 'colour': mod.CYAN, 'state': 0}
    board.habit_sets[str(mod.M_HAB)]['2,1'] = {'name': 'y', 'colour': mod.CYAN, 'state': 2}
    for i in range(6):
        clock.advance(mod.HAB_FLASH)
        board.shown.clear(); board.render()
        assert board.shown[mod.pad(2, 0)][1] == mod.CYAN
        assert board.shown[mod.pad(2, 1)][1] == mod.GREEN


# ---- selection happens on the way down -------------------------------------

def test_pressing_a_habit_selects_it_before_release(hb, mod):
    """Holding a pad cycles it immediately, so selection must not wait for the
    release -- otherwise you watch one cell change while another stays lit."""
    hb.press(mod.pad(3, 2))
    assert hb._editing == (3, 2)
    assert any(c.startswith('edit\t3\t2') for c in cmds(hb, 'edit')), sent(hb)


def test_moving_the_selection_happens_on_press(hb, mod):
    hb.press(mod.pad(3, 2)); hb.release(mod.pad(3, 2))
    hb.press(mod.pad(5, 1))
    assert hb._editing == (5, 1)
    assert any(c.startswith('focus\t5\t1') for c in cmds(hb, 'focus')), sent(hb)


def test_holding_an_unselected_habit_selects_and_cycles_it(hb, mod, clock):
    hb.press(mod.pad(2, 0))
    assert hb._editing == (2, 0), 'selected on the way down'
    clock.advance(mod.HOLD_CYCLE + 0.05); hb.tick()
    assert hb.habit(2, 0)['state'] == 1
    hb.release(mod.pad(2, 0))
    assert hb._editing == (2, 0), 'still selected after release'


def test_releasing_a_habit_pad_changes_nothing_further(hb, mod):
    hb.press(mod.pad(2, 0))
    before = len(sent(hb))
    hb.release(mod.pad(2, 0))
    assert len(sent(hb)) == before, 'release is not a gesture of its own'
    assert hb._editing == (2, 0)
