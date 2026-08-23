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
    for line in window(mod):
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
