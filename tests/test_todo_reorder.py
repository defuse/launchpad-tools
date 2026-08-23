"""Reordering the todo list, with the board and the window both real.

The window shows the list and the board owns it, and every one of the bugs
here came from those two disagreeing about a slot: a name displayed in a box
whose slot no longer holds it, a colour that moved while the text stayed, a
name written back to the wrong slot. So these tests run the real Window
against the real Board and pass the lines between them, then check the whole
list -- not the slot that was dragged.

Needs an X display; run-tests starts a private Xvfb. NEVER :0.
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
ABC = ['a', 'b', 'c', '', '', '', '', '']


class Wire:
    """A board and a window, wired to each other the way the pipes do it."""

    def __init__(self, board, mod, win):
        self.board, self.mod, self.win = board, mod, win
        self.outbox = []
        win.mod.say = self.outbox.append          # the window's stdout
        self.cursor = 0                           # of the board's stdin

    def pump(self, rounds=6):
        """Deliver everything each end has said, until they both go quiet."""
        for _ in range(rounds):
            busy = False
            lines = self.board._pomo_popup.sent()
            while self.cursor < len(lines):
                self.win.handle(lines[self.cursor])
                self.cursor += 1
                busy = True
            self.win.root.update()
            if self.outbox:
                batch, self.outbox[:] = list(self.outbox), []
                self.board._pomo_popup.stdout = iter(l + '\n' for l in batch)
                self.board._pomo_reader()
                busy = True
            if not busy:
                return

    # ---- what is on screen ------------------------------------------------
    def shown(self):
        return [self.win.entries[c].get('1.0', 'end-1c') for c in range(8)]

    def held(self):
        return [s['name'] for s in self.board.todo]

    def states(self):
        return [s['state'] for s in self.board.todo]

    # ---- gestures ---------------------------------------------------------
    def drag(self, src, dst):
        f = self.win.slots[dst]
        self.win.root.update_idletasks()
        x, y = f.winfo_rootx() + 6, f.winfo_rooty() + 6
        self.win.grab(src, types.SimpleNamespace(x_root=0, y_root=0,
                                                 widget=self.win.heads[src]))
        self.win.drag(types.SimpleNamespace(x_root=x, y_root=y), src)
        self.win.drop(types.SimpleNamespace(x_root=x, y_root=y))
        self.pump()

    def type_into(self, col, text):
        box = self.win.entries[col]
        box.focus_set()
        box.delete('1.0', 'end')
        box.insert('1.0', text)
        self.win.root.update()
        box.event_generate('<KeyRelease>')
        self.win.root.update()
        self.pump()


@pytest.fixture
def wire(board, mod, clock):
    win_mod = types.ModuleType('pomo_popup_wired')
    win_mod.__file__ = PPOPUP
    win_mod.__dict__['__name__'] = 'pomo_popup_wired'
    exec(compile(open(PPOPUP).read(), PPOPUP, 'exec'), win_mod.__dict__)
    win_mod.g9_centre_box = lambda: (1800, 900, 0, 0)
    try:
        w = win_mod.Window()
    except tk.TclError as e:                                       # pragma: no cover
        pytest.skip(f'cannot open a window: {e}')
    w.mod = win_mod
    board.mode = mod.M_POMO
    board.toggle_window()                       # spawns the popup and shows it
    wire = Wire(board, mod, w)
    wire.pump()
    yield wire
    try:
        w.root.destroy()
    except Exception:
        pass


def fill(wire, names=ABC):
    for c, n in enumerate(names):
        if n:
            wire.board.todo[c]['name'] = n
    wire.board._pomo_send()
    wire.pump()


# ---- the list itself ------------------------------------------------------

@pytest.mark.parametrize('src,dst', [(s, d) for s in range(8) for d in range(8)])
def test_a_drag_moves_exactly_one_slot(wire, mod, src, dst):
    """Every pair of ends, checked against the whole list. A drag that copies
    instead of moving shows up here as a duplicate."""
    fill(wire, list('abcdefgh'))
    want = [s['name'] for s in mod.move_todo(wire.board.todo, src, dst)]
    wire.drag(src, dst)
    assert wire.held() == want
    assert sorted(wire.held()) == list('abcdefgh'), 'nothing lost, nothing copied'


@pytest.mark.parametrize('src,dst', [(s, d) for s in range(8) for d in range(8)])
def test_the_window_shows_what_the_board_holds(wire, mod, src, dst):
    fill(wire, list('abcdefgh'))
    wire.drag(src, dst)
    assert wire.shown() == wire.held()


def test_a_drag_while_a_box_has_focus_still_moves_only_one(wire, mod):
    """a, b, c and a drag left a, c, c: the box being typed in was never
    repainted, so it kept showing a name that had moved away -- and the next
    keystroke wrote that stale name back over the slot's real one."""
    fill(wire)
    wire.win.entries[2].focus_set()
    wire.win.root.update()
    wire.drag(2, 1)
    assert wire.held() == ['a', 'c', 'b', '', '', '', '', '']
    assert wire.shown() == wire.held()


def test_typing_after_a_move_writes_the_slot_it_is_in(wire):
    """The stale name got written back on the next keystroke, making the
    duplicate permanent."""
    fill(wire)
    wire.win.entries[2].focus_set()
    wire.win.root.update()
    wire.drag(2, 1)
    wire.win.entries[2].event_generate('<KeyRelease>')
    wire.win.root.update()
    wire.pump()
    assert wire.held() == ['a', 'c', 'b', '', '', '', '', '']


def test_an_empty_slot_never_shows_the_last_name_it_held(wire):
    """Dragging a nameless slot over a named one left the old name sitting
    there in the grey of an empty box."""
    fill(wire)
    wire.win.entries[5].focus_set()             # a nameless slot, clicked into
    wire.win.root.update()
    wire.drag(0, 5)
    assert wire.shown() == wire.held()
    assert wire.shown()[5] == 'a' and wire.shown()[0] == 'b'


def test_the_text_and_its_colour_always_agree(wire, mod):
    """Grey is what an empty box looks like. A box showing a name in grey is
    showing a name that is not there any more."""
    fill(wire)
    wire.win.entries[1].focus_set()
    wire.drag(1, 6)
    for c in range(8):
        box = wire.win.entries[c]
        text = box.get('1.0', 'end-1c')
        want = wire.win.mod.WHITE if text else wire.win.mod.MUTED
        assert box.cget('fg') == want, f'slot {c} shows {text!r} in {box.cget("fg")}'


def test_a_slot_carries_its_state_across_the_wire(wire, mod):
    fill(wire)
    for c, st in enumerate([1, 2, 0, 1, 2, 0, 1, 2]):
        wire.board.todo[c]['state'] = st
    wire.board._pomo_send()
    wire.pump()
    wire.drag(0, 3)
    assert wire.states() == [2, 0, 1, 1, 2, 0, 1, 2]
    assert wire.held() == ['b', 'c', '', 'a', '', '', '', '']


def test_the_board_is_what_the_window_ends_up_agreeing_with(wire):
    """A round of gestures, then both ends compared. The window keeps its own
    copy so a drag looks instant; this is the check that it converges."""
    fill(wire, list('abcdefgh'))
    wire.drag(0, 7)
    wire.drag(3, 1)
    wire.drag(6, 6)
    wire.drag(7, 0)
    assert wire.shown() == wire.held()
    assert sorted(wire.held()) == list('abcdefgh')


def test_typing_into_a_box_is_not_undone_by_the_echo(wire):
    """The board normalises a name and sends it back; rewriting the box under
    the cursor is what this guard is for, and it has to survive the fix."""
    fill(wire)
    box = wire.win.entries[3]
    wire.type_into(3, 'two   spaces')
    box.mark_set('insert', 'end')
    wire.board._pomo_send()
    wire.pump()
    assert box.index('insert') != '1.0', 'the cursor was thrown to the start'
    assert wire.held()[3] == 'two spaces'


# ---- frames that were already in flight ----------------------------------

def last_frame(wire):
    return [l for l in wire.board._pomo_popup.sent() if l.startswith('data\t')][-1]


def test_a_frame_in_flight_does_not_clobber_what_you_just_typed(wire):
    """The board renders on its own clock, and with a timer running the cells
    change every second, so a frame is nearly always on its way. One built
    before it read your keystroke carries the name from before it."""
    fill(wire)
    stale = last_frame(wire)
    box = wire.win.entries[0]
    box.focus_set()
    box.delete('1.0', 'end')
    box.insert('1.0', 'abc')
    box.mark_set('insert', 'end')
    box.event_generate('<KeyRelease>')
    wire.win.root.update()
    wire.win.handle(stale)                      # arrives after, was built before
    wire.win.root.update()
    assert box.get('1.0', 'end-1c') == 'abc', 'the typing was undone'
    assert box.index('insert') != '1.0'
    wire.pump()
    assert wire.held()[0] == 'abc'


def test_the_stale_frame_does_not_get_typed_back_to_the_board(wire):
    """The real damage: the box is clobbered, and the next keystroke sends
    what is left in it, so the board loses the name too."""
    fill(wire)
    stale = last_frame(wire)
    box = wire.win.entries[0]
    box.focus_set()
    box.delete('1.0', 'end')
    box.insert('1.0', 'abc')
    box.event_generate('<KeyRelease>')
    wire.win.root.update()
    wire.win.handle(stale)
    wire.win.root.update()
    box.insert('insert', 'd')
    box.event_generate('<KeyRelease>')
    wire.win.root.update()
    wire.pump()
    assert wire.held()[0].startswith('abc')


def test_a_frame_in_flight_does_not_undo_a_drag(wire):
    """Same race, for the gesture that reorders rather than renames."""
    fill(wire, list('abcdefgh'))
    stale = last_frame(wire)
    wire.win.grab(0, types.SimpleNamespace(x_root=0, y_root=0,
                                           widget=wire.win.heads[0]))
    wire.win.drag(types.SimpleNamespace(x_root=400, y_root=0), 0)
    f = wire.win.slots[3]
    wire.win.root.update_idletasks()
    wire.win.drop(types.SimpleNamespace(x_root=f.winfo_rootx() + 6,
                                        y_root=f.winfo_rooty() + 6))
    wire.win.handle(stale)                      # built before the move
    wire.win.root.update()
    assert wire.shown() == list('bcdaefgh'), 'the drag was undone on screen'
    wire.pump()
    assert wire.held() == list('bcdaefgh')
    assert wire.shown() == wire.held()


def test_once_the_board_has_caught_up_its_frames_are_taken_again(wire):
    """Ignoring stale frames must not turn into ignoring frames. A state
    cycled on the pad has to reach the window."""
    fill(wire)
    box = wire.win.entries[0]
    box.focus_set()
    box.delete('1.0', 'end')
    box.insert('1.0', 'abc')
    box.event_generate('<KeyRelease>')
    wire.win.root.update()
    wire.pump()
    wire.board.todo[4]['state'] = 2             # as a pad press would
    wire.board._pomo_send()
    wire.pump()
    assert wire.win.todo[4]['state'] == 2
    assert wire.held()[0] == 'abc'


# ---- a soak, with frames arriving late on purpose -------------------------

@pytest.mark.parametrize('seed', range(6))
def test_gestures_and_late_frames_in_any_order_converge(wire, seed):
    """Drags, typing, taps and clear, mixed with frames delivered a beat after
    the edit that overtook them. Whatever the order, the two ends agree at the
    end and nothing has been copied or lost along the way."""
    import random
    rng = random.Random(seed)
    fill(wire, list('abcdefgh'))
    held_back = []
    for _ in range(24):
        pick = rng.random()
        if pick < 0.05:
            held_back.append(last_frame(wire))         # a frame overtaken
        elif pick < 0.15 and held_back:
            wire.win.handle(held_back.pop(0))          # and delivered late
            wire.win.root.update()
        elif pick < 0.55:
            wire.drag(rng.randrange(8), rng.randrange(8))
        elif pick < 0.8:
            wire.type_into(rng.randrange(8), rng.choice(['x', 'yy', '', 'a  b']))
        else:
            c = rng.randrange(8)
            wire.win.heads[c].event_generate('<Button-1>', x=4, y=4)
            wire.win.heads[c].event_generate('<ButtonRelease-1>', x=4, y=4)
            wire.win.root.update()
            wire.pump()
        assert len(wire.board.todo) == 8 and len(wire.win.todo) == 8
    for line in held_back:
        wire.win.handle(line)
    wire.win.root.update()
    wire.pump()
    wire.board._pomo_send()                            # one honest frame after
    wire.pump()
    assert wire.shown() == wire.held()
    assert [s['state'] for s in wire.win.todo] == wire.states()
