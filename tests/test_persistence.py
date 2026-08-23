"""State file: round trip, migrations, and the failure paths that used to be
silently swallowed."""
import json
import pytest
from lpharness import load_pomodoro, new_board, FakeOut


def test_roundtrip_rows_toggles_habits_mode(mod, board, state_file):
    board.rows[2] = {'state': mod.RUNNING, 'started': 1_000_123.0}
    board.rows[4] = {'state': mod.CLAIMED, 'started': 0.0}
    board.toggles[(6, 3)] = 2
    board.mode = mod.M_HAB2
    board.habit_sets['2']['3,1'] = {'name': 'gym', 'colour': 33, 'state': 1}
    assert board._flush() is True

    d = json.loads(state_file.read_text())
    assert d['rows']['2'] == {'state': 'running', 'started': 1_000_123.0}
    assert d['toggles'] == {'6,3': 2}
    assert d['mode'] == mod.M_HAB2
    assert d['schema'] == 3

    fresh = new_board(mod, FakeOut())
    assert fresh.rows[2] == {'state': mod.RUNNING, 'started': 1_000_123.0}
    assert fresh.rows[4]['state'] == mod.CLAIMED
    assert fresh.toggles == {(6, 3): 2}
    assert fresh.mode == mod.M_HAB2
    assert fresh.habit_sets['2']['3,1']['name'] == 'gym'


def test_missing_file_gives_clean_defaults(mod):
    b = new_board(mod, FakeOut())
    assert all(b.rows[r] == {'state': mod.IDLE, 'started': 0.0} for r in mod.POMO_ROWS)
    assert b.toggles == {}
    assert b.mode == mod.M_POMO
    assert set(b.habit_sets) == {str(m) for m in mod.HAB_MODES}


def test_corrupt_file_is_preserved_not_overwritten(state_file, clock, capsys):
    state_file.write_text('{"rows": {"1": ')          # truncated mid-write
    m = load_pomodoro(state_file, clock)
    b = new_board(m, FakeOut())
    assert not state_file.exists(), 'unreadable file should have been moved aside'
    bad = state_file.parent / (state_file.name + '.bad')
    assert bad.read_text() == '{"rows": {"1": '
    assert 'unreadable' in capsys.readouterr().out
    # and the writer must not have been armed by a failed load
    assert b._dirty is False


def test_partial_load_still_restores_rows(state_file, clock, capsys):
    """Rows load first; junk further down must not cost us the timers."""
    state_file.write_text(json.dumps({
        'rows': {'3': {'state': 'running', 'started': 999.0}},
        'toggles': {'not-a-pair': 1},          # blows up the toggles comprehension
        'schema': 3}))
    m = load_pomodoro(state_file, clock)
    b = new_board(m, FakeOut())
    assert b.rows[3] == {'state': 'running', 'started': 999.0}
    assert 'partly loaded' in capsys.readouterr().out


def test_migration_schema1_reorders_habit_tabs(state_file, clock):
    """Daily/weekly used to live at modes 2 and 3."""
    state_file.write_text(json.dumps({
        'schema': 1,
        'habit_sets': {'2': {'1,1': {'name': 'daily', 'colour': 3, 'done': True}},
                       '3': {'2,2': {'name': 'weekly', 'colour': 9}}}}))
    m = load_pomodoro(state_file, clock)
    b = new_board(m, FakeOut())
    assert b.habit_sets[str(m.M_HAB)]['1,1']['name'] == 'daily'
    assert b.habit_sets[str(m.M_HAB2)]['2,2']['name'] == 'weekly'
    # schema < 3 also turns done -> state
    assert b.habit_sets[str(m.M_HAB)]['1,1']['state'] == 2
    assert 'done' not in b.habit_sets[str(m.M_HAB)]['1,1']
    assert b.habit_sets[str(m.M_HAB2)]['2,2']['state'] == 0
    assert b._dirty is True, 'the migrated layout should be written back out'


def test_migration_flat_habits_key(state_file, clock):
    state_file.write_text(json.dumps({
        'schema': 2, 'habits': {'4,4': {'name': 'old', 'colour': 13, 'state': 1}}}))
    m = load_pomodoro(state_file, clock)
    b = new_board(m, FakeOut())
    assert b.habit_sets[str(m.M_HAB)]['4,4']['name'] == 'old'
    assert b.habit_sets[str(m.M_HAB2)] == {}


def test_unknown_row_keys_are_ignored(seed, mod):
    seed(rows={'1': {'state': 'running', 'started': 5.0},
               '99': {'state': 'running', 'started': 5.0}})
    b = new_board(mod, FakeOut())
    assert b.rows[1]['state'] == 'running'
    assert 99 not in b.rows


def test_bad_persisted_mode_falls_back(seed, mod):
    seed(mode=42)
    assert new_board(mod, FakeOut()).mode == mod.M_POMO


def test_writer_keeps_dirty_when_the_write_fails(board, monkeypatch, mod):
    board.save()
    assert board._dirty is True
    monkeypatch.setattr(board, '_flush', lambda: False)
    assert board._flush_if_dirty() is False
    assert board._dirty is True, 'a failed write must stay queued, not be dropped'
    monkeypatch.setattr(board, '_flush', lambda: True)
    assert board._flush_if_dirty() is True
    assert board._dirty is False
    assert board._flush_if_dirty() is False    # nothing left to do


def test_flush_is_atomic(board, state_file):
    board.save()
    board._flush_if_dirty()
    assert state_file.exists()
    assert not (state_file.parent / (state_file.name + '.tmp')).exists()
    json.loads(state_file.read_text())          # always parseable
