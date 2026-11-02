#!/usr/bin/env python3
import fcntl
import glob
import os
import socket
import subprocess
import sys
import threading
import time

THEME = os.environ.get("CURSOR_THEME_NAME", "Genshin-Official")
SIZE = int(os.environ.get("CURSOR_SIZE_PX", "32"))
SCHEMA = "org.gnome.desktop.interface"
LOG = os.path.expanduser("~/.cache/hypr-genshin/cursor-guard.log")
LOCK = os.path.expanduser("~/.cache/hypr-genshin/cursor-guard.lock")
os.makedirs(os.path.dirname(LOG), exist_ok=True)

_lock = threading.Lock()


def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200_000:
            open(LOG, "w").close()
        with open(LOG, "a") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=6).stdout
    except Exception:
        return ""


def snapshot():
    """The youngest processes right now: whatever just started is probably the cause."""
    out = run(["ps", "-eo", "pid,etimes,args", "--sort=etimes"])
    n = 0
    for line in out.splitlines()[1:]:
        if any(x in line for x in ("cursor-guard", "ps -eo", "gsettings monitor", "gsettings get")):
            continue
        log("    " + " ".join(line.split())[:160])
        n += 1
        if n >= 10:
            break


def apply(reason):
    with _lock:
        cur = run(["gsettings", "get", SCHEMA, "cursor-theme"]).strip().strip("'")
        if cur and cur != THEME:
            run(["gsettings", "set", SCHEMA, "cursor-theme", THEME])
        run(["hyprctl", "setcursor", THEME, str(SIZE - 1)])
        run(["hyprctl", "setcursor", THEME, str(SIZE)])
        log(f"applied {THEME} {SIZE} ({reason}); gsettings was '{cur}'")


def delayed(reason, delays=(0.4, 1.6)):
    for d in delays:
        time.sleep(d)
        apply(reason)


def sock_path():
    rt = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if sig:
        p = f"{rt}/hypr/{sig}/.socket2.sock"
        if os.path.exists(p):
            return p
    found = sorted(glob.glob(f"{rt}/hypr/*/.socket2.sock"), key=os.path.getmtime)
    return found[-1] if found else None


def hypr_events():
    last = 0.0
    while True:
        p = sock_path()
        if p:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(p)
                for line in s.makefile("r", errors="replace"):
                    if line.startswith("configreloaded") and time.time() - last > 1.0:
                        last = time.time()
                        log("event: Hyprland config reloaded; youngest processes:")
                        snapshot()
                        threading.Thread(target=delayed, args=("config reload",), daemon=True).start()
            except OSError:
                pass
        time.sleep(2)


def gsettings_watch():
    while True:
        try:
            p = subprocess.Popen(["gsettings", "monitor", SCHEMA, "cursor-theme"],
                                 stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                val = line.split(":", 1)[-1].strip().strip("'")
                if val and val != THEME:
                    log(f"event: gsettings cursor-theme changed to '{val}'; youngest processes:")
                    snapshot()
                    threading.Thread(target=delayed, args=("gsettings changed", (0.3,)), daemon=True).start()
        except OSError:
            pass
        time.sleep(3)


def main():
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("cursor-guard is already running")
        return
    log(f"cursor-guard started (theme {THEME}, size {SIZE})")
    threading.Thread(target=hypr_events, daemon=True).start()
    threading.Thread(target=gsettings_watch, daemon=True).start()
    apply("start")
    threading.Event().wait()


if __name__ == "__main__":
    main()
