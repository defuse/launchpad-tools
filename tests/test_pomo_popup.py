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
    n = box.count('1.0', 'end - 1c', 'displaylines')
    return (n[0] if isinstance(n, tuple) else n) or 1


def test_every_box_is_the_same_height(win):
    load(win)
    assert len({int(b.cget('height')) for b in win.entries.values()}) == 1


def test_and_that_height_shows_the_longest_item_whole(win):
    """No scrolling and no overflow: if it is in there, it is on screen."""
    load(win)
    need = max(lines(b) for b in win.entries.values())
    assert min(int(b.cget('height')) for b in win.entries.values()) >= need
    assert need > 1, 'the fixture has an item that has to wrap'


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
