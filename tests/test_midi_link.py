"""Noticing that the Launchpad has gone away and come back.

The board's ports are ALSA sequencer ports, and a subscription between two of
them belongs to the kernel client. When the device re-enumerates on USB the
kernel destroys that client and builds a new one, and the subscription does not
survive it. Nothing reports this: sending to an unsubscribed port succeeds. The
board rendered into nothing for ten hours the day this was written.
"""
import pytest
from lpharness import FakeIn, FakeOut, _fake_mido, new_board

PORT = 'Launchpad Mini MK3:Launchpad Mini MK3 LPMiniMK3 MI 24:1'
ALSA = 'Launchpad Mini MK3 LPMiniMK3 MI'


def clients(tmp_path, body):
    p = tmp_path / 'clients'
    p.write_text(body)
    return str(p)


LINKED = f"""Client info
  cur  clients : 8
Client  14 : "Midi Through" [Kernel Legacy]
  Port   0 : "Midi Through Port-0" (RWe-) [In/Out]
Client  24 : "Launchpad Mini MK3" [Kernel Legacy]
  Port   0 : "Launchpad Mini MK3 LPMiniMK3 DA" (RWeX) [In/Out]
  Port   1 : "{ALSA}" (RWeX) [In/Out]
    Connecting To: 129:0
    Connected From: 128:0[r:0]
Client 128 : "RtMidiOut Client" [User Legacy]
  Port   0 : "RtMidi output" (R-e-) [In]
    Connecting To: 24:1[r:0]
"""

# what 19:37 looked like: the device is back, the client is new, and nothing
# is subscribed to it
DROPPED = f"""Client  24 : "Launchpad Mini MK3" [Kernel Legacy]
  Port   0 : "Launchpad Mini MK3 LPMiniMK3 DA" (RWeX) [In/Out]
  Port   1 : "{ALSA}" (RWeX) [In/Out]
Client 128 : "RtMidiOut Client" [User Legacy]
  Port   0 : "RtMidi output" (R-e-) [In]
"""


def test_a_subscribed_port_is_linked(mod, tmp_path):
    assert mod.midi_linked(PORT, clients(tmp_path, LINKED)) is True


def test_the_state_that_went_unnoticed_for_ten_hours(mod, tmp_path):
    assert mod.midi_linked(PORT, clients(tmp_path, DROPPED)) is False


def test_half_a_link_is_not_a_link(mod, tmp_path):
    """Sending to the pads with no presses coming back is as dead as neither."""
    for way in ('    Connecting To: 129:0\n', '    Connected From: 128:0[r:0]\n'):
        body = DROPPED.replace(f'"{ALSA}" (RWeX) [In/Out]\n',
                               f'"{ALSA}" (RWeX) [In/Out]\n' + way)
        assert mod.midi_linked(PORT, clients(tmp_path, body)) is False


def test_a_subscription_on_another_port_is_not_ours(mod, tmp_path):
    """The DAW port is a different port and does not honour programmer mode,
    so something talking to it says nothing about us."""
    body = f"""Client  24 : "Launchpad Mini MK3" [Kernel Legacy]
  Port   0 : "Launchpad Mini MK3 LPMiniMK3 DA" (RWeX) [In/Out]
    Connecting To: 129:0
    Connected From: 128:0[r:0]
  Port   1 : "{ALSA}" (RWeX) [In/Out]
Client 128 : "RtMidiOut Client" [User Legacy]
"""
    assert mod.midi_linked(PORT, clients(tmp_path, body)) is False


@pytest.mark.parametrize('name', [PORT, ALSA, f'x:{ALSA} 24:1', f'{ALSA} 128:0'])
def test_the_port_name_is_found_however_it_is_spelled(mod, tmp_path, name):
    """mido names carry the client:port on the end and the client name on the
    front; the kernel's own name is what is in the middle."""
    assert mod.midi_linked(name, clients(tmp_path, LINKED)) is True
    assert mod.midi_linked(name, clients(tmp_path, DROPPED)) is False


@pytest.mark.parametrize('name', ['', None, 'Some Other Device 99:0'])
def test_anything_it_cannot_answer_counts_as_linked(mod, tmp_path, name):
    """Reconnecting for no reason is worse than not noticing: it would take
    the board through a full repaint on every check."""
    assert mod.midi_linked(name, clients(tmp_path, LINKED)) is True


def test_an_unreadable_file_counts_as_linked(mod):
    assert mod.midi_linked(PORT, '/proc/nothing/here') is True


# ---- and putting it back -------------------------------------------------

def test_relinking_reopens_and_repaints(mod, board):
    """A re-enumerated Launchpad comes back dark and in live mode, so this is
    not a reconnection: programmer mode again, and all 64 pads redrawn."""
    mod.mido = _fake_mido([PORT])
    board.render()
    assert board.shown, 'the board thinks it knows what the pads show'
    old_out = board.out
    out, inp = mod.relink(board, board.out, FakeIn())
    assert old_out.closed, 'the port that lost its subscription is let go'
    assert board.out is out and not board.shown, 'nothing is known about them now'
    assert out.sent[0].type == 'sysex', 'programmer mode, before anything else'
    assert list(out.sent[0].data) == mod.SYSEX_PROGRAMMER


def test_a_launchpad_that_is_not_there_leaves_the_board_running(mod, board):
    """A pomodoro started before the cable came out still finishes, and still
    chimes. It just has nowhere to draw."""
    mod.mido = _fake_mido([])
    out, inp = mod.relink(board, board.out, FakeIn())
    assert isinstance(out, mod.NullPort) and isinstance(inp, mod.NullPort)
    board.render()                                  # must not raise
    assert list(inp.iter_pending()) == []


def test_the_port_names_are_the_midi_ones_not_the_daw_ones(mod):
    """Only the MIDI port honours programmer mode."""
    mod.mido = _fake_mido(['Launchpad Mini MK3 LPMiniMK3 DA 24:0',
                           'Launchpad Mini MK3 LPMiniMK3 MI 24:1'])
    assert mod.midi_ports() == ('Launchpad Mini MK3 LPMiniMK3 MI 24:1',) * 2


def test_nothing_that_is_not_a_launchpad_is_picked_up(mod):
    mod.mido = _fake_mido(['SERIES 208i MIDI OUT 28:0', 'Midi Through Port-0 14:0'])
    assert mod.midi_ports() == (None, None)
