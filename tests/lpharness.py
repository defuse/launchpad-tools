"""Load launchpad-pomodoro / habit-popup as importable modules, with all the
hardware, the filesystem, the clock and the popup subprocess replaced by stubs.

Nothing here may touch the real state file, the real MIDI device, the real
sound player or the user's display.
"""
import os, sys, types, threading, json
import time as _real_time

# Test the scripts sitting next to us in the checkout, not whatever happens to
# be installed -- otherwise a stale ~/.local/bin copy silently gets tested.
BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bin')
# LP_POMODORO / LP_POPUP point the suite at a copy of the scripts, which is how
# the regression tests were checked to actually fail against the old code.
POMODORO = os.environ.get('LP_POMODORO') or os.path.join(BIN, 'launchpad-pomodoro')
POPUP    = os.environ.get('LP_POPUP')    or os.path.join(BIN, 'habit-popup')


class FakeClock:
    """A clock the tests drive by hand. Never sleeps."""
    def __init__(self, start=1_000_000.0):
        self.now = float(start)
        self.slept = []
    def time(self):
        return self.now
    def sleep(self, s):
        self.slept.append(s)
        self.now += s
    def advance(self, s):
        self.now += s
        return self.now
    # a couple of names the module might reach for
    def monotonic(self):
        return self.now
    def localtime(self, t=None):
        """The wall clock the fake epoch corresponds to, in local time --
        the elapsed-time bars are defined against midnight, not an offset."""
        return _real_time.localtime(self.now if t is None else t)


class FakeThread:
    """Records what would have been started; never actually runs."""
    started = []
    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **kw):
        self.target, self.args = target, args or ()
        self.kwargs = kwargs or {}
        self.daemon = daemon
        self.did_start = False
    def start(self):
        self.did_start = True
        FakeThread.started.append(self)
    def join(self, timeout=None):
        pass
    def run(self):
        return self.target(*self.args, **self.kwargs)


class FakePopen:
    """Stands in for the habit-popup child process."""
    instances = []
    def __init__(self, argv, stdin=None, stdout=None, stderr=None,
                 text=None, env=None, bufsize=None, **kw):
        self.argv = list(argv)
        self.lines = []
        self.alive = True
        self.write_error = None
        self.stdin = self
        self.stdout = iter(())
        FakePopen.instances.append(self)
    # stdin side
    def write(self, s):
        if self.write_error:
            raise self.write_error
        self.lines.append(s)
    def flush(self):
        pass
    def poll(self):
        return None if self.alive else 1
    # convenience
    def sent(self):
        return [l.rstrip('\n') for l in self.lines]
    def last(self):
        return self.sent()[-1] if self.lines else None


class FakeMessage:
    def __init__(self, type=None, channel=0, note=0, velocity=0, data=None):
        self.type, self.channel, self.note = type, channel, note
        self.velocity, self.data = velocity, data
    def __repr__(self):
        return f'Message({self.type},n={self.note},v={self.velocity})'


class FakeOut:
    """A MIDI output port that just records."""
    def __init__(self):
        self.sent = []
    def send(self, msg):
        self.sent.append(msg)
    def lit(self):
        """note -> velocity, as the board would look right now."""
        out = {}
        for m in self.sent:
            if m.type == 'note_on':
                out[m.note] = m.velocity
        return out


def _fake_mido():
    return types.SimpleNamespace(
        Message=FakeMessage,
        get_output_names=lambda: [],
        get_input_names=lambda: [],
        open_output=lambda n: None,
        open_input=lambda n: None,
    )


def load_pomodoro(state_file, clock=None):
    """Exec launchpad-pomodoro into a private module namespace.

    Every global that reaches outside the process is replaced.
    """
    clock = clock or FakeClock()
    src = open(POMODORO).read()
    m = types.ModuleType('launchpad_pomodoro_under_test')
    m.__file__ = POMODORO
    code = compile(src, POMODORO, 'exec')
    m.__dict__['__name__'] = 'launchpad_pomodoro_under_test'   # skips main()
    exec(code, m.__dict__)

    # --- neuter everything that leaves the process -----------------------
    m.mido = _fake_mido()
    m.STATE_FILE = str(state_file)
    m.SOUND_DIR = os.path.join(os.path.dirname(str(state_file)), 'sounds')
    m.PLAYER = None                       # ding() becomes a no-op...
    m.time = clock                        # ...and the clock is ours
    m.threading = types.SimpleNamespace(Lock=threading.Lock, Thread=FakeThread,
                                        RLock=threading.RLock)
    m.subprocess = types.SimpleNamespace(Popen=FakePopen, DEVNULL=-3, PIPE=-1)
    m.clock = clock

    # record chimes instead of playing them
    m.dings = []
    m.ding = lambda name: m.dings.append((clock.time(), name))
    return m


def new_board(mod, out=None):
    FakeThread.started = []
    FakePopen.instances = []
    b = mod.Board(out or FakeOut())
    return b


def load_popup(name='habit-popup'):
    """Exec one of the window programs into a private module namespace.

    Only the top level runs -- the Tk window is built in Window()/Grid(), which
    is not called -- so this reaches a window's constants and pure functions
    from a test that has no display.
    """
    path = POPUP if name == 'habit-popup' else os.path.join(BIN, name)
    m = types.ModuleType(name.replace('-', '_') + '_under_test')
    m.__file__ = path
    m.__dict__['__name__'] = m.__name__
    exec(compile(open(path).read(), path, 'exec'), m.__dict__)
    return m
