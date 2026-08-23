# launchpad-tools

A Novation Launchpad Mini MK3 as a desk board: pomodoro and break timers, daily
and weekly habit trackers, and CPU/network meters. The top row switches between
them; everything else keeps running in the background.

> **Written by an AI (Claude Opus) and not reviewed by a human.** It runs as a
> systemd user service, opens a USB MIDI device, spawns a Tk window and writes
> to `~/.local/share`. It works on the machine it was built on and has a test
> suite, but nobody has actually read it line by line. Read it yourself before
> you run it.

```
     0      1       2      3   4    5      6      7
  ┌──────┬───────┬───────┬───┬───┬──────┬──────┬───────┐
8 │ pomo │ daily │ weekly│   │   │ cpu  │ net  │ reset │   tabs
  ├──────┴───────┴───────┴───┴───┴──────┴──────┴───────┤
7 │            day bar: 8 x 3 h, deep blue             │
  ├────────────────────────────────────────────────────┤
6 │            four pomodoro timers                    │
5 │            8 pads x 3 min = 24 min                 │
4 │                                                    │
3 │                                                    │
  ├────────────────────────────────────────────────────┤
2 │            toggles: off / red / green              │
  ├────────────────────────────────────────────────────┤
1 │            break timer, 8 x 1 min = 8 min          │
  └────────────────────────────────────────────────────┘
```

## Timers

Press the leftmost pad to start. The row fills left to right, one pad per
interval, the current pad blinking. When it runs out the row goes red with a
green pad on the end: press the green one to claim it, any red one to write it
off. Either way the leftmost pad puts it back to idle.

Holding the leftmost pad for two seconds abandons a running timer — the only
way to stop one part way through, deliberately awkward.

The break row on the bottom is the same machine with a different length and
palette: eight minutes, blue instead of green, with a two-strike warning at six
minutes. The top row is the day bar, described below.

Chimes are synthesised (see `share/make-sounds`) and distinguishable by count,
so you can tell what happened without looking:

| | |
|---|---|
| one strike | a timer started |
| two fast, an octave up | two minutes of break left |
| three strikes | a pomodoro finished |
| four strikes | a break finished |

## Habits

Two independent grids, daily and weekly. Each pad is one habit, showing its own
colour when unstarted, flashing red while in progress, solid green when done.
A pad with no name is off and does nothing.

**Hold** a pad to cycle its state, once per second held. **Press** it to open a
window on screen showing the whole grid, where you can rename habits, pick
colours, drag them around to rearrange, and double-click to cycle. Picking a
colour for an empty cell creates the habit, named `SET NAME HERE` so you can
type over it — a colour with no name is not a habit and would be dropped. Everything
applies immediately; Esc closes the window, and a quick tap of the reset pad
does too. Holding reset for two seconds clears the current tab back to
unstarted.

## Bars

The top row of the pomodoro tab and of both habit tabs is not part of the tab:
it shows how much of a period has begun. The pomodoro and daily tabs share the
same day — eight three-hour slices from midnight, deep blue — and the weekly
tab shows its week, one slice per day from Sunday, deep purple.

A cell lights as its slice *starts* rather than when it ends, so a full bar
means you are inside the last one. Lighting on the way out would put the final
cell on the stroke of midnight, replaced by an empty bar in the same instant.
Seven days share eight cells, so the spare one lights with the seventh.

A full week turns pink — a bar that will sit there all Saturday should not be
shouting. A full day stays blue: its last three hours are not urgent, they are
just the last three hours. The daily bar leaves blue only once an hour is left,
and then counts itself down:

| | |
|---|---|
| 23:00 | yellow, blinking at half the pomodoro rate |
| 23:30 | orange, pomodoro cadence |
| 23:40 | red, twice that |
| 23:50 | red, rapid |

Slowing the blink lengthens the lit chunk rather than the gap — a dark chunk
that grows with the period stops reading as a blink and starts reading as a pad
that is off. The weekly bar never blinks: it is full for a whole day.

## Meters

CPU shows eight columns of six pads, each column the busiest of four threads —
a single pegged core is visible rather than averaged away. Network is two
half-width bars filling from the bottom, download on the left and upload on the
right, on a log scale from 1 KB/s to about 1 Gbit/s because a linear one sits
at zero all day.

## Install

Needs Python 3, `mido` and `python-rtmidi` for MIDI, and `tkinter` for the habit
window.

```sh
sudo pacman -S python-mido python-rtmidi        # Arch
sudo apt install python3-mido python3-rtmidi python3-tk   # Debian/Ubuntu

git clone git@github.com:defuse/launchpad-tools.git
cd launchpad-tools
./install.sh
```

That symlinks the three programs into `~/.local/bin`, copies the chimes to
`~/.local/share/launchpad-pomodoro/`, and enables a systemd user service. Since
they are symlinks, `git pull` updates what is installed. Nothing needs root and
nothing is written outside `$HOME`.

`./install.sh --uninstall` reverses it, leaving your state file alone.

## State

Everything lives in `~/.local/share/launchpad-pomodoro.json` — timers with their
real start times, habits, toggles and the selected tab. A running timer survives
a restart or a reboot because it stores when it started, not how far along it
is. Delete the file to start over.

## Tests

```sh
tests/run-tests             # 260 tests, about seven seconds
tests/run-tests -k break    # pytest args pass through
```

Safe to run against a live session: the real state file is never opened, MIDI
and audio are stubbed, the window tests get a private Xvfb rather than your
desktop, and the service is never touched.

`bin/launchpad-smoketest` is a faster, dependency-free version that just calls
every entry point once — enough to catch a method that was deleted by a bad
edit, which is a failure mode this code has had more than once.

## Notes

Every tab drives the same 64 physical pads, so a press belongs to the tab it was
made on and no other. Hold a habit in the first column, switch to the pomodoro
tab without letting go, and that hold is not an abandon gesture. Getting this
wrong silently wiped running timers for a while.

Written for a Launchpad Mini MK3 in Programmer Mode. Other Launchpads use
different SysEx and a different pad numbering, so they will not work unmodified.

MIT, see [LICENSE](LICENSE).
