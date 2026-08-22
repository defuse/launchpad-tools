# launchpad

Novation Launchpad Mini MK3 as a desk board: pomodoro timers, daily and weekly
habit trackers, CPU and network meters.

    launchpad-pomodoro    the daemon (MIDI, rendering, input, state)
    habit-popup           resident tkinter habit grid, a separate process that
                          speaks a line protocol with the daemon over stdin/out
    launchpad-smoketest   calls every entry point once, without hardware

Installed by symlinking these into ~/.local/bin, run as the systemd user unit
`launchpad-pomodoro.service`. State lives in
~/.local/share/launchpad-pomodoro.json and is deliberately NOT tracked here.
