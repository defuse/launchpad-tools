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
8 │ pomo │ daily │ weekly│mch│spc│ cpu  │ net  │ reset │   tabs
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
| 23:55 | red, panic strobe |

Slowing the blink lengthens the lit chunk rather than the gap — a dark chunk
that grows with the period stops reading as a blink and starts reading as a pad
that is off. The weekly bar never blinks: it is full for a whole day.

## Machine and audio

Fourth tab. Everything above the bottom row is read-only:

| row | |
|---|---|
| disks | one pad per physical drive — green in sync, amber rebuilding or in a degraded array, strobing red failed |
| filesystems | `/`, `/home`, `Data-1`, `Fast-1` — green over 100GB free, yellow under, red under 30GB |
| temperatures | CPU, GPU, NVMe, thresholds per part: 70°C is a warm CPU and a cooked NVMe |

A pad is the whole drive rather than the partition, since three arrays can
share a pair of drives and it is the drive that dies. A drive that has gone
entirely cannot be listed — `/proc/mdstat` only names what is still there — so
what you see is its array's survivor going amber.

The bottom row is the only part you can press: output to `game_stereo`, output
to the headset, a gap, EasyEffects on/off, a gap, then previous, play/pause and
next. The output pads are white with the current one blue, and every pad shows
what the system is actually doing rather than the last thing the board asked
for — change the output in the tray applet and the pads follow. Picking the
headset takes its microphone with it.

Picking an output picks its processing with it — the speakers are corrected by
an EQ fitted to the room and the headset is not, so `game_stereo` turns
EasyEffects on and the headset bypasses it.

All of it comes from a background poller. Nothing is read during a frame:
`easyeffects -b 3` alone takes a quarter of a second, and a frame is 50ms. That
query is never polled at all, in fact — it starts a second EasyEffects to ask
the first, and that closes the window the first one has open. The bypass state
comes from the config file EasyEffects writes it to instead.

## Spectrum

Fifth tab: eight bands of whatever you are listening to, captured from the
current output's monitor with `pw-record`, so it hears what the speakers get —
EasyEffects included — and follows the output when you switch it. Each band has
its own hue rather than the meters' green-yellow-red, and a peak marker that
hangs above the bar and falls back.

Bands are log spaced from 40Hz to 12kHz, with a 3dB-per-band tilt: music
carries most of its energy low down, so without one the right of the board
barely moves. `SPEC_FLOOR`, `SPEC_CEIL` and `SPEC_TILT` are the knobs if it
sits too high or too low for what you listen to.

Capture runs only while the tab is on screen. Needs `numpy`; without it the tab
is simply dark.

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
sudo pacman -S python-mido python-rtmidi python-numpy   # Arch
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
tests/run-tests             # 337 tests, about nine seconds
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
