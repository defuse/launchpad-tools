# launchpad-tools

A Novation Launchpad Mini MK3 as a desk board: pomodoro and break timers, daily
and weekly habit trackers, machine and audio controls, an audio spectrum, and
CPU/network meters. The top row switches between them; everything keeps running
in the background.

> **Written by an AI (Claude Opus) and not reviewed by a human.** It runs as a
> systemd user service, opens a USB MIDI device, spawns a Tk window and writes
> to `~/.local/share`. It works on the machine it was built on and has a test
> suite, but nobody has actually read it line by line. Read it yourself before
> you run it.

Copyright © 2026 Taylor Hornby. Dual licensed under [MIT](LICENSE-MIT) or
[Apache 2.0](LICENSE-APACHE), at your option — `MIT OR Apache-2.0`.

The diagrams below show one tab each, rows numbered from the top as the code
numbers them. `·` off, `W` white, `G` green, `R` red, `B` blue, `Y` yellow,
`O` orange, `C` cyan, `S` sky, `b` pale blue, `c` the habit's own colour,
`*` blinking.

## The top row

```
 0   pomo daily weekly mach spec cpu net RESET
```

The selected tab is sky blue, the rest white. The red pad on the right does two
jobs: a tap opens or closes this tab's window, a two-second hold resets what the
tab owns. The row fills red as you hold it.

## Timers

```
 1   B  B  B  ·  ·  ·  ·  ·     day bar
 2   W  ·  ·  ·  ·  ·  ·  ·     idle — press the left pad to start
 3   G  G  G* ·  ·  ·  ·  ·     running — 3 min per pad
 4   R  R  R  R  R  R  R  G     elapsed — green claims it, red writes it off
 5   G  G  G  G  G  G  G  G     claimed
 6   W  R  G  ·  ·  ·  ·  ·     todo — named, started, done, empty
 7   B  B  B* ·  ·  ·  ·  ·     break — 8 min, 1 min per pad
```

Four independent timers and a break. A row fills left to right with the current
pad blinking; when it runs out the row goes red with a green pad on the end, to
claim or write off. Holding the leftmost pad for two seconds abandons a running
timer or clears a claimed one.

Row 6 is an eight-slot todo list — dark when empty, white once named, red then
green as you start and finish it. Pressing a pad cycles its state; names are
typed in the window.

Chimes are synthesised (see `share/make-sounds`) and told apart by count: one
for a timer starting, three for a pomodoro finishing, four for a break, two fast
ones two minutes before a break ends.

**The window** mirrors the pads, with a hint on each row for what you can do
now. Clicking a cell does what pressing the pad does, holds included. The todo
list is edited here: type names, click a slot's header to cycle it, drag it by
that header to move it.

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

Two independent grids, daily and weekly, one per tab. **Hold** a pad to cycle
it, once per second held. **Press** it to open the window, where you can rename
habits, pick colours, drag them around, and double-click to cycle. A drag moves
the whole habit, today's state included. Clearing a name removes a habit; the
cell keeps its colour for the next one.

## Machine and audio

```
 1   B  B  B  ·  ·  ·  ·  ·     day bar
 2   ·  G  G  G  G  G  G  ·     disks — one pad per drive, centred
 3   ·  ·  Y  G  G  G  ·  ·     filesystems — / · home · Data-1 · Fast-1
 4   ·  b  b  b  b  b  b  ·     drive temperatures — same columns as row 2
 5   ·  ·  b  b  b  b  ·  ·     temperatures — CPU · GPU · NVMe · CCD2
 7   B  W  ·  W  R  W  S  W     speakers · headset | sub · effects · prev play next
```

Everything above the bottom row is read-only: green or pale blue while fine,
yellow or amber as it gets worse, red when it is bad, strobing when it is
urgent. **Hold** any of those pads for a window with the numbers in it — which
drive, how many degrees, how many gigabytes.

The bottom row is the only part you press. Every pad reports rather than
remembers: it fires the command and reads the state back, so changing the output
or the effects anywhere else moves the pads. Picking the headset takes its
microphone with it, and the EasyEffects pad's colour says which preset is live.

**While this tab is on screen it queries EasyEffects once a second, which closes
the EasyEffects window if you have one open.** Any use of its CLI does; leaving
the tab stops it.

## Spectrum, CPU, network

Eight log-spaced bands of whatever you are listening to, captured from the
current output's monitor, tilted because music carries most of its energy low
down. The CPU tab is one column per group of threads with memory across the
bottom in htop's colours; the network tab is two half-width bars, download
hanging from the top and upload climbing from the bottom, on a log scale from
about 1 KB/s to 1 Gbit/s. Capture and polling run only while the tab is up.

## Bars

Row 1 of most tabs shows how much of the period has begun — eight three-hour
slices of the day, or a day per pad of the week from Sunday. A cell lights as
its slice *starts*, so a full bar means you are inside the last one. The day
bar is blue until the evening, then warms and quickens: gold at 20:00, deeper
gold at 21:00, blinking slowly at 22:00, yellow at 23:00, orange at 23:30, red
and faster from 23:40, a panic strobe for the last five minutes. The week turns
pink and never blinks.

## Install

Needs Python 3, `mido` and `python-rtmidi` for MIDI, `tkinter` for the windows,
and `numpy` for the spectrum.

```sh
sudo pacman -S python-mido python-rtmidi python-numpy   # Arch
sudo apt install python3-mido python3-rtmidi python3-tk python3-numpy   # Debian

git clone git@github.com:defuse/launchpad-tools.git
cd launchpad-tools
./install.sh          # --uninstall reverses it, leaving your state alone
```

Symlinks into `~/.local/bin` so `git pull` updates what is installed, copies the
chimes to `~/.local/share/launchpad-pomodoro/`, and enables a systemd user
service. Nothing needs root and nothing is written outside `$HOME`.

State — timers with their real start times, habits, the todo list, the selected
tab — lives in `~/.local/share/launchpad-pomodoro.json`. A running timer
survives a reboot because it stores when it started, not how far along it is.

Unplug the Launchpad and the board keeps running with nowhere to draw; plug it
back in and it re-opens the ports, puts the device back into programmer mode and
redraws every pad. It checks for that every few seconds, because a device that
re-enumerates on USB silently loses its ALSA subscriptions and nothing reports
it: writing to an unsubscribed port succeeds.

## Tests

`tests/run-tests` (752 of them, about fifty seconds; pytest args pass through).
Safe against a live session: the real state file is never opened, MIDI and audio
are stubbed, the window tests get a private Xvfb, the service is never touched.
`bin/launchpad-smoketest` is a faster dependency-free version that calls every
entry point once.

## What this assumes about the machine

The timers, habits and bars run anywhere. The machine, spectrum and meter tabs
are wired to one particular desk; the names are constants at the top of
`bin/launchpad-pomodoro`.

| | |
|---|---|
| outputs | a PipeWire sink named `game_stereo`, and any sink whose name contains `AT_ATH-M50xSTS` — matched on a fragment, so re-plugging the headset does not break it |
| transport | Spotify, over MPRIS |
| filesystems | `/`, `$HOME`, `~/Data-1`, `~/Fast-1`; thresholds are gigabytes free, the same for all of them |
| temperatures | an AMD CPU (`k10temp`), an NVIDIA GPU (`nvidia-smi`), an NVMe drive, and SATA drives via `drivetemp` |
| disks | whatever `/proc/mdstat` lists |
| subwoofer | two channels of a `TASCAM_SERIES_208i`, which sums them into the speakers as well — so the pad moves between two fixed levels that leave the speakers equally loud either way, rather than muting |
| effects | EasyEffects 8, a Qt app since 8.2 — its CLI is run with `QT_QPA_PLATFORM=offscreen` or it aborts under a service with no display. Which preset is the headset's is read from its own autoload files, so renaming one cannot leave the pad lying |
| hardware | a Launchpad Mini MK3 in Programmer Mode; other Launchpads use different SysEx and pad numbering |

Everything on those tabs needs `pactl`, `pw-record`, `gdbus` and `nvidia-smi` on
`PATH`; a missing one leaves its pads dark rather than breaking the board.

Every tab drives the same 64 pads, so a press belongs to the tab it was made on
and no other: hold a habit, switch tabs without letting go, and that hold is not
a gesture on the new tab.
