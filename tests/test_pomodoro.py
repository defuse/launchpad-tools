"""The pomodoro state machine, the hold-to-abandon timer and reset scoping."""
import pytest
from lpharness import FakeOut, new_board


# A pomodoro row to exercise the state machine on. Row 1 is the day bar, so the
# timers are rows 2..5; ROW is deliberately not 2 or 3, which several tests use
# as "some other row" alongside it.
ROW = 4


def test_the_row_these_tests_use_is_a_pomodoro_row(mod):
    """Guards every literal below: if the layout moves, this fails first and
    says so, instead of thirty tests failing with a KeyError."""
    assert ROW in mod.POMO_ROWS
    assert mod.BAR_ROW not in mod.POMO_ROWS


def col0(mod, row):
    return mod.pad(row, 0)


def tab(mod, mode):
    return mod.pad(mod.FUNC_ROW, mode)


# ---- state machine -------------------------------------------------------

def test_idle_leftmost_press_starts_it(board, mod, clock):
    board.press(col0(mod, ROW))
    assert board.rows[ROW]['state'] == mod.RUNNING
    assert board.rows[ROW]['started'] == clock.time()
    assert board._dirty is True


def test_idle_press_anywhere_but_the_left_does_nothing(board, mod):
    for c in range(1, mod.CELLS):
        board.press(mod.pad(ROW, c))
        board.release(mod.pad(ROW, c))
    assert board.rows[ROW]['state'] == mod.IDLE


def test_running_becomes_elapsed_and_chimes(board, mod, clock):
    board.press(col0(mod, 2)); board.release(col0(mod, 2))
    clock.advance(mod.CELLS * mod.POMODORO.step - 1)
    board.tick()
    assert board.rows[2]['state'] == mod.RUNNING
    assert [d[1] for d in mod.dings] == ['start.wav']

    clock.advance(1)
    board.tick()
    assert board.rows[2]['state'] == mod.ELAPSED
    assert mod.dings[-1] == (clock.time(), 'finish.wav')


def test_elapsed_chimes_exactly_once(board, mod, clock):
    board.rows[3] = {'state': mod.RUNNING, 'started': clock.time() - 99_999}
    for _ in range(20):
        board.tick(); board.render(); clock.advance(0.05)
    assert [d[1] for d in mod.dings].count('finish.wav') == 1


def test_elapsed_runs_in_every_mode(board, mod, clock):
    """A pomodoro must finish while you are looking at another tab."""
    for mode in mod.TABS:
        b = new_board(mod, FakeOut())
        b.mode = mode
        b.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time() - 99_999}
        b.tick()
        assert b.rows[ROW]['state'] == mod.ELAPSED, f'stalled in mode {mode}'


def test_elapsed_claim_and_fail(board, mod, clock):
    board.rows[ROW] = {'state': mod.ELAPSED, 'started': 1.0}
    board.press(mod.pad(ROW, mod.CELLS - 1))
    assert board.rows[ROW]['state'] == mod.CLAIMED

    board.rows[2] = {'state': mod.ELAPSED, 'started': 1.0}
    board.press(mod.pad(2, 3))
    assert board.rows[2] == {'state': mod.IDLE, 'started': 0}


def test_claimed_leftmost_returns_to_idle(board, mod):
    board.rows[5] = {'state': mod.CLAIMED, 'started': 7.0}
    board.press(mod.pad(5, 4))
    assert board.rows[5]['state'] == mod.CLAIMED, 'only the leftmost pad resets it'
    board.press(col0(mod, 5))
    assert board.rows[5] == {'state': mod.IDLE, 'started': 0}


def test_render_draws_the_progress_bar(board, mod, clock, out):
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time() - 3 * mod.POMODORO.step}
    board.render()
    lit = out.lit()
    assert [lit[mod.pad(ROW, c)] for c in range(3)] == [mod.GREEN] * 3
    assert lit[mod.pad(ROW, 7)] == mod.OFF


def test_render_never_transitions_state(board, mod, clock):
    """render() draws; tick() owns transitions. Both doing it double-chimed."""
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time() - 99_999}
    board.render()
    assert board.rows[ROW]['state'] == mod.RUNNING
    assert mod.dings == []


# ---- chimes --------------------------------------------------------------

def test_starting_from_idle_chimes_exactly_once(board, mod, clock):
    board.press(col0(mod, ROW))
    assert [d[1] for d in mod.dings] == ['start.wav']
    clock.advance(0.2)
    board.release(col0(mod, ROW))
    board.tick(); board.render()
    assert [d[1] for d in mod.dings] == ['start.wav'], 'one press, one chime'


def test_pressing_a_running_row_changes_nothing_and_is_silent(board, mod, clock):
    board.press(col0(mod, ROW)); board.release(col0(mod, ROW))
    started = board.rows[ROW]['started']
    mod.dings.clear()
    clock.advance(60)
    for c in range(mod.CELLS):
        board.press(mod.pad(ROW, c)); board.release(mod.pad(ROW, c))
    assert board.rows[ROW]['state'] == mod.RUNNING
    assert board.rows[ROW]['started'] == started
    assert mod.dings == []


def test_recycling_a_claimed_row_takes_two_presses(board, mod, clock):
    """Documented behaviour, not a bug: claimed -> idle -> running. Only the
    second press starts a pomodoro, so only the second one chimes."""
    board.rows[ROW] = {'state': mod.CLAIMED, 'started': 5.0}
    board.press(col0(mod, ROW)); board.release(col0(mod, ROW))
    assert board.rows[ROW]['state'] == mod.IDLE
    assert mod.dings == []
    clock.advance(0.5)
    board.press(col0(mod, ROW)); board.release(col0(mod, ROW))
    assert board.rows[ROW]['state'] == mod.RUNNING
    assert [d[1] for d in mod.dings] == ['start.wav']


def test_elapsed_transitions_are_silent(board, mod):
    board.rows[ROW] = {'state': mod.ELAPSED, 'started': 5.0}
    board.press(mod.pad(ROW, mod.CELLS - 1))            # claim it
    board.rows[2] = {'state': mod.ELAPSED, 'started': 5.0}
    board.press(mod.pad(2, 2))                        # give up on it
    assert (board.rows[ROW]['state'], board.rows[2]['state']) == (mod.CLAIMED, mod.IDLE)
    assert mod.dings == [], 'only starting and finishing make a sound'


# ---- hold to abandon -----------------------------------------------------

def test_a_short_press_does_not_abandon(board, mod, clock):
    """The start gesture and the abandon gesture are the same pad, so an
    ordinary press must never cross the threshold."""
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time() - 300}
    board.press(col0(mod, ROW))
    for _ in range(8):                                # ~0.4 s with the pad down
        clock.advance(0.05); board.tick(); board.render()
    board.release(col0(mod, ROW))
    board.tick(); board.render()
    assert board.rows[ROW]['state'] == mod.RUNNING
    assert board.held == {}


def test_starting_a_pomodoro_survives_the_finger_still_being_down(board, mod, clock):
    board.press(col0(mod, ROW))
    assert board.rows[ROW]['state'] == mod.RUNNING
    for _ in range(10):
        clock.advance(0.05); board.tick(); board.render()
    board.release(col0(mod, ROW))
    assert board.rows[ROW]['state'] == mod.RUNNING



def test_hold_leftmost_abandons_the_row(board, mod, clock):
    board.rows[3] = {'state': mod.RUNNING, 'started': clock.time()}
    board.press(col0(mod, 3))
    clock.advance(mod.RESET_HOLD - 0.1); board.render()
    assert board.rows[3]['state'] == mod.RUNNING, 'must not fire early'
    clock.advance(0.2); board.render()
    assert board.rows[3] == {'state': mod.IDLE, 'started': 0.0}
    assert board._dirty is True


def test_letting_go_early_cancels_the_abandon(board, mod, clock):
    board.rows[3] = {'state': mod.RUNNING, 'started': clock.time()}
    board.press(col0(mod, 3))
    clock.advance(1.0); board.render()
    board.release(col0(mod, 3))
    clock.advance(5.0); board.render()
    assert board.rows[3]['state'] == mod.RUNNING


def test_abandon_only_touches_its_own_row(board, mod, clock):
    for r in mod.POMO_ROWS:
        board.rows[r] = {'state': mod.RUNNING, 'started': clock.time()}
    board.press(col0(mod, ROW))
    clock.advance(mod.RESET_HOLD + 0.1); board.render()
    assert board.rows[ROW]['state'] == mod.IDLE
    others = [r for r in mod.POMO_ROWS if r != ROW]
    assert [board.rows[r]['state'] for r in others] == [mod.RUNNING] * len(others)


def test_abandon_shows_the_row_filling(board, mod, clock, out):
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time()}
    board.press(col0(mod, ROW))
    clock.advance(1.0); board.render()          # half way
    lit = out.lit()
    red = [c for c in range(mod.CELLS) if lit[mod.pad(ROW, c)] == mod.RED]
    assert red == list(range(len(red))) and 0 < len(red) < mod.CELLS


# ---- the reset pad -------------------------------------------------------

def test_reset_pad_needs_the_full_hold(board, mod, clock):
    """Reset fires on RELEASE, not part-way through the hold: the same pad has
    to serve a quick tap (dismiss the habit window) as well."""
    note = mod.pad(mod.FUNC_ROW, mod.RESET_COL)
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time()}

    board.press(note)
    clock.advance(mod.RESET_HOLD - 0.1); board.render()
    assert board.rows[ROW]['state'] == mod.RUNNING     # still held: nothing yet
    board.release(note)
    assert board.rows[ROW]['state'] == mod.RUNNING     # let go early: cancelled

    board.press(note)
    clock.advance(mod.RESET_HOLD + 0.1); board.render()
    assert board.rows[ROW]['state'] == mod.RUNNING     # holding alone does nothing
    board.release(note)
    assert board.rows[ROW]['state'] == mod.IDLE        # released after 2s: reset


def test_reset_pad_tap_closes_the_habit_window(board, mod, clock):
    note = mod.pad(mod.FUNC_ROW, mod.RESET_COL)
    board.mode = mod.M_HAB
    board._editing = (2, 0)
    board.press(note)
    clock.advance(0.2)
    board.release(note)
    assert board._editing is None                    # a tap dismisses the window


def test_reset_pad_tap_does_not_reset(board, mod, clock):
    note = mod.pad(mod.FUNC_ROW, mod.RESET_COL)
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time()}
    board.press(note)
    clock.advance(0.2)
    board.release(note)
    assert board.rows[ROW]['state'] == mod.RUNNING


def test_reset_is_scoped_to_the_pomodoro_tab(board, mod, clock):
    for r in mod.POMO_ROWS:
        board.rows[r] = {'state': mod.RUNNING, 'started': clock.time()}
    board.toggles[(6, 0)] = 1
    board.mode = mod.M_POMO
    board.reset()
    assert all(board.rows[r] == {'state': mod.IDLE, 'started': 0.0} for r in mod.POMO_ROWS)
    assert board.toggles == {}


@pytest.mark.parametrize('mode_name', ['M_SYS', 'M_NET'])
def test_reset_on_a_meter_tab_does_nothing(board, mod, clock, mode_name):
    """It used to wipe every running timer with nothing on screen to show it."""
    for r in mod.POMO_ROWS:
        board.rows[r] = {'state': mod.RUNNING, 'started': clock.time()}
    board.mode = getattr(mod, mode_name)
    board.reset()
    assert all(board.rows[r]['state'] == mod.RUNNING for r in mod.POMO_ROWS)


def test_reset_on_a_habit_tab_clears_states_only(board, mod, clock):
    board.mode = mod.M_HAB
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time()}
    board.habit_sets['1'] = {'2,0': {'name': 'a', 'colour': 3, 'state': 2},
                             '3,0': {'name': 'b', 'colour': 9, 'state': 1}}
    board.reset()
    assert [h['state'] for h in board.habits.values()] == [0, 0]
    assert [h['name'] for h in board.habits.values()] == ['a', 'b']
    assert board.rows[ROW]['state'] == mod.RUNNING, 'pomodoros belong to another tab'


# ---- toggles -------------------------------------------------------------

def test_toggle_rows_cycle(board, mod):
    p = mod.pad(6, 2)
    for expected in (1, 2, 0, 1):
        board.press(p)
        assert board.toggles[(6, 2)] == expected


def test_toggles_are_inert_off_the_pomodoro_tab(board, mod):
    board.mode = mod.M_SYS
    board.press(mod.pad(6, 2))
    assert board.toggles == {}


# ---- break row: same machine, shorter and blue -----------------------------

def test_break_row_is_eight_minutes_not_twentyfour(board, mod, clock):
    assert mod.BREAK.length == 8 * 60
    assert (mod.BREAK.idle, mod.BREAK.fill) == (mod.BLUE, mod.BLUE)
    assert mod.POMODORO.length == 24 * 60
    assert (mod.POMODORO.idle, mod.POMODORO.fill) == (mod.WHITE, mod.GREEN)
    assert mod.TIMERS[mod.BREAK_ROW] is mod.BREAK
    assert {mod.TIMERS[r] for r in mod.POMO_ROWS} == {mod.POMODORO}


def test_break_row_idle_is_light_blue(board, mod):
    board.mode = mod.M_POMO
    board.render()
    assert board.shown[mod.pad(mod.BREAK_ROW, 0)][1] == mod.BLUE
    assert board.shown[mod.pad(mod.BREAK_ROW, 1)][1] == mod.OFF


def test_break_row_fills_blue_a_cell_a_minute(board, mod, clock):
    board.mode = mod.M_POMO
    board.press(mod.pad(mod.BREAK_ROW, 0))
    board.release(mod.pad(mod.BREAK_ROW, 0))
    assert board.rows[mod.BREAK_ROW]['state'] == mod.RUNNING
    clock.advance(60 * 3 + 1)                      # three minutes in
    board.shown.clear(); board.render()
    assert board.shown[mod.pad(mod.BREAK_ROW, 0)][1] == mod.BLUE
    assert board.shown[mod.pad(mod.BREAK_ROW, 2)][1] == mod.BLUE
    assert board.shown[mod.pad(mod.BREAK_ROW, 4)][1] == mod.OFF


def test_break_row_elapses_after_eight_minutes(board, mod, clock):
    board.mode = mod.M_POMO
    board.rows[mod.BREAK_ROW] = {'state': mod.RUNNING, 'started': clock.time()}
    clock.advance(8 * 60 - 5); board.tick()
    assert board.rows[mod.BREAK_ROW]['state'] == mod.RUNNING
    clock.advance(10); board.tick()
    assert board.rows[mod.BREAK_ROW]['state'] == mod.ELAPSED
    board.shown.clear(); board.render()
    # last pad is the claim pad, in the row's own fill colour
    assert board.shown[mod.pad(mod.BREAK_ROW, mod.CELLS - 1)][1] == mod.BLUE
    assert board.shown[mod.pad(mod.BREAK_ROW, 0)][1] == mod.RED


def test_break_row_claim_turns_the_row_blue(board, mod, clock):
    board.mode = mod.M_POMO
    board.rows[mod.BREAK_ROW] = {'state': mod.ELAPSED, 'started': 0.0}
    board.pomo_press(mod.BREAK_ROW, mod.CELLS - 1)
    assert board.rows[mod.BREAK_ROW]['state'] == mod.CLAIMED
    board.shown.clear(); board.render()
    assert all(board.shown[mod.pad(mod.BREAK_ROW, c)][1] == mod.BLUE
               for c in range(mod.CELLS))


def test_row_above_the_break_is_still_a_toggle_row(board, mod):
    assert mod.TOGGLE_ROWS == [6]
    assert mod.BREAK_ROW not in mod.TOGGLE_ROWS
    board.mode = mod.M_POMO
    for expected in (mod.RED, mod.GREEN, mod.OFF):
        board.press(mod.pad(6, 0)); board.release(mod.pad(6, 0))
        board.shown.clear(); board.render()
        assert board.shown[mod.pad(6, 0)][1] == expected


def test_break_and_pomodoro_have_different_chimes(board, mod, clock):
    """Four strikes for the break, three for a pomodoro, so you can tell which
    one ended without looking at the board."""
    assert mod.BREAK.chime == 'break.wav'
    assert mod.POMODORO.chime == 'finish.wav'

    # 'warned' pre-set: this test is about the END chimes, not the warning
    board.rows[mod.BREAK_ROW] = {'state': mod.RUNNING, 'warned': True,
                                 'started': clock.time() - 99_999}
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time() - 99_999}
    board.tick()
    assert sorted(d[1] for d in mod.dings) == ['break.wav', 'finish.wav']


def test_break_chime_fires_exactly_once(board, mod, clock):
    board.rows[mod.BREAK_ROW] = {'state': mod.RUNNING, 'started': clock.time() - 99_999}
    for _ in range(20):
        board.tick(); board.render(); clock.advance(0.05)
    assert [d[1] for d in mod.dings].count('break.wav') == 1


def test_break_warns_two_minutes_before_the_end(board, mod, clock):
    board.mode = mod.M_POMO
    board.press(mod.pad(mod.BREAK_ROW, 0)); board.release(mod.pad(mod.BREAK_ROW, 0))
    mod.dings.clear()
    clock.advance(mod.BREAK.warn[0] - 5); board.tick()
    assert mod.dings == [], 'must not fire early'
    clock.advance(10); board.tick()
    assert [d[1] for d in mod.dings] == ['break-warn.wav']


def test_break_warning_fires_exactly_once(board, mod, clock):
    board.rows[mod.BREAK_ROW] = {'state': mod.RUNNING,
                                 'started': clock.time() - mod.BREAK.warn[0] - 1}
    for _ in range(30):
        board.tick(); clock.advance(0.05)
    assert [d[1] for d in mod.dings].count('break-warn.wav') == 1


def test_a_second_break_warns_again(board, mod, clock):
    """update() keeps existing keys, so a spent 'warned' flag would otherwise
    carry into the next break and silence it."""
    board.mode = mod.M_POMO
    note = mod.pad(mod.BREAK_ROW, 0)
    board.press(note); board.release(note)
    clock.advance(mod.BREAK.warn[0] + 1); board.tick()
    clock.advance(mod.CELLS * mod.BREAK.step); board.tick()
    board.pomo_press(mod.BREAK_ROW, mod.CELLS - 1)          # claim it
    board.pomo_press(mod.BREAK_ROW, 0)                      # back to idle
    mod.dings.clear()
    board.pomo_press(mod.BREAK_ROW, 0)                      # start a second break
    assert board.rows[mod.BREAK_ROW].get('warned') is False
    clock.advance(mod.BREAK.warn[0] + 1); board.tick()
    assert 'break-warn.wav' in [d[1] for d in mod.dings]


def test_pomodoro_rows_have_no_warning(board, mod, clock):
    assert mod.POMODORO.warn is None
    board.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time() - 99_999}
    board.tick()
    assert [d[1] for d in mod.dings] == ['finish.wav']
