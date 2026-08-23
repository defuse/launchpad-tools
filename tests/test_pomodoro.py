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


def test_a_claimed_row_is_not_cleared_by_a_press(board, mod, clock):
    """A claimed row is a finished pomodoro worth keeping on the board, and one
    brushed pad used to wipe it. It goes through the hold now."""
    board.mode = mod.M_POMO
    board.rows[5] = {'state': mod.CLAIMED, 'started': 7.0}
    for c in (4, 0):
        board.press(mod.pad(5, c)); board.release(mod.pad(5, c))
        assert board.rows[5]['state'] == mod.CLAIMED, f'a tap on pad {c} kept it'


def test_holding_the_left_pad_clears_a_claimed_row(board, mod, clock):
    board.mode = mod.M_POMO
    board.rows[5] = {'state': mod.CLAIMED, 'started': 7.0}
    board.press(col0(mod, 5))
    clock.advance(mod.RESET_HOLD + 0.1)
    board.render()                                   # the hold fires while drawing
    assert board.rows[5] == {'state': mod.IDLE, 'started': 0.0}


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


def test_recycling_a_claimed_row_is_a_hold_then_a_press(board, mod, clock):
    """claimed -> idle -> running, and the first step is deliberately awkward:
    clearing a finished pomodoro should take more than a brush."""
    board.mode = mod.M_POMO
    board.rows[ROW] = {'state': mod.CLAIMED, 'started': 5.0}
    board.press(col0(mod, ROW))
    clock.advance(mod.RESET_HOLD + 0.1)
    board.render()
    board.release(col0(mod, ROW))
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


def tap(board, mod, clock, note=None):
    note = note if note is not None else mod.pad(mod.FUNC_ROW, mod.RESET_COL)
    board.press(note)
    clock.advance(0.2)
    board.release(note)


def test_reset_pad_tap_toggles_this_tab_window(board, mod, clock):
    """One pad, two jobs: a tap is the window, a two second hold is the reset."""
    board.mode = mod.M_HAB
    tap(board, mod, clock)
    assert board._window == mod.M_HAB and board._editing is not None
    tap(board, mod, clock)
    assert board._window is None and board._editing is None


def test_reset_pad_tap_opens_the_machine_window(board, mod, clock):
    board.mode = mod.M_MACH
    board.machine.snap = mod.Snapshot(disks=(('sda', 'ok'),))
    tap(board, mod, clock)
    assert board._window == mod.M_MACH


def test_reset_pad_tap_opens_the_pomodoro_window(board, mod, clock):
    board.mode = mod.M_POMO
    tap(board, mod, clock)
    assert board._window == mod.M_POMO
    tap(board, mod, clock)
    assert board._window is None


@pytest.mark.parametrize('mode', ['M_SPEC', 'M_SYS', 'M_NET'])
def test_a_tab_with_nothing_to_show_opens_nothing(board, mod, clock, mode):
    """Rather than an empty window nobody asked for."""
    board.mode = getattr(mod, mode)
    tap(board, mod, clock)
    assert board._window is None


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
    board.todo[0] = {'name': 'x', 'state': 1}
    board.mode = mod.M_POMO
    board.reset()
    assert all(board.rows[r] == {'state': mod.IDLE, 'started': 0.0} for r in mod.POMO_ROWS)
    assert board.todo == mod.blank_todo()


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

def test_todo_pads_cycle_their_state(board, mod):
    p = mod.pad(mod.TODO_ROW, 2)
    for expected in (1, 2, 0, 1):
        board.press(p)
        assert board.todo[2]['state'] == expected


def test_toggles_are_inert_off_the_pomodoro_tab(board, mod):
    board.mode = mod.M_SYS
    board.press(mod.pad(6, 2))
    assert board.todo == mod.blank_todo()


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


def test_the_todo_row_sits_above_the_break(board, mod):
    assert mod.TODO_ROW == 6 and mod.BREAK_ROW not in mod.TOGGLE_ROWS
    board.mode = mod.M_POMO
    for expected in (mod.RED, mod.TODO_DONE, mod.OFF):
        board.press(mod.pad(mod.TODO_ROW, 0)); board.release(mod.pad(mod.TODO_ROW, 0))
        board.shown.clear(); board.render()
        assert board.shown[mod.pad(mod.TODO_ROW, 0)][1] == expected


# ---- the todo list -------------------------------------------------------

@pytest.mark.parametrize('name,state,colour', [
    ('',      0, 'OFF'),         # a slot with nothing in it is dark
    ('ship',  0, 'WHITE'),       # named and not started, like an untouched habit
    ('',      1, 'RED'),         # a state without a name is still a state
    ('ship',  1, 'RED'),
    ('',      2, 'TODO_DONE'),
    ('ship',  2, 'TODO_DONE'),
])
def test_the_four_kinds_of_todo_cell(board, mod, name, state, colour):
    board.mode = mod.M_POMO
    board.todo[3] = {'name': name, 'state': state}
    board.shown.clear(); board.render()
    assert board.shown[mod.pad(mod.TODO_ROW, 3)][1] == getattr(mod, colour)


def test_done_is_a_lighter_green_than_a_claimed_pomodoro(mod):
    """The two rows are adjacent; the same green in both reads as one block."""
    assert mod.TODO_DONE != mod.GREEN
    assert isinstance(mod.TODO_DONE, tuple), 'no palette green is that pale'


def test_clearing_empties_every_slot(board, mod):
    board.todo[1] = {'name': 'a', 'state': 2}
    board.todo[5] = {'name': '', 'state': 1}
    board.clear_todo()
    assert board.todo == mod.blank_todo()


def test_resetting_the_pomodoro_tab_clears_the_list(board, mod):
    board.mode = mod.M_POMO
    board.todo[0] = {'name': 'a', 'state': 1}
    board.reset()
    assert board.todo == mod.blank_todo()


# ---- dragging a slot moves it, and everything in the way shifts ----------

def names(items):
    return [i['name'] for i in items]


def test_dragging_right_shifts_the_ones_it_passes_left(mod):
    items = [{'name': n, 'state': 0} for n in 'abcdefgh']
    assert names(mod.move_todo(items, 1, 4)) == list('acdebfgh')


def test_dragging_left_shifts_the_ones_it_passes_right(mod):
    items = [{'name': n, 'state': 0} for n in 'abcdefgh']
    assert names(mod.move_todo(items, 5, 2)) == list('abfcdegh')


def test_a_slot_carries_its_state_with_it(mod):
    """A state left behind would belong to whichever item slid into its place."""
    items = [{'name': n, 'state': i % 3} for i, n in enumerate('abcdefgh')]
    moved = mod.move_todo(items, 0, 3)
    assert moved[3] == {'name': 'a', 'state': 0}
    assert [i['state'] for i in moved] == [1, 2, 0, 0, 1, 2, 0, 1]


@pytest.mark.parametrize('src,dst', [(0, 7), (7, 0), (3, 4), (4, 3)])
def test_a_move_never_loses_or_duplicates_a_slot(mod, src, dst):
    items = [{'name': n, 'state': 0} for n in 'abcdefgh']
    moved = mod.move_todo(items, src, dst)
    assert sorted(names(moved)) == list('abcdefgh')
    assert len(moved) == 8
    assert moved[dst]['name'] == 'abcdefgh'[src]


@pytest.mark.parametrize('src,dst', [(2, 2), (-1, 3), (3, 99), (0, 8)])
def test_a_move_that_means_nothing_changes_nothing(mod, src, dst):
    items = [{'name': n, 'state': 0} for n in 'abcdefgh']
    assert names(mod.move_todo(items, src, dst)) == list('abcdefgh')


def test_moving_does_not_mutate_what_it_was_given(mod):
    items = [{'name': n, 'state': 0} for n in 'abcdefgh']
    mod.move_todo(items, 0, 5)
    assert names(items) == list('abcdefgh'), 'the caller keeps its own list'


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
    board.rows[mod.BREAK_ROW].update(state=mod.IDLE, started=0)   # as a hold would
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


# ---- the window's cells are the pads -------------------------------------

def feed_pomo(board, lines):
    """Run the pomodoro window's reader over a canned stdout."""
    board._pomo_popup.stdout = iter([l + '\n' for l in lines])
    board._pomo_reader()


@pytest.fixture
def mirror(board, mod, clock):
    board.mode = mod.M_POMO
    tap(board, mod, clock)                      # the red pad opens the window
    return board


def test_a_click_in_the_window_starts_the_timer_it_mirrors(mirror, mod):
    feed_pomo(mirror, [f'press\t{ROW}\t0', f'release\t{ROW}\t0'])
    assert mirror.rows[ROW]['state'] == mod.RUNNING


def test_a_hold_in_the_window_abandons_like_a_held_pad(mirror, mod, clock):
    """The same entry points as the pads, so the two second hold is the two
    second hold and not a second implementation of it."""
    mirror.rows[ROW] = {'state': mod.RUNNING, 'started': clock.time()}
    feed_pomo(mirror, [f'press\t{ROW}\t0'])
    clock.advance(mod.RESET_HOLD + 0.1)
    mirror.render()
    assert mirror.rows[ROW]['state'] == mod.IDLE


def test_a_tap_on_a_slot_cycles_it_as_the_pad_would(mirror, mod):
    feed_pomo(mirror, [f'press\t{mod.TODO_ROW}\t2', f'release\t{mod.TODO_ROW}\t2'])
    assert mirror.todo[2]['state'] == 1


def test_a_claimed_row_survives_a_click_from_the_window_too(mirror, mod):
    mirror.rows[ROW] = {'state': mod.CLAIMED, 'started': 5.0}
    feed_pomo(mirror, [f'press\t{ROW}\t0', f'release\t{ROW}\t0'])
    assert mirror.rows[ROW]['state'] == mod.CLAIMED


def test_the_window_can_rename_and_move_slots(mirror, mod):
    feed_pomo(mirror, ['set\t0\twrite tests', 'set\t1\tfix sub',
                       'state\t0\t2', 'move\t0\t3'])
    assert [t['name'] for t in mirror.todo[:4]] == ['fix sub', '', '', 'write tests']
    assert mirror.todo[3]['state'] == 2, 'the state travelled with the name'


def test_the_window_can_clear_the_list(mirror, mod):
    mirror.todo[0] = {'name': 'a', 'state': 1}
    feed_pomo(mirror, ['clear'])
    assert mirror.todo == mod.blank_todo()
