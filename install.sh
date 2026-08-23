#!/usr/bin/env bash
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Taylor Hornby
# Install launchpad-tools for the current user. No root, nothing outside $HOME.
#
#   ./install.sh              symlink into ~/.local/bin and enable the service
#   ./install.sh --no-enable  install but leave the service alone
#   ./install.sh --uninstall
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
BIN="$HOME/.local/bin"
SHARE="$HOME/.local/share/launchpad-pomodoro"
UNIT="$HOME/.config/systemd/user/launchpad-pomodoro.service"
PROGS=(launchpad-pomodoro habit-popup machine-popup pomo-popup launchpad-smoketest)

if [ "${1:-}" = "--uninstall" ]; then
    systemctl --user disable --now launchpad-pomodoro.service 2>/dev/null || true
    rm -f "$UNIT"
    systemctl --user daemon-reload 2>/dev/null || true
    for p in "${PROGS[@]}"; do
        [ -L "$BIN/$p" ] && rm -f "$BIN/$p"
    done
    echo "Removed. Your habits and timers are still in $SHARE/../launchpad-pomodoro.json"
    exit 0
fi

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
python3 -c 'import mido' 2>/dev/null || {
    echo "Missing python-mido / python-rtmidi." >&2
    echo "  Arch:   sudo pacman -S python-mido python-rtmidi" >&2
    echo "  Debian: sudo apt install python3-mido python3-rtmidi" >&2
    exit 1
}
python3 -c 'import tkinter' 2>/dev/null || \
    echo "warning: no tkinter -- the habit window will not open (Debian: python3-tk)" >&2

mkdir -p "$BIN" "$SHARE" "$(dirname "$UNIT")"

# symlinks, so 'git pull' updates what is installed
for p in "${PROGS[@]}"; do
    ln -sfn "$REPO/bin/$p" "$BIN/$p"
done
# -u, not -n: the programs are symlinks and follow a pull, and the chimes have
# to as well or a regenerated one never reaches the running board. A chime you
# edited yourself is newer than the repo's and survives.
cp -u "$REPO"/share/sounds/*.wav "$SHARE/" 2>/dev/null || true
sed "s|%h/.local/bin|$BIN|g" "$REPO/systemd/launchpad-pomodoro.service" > "$UNIT"

echo "Installed to $BIN (symlinks into $REPO)"
case "$PATH" in *"$BIN"*) ;; *) echo "note: $BIN is not on your PATH" ;; esac

if [ "${1:-}" != "--no-enable" ]; then
    systemctl --user daemon-reload
    systemctl --user enable --now launchpad-pomodoro.service
    sleep 2
    systemctl --user is-active --quiet launchpad-pomodoro.service \
        && echo "Service running. Plug the Launchpad in if it is not already." \
        || echo "Service failed to start: journalctl --user -u launchpad-pomodoro -n 20"
fi
