#!/usr/bin/env python3
import json, time
from battery_info import info

last = None
while True:
    i = info()
    force = None
    try:
        force = open("/tmp/bat-force").read().strip()
    except Exception:
        pass
    charging = i["status"] == "Charging"
    ac = i["ac"]
    if force == "charging":
        charging = True
    elif force == "normal":
        charging, ac = False, False
    lvl = max(0, min(100, int(round(i["cap"] / 5.0)) * 5))
    cls = ["bat", "lvl-%d" % lvl]
    if charging:
        cls.append("charging")
    elif ac:
        cls.append("plugged")
    elif i["cap"] <= 15:
        cls.append("low")
    out = json.dumps({"text": "\u00a0", "class": cls, "tooltip": "\n".join(i["lines"])})
    if out != last:
        print(out, flush=True)
        last = out
    time.sleep(1)
