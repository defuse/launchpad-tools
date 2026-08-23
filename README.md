# launchpad-tools

A Novation Launchpad Mini MK3 as a desk board: pomodoro and break timers, daily
and weekly habit trackers, machine and audio controls, an audio spectrum, and
CPU/network meters. The top row switches between them; everything else keeps
running in the background.

> **Written by an AI (Claude Opus) and not reviewed by a human.** It runs as a
> systemd user service, opens a USB MIDI device, spawns a Tk window and writes
> to `~/.local/share`. It works on the machine it was built on and has a test
> suite, but nobody has actually read it line by line. Read it yourself before
> you run it.

## The top row

```
       0      1      2      3      4      5      6      7
    ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┬───────┐
 0  │ pomo │daily │weekly│ mach │ spec │ cpu  │ net  │ reset │
    └──────┴──────┴──────┴──────┴──────┴──────┴──────┴───────┘
```

The selected tab is sky blue and the rest are white. Reset on the right is
hold-only: two seconds clears what the current tab owns, and the row fills red
as it goes so you can see it coming. A quick tap instead closes the habit
window.

The diagrams below show one tab each, counting down from the row under the tabs
to the bottom of the board — the same numbering the code uses. In them:

```
·  off        W  white     G  green    R  red      B  blue
Y  yellow     O  orange    P  pink     C  cyan     S  sky      M  magenta
c  the habit's own colour               *  blinking
```

## Timers

```
 1   B  B  B  ·  ·  ·  ·  ·     day bar
 2   W  ·  ·  ·  ·  ·  ·  ·     idle — press the left pad to start
 3   G  G  G* ·  ·  ·  ·  ·     running — 3 min per pad
 4   R  R  R  R  R  R  R  G     elapsed — green claims it, red writes it off
 5   G  G  G  G  G  G  G  G     claimed
 6   ·  R  G  ·  ·  ·  ·  ·     toggles — press cycles off / red / green
 7   B  B  B* ·  ·  ·  ·  ·     break — 1 min per pad
```

Rows 2 to 5 are four independent timers, drawn above in the four states one can
be in. A row fills left to right with the current pad blinking, and when it runs
out the whole row goes red with a green pad on the end. Either answer puts it
back to idle, and the left pad starts it again.

Holding the leftmost pad for two seconds abandons a running timer — the only way
to stop one part way through, deliberately awkward.

The break row at the bottom is the same machine with a different length and
palette: eight minutes, blue instead of green, with a warning two minutes from
the end.

Chimes are synthesised (see `share/make-sounds`) and distinguishable by count,
so you can tell what happened without looking:

| | |
|---|---|
| one strike | a timer started |
| two fast, an octave up | two minutes of break left |
| three strikes | a pomodoro finished |
| four strikes | a break finished |

## Habits

```
 1   B  B  B  B  ·  ·  ·  ·     day bar — the weekly tab shows a week bar
 2   c  c  c  c  c  ·  ·  ·     one pad per habit, in its own colour
 3   R* c  G  c  ·  ·  ·  ·     blinking red = in progress, green = done
 4   c  c  c  ·  ·  ·  ·  ·
 5   c  c  c  c  ·  ·  ·  ·
 6   c  c  ·  ·  ·  ·  ·  ·
 7   ·  ·  ·  ·  ·  ·  ·  ·     a pad with no name is off and does nothing
```

Two independent grids, daily and weekly, one per tab.

**Hold** a pad to cycle it, once per second held. **Press** it to open a window
on screen showing the whole grid, where you can rename habits, pick colours,
drag them around to rearrange, and double-click to cycle. Picking a colour for
an empty cell creates the habit, named `SET NAME HERE` so you can type over it —
a colour with no name is not a habit and would be dropped.

Everything applies immediately; Esc closes the window, and a quick tap of the
reset pad does too. Holding reset for two seconds clears the current tab back to
unstarted.

## Machine and audio

```
 1   B  B  B  ·  ·  ·  ·  ·     day bar
 2   G  G  G  G  G  G  ·  ·     disks — one pad per drive
 3   Y  G  G  G  ·  ·  ·  ·     filesystems — / · home · Data-1 · Fast-1
 4   ·  ·  ·  ·  ·  ·  ·  ·
 5   G  G  G  ·  ·  ·  ·  ·     temperatures — CPU · GPU · NVMe
 6   ·  ·  ·  ·  ·  ·  ·  ·
 7   B  W  ·  G  ·  W  S  W     speakers · headset | effects | prev play next
```

Everything above the bottom row is read-only:

| | |
|---|---|
| disks | green in sync, amber rebuilding or in a degraded array, strobing red failed |
| filesystems | green with room to spare, yellow getting full, red nearly full |
| temperatures | green normal, yellow warm, red hot, strobing red too hot |

A pad is a whole drive, not an array member, since several arrays can share a
pair of drives and it is the drive that dies. A drive that has vanished entirely
has no pad to light — `/proc/mdstat` only names what is still there — so what
you see in that case is its array's surviving half going amber.

The bottom row is the only part you can press. The two output pads are white
with the current one blue; picking the headset takes its microphone with it. The
EasyEffects pad is an on/off switch whose colour says which preset is live:
white off, green for the room preset, orange for the headset one — worked out
from EasyEffects' own autoload bindings, so renaming a preset cannot leave the
pad lying. Play/pause lights sky blue while Spotify is playing.

Every pad here reports rather than remembers. Pressing one fires the command and
then reads the state back, so what you see is what `pactl` and EasyEffects say,
never what the board asked for — change the output from the tray applet and the
pads follow.

**While this tab is on screen it queries EasyEffects once a second, and that
closes the EasyEffects window if you have one open.** Any invocation of its CLI
does, there is no quieter way to ask, and its config file is written too lazily
to use instead. Switch to another tab while working in the UI; nothing is asked
from anywhere else.

## Spectrum

```
 1   ·  ·  ·  ·  W  ·  ·  ·     white peaks hang above the bars and fall back
 2   ·  ·  Y  ·  C  ·  ·  W
 3   R  ·  Y  ·  C  ·  ·  ·
 4   R  O  Y  G  C  ·  B  M
 5   R  O  Y  G  C  S  B  M
 6   R  O  Y  G  C  S  B  M
 7   R  O  Y  G  C  S  B  M
     bass ────────────────► treble
```

Eight bands of whatever you are listening to, captured from the current
output's monitor, so it hears what the speakers get — EasyEffects included —
and follows the output when you switch it. Each band has its own hue rather
than the meters' green-yellow-red, so the tab is recognisable at a glance.

Bands are log spaced and tilted, since music carries most of its energy low
down and an untilted display leaves the right of the board dead. This tab is
drawn faster than the rest of the board, which is what audio needs and a
pomodoro cell does not. If it reads too hot or too cold for what you listen to,
`SPEC_FLOOR`, `SPEC_CEIL` and `SPEC_TILT` in `bin/launchpad-pomodoro` are the
knobs; they are calibrated for this system's usual listening level.

Capture runs only while the tab is on screen. Needs `numpy`; without it the tab
is simply dark.

## CPU

```
 1   ·  ·  ·  R  ·  ·  ·  ·     one column per group of threads, six tall
 2   ·  ·  ·  Y  ·  ·  ·  ·
 3   ·  G  ·  G  ·  ·  ·  ·
 4   ·  G  ·  G  ·  G  ·  ·
 5   G  G  ·  G  ·  G  ·  G
 6   G  G  G  G  G  G  G  G
 7   G  G  G  B  B  Y  Y  ·     memory — used · buffers · cache
```

Each column is the busiest of its four threads rather than their average, so a
single pegged core is visible instead of being smeared away. Memory across the
bottom uses htop's colours.

## Network

```
 1   ·  ·  ·  ·   ·  ·  ·  ·    download on the left, upload on the right
 2   ·  ·  ·  ·   ·  ·  ·  ·
 3   C  C  ·  ·   ·  ·  ·  ·
 4   C  C  C  C   O  ·  ·  ·
 5   C  C  C  C   O  O  ·  ·
 6   C  C  C  C   O  O  O  O
 7   C  C  C  C   O  O  O  O
```

Two half-width bars filling from the bottom. Each row is four pads, so a
part-filled row gives four times the resolution of whole rows alone. The scale
is logarithmic, from about 1 KB/s to about 1 Gbit/s, because a linear one sits
at zero all day.

## Bars

Row 1 of the pomodoro tab, both habit tabs and the machine tab is not part of
that tab: it shows how much of a period has begun. The pomodoro, machine and
daily tabs share the same day — eight three-hour slices from midnight, deep blue
— and the weekly tab shows its week, one slice per day from Sunday, deep purple.

```
 09:00   B  B  B  B  ·  ·  ·  ·     four slices of the day gone
 21:00   B  B  B  B  B  B  B  B     full: you are in the last slice
 23:00   Y* Y* Y* Y* Y* Y* Y* Y*    an hour left, and it starts saying so
 23:55   R* R* R* R* R* R* R* R*    five minutes
```

A cell lights as its slice *starts*, so a full bar means you are inside the last
one. Seven days share eight cells, so the spare one lights with the seventh and
Saturday reads as full.

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

The weekly bar never blinks: it is full for a whole day, and a day of blinking
pads is noise.

## Install

Needs Python 3, `mido` and `python-rtmidi` for MIDI, `tkinter` for the habit
window, and `numpy` for the spectrum.

```sh
sudo pacman -S python-mido python-rtmidi python-numpy   # Arch
sudo apt install python3-mido python3-rtmidi python3-tk python3-numpy   # Debian/Ubuntu

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
tests/run-tests             # 358 tests, about nine seconds
tests/run-tests -k break    # pytest args pass through
```

Safe to run against a live session: the real state file is never opened, MIDI
and audio are stubbed, the window tests get a private Xvfb rather than your
desktop, and the service is never touched.

`bin/launchpad-smoketest` is a faster, dependency-free version that just calls
every entry point once — enough to catch a method that was deleted by a bad
edit, which is a failure mode this code has had more than once.

## What this assumes about the machine

The timers, habits and bars run anywhere. The machine, spectrum and meter tabs
are wired to one particular desk, and the names below are constants at the top
of `bin/launchpad-pomodoro` — change them there and those tabs work elsewhere.

| | |
|---|---|
| outputs | a PipeWire sink named `game_stereo`, and any sink whose name contains `AT_ATH-M50xSTS` — matched on a fragment so re-plugging the headset into another port does not break it |
| microphone | the source matching that same fragment; the headset pad sets both |
| transport | Spotify, over MPRIS |
| filesystems | `/`, `$HOME`, `~/Data-1`, `~/Fast-1`, with the yellow and red thresholds beside them |
| temperatures | an AMD CPU (`k10temp`, `Tctl`), an NVIDIA GPU (`nvidia-smi`), an NVMe drive — thresholds are per part |
| disks | whatever `/proc/mdstat` lists; no arrays means an empty row, not an error |
| effects | EasyEffects 8, using its own preset and autoload files under `~/.local/share/easyeffects` |
| hardware | a Launchpad Mini MK3 in Programmer Mode; other Launchpads use different SysEx and pad numbering |

Preset *names* are not assumed anywhere: which preset is the headset's is read
from your EasyEffects autoload bindings, so it follows whatever you have set up.
Everything else on those tabs needs `pactl`, `pw-record`, `gdbus` and
`nvidia-smi` on `PATH`; a missing one leaves its pads dark rather than breaking
the board.

## Notes

Every tab drives the same 64 physical pads, so a press belongs to the tab it was
made on and no other. Hold a habit in the first column, switch to the pomodoro
tab without letting go, and that hold is not an abandon gesture. Getting this
wrong silently wiped running timers for a while.

MIT, see [LICENSE](LICENSE).
