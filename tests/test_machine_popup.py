"""The machine readout window itself. Needs an X display.

run-tests starts a private Xvfb; under bare pytest with no DISPLAY these skip.
They must NEVER run on :0 -- that is the user's desktop.
"""
import json, os, sys
import pytest

pytestmark = pytest.mark.gui

DISPLAY = os.environ.get('DISPLAY', '')
if not DISPLAY:
    pytest.skip('no DISPLAY; window tests skipped', allow_module_level=True)
if DISPLAY.split('.')[0] in (':0', ':0.0'):
    pytest.skip('refusing to open windows on the live desktop (:0)',
                allow_module_level=True)

tk = pytest.importorskip('tkinter')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lpharness import POMODORO                                    # noqa: E402
import types                                                      # noqa: E402

MPOPUP = os.path.join(os.path.dirname(os.path.dirname(POMODORO)), 'bin', 'machine-popup')

CELLS = [{'r': 2, 'c': 1, 'name': 'sda', 'value': 'ok', 'colour': '#33d17a'},
         {'r': 4, 'c': 1, 'name': 'sda SSD', 'value': '31C', 'colour': '#a0d8ff'},
         {'r': 3, 'c': 2, 'name': 'root  8% free', 'value': '37 GB', 'colour': '#ffd21a'}]


@pytest.fixture
def grid():
    mod = types.ModuleType('machine_popup_under_test')
    mod.__file__ = MPOPUP
    mod.__dict__['__name__'] = 'machine_popup_under_test'
    exec(compile(open(MPOPUP).read(), MPOPUP, 'exec'), mod.__dict__)
    mod.g9_centre_box = lambda: (1200, 600, 0, 0)
    try:
        g = mod.Grid()
    except tk.TclError as e:                                      # pragma: no cover
        pytest.skip(f'cannot open a window: {e}')
    g.root.update()
    yield g
    try:
        g.root.destroy()
    except Exception:
        pass


def say(grid, *lines):
    for l in lines:
        grid.handle(l)
    grid.root.update()


def test_it_starts_hidden(grid):
    """A readout for a held pad has no business on screen before the press."""
    assert grid.root.state() == 'withdrawn'


def test_show_puts_the_values_in_their_own_columns(grid):
    say(grid, 'data\t' + json.dumps(CELLS), 'show\t2\t1')
    assert grid.root.state() != 'withdrawn'
    assert grid.values[(2, 1)].cget('text') == 'ok'
    assert grid.names[(4, 1)].cget('text') == 'sda SSD'
    assert grid.values[(3, 2)].cget('text') == '37 GB'
    assert grid.values[(2, 0)].cget('text') == '', 'empty columns stay empty'


def test_the_held_cell_is_the_marked_one(grid):
    say(grid, 'data\t' + json.dumps(CELLS), 'show\t4\t1')
    assert grid.focus_rc == (4, 1)
    assert grid.frames[(4, 1)].cget('highlightbackground') != \
        grid.frames[(2, 1)].cget('highlightbackground')


def test_the_value_carries_the_pad_colour(grid):
    say(grid, 'data\t' + json.dumps(CELLS), 'show\t2\t1')
    assert grid.values[(3, 2)].cget('fg') == '#ffd21a'
    assert grid.values[(2, 1)].cget('fg') == '#33d17a'


def test_hide_withdraws_it(grid):
    say(grid, 'data\t' + json.dumps(CELLS), 'show\t2\t1', 'hide')
    assert grid.root.state() == 'withdrawn'
    assert grid.focus_rc is None


# ---- the control row -----------------------------------------------------

CONTROLS = [{'r': 7, 'c': 0, 'name': 'speakers', 'value': 'in use',
             'detail': 'everything comes out here', 'colour': '#5a7bff'},
            {'r': 7, 'c': 1, 'name': 'headset', 'value': 'ready',
             'detail': 'press to switch to it', 'colour': '#e8e8e8'},
            {'r': 7, 'c': 4, 'name': 'effects', 'value': 'headphones',
             'detail': 'm50x', 'colour': '#ff8c1a'}]


def test_the_buttons_are_a_row_of_the_window(grid):
    say(grid, 'data\t' + json.dumps(CELLS + CONTROLS), 'show\t2\t1')
    assert grid.values[(7, 0)].cget('text') == 'in use'
    assert grid.names[(7, 4)].cget('text') == 'effects'
    assert grid.details[(7, 4)].cget('text') == 'm50x'
    assert grid.values[(7, 4)].cget('fg') == '#ff8c1a'


def test_the_row_is_named_in_the_gap_between_the_buttons(grid):
    """The gap in the middle of the control row is where the title goes -- the
    same rule as the readouts, which are centred and leave one."""
    say(grid, 'data\t' + json.dumps(CELLS + CONTROLS), 'show\t2\t1')
    assert grid.titles[(7, 2)].cget('text') == 'controls'
    assert grid.titles[(7, 0)].cget('text') == ''


def test_the_blank_row_is_blank(grid):
    """Row 6 is dark on the board. It is the gap between what the tab reports
    and what it does, and it is a gap here too rather than a row of cells."""
    assert (6, 0) not in grid.frames
    say(grid, 'data\t' + json.dumps(CELLS + CONTROLS), 'show\t2\t1')
    assert grid.root.state() != 'withdrawn'


def test_nothing_in_the_window_is_clickable(grid):
    """It is a readout. A second set of handlers for the same eight buttons is
    a second set to keep right, and the pads are where you press."""
    say(grid, 'data\t' + json.dumps(CELLS + CONTROLS), 'show\t2\t1')
    for (r, c), f in grid.frames.items():
        assert not f.bind('<Button-1>'), f'cell {r},{c} answers a click'
        for w in f.winfo_children():
            assert not w.bind('<Button-1>')


@pytest.mark.parametrize('line', ['', 'data', 'show', 'show\t2', 'nonsense',
                                  'data\tnot json', 'hide\textra'])
def test_a_bad_line_does_not_kill_it(grid, line):
    """One malformed line used to stop habit-popup listening for the rest of
    the session; the same pump is here."""
    try:
        grid.handle(line)
    except Exception:
        pass                                    # run() logs and carries on
    say(grid, 'data\t' + json.dumps(CELLS), 'show\t2\t1')
    assert grid.root.state() != 'withdrawn', 'still answering the board'
