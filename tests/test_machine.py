"""The machine and audio tab.

Nothing here reads the real machine: every test hands the board a snapshot and
checks what it draws, or presses a pad and checks what it would have run. The
poller that fills the snapshot in is a thread the harness never starts.
"""
import pytest
from lpharness import FakeOut, FakePopen, new_board


def ran(argv0=None):
    """Commands the board fired off, ignoring the popup it always spawns."""
    out = [p.argv for p in FakePopen.instances if 'habit-popup' not in p.argv[0]]
    return [a for a in out if argv0 is None or a[0] == argv0]


@pytest.fixture
def mach(board, mod):
    board.mode = mod.M_MACH
    return board


def row(board, mod, r):
    lit = board.out.lit()
    return [lit.get(mod.pad(r, c)) for c in range(mod.CELLS)]


def show(board, mod, snap, r, paint=None):
    board.machine.snap = snap
    board.shown.clear(); board.out.sent.clear()
    (paint or board.render_machine)()
    return row(board, mod, r)


# ---- where the tab lives -------------------------------------------------
def test_the_machine_tab_is_third_from_the_right(mod):
    assert sorted(mod.TABS)[-3] == mod.M_MACH
    assert mod.M_MACH in mod.BARS, 'row 1 is the day bar here too'


def test_the_reserved_rows_are_claimed_so_nothing_else_can_take_them(mod):
    for r in mod.MACH_BLANK:
        assert mod.widget_at(mod.M_MACH, r) is mod.Widget.BLANK


# ---- RAID ----------------------------------------------------------------
HEALTHY = """Personalities : [raid1]
md127 : active raid1 sde1[1] sda1[0]
      3417629696 blocks super 1.2 [2/2] [UU]
      bitmap: 11/26 pages [44KB], 65536KB chunk

md1 : active raid1 sdf1[1] sdd1[0]
      976000 blocks super 1.2 [2/2] [UU]

unused devices: <none>
"""


def test_a_healthy_array_is_all_green(mod):
    assert mod.parse_mdstat(HEALTHY) == (('sda', 'ok'), ('sdd', 'ok'),
                                         ('sde', 'ok'), ('sdf', 'ok'))


def test_a_faulty_member_is_a_failure(mod):
    text = HEALTHY.replace('sde1[1]', 'sde1[1](F)').replace('[2/2] [UU]', '[2/1] [U_]')
    assert dict(mod.parse_mdstat(text))['sde'] == 'fail'


def test_the_survivor_of_a_degraded_array_goes_amber(mod):
    """A disk that has gone entirely cannot be listed -- mdstat only names what
    is still there -- so the surviving half is what says something is wrong."""
    text = HEALTHY.replace(' sde1[1]', '').replace('[2/2] [UU]', '[2/1] [U_]')
    parsed = dict(mod.parse_mdstat(text))
    assert parsed['sda'] == 'sync' and 'sde' not in parsed


def test_a_rebuilding_array_is_amber_not_green(mod):
    text = HEALTHY.replace('      bitmap: 11/26',
                           '      [==>..]  recovery = 12.3% (1/2) finish=9.0min\n      bitmap: 11/26')
    assert dict(mod.parse_mdstat(text))['sda'] == 'sync'


def test_one_disk_in_three_arrays_takes_its_worst_state(mod):
    """md1, md2 and md3 all live on sdd and sdf: it is the drive that dies, so
    a pad is the drive, not the partition."""
    text = HEALTHY + """
md2 : active raid1 sdf2[1](F) sdd2[0]
      7808384 blocks super 1.2 [2/1] [U_]
"""
    assert dict(mod.parse_mdstat(text))['sdf'] == 'fail'


def test_disk_row_colours(mach, mod):
    snap = mod.Snapshot(disks=(('sda', 'ok'), ('sdb', 'sync'), ('sdc', 'fail')))
    painted = show(mach, mod, snap, mod.DISK_ROW)
    assert painted[:2] == [mod.DISK_OK, mod.DISK_SYNC]
    assert painted[2] in (mod.DISK_FAIL, mod.OFF), 'a failure strobes'
    assert painted[3:] == [mod.OFF] * 5


# ---- filesystems ---------------------------------------------------------
@pytest.mark.parametrize('free,colour', [
    (900, 'GREEN'), (101, 'GREEN'), (100, 'GREEN'),
    (99, 'YELLOW'), (30, 'YELLOW'),
    (29, 'RED'), (0, 'RED'),
])
def test_filesystem_colours_by_room_left(mach, mod, free, colour):
    snap = mod.Snapshot(mounts=((mod.MOUNTS[0], free),))
    assert show(mach, mod, snap, mod.FS_ROW)[0] == getattr(mod, colour)


def test_a_filesystem_that_is_not_there_strobes(mach, mod):
    """All four are always mounted, so a missing one is news, not a blank."""
    snap = mod.Snapshot(mounts=((mod.MOUNTS[0], None),))
    assert show(mach, mod, snap, mod.FS_ROW)[0] in (mod.RED, mod.OFF)


def test_the_four_filesystems_are_the_real_ones(mod):
    assert [m.name for m in mod.MOUNTS] == ['root', 'home', 'data', 'fast']
    assert mod.MOUNTS[0].path == '/'
    assert mod.MOUNTS[2].path.endswith('/Data-1')
    assert mod.MOUNTS[3].path.endswith('/Fast-1')


# ---- temperatures --------------------------------------------------------
def test_thresholds_are_per_part(mod):
    """70C is a warm CPU and a cooked NVMe: one threshold for the row would
    make the colours mean different things in different columns."""
    cpu, gpu, nvme = mod.SENSORS
    assert (cpu.name, gpu.name, nvme.name) == ('cpu', 'gpu', 'nvme')
    assert nvme.warm < cpu.warm and nvme.panic < cpu.panic
    for s in mod.SENSORS:
        assert s.warm < s.hot < s.panic


@pytest.mark.parametrize('temp,colour', [
    (40, 'GREEN'), (69, 'GREEN'), (70, 'YELLOW'), (84, 'YELLOW'), (85, 'RED'), (94, 'RED'),
])
def test_cpu_temperature_colours(mach, mod, temp, colour):
    snap = mod.Snapshot(temps=((mod.SENSORS[0], temp),))
    assert show(mach, mod, snap, mod.TEMP_ROW)[0] == getattr(mod, colour)


def test_an_abnormal_temperature_strobes(mach, mod):
    snap = mod.Snapshot(temps=((mod.SENSORS[0], 99),))
    assert show(mach, mod, snap, mod.TEMP_ROW)[0] in (mod.RED, mod.OFF)


def test_a_sensor_that_cannot_be_read_is_dark_not_alarming(mach, mod):
    snap = mod.Snapshot(temps=((mod.SENSORS[1], None),))
    assert show(mach, mod, snap, mod.TEMP_ROW)[0] == mod.OFF


# ---- the control row -----------------------------------------------------
SINKS = ('game_stereo', 'alsa_output.usb-AT_ATH-M50xSTS-USB-00.analog-stereo')
SOURCES = ('alsa_input.usb-AT_ATH-M50xSTS-USB-00.mono-fallback',)


def audio(mod, **kw):
    return mod.Snapshot(sinks=SINKS, sources=SOURCES, **kw)


def test_the_selected_output_is_the_one_the_system_is_actually_on(mach, mod):
    """Not the last button pressed: change the output anywhere else and the
    pads follow at the next poll."""
    painted = show(mach, mod, audio(mod, sink='game_stereo'), mod.CTRL_ROW)
    assert painted[0] == mod.SELECTED and painted[1] == mod.WHITE
    painted = show(mach, mod, audio(mod, sink=SINKS[1]), mod.CTRL_ROW)
    assert painted[0] == mod.WHITE and painted[1] == mod.SELECTED


def test_an_unplugged_headset_leaves_its_pad_dark(mach, mod):
    snap = mod.Snapshot(sinks=('game_stereo',), sink='game_stereo')
    painted = show(mach, mod, snap, mod.CTRL_ROW)
    assert painted[0] == mod.SELECTED
    assert painted[1] == mod.OFF, 'nothing to switch to'


def test_the_gaps_stay_dark(mach, mod):
    painted = show(mach, mod, audio(mod, sink='game_stereo'), mod.CTRL_ROW)
    assert painted[2] == mod.OFF and painted[4] == mod.OFF


def test_effects_and_transport_colours(mach, mod):
    on = show(mach, mod, audio(mod, effects=True, running=True, playing=True), mod.CTRL_ROW)
    assert on[3] == mod.GREEN and on[6] == mod.GREEN
    off = show(mach, mod, audio(mod), mod.CTRL_ROW)
    assert off[3] == mod.WHITE and off[6] == mod.WHITE
    assert off[5] == mod.WHITE and off[7] == mod.WHITE


# ---- pressing it ---------------------------------------------------------
def press(board, mod, col, snap):
    board.machine.snap = snap
    FakePopen.instances.clear()
    board.press(mod.pad(mod.CTRL_ROW, col))
    board.release(mod.pad(mod.CTRL_ROW, col))


def test_choosing_an_output_sets_the_default_sink(mach, mod):
    press(mach, mod, 0, audio(mod, sink=SINKS[1]))
    assert ran('pactl') == [['pactl', 'set-default-sink', 'game_stereo']]


def test_choosing_the_headset_takes_the_microphone_with_it(mach, mod):
    """Otherwise you switch to the headset and keep recording off whatever was
    selected before."""
    press(mach, mod, 1, audio(mod, sink='game_stereo'))
    assert ran('pactl') == [['pactl', 'set-default-sink', SINKS[1]],
                            ['pactl', 'set-default-source', SOURCES[0]]]


def test_the_pad_lights_before_the_poll_catches_up(mach, mod):
    press(mach, mod, 1, audio(mod, sink='game_stereo'))
    assert mach.machine.snap.sink == SINKS[1]


def test_pressing_an_absent_output_does_nothing_at_all(mach, mod):
    press(mach, mod, 1, mod.Snapshot(sinks=('game_stereo',), sink='game_stereo'))
    assert ran() == []


def test_pressing_a_gap_does_nothing(mach, mod):
    press(mach, mod, 2, audio(mod, sink='game_stereo'))
    press(mach, mod, 4, audio(mod, sink='game_stereo'))
    assert ran() == []


def test_transport_buttons_talk_to_spotify(mach, mod):
    for col, action in ((5, 'Previous'), (6, 'PlayPause'), (7, 'Next')):
        press(mach, mod, col, audio(mod))
        assert ran('gdbus')[0][-1] == f'org.mpris.MediaPlayer2.Player.{action}'
        assert mod.SPOTIFY in ran('gdbus')[0]


@pytest.mark.parametrize('running,effects,expect', [
    (True,  True,  ['easyeffects', '-b', '1']),                # on  -> bypassed
    (True,  False, ['easyeffects', '-b', '2']),                # bypassed -> on
    (False, False, ['easyeffects', '--gapplication-service']),  # stopped -> started
])
def test_the_effects_button_turns_it_on_however_it_was_off(mach, mod, running, effects, expect):
    press(mach, mod, 3, audio(mod, running=running, effects=effects))
    assert ran('easyeffects') == [expect]
    assert mach.machine.snap.effects is not effects


# ---- the poller ----------------------------------------------------------
def test_nothing_is_read_during_a_frame(mach, mod):
    """render() must not shell out: `easyeffects -b 3` alone is a quarter of a
    second, and a frame is 50ms."""
    FakePopen.instances.clear()
    mach.render()
    assert ran() == []


def test_the_poller_runs_off_the_drawing_thread(mach, mod):
    from lpharness import FakeThread
    assert any(t.target == mach.machine._loop for t in FakeThread.started)
