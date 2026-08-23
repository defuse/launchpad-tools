"""The audio spectrum tab.

No audio is captured here: pw-record is the harness's fake process, and the
sample window is written straight into the analyser.
"""
import math
import pytest
from lpharness import FakePopen, new_board

np = pytest.importorskip('numpy')


@pytest.fixture
def spec(board, mod):
    board.mode = mod.M_SPEC
    return board.spectrum


def captures():
    return [p.argv for p in FakePopen.instances if p.argv[0] == 'pw-record']


def tone(mod, hz, amplitude=0.5, samples=None):
    """One window of a pure tone, as pw-record would deliver it."""
    n = samples or mod.Spectrum.WINDOW
    t = np.arange(n) / mod.Spectrum.RATE
    return (amplitude * np.sin(2 * math.pi * hz * t)).astype(np.float32).tobytes()


def feed(spec, target, raw, now):
    """Start capture, hand it a window, and read the bands back."""
    spec.bands(target, now)                 # first call starts the capture
    spec.raw = raw
    return spec.bands(target, now)


# ---- capture lifecycle ---------------------------------------------------
def test_nothing_is_captured_until_the_tab_is_drawn(board, mod):
    """Sitting on the pomodoro tab should not cost a recording stream."""
    assert board.spectrum.proc is None
    assert captures() == []


def test_drawing_the_tab_starts_a_capture_of_the_current_output(spec, mod):
    spec.bands('game_stereo', 1000.0)
    assert captures() == [['pw-record', '--target', 'game_stereo',
                           '-P', 'stream.capture.sink=true',
                           f'--rate={mod.Spectrum.RATE}', '--channels=1',
                           '--format=f32', '--latency=10ms', '-']]


def test_the_spectrum_tab_is_drawn_faster_than_the_rest_of_the_board(mod):
    """Everything else changes on a human timescale; audio does not, and the
    frame rate was the only thing limiting it -- capture delivers at 96Hz and
    a frame of analysis and drawing costs a tenth of a millisecond."""
    assert mod.SPEC_TICK < mod.TICK
    assert mod.SPEC_TICK >= 0.01, 'still slower than the pads can be sent'


def test_capture_asks_for_the_monitor_side_of_the_sink(spec):
    """Without stream.capture.sink pw-record connects, streams at the right
    rate, and delivers digital silence."""
    spec.bands('game_stereo', 1000.0)
    assert 'stream.capture.sink=true' in captures()[0]


def test_capture_follows_the_output(spec, mod):
    """It listens to the sink's monitor, so switching to the headset has to
    move the capture with it or the bars keep showing the speakers."""
    spec.bands('game_stereo', 1000.0)
    spec.bands('headset', 1000.1)
    assert [c[2] for c in captures()] == ['game_stereo', 'headset']


def test_leaving_the_tab_stops_the_capture(spec, mod):
    spec.bands('game_stereo', 1000.0)
    spec.reap(1000.0 + mod.Spectrum.IDLE - 0.1)
    assert spec.proc is not None, 'still on the tab'
    spec.reap(1000.0 + mod.Spectrum.IDLE + 0.1)
    assert spec.proc is None


def test_no_output_means_no_capture_attempt(spec):
    """An empty sink name would make pw-record pick the default source, which
    is the microphone -- the board would show the room, not the music."""
    levels, _ = spec.bands('', 1000.0)
    assert captures() == [] and levels == [0.0] * 8


# ---- analysis ------------------------------------------------------------
def test_the_bands_are_log_spaced(spec, mod):
    edges = spec.edges()
    assert len(edges) == mod.CELLS + 1
    assert edges == sorted(edges)
    widths = [b - a for a, b in zip(edges, edges[1:])]
    assert widths[-1] > widths[0] * 4, 'octaves, not a linear split'


def test_a_tone_lights_the_band_it_belongs_to(spec, mod):
    """1kHz sits in the fifth band of 40Hz..12kHz over eight columns."""
    levels, _ = feed(spec, 'x.monitor', tone(mod, 1000), 1000.0)
    assert levels.index(max(levels)) == 4
    assert max(levels) > 0.5


def test_a_low_tone_lights_a_low_band(spec, mod):
    """Band 0 or 1, not an exact column: at 23Hz per bin a 60Hz tone straddles
    the boundary, and the tilt lifts the band above it by design."""
    levels, _ = feed(spec, 'x.monitor', tone(mod, 60), 1000.0)
    assert levels.index(max(levels)) <= 1
    assert max(levels[4:]) < max(levels[:2])


def test_silence_is_dark(spec, mod):
    quiet = np.zeros(mod.Spectrum.WINDOW, dtype=np.float32).tobytes()
    levels, _ = feed(spec, 'x.monitor', quiet, 1000.0)
    assert levels == [0.0] * mod.CELLS


def test_a_quieter_tone_reads_lower(spec, mod):
    loud, _ = feed(spec, 'x.monitor', tone(mod, 1000, 0.5), 1000.0)
    soft, _ = feed(spec, 'x.monitor', tone(mod, 1000, 0.02), 1000.1)
    assert soft[4] < loud[4]


def test_peaks_hang_above_the_bar_and_fall_back(spec, mod):
    levels, peaks = feed(spec, 'x.monitor', tone(mod, 1000, 0.5), 1000.0)
    assert peaks[4] == levels[4]
    spec.raw = np.zeros(mod.Spectrum.WINDOW, dtype=np.float32).tobytes()
    _, later = spec.bands('x.monitor', 1000.5)
    assert 0 < later[4] < peaks[4], 'falling, not gone'
    _, much_later = spec.bands('x.monitor', 1010.0)
    assert much_later[4] == 0.0


# ---- what lands on the pads ---------------------------------------------
def test_the_columns_are_a_rainbow_not_a_traffic_light(mod):
    """The meters go green-yellow-red by height; this is one hue per band, so
    a glance tells you which tab you are looking at."""
    assert len(set(mod.SPEC_HUES)) == mod.CELLS
    assert mod.SPEC_HUES[0] != mod.SPEC_HUES[-1]
    assert set(mod.SPEC_HUES) != {mod.GREEN, mod.YELLOW, mod.RED}


def test_a_column_fills_from_the_bottom(board, mod, out, monkeypatch):
    board.mode = mod.M_SPEC
    levels = [0.0] * mod.CELLS; levels[3] = 3 / 7          # three of seven rows
    monkeypatch.setattr(board.spectrum, 'bands', lambda *a, **k: (levels, [0.0] * mod.CELLS))
    board.shown.clear(); out.sent.clear()
    board.render_spectrum()
    lit = out.lit()
    column = [lit.get(mod.pad(r, 3)) for r in mod.SPEC_ROWS]      # top row first
    assert column == [mod.OFF] * 4 + [mod.SPEC_HUES[3]] * 3


def test_the_peak_sits_above_the_bar(board, mod, out, monkeypatch):
    board.mode = mod.M_SPEC
    levels = [0.0] * mod.CELLS; levels[0] = 2 / 7
    peaks = [0.0] * mod.CELLS; peaks[0] = 5 / 7
    bar = board.bar_colours(mod.DAY)
    column = draw(board, mod, out, levels, peaks, 0)
    assert column == [bar[0], mod.OFF, mod.SPEC_PEAK, mod.OFF,
                      mod.OFF, mod.SPEC_HUES[0], mod.SPEC_HUES[0]]


# ---- the day bar shares the top row -------------------------------------
def draw(board, mod, out, levels, peaks, col):
    """Render one frame and read a column back, top row first."""
    board.spectrum.bands = lambda *a, **k: (levels, peaks)
    board.shown.clear(); out.sent.clear()
    board.render_spectrum()
    return [out.lit().get(mod.pad(r, col)) for r in mod.SPEC_ROWS]


def test_the_top_row_shows_the_day_bar(board, mod, out):
    """It costs the spectrum nothing until a column actually needs that cell,
    which beats giving the bar a row of its own out of seven."""
    board.mode = mod.M_SPEC
    quiet = [0.0] * mod.CELLS
    bar = board.bar_colours(mod.DAY)
    assert bar[0] != mod.OFF, 'the fixture clock is inside the first slice'
    top = [draw(board, mod, out, quiet, quiet, c)[0] for c in range(mod.CELLS)]
    assert top == bar


def test_a_loud_band_writes_over_its_own_bar_cell_only(board, mod, out):
    """Not the whole row: the columns beside it still show the bar."""
    board.mode = mod.M_SPEC
    levels = [0.0] * mod.CELLS; levels[0] = 1.0          # column 0 to the top
    quiet = [0.0] * mod.CELLS
    bar = board.bar_colours(mod.DAY)
    board.spectrum.bands = lambda *a, **k: (levels, quiet)
    board.shown.clear(); out.sent.clear()
    board.render_spectrum()
    top = [out.lit().get(mod.pad(mod.BAR_ROW, c)) for c in range(mod.CELLS)]
    assert top[0] == mod.SPEC_HUES[0]
    assert top[1:] == bar[1:]


def test_a_peak_reaching_the_top_writes_over_the_bar_too(board, mod, out):
    board.mode = mod.M_SPEC
    quiet = [0.0] * mod.CELLS
    peaks = [0.0] * mod.CELLS; peaks[3] = 1.0
    assert draw(board, mod, out, quiet, peaks, 3)[0] == mod.SPEC_PEAK


def test_the_bar_comes_back_when_the_band_drops(board, mod, out):
    board.mode = mod.M_SPEC
    loud = [0.0] * mod.CELLS; loud[0] = 1.0
    quiet = [0.0] * mod.CELLS
    bar = board.bar_colours(mod.DAY)
    assert draw(board, mod, out, loud, quiet, 0)[0] == mod.SPEC_HUES[0]
    assert draw(board, mod, out, quiet, quiet, 0)[0] == bar[0]


def test_the_spectrum_owns_its_top_row_rather_than_sharing_it(mod):
    """It draws the bar itself, so the row stays one widget's on the layout:
    two widgets drawing one row is what the startup check exists to stop."""
    assert mod.M_SPEC not in mod.BARS
    assert mod.SPEC_ROWS == [1, 2, 3, 4, 5, 6, 7]
    assert mod.widget_at(mod.M_SPEC, mod.BAR_ROW) is mod.Widget.SPECTRUM
