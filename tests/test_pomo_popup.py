"""The pomodoro window. Needs an X display.

run-tests starts a private Xvfb; under bare pytest with no DISPLAY these skip.
They must NEVER run on :0 -- that is the user's desktop.
"""
import json, os, sys, types
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
from lpharness import POMODORO                                     # noqa: E402

PPOPUP = os.path.join(os.path.dirname(os.path.dirname(POMODORO)), 'bin', 'pomo-popup')
NAMES = ['write tests', 'fix the subwoofer mute so it stops touching the speakers',
         'README', 'supercalifragilisticexpialidocious', '', 'short', '',
         'call the bank about the thing']


@pytest.fixture
def win(capsys):
    mod = types.ModuleType('pomo_popup_under_test')
    mod.__file__ = PPOPUP
    mod.__dict__['__name__'] = 'pomo_popup_under_test'
    exec(compile(open(PPOPUP).read(), PPOPUP, 'exec'), mod.__dict__)
    mod.g9_centre_box = lambda: (1800, 900, 0, 0)
    try:
        w = mod.Window()
    except tk.TclError as e:                                       # pragma: no cover
        pytest.skip(f'cannot open a window: {e}')
    w.mod = mod
    w.root.update()
    yield w
    try:
        w.root.destroy()
    except Exception:
        pass


def load(win, names=NAMES, rows=None, show=True):
    todo = [{'name': n, 'state': 0} for n in names]
    win.handle('data\t' + json.dumps({'rows': rows or [], 'todo': todo}))
    if show:
        win.handle('show')
    win.root.update()
    win.fit_slots()
    win.root.update()
    return todo


def lines(box):
    """Display lines the text takes. Tk's -displaylines counts the gaps
    BETWEEN two indices, so a box holding four lines answers three."""
    n = box.count('1.0', 'end - 1c', 'displaylines')
    return int((n[0] if isinstance(n, tuple) else n) or 0) + 1


def test_every_box_is_the_same_height(win):
    load(win)
    assert len({int(b.cget('height')) for b in win.entries.values()}) == 1


def test_and_that_height_shows_the_longest_item_whole(win):
    """No scrolling and no overflow: if it is in there, it is on screen."""
    load(win)
    need = max(lines(b) for b in win.entries.values())
    assert min(int(b.cget('height')) for b in win.entries.values()) >= need
    assert need > 1, 'the fixture has an item that has to wrap'


def test_nothing_is_scrolled_out_of_any_box(win):
    """The measurement above and the thing being measured share a function, so
    ask Tk the other question instead: is any of the text out of view? A box
    showing all it holds is scrolled to 0.0 and its view reaches 1.0."""
    load(win)
    for c, box in win.entries.items():
        assert box.yview() == (0.0, 1.0), f'slot {c} is hiding some of its text'


def test_nothing_is_scrolled_out_of_a_narrow_box(win):
    """Narrow enough that the longest item takes another line than it did."""
    win.root.geometry('1200x900')
    load(win)
    win.root.update()
    win.fit_slots()
    win.root.update()
    for c, box in win.entries.items():
        assert box.yview() == (0.0, 1.0), f'slot {c} is hiding some of its text'


def test_it_wraps_at_words(win):
    load(win)
    assert win.entries[1].cget('wrap') == 'word'
    assert lines(win.entries[1]) > 1


def test_a_word_too_long_to_fit_is_broken_anyway(win):
    """Tk breaks a word that cannot fit a line even in word mode, which is what
    keeps it from running off the side."""
    load(win, ['x' * 60] + [''] * 7)
    assert lines(win.entries[0]) > 1


def test_the_boxes_grow_as_you_type(win):
    load(win, [''] * 8)
    before = int(win.entries[0].cget('height'))
    win.entries[0].insert('1.0', 'a really quite long todo item that has to wrap')
    win.name_typed(0)
    win.root.update()
    assert int(win.entries[0].cget('height')) > before
    assert len({int(b.cget('height')) for b in win.entries.values()}) == 1


def test_return_does_not_add_a_line(win):
    """A name is one line of text; the box is multiline so it can wrap."""
    load(win, [''] * 8)
    win.entries[0].insert('1.0', 'one')
    win.entries[0].event_generate('<Return>')
    win.root.update()
    assert '\n' not in win.entries[0].get('1.0', 'end').strip()


def test_a_hidden_window_is_not_measured(win):
    """Tk answers None for a withdrawn window, which would size every box to
    one line and hide the rest of the text."""
    load(win, show=False)
    win.fit_slots()                                # must not blow up or shrink
    win.handle('show')
    win.root.update()
    win.fit_slots()
    assert max(int(b.cget('height')) for b in win.entries.values()) > 1


ROWS_ONE = [{'row': 2, 'name': 't1', 'state': 'idle', 'cells': ['#191920'] * 8}]


def test_typing_grows_the_box_line_by_line(win):
    """It scrolled instead of growing: the board echoes the name back and the
    repaint replaced the text under the cursor, which reset the view."""
    load(win, [''] * 8, rows=ROWS_ONE)
    box = win.entries[0]
    box.focus_set()
    win.root.update()
    text = ''
    for word in 'fix the subwoofer mute so it stops pulling the speakers'.split():
        text = (text + ' ' + word).strip()
        box.delete('1.0', 'end'); box.insert('1.0', text)
        win.name_typed(0)
        win.root.update()
        assert int(box.cget('height')) >= lines(box), f'scrolled at {text!r}'


def test_an_echo_does_not_move_the_cursor(win):
    load(win, [''] * 8, rows=ROWS_ONE)
    box = win.entries[0]
    box.focus_set(); box.insert('1.0', 'half typed'); win.root.update()
    box.mark_set('insert', 'end')
    win.handle('data\t' + json.dumps(
        {'rows': ROWS_ONE, 'todo': [{'name': 'half typed', 'state': 0}] + [{'name': '', 'state': 0}] * 7}))
    win.root.update()
    assert box.index('insert') != '1.0', 'the box being typed in was rewritten'


def test_a_data_frame_does_not_rebuild_the_widgets(win):
    """Rebuilding takes the text box out from under whoever is typing."""
    load(win, [''] * 8, rows=ROWS_ONE)
    before = win.entries[0]
    win.handle('data\t' + json.dumps({'rows': ROWS_ONE, 'todo': [{'name': 'x', 'state': 0}] * 8}))
    assert win.entries[0] is before


def test_the_names_are_in_a_fixed_pitch_font(win):
    load(win, rows=ROWS_ONE)
    assert 'Mono' in str(win.entries[0].cget('font'))


def test_a_wobble_while_clicking_is_still_a_click(win):
    """A hand moves a few pixels during a click; treating that as a drag meant
    taps on the handle went nowhere."""
    load(win, rows=ROWS_ONE)
    ev = types.SimpleNamespace(x_root=500, y_root=400, widget=win.slots[1])
    win.grab(1, ev)
    win.drag(types.SimpleNamespace(x_root=503, y_root=402), 1)
    assert not win.dragged, 'three pixels is not a drag'
    win.drag(types.SimpleNamespace(x_root=560, y_root=402), 1)
    assert win.dragged, 'sixty is'


def test_a_window_is_placed_when_it_is_shown(win):
    """Not once at construction: a slow xrandr there would leave it on
    whichever monitor the fallback lands on for the whole session."""
    seen = []
    win.mod.g9_centre_box = lambda: (seen.append(1), (900, 600, 40, 50))[1]
    win.handle('show')
    win.root.update()
    assert seen, 'show asked where to put itself'


def test_the_text_box_takes_no_gesture(win):
    """Dragging inside it is selecting text. It used to move the item as well,
    which loses the selection and the order in one motion."""
    load(win, rows=ROWS_ONE)
    for seq in ('<Button-1>', '<B1-Motion>', '<ButtonRelease-1>'):
        assert not win.entries[0].bind(seq), f'{seq} is the text box\'s own'


def test_selecting_text_does_not_reorder_the_list(win, capsys):
    """The gesture a hand makes to select a long name is exactly a drag."""
    todo = load(win, rows=ROWS_ONE)
    capsys.readouterr()
    box = win.entries[1]
    box.event_generate('<Button-1>', x=4, y=4)
    for x in (20, 60, 120):
        box.event_generate('<B1-Motion>', x=x, y=4)
    box.event_generate('<ButtonRelease-1>', x=120, y=4)
    win.root.update()
    assert 'move' not in capsys.readouterr().out
    assert [t['name'] for t in win.todo] == [t['name'] for t in todo]


def test_the_handle_still_drags(win, capsys):
    load(win, rows=ROWS_ONE)
    ev = types.SimpleNamespace(x_root=500, y_root=400, widget=win.slots[1])
    win.grab(1, ev)
    win.drag(types.SimpleNamespace(x_root=600, y_root=400), 1)
    assert win.dragged


def test_the_row_name_is_not_clipped(win):
    """width=8 fitted 'timer 1' and cut the length off the front of it."""
    rows = [{'row': 2, 'name': 'timer 1 (24 min)', 'state': 'idle',
             'cells': ['#191920'] * 8},
            {'row': 7, 'name': 'break (8 min)', 'state': 'idle',
             'cells': ['#191920'] * 8}]
    load(win, rows=rows)
    label = win.row_names[2]
    import tkinter.font as tkfont
    wide = tkfont.Font(root=win.root, font=label.cget('font')).measure(label.cget('text'))
    assert label.winfo_reqwidth() >= wide


def test_only_the_header_answers_to_a_click(win):
    """The margin around the text box is where a hand lands reaching for it.
    Cycling the state from there is a state change nobody asked for."""
    load(win, rows=ROWS_ONE)
    assert not win.slots[0].bind('<Button-1>'), 'the slot frame is not a button'
    assert win.heads[0].bind('<Button-1>'), 'its header is'


def test_the_state_colour_still_reaches_the_grip(win):
    """It sits one level deeper now, inside the header."""
    load(win, names=['x'] * 8, rows=ROWS_ONE)
    win.todo[0]['state'] = 2
    win.paint()
    win.root.update()
    bg = win.mod.STATE_BG[2]
    grip = win.heads[0].winfo_children()[0]
    assert win.slots[0].cget('bg') == bg
    assert win.heads[0].cget('bg') == bg
    assert grip.cget('bg') == bg


def test_clicking_the_header_still_presses(win, capsys):
    load(win, rows=ROWS_ONE)
    capsys.readouterr()
    win.heads[3].event_generate('<Button-1>', x=40, y=4)
    win.heads[3].event_generate('<ButtonRelease-1>', x=40, y=4)
    win.root.update()
    out = capsys.readouterr().out
    assert f'press\t{win.mod.TODO_ROW}\t3' in out


# ---- a row can say what each of its pads stands for -----------------------

BAR = [{'row': 1, 'name': 'time of day', 'state': 'bar',
        'cells': ['#5a7bff'] * 3 + ['#191920'] * 5,
        'labels': ['00–03', '03–06', '06–09', '09–12',
                   '12–15', '15–18', '18–21', '21–00']}]


def test_a_labelled_row_prints_its_labels_in_the_cells(win):
    load(win, rows=BAR)
    assert [c.cget('text') for c in win.row_caps[1]] == BAR[0]['labels']


def test_a_label_sits_on_the_colour_the_pad_is_showing(win):
    """It is a mirror: the cell is the pad's colour and the words are on it,
    not beside it."""
    load(win, rows=BAR)
    for c in range(8):
        assert win.row_caps[1][c].cget('bg') == BAR[0]['cells'][c]
        assert win.row_pads[1][c].cget('bg') == BAR[0]['cells'][c]


def test_the_ink_is_readable_on_whatever_the_cell_is(win):
    """A bar cell is deep blue most of the day and yellow, orange or red in
    the last hour. One fixed ink is unreadable on some of those."""
    dark = dict(BAR[0], cells=['#191920'] * 8)
    load(win, rows=[dark])
    assert win.row_caps[1][0].cget('fg') == '#c9c9d4'
    load(win, rows=[dict(BAR[0], cells=['#ffd21a'] * 8)])
    assert win.row_caps[1][0].cget('fg') == '#0d0d11', 'dark ink on yellow'


def test_an_unlabelled_cell_shows_nothing_at_all(win):
    """Not even a gap: the label is painted in the cell's own colour."""
    load(win, rows=ROWS_ONE)
    cap = win.row_caps[2][0]
    assert cap.cget('text') == ''
    assert cap.cget('fg') == cap.cget('bg')


def test_a_labelled_cell_is_still_the_pad(win, capsys):
    """The words are a child of the cell, and a child eats the clicks its
    parent was bound for unless it takes the same ones."""
    load(win, rows=BAR)
    capsys.readouterr()
    win.row_caps[1][4].event_generate('<Button-1>', x=2, y=2)
    win.root.update()
    assert 'press\t1\t4' in capsys.readouterr().out


RESET = [{'row': 0, 'name': 'reset', 'state': 'reset', 'live': [7],
          'cells': [None] * 7 + ['#ff4444']}]


def test_a_null_cell_is_no_pad_at_all(win):
    """As against a pad that is unlit and has a colour of its own: it takes the
    page's background and disappears."""
    load(win, rows=RESET)
    assert win.row_pads[0][0].cget('bg') == win.mod.BG
    assert win.row_pads[0][7].cget('bg') == '#ff4444'


def test_only_the_live_cells_of_a_row_are_buttons(win, capsys):
    """The other seven of that row are the tab strip, which this window is
    not, and a click landing on one would switch tabs."""
    load(win, rows=RESET)
    capsys.readouterr()
    for c in range(7):
        win.row_pads[0][c].event_generate('<Button-1>', x=4, y=4)
    win.root.update()
    assert capsys.readouterr().out == ''
    win.row_pads[0][7].event_generate('<Button-1>', x=4, y=4)
    win.root.update()
    assert 'press\t0\t7' in capsys.readouterr().out


def test_the_reset_hint_points_back_at_it(win):
    """It is the last cell of its row, so the hint goes to its right and points
    left -- the same way an elapsed row's claim hint does."""
    load(win, rows=RESET)
    assert win.row_hints[0].cget('text').startswith('←')
    assert win.row_lefts[0].cget('text') == ''


def test_the_labels_survive_a_repaint(win):
    load(win, rows=BAR)
    win.handle('data\t' + json.dumps({'rows': BAR, 'todo': win.todo}))
    win.root.update()
    assert win.row_caps[1][7].cget('text') == '21–00'
