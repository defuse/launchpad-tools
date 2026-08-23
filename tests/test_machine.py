"""The machine and audio tab.

Nothing here reads the real machine: every test hands the board a snapshot and
checks what it draws, or presses a pad and checks what it would have run. The
poller that fills the snapshot in is a thread the harness never starts.
"""
import json
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
    rgb = {}
    for msg in board.out.sent:                      # RGB pads arrive as sysex
        if msg.type == 'sysex' and tuple(msg.data[:7]) == mod.SYSEX_RGB:
            rgb[msg.data[7]] = tuple(msg.data[8:11])
    return [rgb.get(mod.pad(r, c), lit.get(mod.pad(r, c))) for c in range(mod.CELLS)]


def middle(board, mod, r, n):
    """The n indicators of a centred row, without the dark pads either side."""
    first = mod.centred(n)
    return row(board, mod, r)[first:first + n]


def show(board, mod, snap, r, paint=None):
    board.machine.snap = snap
    board.shown.clear(); board.out.sent.clear()
    (paint or board.render_machine)()
    return row(board, mod, r)


# ---- where the tab lives -------------------------------------------------
def test_the_machine_tab_is_the_fourth_one(mod):
    assert sorted(mod.TABS)[3] == mod.M_MACH
    assert sorted(mod.TABS)[4] == mod.M_SPEC, 'the spectrum sits next to it'
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
    drives = painted[mod.centred(3):mod.centred(3) + 3]
    assert drives[:2] == [mod.DISK_OK, mod.DISK_SYNC]
    assert drives[2] in (mod.DISK_FAIL, mod.OFF), 'a failure strobes'
    assert painted.count(mod.OFF) >= 5, 'the rest of the row is dark'


@pytest.mark.parametrize('n,first', [(6, 1), (4, 2), (3, 2), (8, 0), (1, 3)])
def test_indicators_are_centred(mod, n, first):
    """Six drives left-aligned read as a bar that stopped part way."""
    assert mod.centred(n) == first


def test_the_disks_and_filesystems_sit_in_the_middle(mach, mod):
    disks = tuple((f'sd{c}', 'ok') for c in 'abcdef')          # six drives
    painted = show(mach, mod, mod.Snapshot(disks=disks), mod.DISK_ROW)
    assert painted[0] == mod.OFF and painted[7] == mod.OFF
    assert painted[1:7] == [mod.DISK_OK] * 6
    mounts = tuple((m, 900, 40.0) for m in mod.MOUNTS)         # four filesystems
    painted = show(mach, mod, mod.Snapshot(mounts=mounts), mod.FS_ROW)
    assert painted[:2] == [mod.OFF] * 2 and painted[6:] == [mod.OFF] * 2
    assert painted[2:6] == [mod.GREEN] * 4


# ---- filesystems ---------------------------------------------------------
@pytest.mark.parametrize('free,colour', [
    (900, 'GREEN'), (101, 'GREEN'), (100, 'GREEN'),
    (99, 'YELLOW'), (30, 'YELLOW'),
    (29, 'RED'), (0, 'RED'),
])
def test_filesystem_colours_by_room_left(mach, mod, free, colour):
    snap = mod.Snapshot(mounts=((mod.MOUNTS[0], free, 12.0),))
    show(mach, mod, snap, mod.FS_ROW)
    assert middle(mach, mod, mod.FS_ROW, 1) == [getattr(mod, colour)]


def test_a_filesystem_that_is_not_there_strobes(mach, mod):
    """All four are always mounted, so a missing one is news, not a blank."""
    snap = mod.Snapshot(mounts=((mod.MOUNTS[0], None, None),))
    show(mach, mod, snap, mod.FS_ROW)
    assert middle(mach, mod, mod.FS_ROW, 1)[0] in (mod.RED, mod.OFF)


def test_the_readme_still_names_what_this_tab_assumes(mod):
    """The README tells a reader which tabs are wired to one particular desk.
    Renaming a sink or a mount here without updating it there would leave that
    section quietly lying, which it has done before."""
    import os
    readme = os.path.join(os.path.dirname(os.path.dirname(mod.__file__)), 'README.md')
    text = open(readme).read()
    for claim in (mod.GAME_SINK, mod.HEADSET, 'Data-1', 'Fast-1',
                  'k10temp', 'nvidia-smi', '/proc/mdstat'):
        assert claim in text, f'README no longer mentions {claim}'


def test_the_four_filesystems_are_the_real_ones(mod):
    assert [m.name for m in mod.MOUNTS] == ['root', 'home', 'data', 'fast']
    assert mod.MOUNTS[0].path == '/'
    assert mod.MOUNTS[2].path.endswith('/Data-1')
    assert mod.MOUNTS[3].path.endswith('/Fast-1')


# ---- temperatures --------------------------------------------------------
def test_thresholds_are_per_part(mod):
    """70C is a warm CPU and a cooked NVMe: one threshold for the row would
    make the colours mean different things in different columns."""
    cpu, gpu, nvme, ccd2 = mod.SENSORS
    assert (cpu.name, gpu.name, nvme.name, ccd2.name) == ('cpu', 'gpu', 'nvme', 'ccd2')
    assert nvme.warm < cpu.warm and nvme.panic < cpu.panic
    for s in mod.SENSORS:
        assert s.warm < s.hot < s.panic


@pytest.mark.parametrize('temp,colour', [
    (40, 'TEMP_OK'), (69, 'TEMP_OK'), (70, 'YELLOW'), (84, 'YELLOW'), (85, 'RED'), (94, 'RED'),
])
def test_cpu_temperature_colours(mach, mod, temp, colour):
    snap = mod.Snapshot(temps=((mod.SENSORS[0], temp),))
    show(mach, mod, snap, mod.TEMP_ROW)
    assert middle(mach, mod, mod.TEMP_ROW, 1) == [getattr(mod, colour)]


def test_a_normal_temperature_is_a_colour_the_palette_does_not_have(mach, mod):
    """Sent as RGB rather than a palette index: pale blue, so the row does not
    read as one more meter reporting good news in green."""
    assert isinstance(mod.TEMP_OK, tuple) and len(mod.TEMP_OK) == 3
    assert all(0 <= v <= 127 for v in mod.TEMP_OK), 'seven bits per channel'
    r, g, b = mod.TEMP_OK
    assert b > g > r, 'blue, and pale'
    snap = mod.Snapshot(temps=((mod.SENSORS[0], 40),))
    show(mach, mod, snap, mod.TEMP_ROW)
    assert middle(mach, mod, mod.TEMP_ROW, 1)[0] == mod.TEMP_OK


def test_an_rgb_colour_goes_out_as_a_lighting_sysex(board, mod, out):
    board.set(mod.pad(3, 4), (80, 110, 127))
    sysex = [m for m in out.sent if m.type == 'sysex']
    assert len(sysex) == 1
    assert tuple(sysex[0].data) == mod.SYSEX_RGB + (mod.pad(3, 4), 80, 110, 127)


def test_a_palette_colour_still_goes_out_as_a_note(board, mod, out):
    board.set(mod.pad(3, 4), mod.GREEN)
    assert [m.type for m in out.sent] == ['note_on']


def test_the_fourth_sensor_makes_the_row_centreable(mod):
    """Four across eight sits in the middle; three did not."""
    assert [x.name for x in mod.SENSORS] == ['cpu', 'gpu', 'nvme', 'ccd2']
    assert mod.centred(len(mod.SENSORS)) == 2


def test_the_system_temperatures_are_centred(mach, mod):
    snap = mod.Snapshot(temps=tuple((x, 40) for x in mod.SENSORS))
    painted = show(mach, mod, snap, mod.TEMP_ROW)
    assert painted[:2] == [mod.OFF] * 2 and painted[6:] == [mod.OFF] * 2
    assert painted[2:6] == [mod.TEMP_OK] * 4


# ---- drive temperatures --------------------------------------------------
DRIVES = (('sda', 31.0, False), ('sdb', 36.0, True), ('sdc', 36.0, True),
          ('sdd', 33.0, False), ('sde', 37.0, False), ('sdf', 35.0, False))
HEALTH = tuple((name, 'ok') for name, _, _ in DRIVES)


def test_a_platter_drive_is_warm_where_an_ssd_is_not(mod):
    """45C is unremarkable for an SSD and the start of trouble for a disk that
    spins, so the thresholds cannot be shared."""
    hdd, ssd = mod.DRIVE_LIMITS[True], mod.DRIVE_LIMITS[False]
    assert hdd[0] < ssd[0] and hdd[2] < ssd[2]


@pytest.mark.parametrize('temp,spins,colour', [
    (31, False, 'TEMP_OK'), (54, False, 'TEMP_OK'), (55, False, 'YELLOW'),
    (65, False, 'RED'),
    (36, True, 'TEMP_OK'), (44, True, 'TEMP_OK'), (45, True, 'YELLOW'),
    (50, True, 'RED'),
])
def test_drive_temperature_colours(mach, mod, temp, spins, colour):
    snap = mod.Snapshot(disks=(('sda', 'ok'),), drives=(('sda', temp, spins),))
    show(mach, mod, snap, mod.DRIVE_TEMP_ROW)
    assert middle(mach, mod, mod.DRIVE_TEMP_ROW, 1) == [getattr(mod, colour)]


def test_each_drive_sits_under_its_own_health_pad(mach, mod):
    """One column is one drive: state above, temperature below."""
    snap = mod.Snapshot(disks=HEALTH, drives=DRIVES)
    show(mach, mod, snap, mod.DISK_ROW)
    health = row(mach, mod, mod.DISK_ROW)
    temps = row(mach, mod, mod.DRIVE_TEMP_ROW)
    lit = [c for c, v in enumerate(health) if v != mod.OFF]
    assert lit == [c for c, v in enumerate(temps) if v != mod.OFF], \
        'the two rows light the same columns'
    assert lit == [1, 2, 3, 4, 5, 6], 'six drives, centred'


def test_a_drive_with_no_sensor_leaves_its_column_dark_without_shifting_the_rest(mach, mod):
    """drivetemp not loaded, or one drive not reporting: the columns must still
    name the same disks as the row above."""
    snap = mod.Snapshot(disks=HEALTH, drives=tuple(d for d in DRIVES if d[0] != 'sdc'))
    show(mach, mod, snap, mod.DRIVE_TEMP_ROW)
    temps = row(mach, mod, mod.DRIVE_TEMP_ROW)
    assert temps[3] == mod.OFF, 'sdc is the third of six, at column 3'
    assert temps[4] != mod.OFF, 'and sdd still holds its own column'


def test_no_drivetemp_module_means_a_dark_row_not_an_error(mach, mod):
    snap = mod.Snapshot(disks=HEALTH, drives=())
    assert show(mach, mod, snap, mod.DRIVE_TEMP_ROW) == [mod.OFF] * mod.CELLS


def test_an_abnormal_temperature_strobes(mach, mod):
    snap = mod.Snapshot(temps=((mod.SENSORS[0], 99),))
    show(mach, mod, snap, mod.TEMP_ROW)
    assert middle(mach, mod, mod.TEMP_ROW, 1)[0] in (mod.RED, mod.OFF)


def test_a_sensor_that_cannot_be_read_is_dark_not_alarming(mach, mod):
    snap = mod.Snapshot(temps=((mod.SENSORS[1], None),))
    show(mach, mod, snap, mod.TEMP_ROW)
    assert middle(mach, mod, mod.TEMP_ROW, 1)[0] == mod.OFF


# ---- the network meter ---------------------------------------------------
def test_the_snake_turns_around_on_every_other_row(mod):
    assert [mod.snake(0, j, 4) for j in range(4)] == [0, 1, 2, 3]
    assert [mod.snake(1, j, 4) for j in range(4)] == [3, 2, 1, 0]
    assert [mod.snake(2, j, 4) for j in range(4)] == [0, 1, 2, 3]


def test_the_fill_is_one_unbroken_run(mod):
    """Each row picks up where the one below it stopped, so the bar climbs
    rather than restarting at the left every four steps."""
    width = 4
    path = [(row, mod.snake(row, step, width))
            for row in range(7) for step in range(width)]
    for (r1, c1), (r2, c2) in zip(path, path[1:]):
        same_row = r1 == r2 and abs(c1 - c2) == 1
        next_row = r2 == r1 + 1 and c1 == c2
        assert same_row or next_row, f'{(r1, c1)} to {(r2, c2)} is a jump'


def net(board, mod, out, rx, tx):
    """Paint the meter at known rates and return {row: [8 colours]}."""
    board.net_rates = lambda: (rx, tx)
    board.mode = mod.M_NET
    board.shown.clear(); out.sent.clear()
    board.render_net()
    lit = out.lit()
    return {r: [lit.get(mod.pad(r, c)) for c in range(mod.CELLS)]
            for r in mod.CPU_ROWS + [mod.MEM_ROW]}


def test_download_grows_down_from_the_top_left(board, mod, out):
    """Which half is which should be legible from the shape, not from
    remembering which colour meant what."""
    painted = net(board, mod, out, rx=5e5, tx=0.0)
    top, bottom = mod.CPU_ROWS[0], mod.MEM_ROW
    assert painted[top][:4] == [mod.CYAN] * 4, 'starts at the top left'
    assert painted[bottom][:4] == [mod.OFF] * 4, 'and has not reached the floor'


def test_upload_grows_up_from_the_bottom(board, mod, out):
    painted = net(board, mod, out, rx=0.0, tx=5e5)
    top, bottom = mod.CPU_ROWS[0], mod.MEM_ROW
    assert painted[bottom][4:] == [mod.ORANGE] * 4, 'starts at the bottom'
    assert painted[top][4:] == [mod.OFF] * 4


def test_the_two_halves_grow_towards_each_other(board, mod, out):
    painted = net(board, mod, out, rx=3e4, tx=3e4)          # the same modest rate
    lit_rows = lambda half: [r for r, cells in painted.items()
                             if any(v not in (None, mod.OFF) for v in
                                    (cells[:4] if half == 0 else cells[4:]))]
    assert min(lit_rows(0)) == mod.CPU_ROWS[0], 'download hangs from the top'
    assert max(lit_rows(1)) == mod.MEM_ROW, 'upload stands on the bottom'


def test_the_network_meter_paints_a_snake(board, mod, out):
    painted = net(board, mod, out, rx=5e5, tx=0.0)
    rows = mod.CPU_ROWS + [mod.MEM_ROW]                     # download runs top-down
    on = [(i, c) for i, r in enumerate(rows) for c in range(4)
          if painted[r][c] == mod.CYAN]
    assert on, 'something is lit'
    order = [(i, mod.snake(i, j, 4)) for i in range(len(rows)) for j in range(4)]
    assert set(on) == set(order[:len(on)]), 'the first N steps of the snake'
    assert on == sorted(on)


# ---- the control row -----------------------------------------------------
SINKS = ('game_stereo', 'alsa_output.usb-AT_ATH-M50xSTS-USB-00.analog-stereo')
SOURCES = ('alsa_input.usb-AT_ATH-M50xSTS-USB-00.mono-fallback',)


def col_of(mod, kind, row=None):
    """Which column carries a given control. Looked up rather than written
    down: these pads have moved twice, and every literal is a place to miss."""
    row = mod.CTRL_ROW if row is None else row
    for i, b in enumerate(mod.CONTROLS[row]):
        if b and b.kind == kind:
            return i
    raise AssertionError(f'no {kind} pad on row {row}')


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


def test_the_outputs_are_kept_apart_from_the_sub_and_effects(mach, mod):
    """A gap between them: choosing an output and silencing the sub are
    different jobs, and a stray press should not fire the wrong one."""
    painted = show(mach, mod, audio(mod, sink='game_stereo'), mod.CTRL_ROW)
    assert painted[2] == mod.OFF
    row = mod.CONTROLS[mod.CTRL_ROW]
    assert [b.kind if b else None for b in row[:5]] == \
        ['sink', 'sink', None, 'sub', 'effects']


def test_the_whole_control_row_in_order(mach, mod):
    """Outputs, a gap, the sub and effects, then the transport."""
    assert [b.kind if b else None for b in mod.CONTROLS[mod.CTRL_ROW]] == \
        ['sink', 'sink', None, 'sub', 'effects', 'media', 'media', 'media']


def test_transport_colours(mach, mod):
    on = show(mach, mod, audio(mod, playing=True), mod.CTRL_ROW)
    assert on[6] == mod.PLAYING
    off = show(mach, mod, audio(mod), mod.CTRL_ROW)
    assert off[5] == mod.WHITE and off[6] == mod.WHITE and off[7] == mod.WHITE


# ---- which preset is live ------------------------------------------------
@pytest.mark.parametrize('effects,preset,colour', [
    (False, 'room',    'PRESET_OFF'),      # off is off, whatever would load
    (False, 'cans',    'PRESET_OFF'),
    (True,  'room',    'PRESET_MAIN'),
    (True,  'cans',    'PRESET_HEADSET'),
    (True,  '',        'PRESET_MAIN'),     # nothing known: on is on
])
def test_the_effects_pad_shows_which_preset_is_active(mach, mod, effects, preset, colour):
    """Getting the room's EQ in headphones sounds wrong in a way that is easy
    to miss and hard to place, so the pad says which one you are hearing."""
    snap = audio(mod, running=True, effects=effects, preset=preset, headset_preset='cans')
    assert show(mach, mod, snap, mod.CTRL_ROW)[col_of(mod, 'effects')] == getattr(mod, colour)


def test_it_is_still_an_on_off_button(mach, mod):
    """The colour reports the preset; the press does not choose one."""
    press(mach, mod, col_of(mod, 'effects'), audio(mod, running=True, effects=True,
                              preset='cans', headset_preset='cans'))
    assert ran('easyeffects') == [['easyeffects', '-b', '1']]


def test_the_headset_preset_is_read_from_easyeffects_own_bindings(mod, tmp_path, monkeypatch):
    """Not copied in here: renaming a preset in EasyEffects must not leave the
    board reporting a preset that no longer exists."""
    monkeypatch.setattr(mod, 'EE_AUTOLOAD', str(tmp_path))
    (tmp_path / 'game_stereo:.json').write_text(json.dumps(
        {'device': 'game_stereo', 'device-profile': '', 'preset-name': 'room'}))
    (tmp_path / 'headset.json').write_text(json.dumps(
        {'device': f'alsa_output.usb-{mod.HEADSET}-USB-00.analog-stereo',
         'device-profile': 'Analog Output', 'preset-name': 'at headphones'}))
    assert mod.headset_preset() == 'at headphones'


def test_no_bindings_at_all_is_not_an_error(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, 'EE_AUTOLOAD', str(tmp_path / 'nope'))
    assert mod.headset_preset() == ''


# ---- pressing it ---------------------------------------------------------
def press(board, mod, col, snap, row=None):
    board.machine.snap = snap
    FakePopen.instances.clear()
    p = mod.pad(mod.CTRL_ROW if row is None else row, col)
    board.press(p)
    board.release(p)


def test_choosing_an_output_sets_the_default_sink(mach, mod):
    press(mach, mod, 0, audio(mod, sink=SINKS[1]))
    assert ran('pactl') == [['pactl', 'set-default-sink', 'game_stereo']]


def test_choosing_the_headset_takes_the_microphone_with_it(mach, mod):
    """Otherwise you switch to the headset and keep recording off whatever was
    selected before."""
    press(mach, mod, 1, audio(mod, sink='game_stereo'))
    assert ran('pactl') == [['pactl', 'set-default-sink', SINKS[1]],
                            ['pactl', 'set-default-source', SOURCES[0]]]


@pytest.mark.parametrize('col', [0, 1])
def test_switching_output_leaves_easyeffects_alone(mach, mod, col):
    """EasyEffects autoloads a preset per output device, so the switch carries
    its own processing. Bypassing for the headset -- which is what this used to
    do, before there was a headset preset -- would make that preset unreachable
    from the board."""
    press(mach, mod, col, audio(mod, sink='', running=True, effects=True))
    assert ran('easyeffects') == []
    assert ran('pactl')[0][1] == 'set-default-sink'


def test_a_press_schedules_a_read_back_instead_of_assuming(mach, mod):
    """The pads report what pactl and EasyEffects say, never what the board
    asked them for. A press that fails, or is overridden a moment later, must
    not leave the board asserting something untrue."""
    press(mach, mod, 1, audio(mod, sink='game_stereo'))
    assert mach.machine.snap.sink == 'game_stereo', 'not touched by the press'
    assert mach.machine.recheck_at > 0, 'a read-back is pending'


def test_pressing_an_absent_output_does_nothing_at_all(mach, mod):
    press(mach, mod, 1, mod.Snapshot(sinks=('game_stereo',), sink='game_stereo'))
    assert ran() == []


def test_pressing_a_gap_does_nothing(mach, mod):
    press(mach, mod, 2, audio(mod, sink='game_stereo'))          # outputs | sub
    assert ran() == []


def test_transport_buttons_talk_to_spotify(mach, mod):
    for col, action in ((5, 'Previous'), (6, 'PlayPause'), (7, 'Next')):
        press(mach, mod, col, audio(mod), row=mod.CTRL_ROW)
        assert ran('gdbus')[0][-1] == f'org.mpris.MediaPlayer2.Player.{action}'
        assert mod.SPOTIFY in ran('gdbus')[0]


@pytest.mark.parametrize('running,effects,expect', [
    (True,  True,  ['easyeffects', '-b', '1']),                # on  -> bypassed
    (True,  False, ['easyeffects', '-b', '2']),                # bypassed -> on
    (False, False, ['easyeffects', '--gapplication-service']),  # stopped -> started
])
def test_the_effects_button_turns_it_on_however_it_was_off(mach, mod, running, effects, expect):
    press(mach, mod, col_of(mod, 'effects'), audio(mod, running=running, effects=effects))
    assert ran('easyeffects') == [expect]
    assert mach.machine.snap.effects is effects, 'unchanged until it is read back'
    assert mach.machine.recheck_at > 0


# ---- the subwoofer ------------------------------------------------------
TEN = (40000, 40000, 40000, 40000, 0, 0, 0, 0, 0, 0)      # a 10-channel interface
MUTED = (40000, 40000, 0, 0, 0, 0, 0, 0, 0, 0)


def with_sub(mod, volumes=TEN, **kw):
    return mod.Snapshot(sinks=SINKS + ('alsa_output.usb-TASCAM_SERIES_208i-00.multichannel',),
                        sources=SOURCES, sub=volumes, **kw)


@pytest.fixture
def live(mod, monkeypatch):
    """What a fresh read of the interface returns when the pad is pressed.

    The button re-reads rather than using the snapshot, so the tests have to
    say what the read finds -- which is the point: they can now make the two
    disagree.
    """
    box = {'volumes': TEN}
    monkeypatch.setattr(mod, 'channel_volumes', lambda sink: box['volumes'])
    return box


def test_the_sub_is_two_channels_of_an_interface_not_a_device(mod):
    """Which is why muting it cannot be pactl set-sink-mute, and why cutting
    its links would not stick: a watcher outside this program restores them."""
    assert mod.SUB_CHANNELS == (2, 3)
    assert mod.MAIN_CHANNELS == (0, 1)


@pytest.mark.parametrize('volumes,colour', [
    (TEN,   'SUB_ON'),
    (MUTED, 'SUB_MUTE'),
    ((),    'OFF'),                                        # no interface, no sub
])
def test_the_sub_pad_shows_whether_it_is_muted(mach, mod, volumes, colour):
    painted = show(mach, mod, with_sub(mod, volumes, sink='game_stereo'), mod.CTRL_ROW)
    assert painted[col_of(mod, 'sub')] == getattr(mod, colour)


def wrote(mod):
    """The ten channel values the press sent to pactl."""
    return [int(v) for v in ran('pactl')[0][3:]]


def test_the_two_states_leave_the_speakers_at_the_same_loudness(mod):
    """The interface sums the sub's channels into the speakers, so muting the
    sub would take 6dB off them. Half plus half is one, and one is one."""
    half = (mod.SUB_HALF / 65536) ** 3                     # PulseAudio is cubic
    assert round(half, 3) == 0.5
    assert round(half + half, 3) == round((mod.SUB_FULL / 65536) ** 3, 3) == 1.0


def test_turning_the_sub_off_gives_the_speakers_their_own_full_level(mach, mod, live):
    live['volumes'] = (mod.SUB_HALF,) * 4 + (0,) * 6       # sub currently on
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, sink='game_stereo'))
    assert wrote(mod)[:4] == [mod.SUB_FULL, mod.SUB_FULL, 0, 0]


def test_turning_the_sub_on_halves_everything(mach, mod, live):
    live['volumes'] = (mod.SUB_FULL, mod.SUB_FULL, 0, 0) + (0,) * 6
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, MUTED, sink='game_stereo'))
    assert wrote(mod)[:4] == [mod.SUB_HALF] * 4


def test_there_is_nothing_to_remember(mach, mod, live):
    """Two states, both fixed. A level carried across a mute is a level that
    can be lost, or restored wrong after a restart."""
    assert not hasattr(mach.machine, '_sub_level')
    live['volumes'] = (mod.SUB_HALF,) * 4 + (0,) * 6
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, sink='game_stereo'))
    off = wrote(mod)
    FakePopen.instances.clear()
    live['volumes'] = tuple(off)
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, MUTED, sink='game_stereo'))
    on = wrote(mod)
    assert off[:4] == [mod.SUB_FULL, mod.SUB_FULL, 0, 0]
    assert on[:4] == [mod.SUB_HALF] * 4, 'straight back, no history involved'


def test_the_other_channels_are_left_alone(mach, mod, live):
    live['volumes'] = (mod.SUB_HALF,) * 4 + (12345,) * 6
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, sink='game_stereo'))
    assert wrote(mod)[4:] == [12345] * 6


def test_a_stale_snapshot_cannot_write_over_the_speakers(mach, mod, live):
    """THE HAZARD: a volume is set by writing every channel at once, so acting
    on a reading up to a second old could push stale values back onto channels
    this button does not own. Here the poll still shows the speakers at zero --
    caught mid-change by something else -- and the press must not write that.
    """
    live['volumes'] = TEN                                  # what is true now
    stale = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)                 # what the poll saw
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, stale, sink='game_stereo'))
    written = wrote(mod)
    assert written[:4] == [mod.SUB_FULL, mod.SUB_FULL, 0, 0], \
        'acted on the fresh read: the sub was on, so this turns it off'
    assert written[4:] == list(TEN[4:]), 'and the rest came from the read too'


def test_pressing_the_sub_pad_with_no_interface_does_nothing(mach, mod):
    press(mach, mod, col_of(mod, 'sub'), mod.Snapshot(sinks=SINKS, sink='game_stereo'))
    assert ran() == []


def test_the_sub_pad_reads_back_rather_than_assuming(mach, mod, live):
    before = mach.machine.snap.sub
    press(mach, mod, col_of(mod, 'sub'), with_sub(mod, sink='game_stereo'))
    assert mach.machine.snap.sub == before or mach.machine.snap.sub == TEN
    assert mach.machine.recheck_at > 0


def test_reading_the_channel_volumes(mod, monkeypatch):
    reply = ('Volume: aux0: 65536 / 100% / 0.00 dB,   aux1: 65536 / 100% / 0.00 dB,   '
             'aux2: 0 / 0% / -inf dB,   aux3: 0 / 0% / -inf dB\n        balance 0.00\n')
    monkeypatch.setattr(mod, 'sh', lambda *a, **k: reply)
    assert mod.channel_volumes('tascam') == (65536, 65536, 0, 0)
    assert mod.sub_muted((65536, 65536, 0, 0)) is True
    assert mod.sub_muted((65536, 65536, 65536, 65536)) is False
    assert mod.sub_muted((65536, 65536)) is False, 'a stereo sink has no sub'
    assert mod.channel_volumes('') == ()


def test_a_stereo_sink_is_not_mistaken_for_the_interface(mod, monkeypatch):
    """front-left/front-right deliberately do not match: the sub lives on a
    multichannel device or nowhere."""
    monkeypatch.setattr(mod, 'sh', lambda *a, **k:
                        'Volume: front-left: 26212 / 40%,   front-right: 26212 / 40%\n')
    assert mod.channel_volumes('game_stereo') == ()


# ---- asking EasyEffects which preset is loaded ---------------------------
@pytest.fixture
def asked(mod, monkeypatch):
    """Record what the poller shells out for, and answer for it."""
    calls, answers = [], {'easyeffects': 'at headphones\n\n2\n',
                          'pgrep': '858705\n',          # EasyEffects is up
                          'xdotool': ''}
    def fake_sh(*cmd, **kw):
        calls.append(list(cmd))
        return answers.get(cmd[0], '')
    monkeypatch.setattr(mod, 'sh', fake_sh)
    return calls, answers


def asked_ee(calls):
    return [c for c in calls if c[0] == 'easyeffects']


ASK = ['easyeffects', '-b', '3', '-a', 'output']


def looking(mach):
    mach.machine.assume(running=True)
    mach.machine.attend()
    return mach.machine


def test_easyeffects_is_not_asked_when_nobody_is_looking(mach, mod, asked):
    """It costs a process, and the pad it colours is only drawn on one tab."""
    calls, _ = asked
    mach.machine.assume(running=True)
    mach.machine.watched = 0.0
    mach.machine.read_easyeffects()
    assert asked_ee(calls) == []


def test_it_is_not_asked_when_it_is_not_running(mach, mod, asked):
    """The query would start the very thing it is asking about."""
    calls, _ = asked
    mach.machine.assume(running=False)
    mach.machine.attend()
    mach.machine.read_easyeffects()
    assert asked_ee(calls) == []


def test_drawing_the_tab_makes_it_ask(mach, mod, asked):
    calls, _ = asked
    looking(mach).read_easyeffects()
    assert asked_ee(calls) == [ASK], 'one process, both answers'
    assert mach.machine.snap.preset == 'at headphones'
    assert mach.machine.snap.effects is True


@pytest.mark.parametrize('reply,preset,effects', [
    ('at headphones\n\n2\n', 'at headphones', True),
    ('room\n\n1\n', 'room', False),
    ('2\n', None, True),
    ('', None, None),
])
def test_what_it_makes_of_the_reply(mach, mod, asked, reply, preset, effects):
    """1 is bypassed, 2 is not; the preset comes back on the line above."""
    calls, answers = asked
    answers['easyeffects'] = reply
    mach.machine.assume(preset='before', effects=False)
    looking(mach).read_easyeffects()
    assert mach.machine.snap.preset == (preset if preset is not None else 'before')
    assert mach.machine.snap.effects is (effects if effects is not None else False)


def test_a_press_is_confirmed_by_easyeffects_not_overwritten(mach, mod, asked):
    """THE BUG: bypass was read from the config file, which EasyEffects writes
    lazily. Pressing the pad off set it off, and a second later the poll read
    the not-yet-written file and set it back on -- the pad springing green
    while the tray showed it off.
    """
    calls, answers = asked
    answers['easyeffects'] = 'room\n\n1\n'                 # EasyEffects: bypassed
    mach.machine.assume(running=True, effects=True)
    mach.machine.set_effects(False)
    assert mach.machine.recheck_at > 0, 'the press asks to be read back'
    looking(mach).read_easyeffects()
    assert mach.machine.snap.effects is False, 'and the read is what sets it'


def test_the_read_back_runs_off_the_poller_thread(mach, mod, asked):
    """A press must not wait on easyeffects: the thread that reads the pads is
    the thread that draws them, and the query takes a quarter of a second."""
    calls, _ = asked
    m = looking(mach)
    m.set_effects(False)
    assert asked_ee(calls) == [], 'nothing queried on the input thread'
    m.poll_once()
    assert asked_ee(calls) == [ASK], 'the poller picks it up'


def test_the_read_back_does_not_wait_for_the_next_cadence(mach, mod, asked):
    """Without this the pad sits wrong for up to a second after every press."""
    calls, _ = asked
    m = looking(mach)
    m.poll_once()                                          # everything just ran
    calls.clear()
    m.poll_once()                                          # nothing due yet
    assert asked_ee(calls) == []
    m.recheck()
    m.attend(now=m.recheck_at)
    m.poll_once(now=m.recheck_at)
    assert asked_ee(calls) == [ASK], 'the press jumps the queue'


def test_leaving_the_tab_stops_the_asking_immediately(mach, mod, asked):
    """THE BUG: a three second grace period meant another query -- and so
    another EasyEffects window closing -- landed after you had switched away
    precisely to stop it. Leaving is an event, not something to time out."""
    calls, _ = asked
    m = looking(mach)
    m.read_easyeffects()
    assert len(asked_ee(calls)) == 1, 'asked while the tab was up'
    mach.press(mod.pad(mod.FUNC_ROW, mod.M_POMO))          # switch away
    m.read_easyeffects()
    m.read_easyeffects()
    assert len(asked_ee(calls)) == 1, 'and not once more after leaving'


def test_switching_between_tabs_that_both_show_it_keeps_asking(mach, mod, asked):
    """Only leaving for a tab without the control row stops it."""
    calls, _ = asked
    m = looking(mach)
    mach.press(mod.pad(mod.FUNC_ROW, mod.M_MACH))          # the same tab again
    m.read_easyeffects()
    assert len(asked_ee(calls)) == 1


def test_the_idle_backstop_is_about_a_frame(mod):
    """It only exists for frames stopping some other way; longer, and it starts
    doing what leave() is there to prevent."""
    assert mod.Machine.PRESET_IDLE <= 1.0


def test_it_asks_every_time_while_the_tab_is_up(mach, mod, asked):
    """A preset or a bypass changed in the EasyEffects UI has to show up on the
    pad, and nothing about the output changes when it does."""
    calls, _ = asked
    m = looking(mach)
    for _ in range(3):
        m.read_easyeffects()
    assert len(asked_ee(calls)) == 3


def test_it_asks_even_with_the_easyeffects_window_open(mach, mod, asked):
    """The query closes that window, and it is asked anyway: a pad quietly
    disagreeing with the UI is worse than a window shutting, which is at least
    obvious and stops as soon as you leave the tab."""
    calls, _ = asked
    looking(mach).read_easyeffects()
    assert asked_ee(calls) == [ASK]
    assert not [c for c in calls if c[0] == 'xdotool'], 'no window check at all'


def test_nothing_reads_the_config_file_for_state_any_more(mod):
    """It is a lazily written record, not a signal: it named the previous
    preset a minute after the switch, and reading bypass out of it is what
    made a pressed pad spring back to green.
    """
    src = open(mod.__file__).read()
    assert 'read_bypass' not in src
    assert 'lastLoadedOutputPreset' not in src


def test_drawing_the_machine_tab_counts_as_looking(mach, mod):
    mach.machine.watched = 0.0
    mach.render_machine()
    assert mach.machine.watched > 0.0


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
