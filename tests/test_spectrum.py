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
                           '--format=f32', '--latency=20ms', '-']]


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
    levels, _ = feed(spec, 'x.monitor', tone(mod, 60), 1000.0)
    assert levels.index(max(levels)) == 0


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
    monkeypatch.setattr(board.spectrum, 'bands', lambda *a, **k: (levels, peaks))
    board.shown.clear(); out.sent.clear()
    board.render_spectrum()
    column = [out.lit().get(mod.pad(r, 0)) for r in mod.SPEC_ROWS]
    assert column == [mod.OFF, mod.OFF, mod.SPEC_PEAK, mod.OFF,
                      mod.OFF, mod.SPEC_HUES[0], mod.SPEC_HUES[0]]


def test_the_spectrum_tab_has_no_day_bar(mod):
    """Seven rows of resolution beats six and a clock you can read on four
    other tabs."""
    assert mod.M_SPEC not in mod.BARS
    assert mod.SPEC_ROWS == [1, 2, 3, 4, 5, 6, 7]
