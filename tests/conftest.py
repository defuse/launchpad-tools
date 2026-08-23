import os, sys, json, pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lpharness import (FakeClock, FakeOut, FakePopen, FakeThread,   # noqa: F401
                       load_pomodoro, load_popup, new_board)


@pytest.fixture
def clock():
    return FakeClock(start=1_000_000.0)


@pytest.fixture
def state_file(tmp_path):
    """A state file inside tmp_path. The real one is never opened."""
    return tmp_path / 'launchpad-pomodoro.json'


@pytest.fixture
def mod(state_file, clock):
    m = load_pomodoro(state_file, clock)
    assert m.STATE_FILE == str(state_file), 'test would have used the real state file'
    return m


@pytest.fixture
def out():
    return FakeOut()


@pytest.fixture
def board(mod, out):
    return new_board(mod, out)


@pytest.fixture
def seed(state_file):
    """Write a state file before the Board is built."""
    def _seed(**blob):
        blob.setdefault('schema', 3)
        state_file.write_text(json.dumps(blob))
        return state_file
    return _seed


@pytest.fixture
def popup():
    """The habit-popup module, without opening Tk."""
    return load_popup()
