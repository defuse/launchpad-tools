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

Copyright © 2026 Taylor Hornby. Dual licensed under [MIT](LICENSE-MIT) or
[Apache 2.0](LICENSE-APACHE), at your option — `MIT OR Apache-2.0`.

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
b  pale blue    c  the habit's own colour    *  blinking
```

## Timers

```
 1   B  B  B  ·  ·  ·  ·  ·     day bar
 2   W  ·  ·  ·  ·  ·  ·  ·     idle — press the left pad to start
 3   G  G  G* ·  ·  ·  ·  ·     running — 3 min per pad
 4   R  R  R  R  R  R  R  G     elapsed — green claims it, red writes it off
 5   G  G  G  G  G  G  G  G     claimed
 6   W  R  G  ·  ·  ·  ·  ·     todo — named, started, done, empty
 7   B  B  B* ·  ·  ·  ·  ·     break — 1 min per pad
```

Rows 2 to 5 are four independent timers, drawn above in the four states one can
be in. A row fills left to right with the current pad blinking, and when it runs
out the whole row goes red with a green pad on the end. Writing it off puts the
row back to idle; claiming it leaves the row green, and clearing that takes the
same two-second hold as abandoning — a finished pomodoro should not be wiped by
a brushed pad.

Holding the leftmost pad for two seconds abandons a running timer — the only way
to stop one part way through, deliberately awkward.

The break row at the bottom is the same machine with a different length and
palette: eight minutes, blue instead of green, with a warning two minutes from
the end.

Row 6 is an eight-slot todo list. A slot always exists and always has a state,
so a pad is dark when it is empty and unstarted, white once it has a name, and
red then green as you start and finish it — a state on an unnamed slot is
allowed and shows. Pressing a pad cycles its state; the names are typed in the
window.

**Tap the red pad** to open the window for whichever tab you are on — the habit
grid, the machine readout, or the pomodoro mirror — and tap it again to close
it. Holding it for two seconds still resets the tab.

Chimes are synthesised (see `share/make-sounds`) and distinguishable by count,
so you can tell what happened without looking:

| | |
|---|---|
| one strike | a timer started |
| two fast, an octave up | two minutes of break left |
| three strikes | a pomodoro finished |
| four strikes | a break finished |

### The pomodoro window

A mirror of the pads, annotated with what you can do *now*. Each hint points at
the pad it is about — from the left at the pad that starts or clears a row, and
from the right at the green pad that claims an elapsed one — and only appears
for a state that actually exists, since an instruction for a button that is not
there is an instruction in the way.

**The cells are the pads.** Clicking one does what pressing the pad does, and
holding one holds it, through the same code — so a two-second hold in the window
abandons a timer exactly as it does on the board. Clicking into a todo text box
to type is not a press.

The colours are read back off the pads rather than worked out again, so the
blinking cell of a running timer blinks here in step with the board, and the red
fill of a hold-to-abandon crawls across both at once. Each row is labelled with
its length.

The day bar is at the top, as `time of day`, with each pad printed with the
three hours it stands for — `00–03` through `21–00`. It is read-only here as it
is on the board; it is in the window so the row on the board can be read
without being explained. The hours come from the same slices and step the bar is
drawn from, so there is no second description of the row to keep in step, and
the ink is picked against whatever colour the pad is showing so it stays legible
through the last hour's yellow, orange and red.

**Switching tabs switches the window.** Whatever was on screen closes and the
new tab's window opens in its place — or nothing does, on a tab that has none.

The todo list is edited here — type a name, click a slot's header to cycle its
state, drag it by that header to move it. The text box and the margin around it
take no gesture at all, so reaching for the box never changes a state and
selecting a name never reorders the list. The name boxes wrap like a text
editor and every one of them is as tall as the longest item needs, so nothing
scrolls and nothing is hidden. A drag is a *move*, not a swap: everything
between the slot and where it lands shifts by one, in whichever direction that
turns out to be, and each slot carries its own state along with it. `clear
list` empties them all.

The list lives on the board and is shown here, so the two have to agree about
it. Every edit the window sends is numbered and the board says in each frame
which one it has applied; a frame that has not caught up is drawn but its
version of the list is dropped. Without that, a frame the board had rendered a
moment earlier — and with a timer running it renders every second — arrives
after your drag and undoes it on screen.

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
 2   ·  G  G  G  G  G  G  ·     disks — one pad per drive, centred
 3   ·  ·  Y  G  G  G  ·  ·     filesystems — / · home · Data-1 · Fast-1
 4   ·  b  b  b  b  b  b  ·     drive temperatures — same columns as row 2
 5   ·  ·  b  b  b  b  ·  ·     temperatures — CPU · GPU · NVMe · CCD2
 6   ·  ·  ·  ·  ·  ·  ·  ·
 7   B  W  ·  W  R  W  S  W     speakers · headset | sub · effects · prev play next
```

Everything above the bottom row is read-only:

| | |
|---|---|
| disks | green in sync, amber rebuilding or in a degraded array, strobing red failed |
| filesystems | green with room to spare, yellow getting full, red nearly full |
| drive temperatures | one per drive, in its own column below its health pad |
| temperatures | pale blue normal, yellow warm, red hot, strobing red too hot |

**Hold any of those four pads** and a window appears for as long as you hold
it, laid out as the same grid: the same rows in the same columns, with the held
cell outlined. It carries what a colour cannot — which drive, how many degrees,
how many gigabytes and what share of the volume that is. Releasing the pad
closes it; tapping the red pad opens the same window and leaves it open.

The control row is in that window too, along the bottom where it is on the
board. Each button says what it **is** — the sink's own name, `sub`,
`EasyEffects`, a transport icon — and its state is the colour, the same colour
the pad is showing. Underneath, what a press would do, and only when there is
something to do: the output you are already on says nothing. The `EasyEffects`
cell names the loaded preset, which is the part the colour can only hint at.

Nothing in the window is clickable: it is a readout, the pads are where you
press, and a second set of handlers for the same eight buttons is a second set
to keep right. An open window is kept current, since the row changes under it
every time a pad switches the output or mutes the sub.

Rows 2 and 4 are the same six drives in the same order, so a column is one
drive: its array state above, its temperature below. Drive temperatures need
the `drivetemp` module (`modprobe drivetemp`); without it that row is dark,
since `smartctl` would need root for every reading.

A pad is a whole drive, not an array member, since several arrays can share a
pair of drives and it is the drive that dies. A drive that has vanished entirely
has no pad to light — `/proc/mdstat` only names what is still there — so what
you see in that case is its array's surviving half going amber.

The bottom row is the only part you can press, with a gap separating choosing
an output from silencing the sub. The two output pads are white with the
current one blue; picking the headset takes its microphone with it.
Next to them the subwoofer pad is white while the sub is passing signal and red
while it is muted. The interface sums the sub's channels into the speakers as
well, so simply zeroing them would take 6dB off the speakers too; instead the
pad moves between two fixed levels that leave the speakers at the same
loudness either way — every channel at half with the sub on, the sub's pair at
zero and the speakers at full with it off. The
EasyEffects pad is an on/off switch whose colour says which preset is live:
red off, green for the room preset, orange for the headset one — worked out
from EasyEffects' own autoload bindings, so renaming a preset cannot leave the
pad lying. Play/pause lights sky blue while Spotify is playing.

Every pad here reports rather than remembers. Pressing one fires the command and
then reads the state back, so what you see is what `pactl` and EasyEffects say,
never what the board asked for — change the output from the tray applet and the
pads follow.

**While this tab is on screen it queries EasyEffects once a second, and that
closes the EasyEffects window if you have one open.** Any invocation of its CLI
does, there is no quieter way to ask, and its config file is written too lazily
to use instead. Switching to another tab stops it on the press — not after a
delay, which would spend one more window on someone who had already left.

Most pads use the Launchpad's own 128-colour palette, which a note can name
directly. The pale blue of a normal temperature is not in it, so that pad is
lit with the lighting SysEx instead — seven bits per channel, any colour the
LEDs can make. `TEMP_OK` in `bin/launchpad-pomodoro` is the triple.

## Spectrum

```
 1   B  B  ·  ·  W  ·  ·  ·     the day bar, except where a band reaches it
 2   ·  ·  Y  ·  C  ·  ·  W     white peaks hang above the bars and fall back
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

The top row carries the day bar too, one cell at a time: a band loud enough to
reach it writes over its own cell and the bar returns underneath as soon as the
band drops. Giving the bar a row to itself would have cost the spectrum a
seventh of its height permanently, for a cell that is only wanted when a column
is actually that loud.

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
 1   C C C C · · · ·    download hangs from the top left, snaking down
 2   C C C C · · · ·
 3   C C C C · · · ·
 4   · C C C · · · ·
 5   · · · · O O · ·
 6   · · · · O O O O
 7   · · · · O O O O    upload climbs from the bottom, snaking up
```

Two half-width bars filling from the bottom. Each row is four pads, so a
part-filled row gives four times the resolution of whole rows alone. The scale
is logarithmic, from about 1 KB/s to about 1 Gbit/s, because a linear one sits
at zero all day.

Every other row runs the other way, so the lit pads are one unbroken run rather
than a stack of rows each restarting at the left — growth reads as growth
wherever in the row it happens to be. Download hangs down from the top and
upload climbs from the bottom, so which half is which is legible from the shape
without remembering which colour was which.

## Bars

Row 1 of the pomodoro tab, both habit tabs and the machine tab is not part of
that tab: it shows how much of a period has begun. The spectrum shares that row
rather than reserving it, as described above. The pomodoro, machine and
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

That symlinks the five programs into `~/.local/bin`, copies the chimes to
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
tests/run-tests             # 682 tests, about forty-five seconds
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
| temperatures | an AMD CPU (`k10temp`, `Tctl` and `Tccd2`), an NVIDIA GPU (`nvidia-smi`), an NVMe drive, and SATA drives via `drivetemp` — thresholds are per part, and per drive type |
| disks | whatever `/proc/mdstat` lists; no arrays means an empty row, not an error |
| subwoofer | two channels of a multichannel interface (`TASCAM_SERIES_208i`, LINE OUT 3/4), fed by links something else maintains — the pad only sets those channels' volume |
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
