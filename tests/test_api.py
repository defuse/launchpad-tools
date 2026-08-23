"""Every entry point exists and survives being called.

Twice a hand-patch has deleted a method while rewriting the one next to it. The
file stayed valid Python and only blew up when that pad was pressed, hours
later. These tests name every public method explicitly so a deletion fails here
instead of on the hardware.
"""
import inspect
import pytest
from lpharness import FakeOut, new_board

BOARD_API = [
    'clear', 'cpu_usage', 'cycle_state', 'edit_habit', 'flash', 'habit',
    'habit_table', 'held_since', 'load', 'mem_usage', 'net_iface', 'net_rates',
    'pomo_press', 'press', 'rc', 'release', 'render', 'render_habits',
    'render_net', 'render_sys', 'reset', 'save', 'set', 'set_habit', 'tick',
    '_flush', '_flush_if_dirty', '_popup_cmd', '_popup_reader',
    '_popup_send_table', '_start_popup', '_writer',
]

GRID_API = [
    'cancel', 'cycle_state', 'drag_drop', 'drag_start', 'emit', 'finish', 'get',
    'handle', 'key', 'kill_ghost', 'move_ghost', 'name_typed', 'paint',
    'pull_names', 'put', 'run', 'save', 'set_colour', 'set_focus',
]

MODULE_API = ['pad', 'ding', 'main', 'Board']


@pytest.mark.parametrize('name', BOARD_API)
def test_board_method_exists(mod, name):
    assert callable(getattr(mod.Board, name, None)), f'Board.{name} has gone missing'


@pytest.mark.parametrize('name', GRID_API)
def test_grid_method_exists(popup, name):
    assert callable(getattr(popup.Grid, name, None)), f'Grid.{name} has gone missing'


@pytest.mark.parametrize('name', MODULE_API)
def test_module_symbol_exists(mod, name):
    assert getattr(mod, name, None) is not None


def test_board_property_habits(mod):
    assert isinstance(inspect.getattr_static(mod.Board, 'habits'), property)


@pytest.mark.parametrize('mode', ['M_POMO', 'M_HAB', 'M_HAB2', 'M_SYS', 'M_NET'])
def test_tick_and_render_survive_every_mode(mod, mode, clock):
    b = new_board(mod, FakeOut())
    b.mode = getattr(mod, mode)
    for _ in range(3):
        b.tick(); b.render(); clock.advance(0.05)


@pytest.mark.parametrize('mode', ['M_POMO', 'M_HAB', 'M_HAB2', 'M_SYS', 'M_NET'])
def test_every_pad_can_be_pressed_and_released_in_every_mode(mod, mode, clock):
    b = new_board(mod, FakeOut())
    b.mode = getattr(mod, mode)
    for lr in range(8):
        for lc in range(8):
            note = mod.pad(lr, lc)
            b.press(note)
            b.mode = getattr(mod, mode)      # a tab press changes it; put it back
            b.tick(); b.render()
            b.release(note)
            clock.advance(0.01)
    assert b.held == {}


def test_helpers_run(mod, clock):
    b = new_board(mod, FakeOut())
    assert b.rc(mod.pad(3, 4)) == (3, 4)
    assert b.rc(99) is None
    assert mod.pad(0, 0) == 81 and mod.pad(7, 7) == 18
    b.flash(mod.pad(1, 1), mod.GREEN)
    b.clear()
    b.save()
    assert isinstance(b.cpu_usage(), dict)
    assert len(b.mem_usage()) == 3
    assert isinstance(b.net_iface(), str)
    assert len(b.net_rates()) == 2
    assert b.held_since(mod.pad(1, 0)) is None


def test_ding_is_a_no_op_without_a_player(state_file, clock):
    from lpharness import load_pomodoro
    m = load_pomodoro(state_file, clock)
    m.ding('nope.wav')                            # the harness records instead
    assert m.dings == [(clock.time(), 'nope.wav')]
