"""The habit-popup window itself. Needs an X display.

run-tests starts a private Xvfb; run under bare pytest with no DISPLAY these
skip. They must NEVER run on :0 -- that is the user's desktop.
"""
import io, json, os, sys
import pytest

pytestmark = pytest.mark.gui

DISPLAY = os.environ.get('DISPLAY', '')
if not DISPLAY:
    pytest.skip('no DISPLAY; window tests skipped', allow_module_level=True)
if DISPLAY.split('.')[0] in (':0', ':0.0'):
    pytest.skip('refusing to open windows on the live desktop (:0)',
                allow_module_level=True)

tk = pytest.importorskip('tkinter')

HABITS = {'2,0': {'name': 'medication', 'colour': 37, 'state': 0},
          '3,1': {'name': 'shower',     'colour': 13, 'state': 0}}


class Emitted(list):
    """Captures what the window writes back to the daemon."""
    def lines(self, kind=None):
        return [l for l in self if kind is None or l.split('\t')[0] == kind]


@pytest.fixture
def grid(popup):
    popup.g9_centre_box = lambda: (1200, 800, 0, 0)
    try:
        g = popup.Grid()
    except tk.TclError as e:                       # pragma: no cover
        pytest.skip(f'cannot open a window: {e}')
    g.root.update()
    yield g
    try: g.root.destroy()
    except Exception: pass


@pytest.fixture
def say(grid):
    """Send the window a command and return everything it said back."""
    def _say(*lines):
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            for l in lines:
                grid.handle(l)
            grid.root.update()
        finally:
            sys.stdout = real
        return Emitted(buf.getvalue().splitlines())
    return _say


def click(w, t, x=60, y=40):
    rx, ry = w.winfo_rootx() + x, w.winfo_rooty() + y
    w.event_generate('<ButtonPress-1>',   x=x, y=y, rootx=rx, rooty=ry, time=t, when='now')
    w.event_generate('<ButtonRelease-1>', x=x, y=y, rootx=rx, rooty=ry, time=t + 8, when='now')


# ---- protocol ------------------------------------------------------------

def test_load_replaces_the_whole_table(grid, say):
    say('load\t' + json.dumps(HABITS))
    assert grid.habits == HABITS
    say('load\t' + json.dumps({'5,5': {'name': 'other', 'colour': 9, 'state': 0}}))
    assert list(grid.habits) == ['5,5'], 'load must not leave the previous tab behind'


def test_edit_shows_the_window_and_selects_the_cell(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    assert grid.mode == 'edit' and grid.focus_rc == (2, 0)
    assert grid.root.state() == 'normal'


def test_focus_moves_the_selection(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0', 'focus\t3\t1')
    assert grid.focus_rc == (3, 1)


def test_hide_withdraws_and_reports_closed(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    out = say('hide')
    assert out.lines('closed') == ['closed']
    assert grid.mode is None and grid.root.state() == 'withdrawn'


def test_data_merges_only_state_while_editing(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    grid.vars[(2, 0)].set('half typed name')
    incoming = json.loads(json.dumps(HABITS))
    incoming['2,0']['state'] = 2
    say('data\t' + json.dumps(incoming))
    assert grid.habits['2,0']['state'] == 2
    assert grid.habits['2,0']['name'] == 'half typed name', \
        'an echo from the board must not stamp on what is being typed'


def test_data_replaces_wholesale_when_not_editing(grid, say):
    say('data\t' + json.dumps(HABITS))
    say('data\t' + json.dumps({'1,1': {'name': 'x', 'colour': 3, 'state': 0}}))
    assert list(grid.habits) == ['1,1']


@pytest.mark.parametrize('line', ['', 'data', 'load', 'edit', 'edit\t2',
                                  'focus\t2', 'nonsense', 'data\tnot json',
                                  'show\t1'])
def test_malformed_commands_are_survivable(grid, say, line):
    """A short line used to throw out of handle(), out of pump(), and the
    window stopped listening to the board for the rest of the session."""
    say(line)
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    assert grid.mode == 'edit', 'the window must still be answering the board'


# ---- clicking ------------------------------------------------------------

def test_double_click_cycles_once(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    f = grid.frames[(2, 0)]
    out = say()
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        click(f, 10000); click(f, 10100)
        grid.root.update()
    finally:
        sys.stdout = real
    said = Emitted(buf.getvalue().splitlines()).lines('state')
    assert said == ['state\t2\t0\t1']
    assert grid.habits['2,0']['state'] == 1


def test_a_lone_click_does_not_cycle(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    f = grid.frames[(2, 0)]
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        for t in (10000, 12000, 14000, 16000):     # 2 s apart: four single clicks
            click(f, t)
        grid.root.update()
    finally:
        sys.stdout = real
    assert Emitted(buf.getvalue().splitlines()).lines('state') == []
    assert grid.habits['2,0']['state'] == 0


@pytest.mark.parametrize('n', [3, 4, 5, 8])
def test_extra_clicks_do_not_keep_cycling(grid, say, n):
    """REGRESSION: '<Double-Button-1>' was the most specific button binding, so
    Tk sent it every press with a click count of two OR MORE. Tk keeps counting
    while clicks stay within 500 ms and 5 px and then saturates, so after one
    double-click every further click cycled the habit again -- the reported
    'after a while a single click cycles it'."""
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    f = grid.frames[(2, 0)]
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        for i in range(n):
            click(f, 20000 + i * 100)              # a fast burst, same spot
        grid.root.update()
    finally:
        sys.stdout = real
    said = Emitted(buf.getvalue().splitlines()).lines('state')
    assert said == ['state\t2\t0\t1'], f'{n} rapid clicks cycled {len(said)} times'
    assert grid.habits['2,0']['state'] == 1


def test_cycling_wraps_and_only_named_cells_cycle(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        for expected in (1, 2, 0):
            grid.cycle_state(2, 0)
            assert grid.habits['2,0']['state'] == expected
        grid.cycle_state(7, 7)
    finally:
        sys.stdout = real
    assert '7,7' not in grid.habits


# ---- editing -------------------------------------------------------------

def test_typing_a_name_emits_it(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t4\t4')
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.vars[(4, 4)].set('new habit')
        grid.root.update()
    finally:
        sys.stdout = real
    assert Emitted(buf.getvalue().splitlines()).lines('set') == ['set\t4\t4\tnew habit\t3']


def test_a_name_with_a_tab_cannot_break_the_protocol(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t4\t4')
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.vars[(4, 4)].set('a\tb\nc')
        grid.root.update()
    finally:
        sys.stdout = real
    for line in Emitted(buf.getvalue().splitlines()).lines('set'):
        assert len(line.split('\t')) == 5


def test_clearing_a_name_deletes_the_habit(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.vars[(2, 0)].set('')
        grid.root.update()
    finally:
        sys.stdout = real
    assert '2,0' not in grid.habits


def test_set_colour_only_applies_while_editing(grid, say):
    say('load\t' + json.dumps(HABITS))
    grid.set_colour(2, 0, 45)
    assert grid.habits['2,0']['colour'] == 37
    say('edit\t2\t0')
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.set_colour(2, 0, 45)
    finally:
        sys.stdout = real
    assert grid.habits['2,0']['colour'] == 45


def capture(grid, fn):
    """Run fn() and return what the window wrote back to the board."""
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        fn()
        grid.root.update()
    finally:
        sys.stdout = real
    return Emitted(buf.getvalue().splitlines())


def test_colouring_an_empty_cell_turns_the_habit_on(grid, say, popup):
    """A colour on its own does not exist as far as the board is concerned: a
    cell with no name is a cell with no habit, and set_habit drops it. Picking
    a colour therefore has to name the habit as well, or the pick is silently
    thrown away."""
    say('load\t' + json.dumps(HABITS), 'edit\t4\t4')
    out = capture(grid, lambda: grid.set_colour(4, 4, 45))

    assert grid.habits['4,4'] == {'name': popup.PLACEHOLDER, 'colour': 45, 'state': 0}
    assert out.lines('set') == [f'set\t4\t4\t{popup.PLACEHOLDER}\t45']


def test_the_placeholder_name_shows_in_the_cell_to_be_typed_over(grid, say, popup):
    say('load\t' + json.dumps(HABITS), 'edit\t4\t4')
    capture(grid, lambda: grid.set_colour(4, 4, 45))
    assert grid.vars[(4, 4)].get() == popup.PLACEHOLDER


def test_colouring_a_cell_being_typed_into_keeps_what_was_typed(grid, say, popup):
    """The placeholder is for cells with nothing in them at all -- a half typed
    name must survive picking a colour for it."""
    say('load\t' + json.dumps(HABITS), 'edit\t4\t4')
    grid.vars[(4, 4)].set('half typed')
    capture(grid, lambda: grid.set_colour(4, 4, 45))
    assert grid.habits['4,4']['name'] == 'half typed'


def test_the_placeholder_is_a_real_name_the_board_will_keep(grid, say, popup):
    """Not a blank-looking string: whitespace would be stripped back to empty
    and dropped again by the board."""
    assert popup.PLACEHOLDER.strip() == popup.PLACEHOLDER
    assert popup.PLACEHOLDER


def test_painting_flag_is_released_even_if_paint_throws(grid, say, monkeypatch):
    """Stuck on, it made typing a habit name silently do nothing."""
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    monkeypatch.setattr(grid, '_paint', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    with pytest.raises(RuntimeError):
        grid.paint()
    assert grid._painting is False


# ---- drag to swap --------------------------------------------------------

def test_drag_swaps_two_cells(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    src, tgt = grid.frames[(2, 0)], grid.frames[(3, 1)]
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.drag_start(2, 0)
        ev = type('E', (), {'x_root': tgt.winfo_rootx() + 20,
                            'y_root': tgt.winfo_rooty() + 20})()
        grid.drag_drop(ev)
        grid.root.update()
    finally:
        sys.stdout = real
    assert grid.habits['2,0']['name'] == 'shower'
    assert grid.habits['3,1']['name'] == 'medication'
    assert Emitted(buf.getvalue().splitlines()).lines('set') != []
    assert grid.ghost is None and grid.drag_from is None


def test_dropping_on_nothing_leaves_the_table_alone(grid, say):
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    before = json.dumps(grid.habits, sort_keys=True)
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.drag_start(2, 0)
        ev = type('E', (), {'x_root': 5000, 'y_root': 5000})()
        grid.drag_drop(ev)
    finally:
        sys.stdout = real
    assert json.dumps(grid.habits, sort_keys=True) == before
    assert grid.ghost is None


def test_an_abandoned_drag_does_not_strand_the_ghost(grid, say):
    """kill_ghost() used to be skipped on the early return, leaving an
    override-redirect topmost window on screen with nothing to close it."""
    say('load\t' + json.dumps(HABITS), 'edit\t2\t0')
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        grid.drag_start(2, 0)
        assert grid.ghost is not None
        grid.mode = None                            # the board hid the window mid-drag
        grid.drag_drop(type('E', (), {'x_root': 0, 'y_root': 0})())
    finally:
        sys.stdout = real
    assert grid.ghost is None and grid.drag_from is None
