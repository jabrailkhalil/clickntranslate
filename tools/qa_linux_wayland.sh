#!/usr/bin/env bash
# Run as a regular user inside an isolated Linux test machine/container:
# dbus-run-session -- bash tools/qa_linux_wayland.sh /tmp/cnt-wayland-report
# Needs sway, grim, pipewire, xdg-desktop-portal{,-wlr,-gtk}, wl-clipboard,
# dbus-x11 and the application's Python environment on PATH.
# Set CNT_QA_WAYLAND_SCALE=2 to test mixed monitor scales.
set -euo pipefail
if [ "$(id -u)" -eq 0 ]; then
    echo 'Sway must run as a regular user.' >&2
    exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${1:?Specify the report directory}"
mkdir -p "$OUTPUT"
OUTPUT="$(cd "$OUTPUT" && pwd)"
RUNTIME="$(mktemp -d /tmp/cnt-wayland-qa.XXXXXXXX)"
pids=()
cleanup() {
    if [ "${#pids[@]}" -gt 0 ]; then
        kill "${pids[@]}" 2>/dev/null || true
        wait "${pids[@]}" 2>/dev/null || true
    fi
    # The D-Bus-activated document portal mounts a FUSE filesystem here. Its
    # process outlives our explicitly started helpers until the session ends.
    # Unmount our private portal before removing its temporary directory.
    if mountpoint -q "$RUNTIME/doc"; then
        FUSE_UNMOUNT="$(command -v fusermount3 || command -v fusermount)"
        "$FUSE_UNMOUNT" -u "$RUNTIME/doc"
    fi
    rm -rf -- "$RUNTIME"
}
trap cleanup EXIT
export XDG_RUNTIME_DIR="$RUNTIME"
export XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=sway
export XDG_CONFIG_HOME="$RUNTIME/config" XDG_DATA_HOME="$RUNTIME/data" XDG_CACHE_HOME="$RUNTIME/cache"
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 WLR_HEADLESS_OUTPUTS=2
mkdir -p "$XDG_CONFIG_HOME/xdg-desktop-portal"
cat > "$XDG_CONFIG_HOME/xdg-desktop-portal/portals.conf" <<'PORTALS'
[preferred]
default=gtk
org.freedesktop.impl.portal.Screenshot=wlr
org.freedesktop.impl.portal.ScreenCast=wlr
PORTALS
SCALE="${CNT_QA_WAYLAND_SCALE:-1}"
case "$SCALE" in 1|2) ;; *) echo 'Scale must be 1 or 2.' >&2; exit 2;; esac
cat > "$RUNTIME/sway.conf" <<CONFIG
output HEADLESS-1 resolution 1280x720 position 0 0 scale $SCALE bg #14644d solid_color
output HEADLESS-2 resolution 1024x768 position -1024 0 bg #263555 solid_color
seat seat0 fallback true
default_border none
font monospace 10
CONFIG
sway --unsupported-gpu -c "$RUNTIME/sway.conf" > "$OUTPUT/sway.log" 2>&1 &
pids+=("$!")
for attempt in $(seq 1 80); do
    if [ -S "$RUNTIME/wayland-1" ]; then break; fi
    sleep 0.1
done
test -S "$RUNTIME/wayland-1"
export WAYLAND_DISPLAY=wayland-1 QT_QPA_PLATFORM=wayland
unset DISPLAY QT_SCALE_FACTOR QT_SCREEN_SCALE_FACTORS
dbus-update-activation-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_RUNTIME_DIR XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME
pipewire > "$OUTPUT/pipewire.log" 2>&1 &
pids+=("$!")
sleep 0.3
/usr/libexec/xdg-desktop-portal-wlr > "$OUTPUT/portal-wlr.log" 2>&1 &
pids+=("$!")
/usr/libexec/xdg-desktop-portal > "$OUTPUT/portal.log" 2>&1 &
pids+=("$!")
python "$ROOT/tools/qa_linux_wayland.py" --output "$OUTPUT" \
    --background 'HEADLESS-1=#14644d' --background 'HEADLESS-2=#263555'
