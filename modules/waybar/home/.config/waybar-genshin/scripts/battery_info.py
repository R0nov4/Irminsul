import glob

def _rd(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except Exception:
        return None

def _num(p):
    try:
        return float(_rd(p))
    except Exception:
        return None

def _fmt(h):
    m = int(round(h * 60))
    return "%dh %02dm" % (m // 60, m % 60)

def info():
    ac = False
    for d in glob.glob("/sys/class/power_supply/*"):
        if _rd(d + "/type") == "Mains" and _rd(d + "/online") == "1":
            ac = True
    bats = sorted(glob.glob("/sys/class/power_supply/BAT*"))
    if not bats:
        return {"cap": 0, "status": "None", "ac": ac, "lines": ["No battery found"]}
    b = bats[0]
    cap = int(_num(b + "/capacity") or 0)
    status = _rd(b + "/status") or "Unknown"
    volt = _num(b + "/voltage_now")

    def energy(n):
        e = _num("%s/energy_%s" % (b, n))
        if e is not None:
            return e
        c = _num("%s/charge_%s" % (b, n))
        if c is not None and volt:
            return c * volt / 1e6
        return None

    e_now, e_full, e_des = energy("now"), energy("full"), energy("full_design")
    p = _num(b + "/power_now")
    if not p:
        cur = _num(b + "/current_now")
        if cur and volt:
            p = cur * volt / 1e6

    lines = ["Elemental Energy: %d%%  ·  %s" % (cap, status)]
    if p:
        lines.append("Power flow: %.1f W" % (p / 1e6))
        if status == "Discharging" and e_now:
            lines.append("Time left: " + _fmt(e_now / p))
        elif status == "Charging" and e_now and e_full:
            lines.append("Until full: " + _fmt((e_full - e_now) / p))
    if e_full and e_des:
        lines.append("Vessel health: %.0f%%" % (e_full / e_des * 100))
    cyc = _rd(b + "/cycle_count")
    if cyc and cyc != "0":
        lines.append("Charge cycles: " + cyc)
    return {"cap": cap, "status": status, "ac": ac, "lines": lines}
