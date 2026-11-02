#!/usr/bin/env python3
"""
✦ Genshin tray doctor — finds the icons that live in the waybar tray and removes unwanted ones
  (by default: Wi-Fi / network applets). Works on any Hyprland/waybar setup — nothing is hard-coded
  to one machine: it reads what is REALLY in the tray, finds who starts it, and switches that off.

    python3 genshin-tray-doctor.py                 # dry run: list every tray icon + who starts it
    python3 genshin-tray-doctor.py --apply         # remove the flagged ones
    python3 genshin-tray-doctor.py --match udiskie # also flag items matching this regex
    python3 genshin-tray-doctor.py --pid 1234      # act directly on one process

What "remove" means (all reversible, backups in ~/.cache/celestia-purge/<time>-tray):
  • systemd user unit that runs it → stopped + masked          (undo: systemctl --user unmask UNIT)
  • XDG autostart .desktop        → Hidden=true override
  • exec / exec-once lines (.conf) and startup entries (.lua) in ~/.config/hypr*, hyde, uwsm → commented out
    (backup folders such as hypr_old_backup are skipped)
  • the process itself            → terminated
Anything else that mentions the program (scripts etc.) is only REPORTED, never edited.
"""
import argparse, glob, os, re, shutil, signal, subprocess, sys, time

HOME = os.path.expanduser("~")
NET_RE = r'nm[-_]?applet|nm[-_]?tray|network|wi-?fi|wlan|wireless|iwgtk|impala|connman|cmst|wicd'
WATCHER = ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher")
STAMP = time.strftime("%Y%m%d-%H%M%S")
BK = os.path.join(HOME, ".cache", "celestia-purge", STAMP + "-tray")
MARK = "# [celestia-cleanup] "
LUA_MARK = "-- [celestia-cleanup] "


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


def quoted(s):
    return re.findall(r'"((?:[^"\\]|\\.)*)"', s or "")


def prop(dest, path, iface, name):
    r = run(["busctl", "--user", "get-property", dest, path, iface, name])
    return r.stdout.strip() if r.returncode == 0 else ""


def tray_items():
    r = run(["busctl", "--user", "get-property", *WATCHER, "RegisteredStatusNotifierItems"])
    if r.returncode != 0:
        return None
    items = []
    for it in quoted(r.stdout):
        name, _, path = it.partition("/")
        items.append({"raw": it, "bus": name, "path": "/" + path if path else "/StatusNotifierItem"})
    return items


def fill_item(it):
    for p in ("Id", "Title", "IconName", "Status"):
        v = quoted(prop(it["bus"], it["path"], "org.kde.StatusNotifierItem", p))
        it[p] = v[0] if v else ""
    m = re.search(r'^PID=(\d+)', run(["busctl", "--user", "status", it["bus"]]).stdout, re.M)
    it["pid"] = int(m.group(1)) if m else None


def proc_args(pid):
    try:
        raw = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="replace")
        return [a for a in raw.split("\0") if a]
    except Exception:
        return []


def proc_name(args, pid=None):
    base = ""
    if pid:
        try:
            base = os.path.basename(os.readlink(f"/proc/{pid}/exe")).replace(" (deleted)", "")
        except Exception:
            pass
    if not base and args:
        base = os.path.basename(args[0])
    if re.match(r'(python[\d.]*|bash|sh|dash|zsh|node|electron)$', base):
        for a in args[1:]:
            if not a.startswith("-"):
                return os.path.basename(a)
    return base


def proc_unit(pid):
    try:
        for line in open(f"/proc/{pid}/cgroup"):
            seg = line.strip().split("/")[-1]
            if seg.endswith(".service") and not seg.startswith(("user@", "session-")):
                return seg
    except Exception:
        pass
    return None


def word(name):
    return re.compile(r'(?<![\w.-])' + re.escape(name) + r'(?![\w-])')


def backup(path):
    dst = os.path.join(BK, os.path.relpath(path, "/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(path, dst)


def find_autostart(name):
    pat, out = word(name), []
    for d in ("/etc/xdg/autostart", os.path.join(HOME, ".config", "autostart")):
        for f in sorted(glob.glob(d + "/*.desktop")):
            try:
                txt = open(f, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if re.search(r'^Hidden=true', txt, re.M):
                continue
            if f.startswith("/etc/"):
                ov = os.path.join(HOME, ".config", "autostart", os.path.basename(f))
                if os.path.exists(ov) and "Hidden=true" in open(ov, errors="replace").read():
                    continue
            if any(l.startswith("Exec=") and pat.search(l) for l in txt.splitlines()):
                out.append(f)
    return out


BACKUP_DIR = re.compile(r'back|bak|(^|[._-])old($|[._-])', re.I)


def conf_files():
    roots = glob.glob(os.path.join(HOME, ".config", "hypr*")) + [
        os.path.join(HOME, ".config", "hyde"), os.path.join(HOME, ".config", "uwsm")]
    for root in roots:
        if BACKUP_DIR.search(os.path.basename(root)):
            continue
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if not BACKUP_DIR.search(d)]
            for n in fn:
                if n.endswith((".conf", ".lua")) and ".bak" not in n:
                    yield os.path.join(dp, n)


def find_conf_lines(name):
    """Lines that START the program: `exec-once = ...` in .conf, and in .lua either an
    exec-style call or a bare string entry of a startup list (\"cmd &\",)."""
    pat = word(name)
    ex = re.compile(r'^\s*exec(r)?(-once)?\s*=')
    lua_exec = re.compile(r'exec|spawn|run|launch|start', re.I)
    lua_item = re.compile(r'^\s*["\'].*["\']\s*,?\s*$')
    hits = []
    for f in conf_files():
        try:
            lines = open(f, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        is_lua = f.endswith(".lua")
        for i, l in enumerate(lines):
            if not pat.search(l):
                continue
            if is_lua:
                if l.lstrip().startswith("--"):
                    continue
                if lua_item.match(l) or lua_exec.search(l):
                    hits.append((f, i, l.strip()))
            elif ex.match(l):
                hits.append((f, i, l.strip()))
    return hits


SKIP_DIRS = {"google-chrome", "chromium", "BraveSoftware", "Code", "discord", "cache", "Cache", "node_modules", ".git",
             "celestia-purge"}
EXTS = (".sh", ".conf", ".py", ".jsonc", ".json", ".service", ".desktop", ".lua", ".zsh", ".fish")


def find_mentions(name, skip_files):
    pat, out = word(name), []
    roots = [os.path.join(HOME, ".config"), os.path.join(HOME, ".local", "bin"),
             os.path.join(HOME, ".local", "lib"), os.path.join(HOME, ".local", "share", "hyde")]
    me = os.path.abspath(__file__)
    for root in roots:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP_DIRS]
            for n in fn:
                p = os.path.join(dp, n)
                if not n.endswith(EXTS) or ".bak" in n or p in skip_files or os.path.abspath(p) == me:
                    continue
                try:
                    if os.path.getsize(p) > 300_000:
                        continue
                    for i, l in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
                        if pat.search(l) and not l.lstrip().startswith("#"):
                            out.append((p, i, l.strip()[:100]))
                            break
                except Exception:
                    continue
                if len(out) >= 12:
                    return out
    return out


def short(p):
    return p.replace(HOME, "~")


def plan(name, pid):
    return {"unit": proc_unit(pid) if pid else None,
            "autostart": find_autostart(name),
            "conf": find_conf_lines(name)}


def apply_plan(name, pid, pl):
    if pl["unit"]:
        run(["systemctl", "--user", "stop", pl["unit"]])
        r = run(["systemctl", "--user", "mask", pl["unit"]])
        if r.returncode == 0:
            print(f"      − unit stopped + masked: {pl['unit']}   (undo: systemctl --user unmask {pl['unit']})")
        else:
            print(f"      ! could not mask {pl['unit']} (transient or file-based unit): {r.stderr.strip()[:90]}")
    for f in pl["autostart"]:
        ov = os.path.join(HOME, ".config", "autostart", os.path.basename(f))
        os.makedirs(os.path.dirname(ov), exist_ok=True)
        if f.startswith("/etc/") or f.startswith("/usr/"):
            name_ = os.path.basename(f)
            open(ov, "w").write(f"[Desktop Entry]\nType=Application\nName={name_}\nHidden=true\n")
        else:
            backup(f)
            open(f, "a").write("\nHidden=true\n")
        print(f"      − autostart disabled: {short(f)}")
    by_file = {}
    for f, i, _ in pl["conf"]:
        by_file.setdefault(f, []).append(i)
    for f, idxs in by_file.items():
        backup(f)
        lines = open(f, encoding="utf-8", errors="replace").read().split("\n")
        mark = LUA_MARK if f.endswith(".lua") else MARK
        for i in idxs:
            if not lines[i].lstrip().startswith(mark.strip()):
                ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                lines[i] = ind + mark + lines[i].lstrip()
        open(f, "w", encoding="utf-8").write("\n".join(lines))
        print(f"      − {len(idxs)} line(s) commented out in {short(f)}")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"      − process {pid} terminated")
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"      ! could not stop {pid}: {e}")


def main():
    ap = argparse.ArgumentParser(description="Find and remove unwanted waybar tray icons.")
    ap.add_argument("--apply", action="store_true", help="really remove the flagged items (default: dry run)")
    ap.add_argument("--match", default="", help="extra regex; items whose id/title/icon/program match are flagged too")
    ap.add_argument("--pid", type=int, help="act directly on this process id")
    a = ap.parse_args()

    print("\n  ✦ APPLY mode" if a.apply else "\n  ✦ DRY RUN — nothing will be changed (add --apply)")
    flag_re = re.compile(NET_RE + (("|" + a.match) if a.match else ""), re.I)
    targets = []

    if a.pid:
        args = proc_args(a.pid)
        if not args:
            sys.exit(f"  no such process: {a.pid}")
        targets.append({"label": f"pid {a.pid}", "name": proc_name(args, a.pid), "pid": a.pid, "extra": ""})
    else:
        items = tray_items()
        if items is None:
            sys.exit("  Could not read the tray (busctl / org.kde.StatusNotifierWatcher). Is waybar's tray running?")
        print(f"\n  Tray icons registered right now: {len(items)}\n")
        seen = set()
        for n, it in enumerate(items, 1):
            fill_item(it)
            args = proc_args(it["pid"]) if it["pid"] else []
            name = proc_name(args, it['pid']) or it["Id"]
            text = " ".join([it["Id"], it["Title"], it["IconName"], name])
            flagged = bool(flag_re.search(text))
            print(f"  [{n}] {'FLAG ▶' if flagged else '      '} {name or '?'}  (pid {it['pid']})")
            print(f"        Id={it['Id'] or '-'}  Title={it['Title'] or '-'}  Icon={it['IconName'] or '-'}  Status={it['Status'] or '-'}")
            if not flagged:
                continue
            if it["pid"] in seen:
                continue
            seen.add(it["pid"])
            targets.append({"label": f"[{n}] {name}", "name": name, "pid": it["pid"], "extra": it["IconName"]})

    if not targets:
        print("\n  Nothing flagged. If you can SEE an unwanted icon above, re-run with  --match <part of its name/icon>")
        return

    print()
    for t in targets:
        pl = plan(t["name"], t["pid"])
        print(f"  ── {t['label']}  — who starts it:")
        print(f"      systemd unit : {pl['unit'] or '-'}")
        print(f"      autostart    : {', '.join(short(f) for f in pl['autostart']) or '-'}")
        for f, i, l in pl["conf"]:
            print(f"      config line  : {short(f)}:{i+1}  {l[:80]}")
        if not pl["conf"]:
            print("      config line  : -")
        skip = {f for f, _, _ in pl["conf"]} | set(pl["autostart"])
        for p, i, l in find_mentions(t["name"], skip):
            print(f"      mentioned in : {short(p)}:{i}  (report only)  {l[:60]}")
        if a.apply:
            apply_plan(t["name"], t["pid"], pl)
        print()

    if a.apply:
        print(f"  ✓ Done. Backups: {short(BK)}")
        print("    A HyDE update can restore its own files — just run this again if an icon comes back.")
    else:
        print("  Looks right? Run again with --apply.")


if __name__ == "__main__":
    main()
