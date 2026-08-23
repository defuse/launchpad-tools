"""Holding a read-only pad on the machine tab opens the readout window.

The board end only: what it sends, when it starts the process, and that the
values match the pads. The window itself is tested in test_machine_popup.py.
"""
import json
import pytest
from lpharness import FakeOut, FakePopen, new_board


@pytest.fixture
def mach(board, mod):
    board.mode = mod.M_MACH
    board.machine.snap = mod.Snapshot(
        disks=(('sda', 'ok'), ('sdb', 'sync'), ('sdc', 'fail')),
        drives=(('sda', 31.0, False), ('sdb', 47.0, True), ('sdc', 36.0, True)),
        mounts=((mod.MOUNTS[0], 37.0, 8.0), (mod.MOUNTS[1], 1200.0, 63.0)),
        temps=((mod.SENSORS[0], 62.0), (mod.SENSORS[1], 88.0)))
    return board


def window(mod):
    """Lines the board sent to the machine window."""
    for p in FakePopen.instances:
        if 'machine-popup' in p.argv[0]:
            return p.sent()
    return []


def cells(mod):
    """The LAST frame the window was given -- what it is showing now."""
    for line in reversed(window(mod)):
        if line.startswith('data\t'):
            return {(c['r'], c['c']): c for c in json.loads(line.split('\t', 1)[1])}
    return {}


def test_nothing_is_spawned_until_a_pad_is_held(mach, mod):
    """A window process per boot, for a feature used seconds at a time, is a
    process that spends all day doing nothing."""
    assert window(mod) == []


def test_holding_a_disk_pad_shows_it_with_that_cell_marked(mach, mod):
    col = mod.centred(3) + 1                                # sdb, second of three
    mach.press(mod.pad(mod.DISK_ROW, col))
    assert window(mod)[-1] == f'show\t{mod.DISK_ROW}\t{col}'
    assert cells(mod)[(mod.DISK_ROW, col)]['name'] == 'sdb'


def test_releasing_hides_it(mach, mod):
    col = mod.centred(3)
    mach.press(mod.pad(mod.DISK_ROW, col))
    mach.release(mod.pad(mod.DISK_ROW, col))
    assert window(mod)[-1] == 'hide'


@pytest.mark.parametrize('row', ['DISK_ROW', 'FS_ROW', 'DRIVE_TEMP_ROW', 'TEMP_ROW'])
def test_every_read_only_row_can_be_peeked(mach, mod, row):
    r = getattr(mod, row)
    mach.press(mod.pad(r, mod.centred(2)))
    assert any(l.startswith('show\t') for l in window(mod))


def test_the_control_row_is_not_a_peek(mach, mod):
    """It does things; holding it should not put a window over them."""
    mach.press(mod.pad(mod.CTRL_ROW, 0))
    assert not any(l.startswith('show\t') for l in window(mod))


def test_the_values_are_the_ones_the_pads_are_drawn_from(mach, mod):
    mach.press(mod.pad(mod.DISK_ROW, mod.centred(3)))
    c = cells(mod)
    first = mod.centred(3)
    assert c[(mod.DISK_ROW, first)]['value'] == 'ok'
    assert c[(mod.DISK_ROW, first + 2)]['value'] == 'fail'
    assert c[(mod.DRIVE_TEMP_ROW, first + 1)]['value'] == '47C'
    assert c[(mod.FS_ROW, mod.centred(2))]['value'] == '37 GB'
    assert c[(mod.FS_ROW, mod.centred(2) + 1)]['value'] == '1.2 TB', 'terabytes read better'
    assert c[(mod.TEMP_ROW, mod.centred(2))]['value'] == '62C'


def test_a_temperature_names_its_drive_and_kind(mach, mod):
    """Which drive, because the column only says that if you can also see the
    health row; and which kind, because the thresholds differ by a wide margin
    and that explains a colour which would otherwise look wrong."""
    mach.press(mod.pad(mod.DRIVE_TEMP_ROW, mod.centred(3)))
    c = cells(mod)
    first = mod.centred(3)
    assert c[(mod.DRIVE_TEMP_ROW, first)]['name'] == 'sda SSD'
    assert c[(mod.DRIVE_TEMP_ROW, first + 1)]['name'] == 'sdb HDD'


def test_a_filesystem_gives_both_the_size_and_the_share(mach, mod):
    """37GB is roomy on a root partition and nothing on a 12TB array; a
    percentage alone hides how much there is to work with."""
    mach.press(mod.pad(mod.FS_ROW, mod.centred(2)))
    c = cells(mod)
    first = mod.centred(2)
    assert c[(mod.FS_ROW, first)]['value'] == '37 GB'
    assert c[(mod.FS_ROW, first)]['detail'] == '8% free'
    assert c[(mod.FS_ROW, first)]['name'] == mod.MOUNTS[0].path, 'the path, not a nickname'
    assert c[(mod.FS_ROW, first + 1)]['value'] == '1.2 TB'
    assert c[(mod.FS_ROW, first + 1)]['detail'] == '63% free'
    assert c[(mod.FS_ROW, first + 1)]['name'].endswith('firexware')


def test_the_colours_match_the_pads(mach, mod):
    """47C is fine on an SSD and yellow on a platter; the window has to agree
    with the pad or the peek contradicts what you are looking at."""
    mach.press(mod.pad(mod.DRIVE_TEMP_ROW, mod.centred(3)))
    c = cells(mod)
    first = mod.centred(3)
    assert c[(mod.DRIVE_TEMP_ROW, first + 1)]['colour'] == mod.HEX[mod.YELLOW]  # 47C, HDD
    assert c[(mod.DISK_ROW, first + 2)]['colour'] == mod.HEX[mod.DISK_FAIL]
    assert c[(mod.TEMP_ROW, mod.centred(2) + 1)]['colour'] == mod.HEX[mod.RED]


def test_a_cell_with_no_reading_says_so(mach, mod):
    mach.machine.snap = mach.machine.snap._replace(
        drives=(), temps=((mod.SENSORS[0], None),),
        mounts=((mod.MOUNTS[0], None, None),))
    mach.press(mod.pad(mod.DISK_ROW, mod.centred(3)))
    c = cells(mod)
    assert c[(mod.DRIVE_TEMP_ROW, mod.centred(3))]['value'] == '--'
    assert c[(mod.TEMP_ROW, mod.centred(1))]['value'] == '--'


# ---- the control row, said in words --------------------------------------

@pytest.fixture
def audio(mach, mod):
    """A machine with both outputs present, listening on the speakers, sub
    passing, effects on with the room's preset, and Spotify paused."""
    mach.machine.snap = mach.machine.snap._replace(
        sinks=('alsa_output.game_stereo', 'alsa_input.AT_ATH-M50xSTS'),
        sources=('alsa_input.AT_ATH-M50xSTS',),
        sink='alsa_output.game_stereo',
        sub=(52016,) * 10, running=True, effects=True,
        preset='room', headset_preset='m50x')
    return mach


def controls(mach, mod):
    """The control row as the window has it, opening the window if need be.
    Safe to call again after changing the snapshot."""
    if mach._window is None:
        mach.toggle_window()
    mach._machine_send()
    return {c: cell for (r, c), cell in cells(mod).items() if r == mod.CTRL_ROW}


def test_every_button_is_in_the_window_and_the_gap_is_not(audio, mod):
    """The gap is a deliberate hole in the row, and a cell there would invite
    a press that fires nothing."""
    got = controls(audio, mod)
    want = [c for c, b in enumerate(mod.CONTROLS[mod.CTRL_ROW]) if b is not None]
    assert sorted(got) == want


def test_a_button_says_what_it_is(audio, mod):
    """What it IS, not what it is doing: the state is the colour, and a cell
    that also spelled it out would be saying it twice and could disagree with
    itself."""
    c = controls(audio, mod)
    assert c[0]['value'] == mod.GAME_SINK, 'the sink is called what it is called'
    assert c[1]['value'] == mod.HEADSET
    assert c[3]['value'] == 'sub'
    assert c[4]['value'] == 'EasyEffects'
    assert c[6]['value'] == '⏯' and c[5]['value'] == '⏮' and c[7]['value'] == '⏭'


def test_no_button_carries_a_label(audio, mod):
    """A drive temperature needs its drive named; game_stereo does not need a
    line above it saying speakers."""
    assert all(cell['name'] == '' for cell in controls(audio, mod).values())


def test_the_detail_is_what_a_press_would_do(audio, mod):
    c = controls(audio, mod)
    assert c[1]['detail'] == 'press to switch to it'
    assert c[3]['detail'] == 'press to mute'


def test_the_output_you_are_on_has_nothing_to_say(audio, mod):
    """Same rule as the pomodoro window's hints: an instruction for something
    you cannot do is an instruction in the way."""
    assert controls(audio, mod)[0]['detail'] == ''


def test_the_effects_cell_names_the_preset(audio, mod):
    """Which one is loaded is the thing the colour is only hinting at, and the
    names are the user's to change."""
    assert controls(audio, mod)[4]['detail'] == 'room'
    audio.machine.snap = audio.machine.snap._replace(preset='m50x')
    assert controls(audio, mod)[4]['detail'] == 'm50x'
    audio.machine.snap = audio.machine.snap._replace(effects=False)
    c = controls(audio, mod)
    assert c[4]['value'] == 'EasyEffects' and c[4]['detail'] == 'bypassed'


def test_a_muted_sub_says_how_to_get_it_back(audio, mod):
    audio.machine.snap = audio.machine.snap._replace(sub=(0,) * 10)
    c = controls(audio, mod)
    assert (c[3]['value'], c[3]['detail']) == ('sub', 'press to unmute')


def test_an_output_that_is_not_there_says_so(audio, mod):
    """Still by name -- the colour going dark is the missing part."""
    audio.machine.snap = audio.machine.snap._replace(sinks=(), sink='')
    c = controls(audio, mod)
    assert c[0]['value'] == mod.GAME_SINK and c[0]['detail'] == 'not connected'
    assert c[0]['colour'] == mod.HEX[mod.OFF]


def test_the_control_colours_are_the_ones_on_the_pads(audio, mod):
    """Same rule for the window as for the readouts: it has to agree with what
    you are looking at, so the colour comes from the function that lights the
    pad rather than from a second copy of the rules."""
    c = controls(audio, mod)
    for col, b in enumerate(mod.CONTROLS[mod.CTRL_ROW]):
        if b is not None:
            assert c[col]['colour'] == mod.HEX[audio.control_colour(b, audio.machine.snap)]


def test_every_colour_a_control_can_take_has_a_hex(mod):
    """A colour missing from that table arrives as the fallback grey, which is
    the window quietly disagreeing with the board."""
    for colour in (mod.SELECTED, mod.SUB_ON, mod.SUB_MUTE, mod.PLAYING,
                   mod.WHITE, mod.OFF, mod.PRESET_OFF, mod.PRESET_MAIN,
                   mod.PRESET_HEADSET):
        assert colour in mod.HEX


# ---- an open window is kept current --------------------------------------

def test_an_unchanged_frame_is_not_sent_twice(audio, mod):
    audio.toggle_window()
    before = len([l for l in window(mod) if l.startswith('data\t')])
    audio.render_machine()
    audio.render_machine()
    assert len([l for l in window(mod) if l.startswith('data\t')]) == before


def test_a_control_changing_reaches_the_open_window(audio, mod):
    """Press headset on the board and the window still said speakers: it was
    sent once, when it opened."""
    audio.toggle_window()
    was = {col: cell['colour'] for (r, col), cell in cells(mod).items()
           if r == mod.CTRL_ROW}
    audio.machine.snap = audio.machine.snap._replace(
        sink='alsa_input.AT_ATH-M50xSTS')
    audio.render_machine()
    now = {col: cell['colour'] for (r, col), cell in cells(mod).items()
           if r == mod.CTRL_ROW}
    assert was[0] == mod.HEX[mod.SELECTED] and now[0] == mod.HEX[mod.WHITE]
    assert now[1] == mod.HEX[mod.SELECTED], 'the headset is the one in use now'


def test_a_closed_window_is_not_written_to(audio, mod):
    audio.render_machine()
    assert not [l for l in window(mod) if l.startswith('data\t')]


def test_a_respawned_window_is_told_everything_again(audio, mod):
    """It is a new process: whatever the last one was sent, it does not know."""
    audio.toggle_window()
    for p in FakePopen.instances:
        if 'machine-popup' in p.argv[0]:
            p.alive = False
    audio.render_machine()
    fresh = [p for p in FakePopen.instances if 'machine-popup' in p.argv[0]][-1]
    assert any(l.startswith('data\t') for l in fresh.sent())
