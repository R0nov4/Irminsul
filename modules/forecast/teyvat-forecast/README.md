# Teyvat Forecast

A Genshin Impact–styled weather popup for **Waybar**, built with
**Quickshell (QML)** on Wayland/Hyprland. Live particle weather scenes
(rain, snow, storms, drifting clouds, twinkling nights, fog), an element
system (Hydro/Cryo/Electro/Pyro/Anemo/Geo/Dendro), elemental reaction
banners, an animated sunrise→sunset arc, a 24-hour temperature curve, an
"Abyssal Corruption" AQI meter, a "Resin" UV meter — and Paimon
commenting on all of it.

Data comes from **Open-Meteo** (no API key, no secrets). One shared JSON
cache feeds both the Waybar module and the popup, so nothing is fetched
twice.

```
┌──────────────────────────────────────────────────────────────┐
│  weather.sh (shim) ──┐                                       │
│   Waybar module      │ reads                                 │
│                      ▼                                       │
│            ~/.cache/teyvat-forecast/weather.json              │
│                      ▲                                       │
│  systemd user timer  │ writes (atomic, flock'd, 12 min)      │
│   └─ teyvat-fetch.py ┘   Open-Meteo forecast + air quality   │
│                                                              │
│  Quickshell popup (QML) ── reads the same JSON via inotify   │
│   └─ toggled from Waybar via: qs ipc call teyvat toggle      │
└──────────────────────────────────────────────────────────────┘
```

**Why a systemd timer instead of a loop inside the popup?** The timer
keeps data fresh for the *bar* even when the popup (or all of
Quickshell) isn't running, it leaves zero processes idle (oneshot
units), and it survives Quickshell restarts. The popup itself contains
**no network I/O and no polling timers while closed** — when the panel
is hidden there is no window, no animation and no timer running, so the
closed-popup cost is effectively zero.

---

## Requirements

| Tool      | Hard? | Used for                            |
|-----------|-------|-------------------------------------|
| `qs` (quickshell) | required | the popup (targeted: **Quickshell 0.3.x**, current release 0.3.2) |
| `python3` | required | data layer (stdlib only)            |
| `curl`    | required | HTTP requests                      |
| `jq`      | required | Waybar shim output                 |
| `systemctl` | optional | 12-min refresh timer (fallback: shim self-heals) |
| `mpv` / `paplay` | optional | ambient sound / click (off by default) |

Fonts: **SDK_SC_Web** (fallback **HYWenHei**) — change via the `font`
config key if your Qt sees them under different names.

## Install

```sh
cd teyvat-forecast
./install.sh --deps-check     # verify tools first
./install.sh --install
```

The installer is idempotent (safe to re-run for updates) and it:

1. copies the Quickshell config to `~/.config/quickshell/teyvat-forecast/`
2. installs the data layer to `~/.config/teyvat-forecast/teyvat-fetch.py`
3. writes a default `~/.config/teyvat-forecast/config.json` (**never**
   overwrites an existing one) and records the detected sound player
4. installs the CLI to `~/.local/bin/teyvat-forecast`
5. backs up your `weather.sh` → `weather.sh.teyvat-orig.bak` and installs
   a shim that reads the shared cache (**output format identical to your
   current module**, same CSS classes)
6. backs up `config.jsonc` → `config.jsonc.teyvat.bak` and adds **only**
   the `on-click` key inside the `custom/weather` block (other modules
   are never touched)
7. copies any element/Paimon icons it finds in your
   `~/.config/waybar-genshin` theme into the popup (bundled vector-drawn
   emblems are used otherwise)
8. installs + enables the systemd user timer
9. performs a first fetch

### Autostart with Hyprland (Lua config)

```lua
-- preferred pattern (Hyprland 0.55+/0.56 Lua configs):
hl.on("hyprland.start", function()
    hl.exec_cmd("qs -c teyvat-forecast")
end)

-- universal fallback that works in any Lua config:
os.execute("qs -c teyvat-forecast &")
```

Plain-syntax equivalent, if you still have a `hyprland.conf` anywhere:
`exec-once = qs -c teyvat-forecast`.

Optional Hyprland layer rules for blur behind the popup (namespace:
`teyvat-forecast`):

```
layerrule = blur, teyvat-forecast
```

## Waybar hook

The installer does this for you; manually it is exactly this key inside
the existing `custom/weather` block:

```jsonc
"custom/weather": {
    "exec": "$HOME/.config/waybar-genshin/scripts/weather.sh",
    "return-type": "json",
    "interval": 600,
    "on-click": "/home/YOURUSER/.local/bin/teyvat-forecast toggle"
}
```

Restart Waybar (your usual reload keybind) after editing. Click the
weather module to open, click again / press `Esc` / click anywhere
outside to close. `←` / `→` switch tabs.

> Position note: your weather module sits in `modules-center`. The popup
> defaults to `top_right` with `offset_x: 310` — if you want it directly
> under the module, try `"anchor": "top_center"` and tune `offset_x`.

## Config

`~/.config/teyvat-forecast/config.json` (defaults shown):

| Key | Type | Meaning |
|-----|------|---------|
| `city` | string | display name; empty = auto from IP |
| `lat`, `lon` | number | coordinates; `null` = auto-detect by IP |
| `units` | `"metric"` / `"imperial"` | °C·km/h or °F·mph |
| `quality` | `"low"` / `"medium"` / `"high"` | particle budgets (rain 90/170/300, stars 24/32/42 …) |
| `refresh_minutes` | number | informational — the timer is 12 min |
| `position.anchor` | `"top_right"` / `"top_left"` / `"top_center"` | anchor |
| `position.offset_x` | number | px from right/left edge, or delta from center |
| `position.offset_y` | number | px below the top edge (bar height + gap) |
| `monitor` | `"primary"` or connector (`"eDP-1"`, `"DP-1"`…) | which output |
| `scale` | 0.75–1.75 | UI scale (base panel ≈ 460×676) |
| `font` | string | primary font family, e.g. `SDK_SC_Web`; auto-falls back to `HYWenHei` |
| `show_paimon` | bool | show the Paimon line |
| `sound.enabled` | bool | **default false** |
| `sound.volume` | 0–100 | mpv volume for the ambient loop |
| `sound.click` | bool | UI click sounds |
| `sound.player` | auto-filled | `mpv` / `paplay` / `""` |

Config edits are picked up live (the popup watches the file).

### Changing the city

Three ways, all of which write `city` / `lat` / `lon` into `config.json`
(that file wins over the legacy `weather.conf` and the location caches) and
refetch immediately:

- **In the popup** — click the city name (the small magnifier next to it),
  type at least 2 letters (any language), pick a result with the mouse or
  ↑/↓ + Enter. "Use my current location" detects it by IP. `Esc` closes the
  picker.
- **CLI** — `teyvat-forecast city` (opens the picker), `teyvat-forecast city Karaj`
  (first match), `teyvat-forecast city --here` (by IP).
- **By hand** — edit `config.json`.

Lookups use the free Open-Meteo geocoding API, run by the data layer
(`teyvat-fetch.py search|set-city|locate`) — QML itself still does no network I/O.

## CLI & IPC

```sh
teyvat-forecast toggle            # what the Waybar module calls
teyvat-forecast show | hide
teyvat-forecast fetch             # refresh data now
teyvat-forecast start | stop      # start/stop the Quickshell shell
teyvat-forecast status            # data + shell + timer status
teyvat-forecast timer on | off
```

Direct IPC (what the CLI uses under the hood):

```sh
qs ipc call teyvat toggle
qs ipc call teyvat show
qs ipc call teyvat hide
qs ipc call teyvat refresh
qs ipc call teyvat search         # open the popup with the city picker
qs ipc call teyvat ping           # liveness check
qs ipc call teyvat quit
```

## Preview mode

See every scene, element and reaction without waiting for weather:

```sh
teyvat-forecast --preview clear    # golden motes, Anemo/gold
teyvat-forecast --preview rain     # Hydro + rain scene
teyvat-forecast --preview snow     # Cryo + snow (+ Frozen reaction)
teyvat-forecast --preview storm    # Electro + lightning + Electro-Charged
teyvat-forecast --preview fog      # Geo + fog banks
teyvat-forecast --preview hot      # Pyro + Vaporize reaction
teyvat-forecast --preview windy    # Anemo teal + wind streaks
teyvat-forecast --preview night    # stars + moon
teyvat-forecast --demo-stale       # preview the STALE DATA badge
teyvat-forecast preview off        # restore real data
```

While a preview is active the **bar shows the fake temperature too** —
that's expected (it reads the same cache). The 12-minute timer will
overwrite previews; stop it during styling sessions with
`teyvat-forecast timer off`.

## Performance notes (old-iGPU friendly)

- **Closed popup ≈ zero cost**: no window is mapped (PanelWindow
  `visible: false`), all Timers/animations bind their `running` state to
  the popup being open, and the only always-on work is two inotify
  watches (config + cache) that cost nothing.
- **No JS-per-frame loops anywhere.** Scenes use `QtQuick.Particles`
  (C++-side simulation, batched rendering) or plain property animations;
  the hourly curve and sun arc are `Canvas` items that repaint **only**
  when data or size changes, never per frame.
- Particle counts are hard-capped by the `quality` setting.
- Optional extras (sheen sweeps, glow pulses) run only while the popup
  is visible.

## Troubleshooting

**Popup doesn't open on click** — is the shell running?
`teyvat-forecast status`. Start it: `teyvat-forecast start`. If Waybar's
click does nothing at all, check that `~/.local/bin` is in Waybar's
environment PATH, or use the absolute path form shown above.

**Clicking outside doesn't close it** — outside-dismissal uses Hyprland's
`hyprland_focus_grab_v1` protocol via `HyprlandFocusGrab`. Very old
compositors without that protocol will only close via `Esc` / re-click /
`qs ipc call teyvat hide`.

**Keyboard doesn't work (Esc / arrows)** — the popup takes exclusive
layer-shell keyboard focus. If that misbehaves on your build, change
`WlrLayershell.keyboardFocus` in `WeatherPopup.qml` to
`WlrKeyboardFocus.OnDemand` and reload.

**Data is stale / offline** — the popup shows a red **STALE DATA**
badge, the bar adds the `offline` class (same as before), and both keep
the last good data. Check: `teyvat-forecast fetch` and
`systemctl --user status teyvat-forecast-fetch.timer`.

**Popup shows "Weather Network Unreachable"** — no cache yet (fresh
install, offline). Press *Retry now* or run `teyvat-forecast fetch`.

**Wrong city** — set `lat`/`lon`/`city` in the config, or keep your old
`~/.config/waybar-genshin/weather.conf` (`LAT=`, `LON=`, `CITY=`) —
it is still honored.

**Fonts look wrong / generic face** — the popup resolves its font at
startup: it tries the config `font` family, then `SDK_SC_Web`, then
`HYWenHei` (any weight), matching exactly or fuzzily (case/spaces/
underscores ignored) against the families Qt can actually see
(`Qt.fontFamilies()`). To check what your system offers:

```sh
fc-list | grep -i -E "sdk|hywen"    # → family names Qt will see
# e.g.  /home/you/.fonts/HYWenHei-85W.ttf: HYWenHei 85W:style=Regular
```

Put the exact family name from that output into `"font"` in
`~/.config/teyvat-forecast/config.json` (picked up live). If neither font
is installed, install one — e.g. the HYWenHei / Genshin web font — or set
`font` to any family you like. Numbers use the same font.

**QML errors on start** — run `qs -c teyvat-forecast` in a terminal and
read the log. This project targets Quickshell **0.3.x**; older releases
may lack properties used here (see the verification notes in the project
delivery notes).

## Uninstall

```sh
./install.sh --uninstall   # restores weather.sh + removes the on-click key
./install.sh --purge       # also deletes ~/.config|cache/teyvat-forecast
```

Your `config.jsonc`, `weather.sh` and every other Waybar module are
restored to their pre-install state (from the backups listed in
`~/.config/teyvat-forecast/install-state.json`).
