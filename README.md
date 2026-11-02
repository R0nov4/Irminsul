<div align="center">

<!-- 📸 Optional: replace this generated header with your own wide banner → reference/banner.png (1600×600) -->
<img src="reference/banner.png" alt="Irminsul" width="100%">

<a href="https://github.com/R0nov4/irminsul">
  <img src="https://readme-typing-svg.demolab.com?font=Cinzel&weight=600&size=21&duration=3200&pause=900&color=F5C542&center=true&vCenter=true&width=760&lines=Boot+%C2%B7+Login+%C2%B7+Bar+%C2%B7+Launcher+%C2%B7+Lock+%C2%B7+Power;Wi-Fi+%C2%B7+Bluetooth+%C2%B7+Sound+%C2%B7+Battery+%C2%B7+Polkit;Icons+%C2%B7+File+Chooser+%C2%B7+Screenshots+%C2%B7+Terminal;17+modules.+One+installer.+Zero+frameworks." alt="Irminsul features">
</a>

<br><br>

![Arch Linux](https://img.shields.io/badge/Arch_Linux-1793D1?style=for-the-badge&logo=archlinux&logoColor=white)
![Hyprland](https://img.shields.io/badge/Hyprland-58E1FF?style=for-the-badge&logo=hyprland&logoColor=black)
![Bash](https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)
![GTK3](https://img.shields.io/badge/GTK3-7FE719?style=for-the-badge&logo=gtk&logoColor=black)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
<br>
![Version](https://img.shields.io/badge/version-1.0.0-f5c542?style=for-the-badge&labelColor=1a1a2e)
![Modules](https://img.shields.io/badge/modules-17-ff9d5c?style=for-the-badge&labelColor=1a1a2e)
![Stars](https://img.shields.io/github/stars/R0nov4/irminsul?style=for-the-badge&color=f5c542&labelColor=1a1a2e)
![Last commit](https://img.shields.io/github/last-commit/R0nov4/irminsul?style=for-the-badge&color=9b7dff&labelColor=1a1a2e)

<br>

[**✦ Showcase**](#showcase) &nbsp;·&nbsp;
[**❖ Spotlights**](#spotlights) &nbsp;·&nbsp;
[**🧩 Modules**](#modules) &nbsp;·&nbsp;
[**🚀 Install**](#installation) &nbsp;·&nbsp;
[**⌨️ Keybindings**](#keybindings) &nbsp;·&nbsp;
[**🛠 Maintenance**](#maintenance)

</div>

<br>

> **Irminsul** turns a bare Arch + Hyprland install into a living piece of Teyvat — from the very first boot splash to the *Quit Game* dialog. Every piece is hand-built, themed after the game, and installable on its own. No theme frameworks. No hidden dependencies on HyDE.

<br>

<div align="center">

| 🧩 | 🌅 | 🌐 | 🎧 | 📸 | 🪄 |
|:-:|:-:|:-:|:-:|:-:|:-:|
| **17**<br><sub>modules</sub> | **4**<br><sub>time-of-day phases</sub> | **7**<br><sub>elemental workspaces</sub> | **85+**<br><sub>Traveler cards</sub> | **eng + fas**<br><sub>OCR</sub> | **1**<br><sub>installer</sub> |

</div>

<br>

---

<a id="a-day-in-teyvat"></a>
## ✦ A day in Teyvat

Everything you touch, from power button to power menu, belongs to the same world.

```mermaid
flowchart LR
    A["🔌 Power on"] --> B["🌅 Plymouth loading screen<br/>hardware clock → Day / Night"]
    B --> C["🏰 SDDM Celestia<br/>Dawn · Day · Dusk · Night"]
    C --> D["🌿 Hyprland<br/>standalone Lua core"]
    D --> E["📊 Waybar · 🚀 Rofi · 🔔 Dunst<br/>📶 Wi-Fi · 🔵 Bluetooth · 🔊 Sound"]
    E --> F["🔒 Hyprlock"]
    F --> G["🧚 Quit Game?"]
```

<br>

---

<a id="showcase"></a>
## ✦ Showcase

<!-- 📸 Drop your screenshots into reference/ using these names (or edit the paths). -->

<div align="center">

| Desktop | Theme Builder v3 |
|:---:|:---:|
| <img src="reference/desktop.png" width="480"> | <img src="reference/theme-builder.png" width="480"> |
| **Celestia Wi-Fi · Mini Popup** | **Celestia Wi-Fi · Akasha Terminal** |
| <img src="reference/wifi-mini.png" width="480"> | <img src="reference/wifi-akasha.png" width="480"> |
| **Teyvat Archive · Bluetooth** | **Teyvat Ley Line Network · quick popup** |
| <img src="reference/bluetooth-archive.png" width="480"> | <img src="reference/bluetooth-popup.png" width="480"> |
| **Irminsul Sound Console** | **The Resonance Archive · sound settings** |
| <img src="reference/sound-popup.png" width="480"> | <img src="reference/sound-settings.png" width="480"> |
| **Battery · Elemental Energy** | **Polkit · admin password** |
| <img src="reference/battery.png" width="480"> | <img src="reference/polkit.png" width="480"> |
| **Celestia file chooser** | **Wallpaper Gallery** |
| <img src="reference/file-chooser.png" width="480"> | <img src="reference/gallery.png" width="480"> |
| **Kamera screenshot suite** | **Clipboard Archive** |
| <img src="reference/kamera.png" width="480"> | <img src="reference/clipboard.png" width="480"> |
| **Boot** | **Login** |
| <img src="reference/boot.png" width="480"> | <img src="reference/login.png" width="480"> |
| **Lock screen** | **Quit Game** |
| <img src="reference/lock.png" width="480"> | <img src="reference/power.png" width="480"> |

</div>

<br>

---

<a id="spotlights"></a>
## ❖ Spotlights

The pieces that make Irminsul more than a wallpaper pack.

### 📶 Celestia — the Ley-Line Network Suite &nbsp;<sub>`v4 · Starfell`</sub>

A complete Wi-Fi experience that replaces `nm-applet` and every other network popup.

| | |
|:--|:--|
| 🖱️ **Left-click** the bar icon | **Mini Popup** — Paimon-style quick panel for fast connect / disconnect |
| 🖱️ **Right-click** the bar icon | **Akasha Terminal** — the full, Inventory-style network console |
| 🔐 **Enterprise-ready** | 802.1X and VPN profiles via the NetworkManager connection editor |
| 🎞️ **Smooth, cheap motion** | one shared timer, frame-region redraws and **auto-sleep** — animated but idle-friendly |
| 🎨 **Custom bar icons** | Genshin-style SVG glyphs for Wi-Fi / Ethernet / Off, in a pill that matches the battery |
| 🧹 **Clean-up tools** | dry-run-by-default scripts that remove every *other* network UI and tray applet |

*GTK3 · gtk-layer-shell · NetworkManager (`nmcli`)*

<br>

### 🔵 Teyvat Archive — the Bluetooth manager

A native, D-Bus-driven Bluetooth app. **Everything is live** — signals from BlueZ, no polling.

| Page | What lives there |
|:--|:--|
| 🧭 **Companions** | paired and nearby devices |
| 🗺️ **Ley Line Atlas** | discovery and scanning |
| 🎼 **Resonance** | audio-device awareness through PipeWire / Pulse |
| 📨 **Transmission** | file transfer over OBEX |
| 🗿 **Statue of the Seven** | power and adapter control |
| ⚙️ **Archive Settings** | preferences |

Plus the **Teyvat Ley Line Network** — a lightning-fast Rofi quick popup for when you just want to connect a device:

<kbd>Alt</kbd>+<kbd>1</kbd> Elemental Sight &nbsp;·&nbsp; <kbd>Alt</kbd>+<kbd>2</kbd> Power &nbsp;·&nbsp; <kbd>Alt</kbd>+<kbd>3</kbd> Open the Archive &nbsp;·&nbsp; <kbd>Alt</kbd>+<kbd>4</kbd> Refresh

*GTK3 · PyGObject · Cairo · BlueZ (`org.bluez`) · obexd · PipeWire/Pulse*

<br>

### 🔊 Irminsul Sound Console

Audio control with the weight of an in-game menu.

- 🎚️ **`irminsul-volume`** — a compact volume popup (press again to dismiss)
- 🏛️ **`irminsul-settings`** — the full settings window, **The Resonance Archive**
- 🎛️ **EQ · Mono · Clear Voice** — switchable audio effects
- 🤝 **Co-op Output** — play your system audio on **several devices at once** (two headphones, a speaker and a headset…), choose exactly which devices join, with **latency sync** to keep them together
- ♻️ **Everything is restored at login** — EQ, Mono, Co-op and Clear Voice come back after you sign in
- 🔈 Genshin-styled **volume / brightness HUD** that follows the media keys

<kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd> popup &nbsp;·&nbsp; <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> full settings

*PipeWire · WirePlumber · GTK3 · Cairo*

<br>

### 🔋 Elemental Energy — battery & charging

- ⚡ The **battery icon itself animates** while charging — SVG frame animation right in the bar
- 🖱️ Click it for a Genshin-styled panel: **Elemental Energy %**, **Charging** state, **Power flow**, **Until full**, **Vessel health**
- 🎚️ One-tap power profiles — **Power Saver · Balanced · Performance**
- 🔒 The same battery readout appears on the **lock screen**

<br>

### 🛡️ Polkit — the admin-password dialog

A real Polkit authentication agent, not a skin. Whenever `pkexec`, a package-manager GUI, a disk mount or NetworkManager asks for admin rights, you get a full-screen dimmed Genshin dialog.

- 🎭 Three looks — **Theme**, **Classic**, **Gold**
- 🌫️ Wayland-native overlay through gtk-layer-shell
- 🛟 Falls back gracefully to the system agent if yours isn't installed

<br>

### 🎨 Celestia — the global theme

One look for every app, not just the ones you themed by hand.

- 🪟 **GTK3 · GTK4 / libadwaita · Qt5 · Qt6** (qt5ct / qt6ct and KDE colors)
- 🗂️ **Genshin file-chooser dialog** for every Open / Save window
- 🧭 **Coloured sidebar icons** — round badges with an elemental colour, a golden rim and a dark glyph
- 🧿 **Icon pack** where every category has its own element:

| Element | Used for |
|:--|:--|
| 🍃 **Anemo** | browser · network · photos |
| ⚡ **Electro** | terminal |
| 🪨 **Geo** | files · calculator |
| 🌱 **Dendro** | code · system monitor |
| 💧 **Hydro** | chat · sound · Bluetooth |
| 🔥 **Pyro** | media · PDF |
| ❄️ **Cryo** | games · settings |

- ↩️ Fully reversible — every installer ships an `--undo` / `--uninstall`

<br>

### 📸 Kamera — the screenshot suite

| Shortcut | Result |
|:--|:--|
| <kbd>Super</kbd>+<kbd>P</kbd> | region capture |
| <kbd>Super</kbd>+<kbd>Ctrl</kbd>+<kbd>P</kbd> | **freeze the screen** and snip |
| <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd> | focused monitor |
| <kbd>Print</kbd> | all monitors |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | colour picker |

After every shot, a **post-shot Rofi menu** offers **Swappy** editing (with its own `GenshinSwappy` GTK3 theme), **OCR** in **English + Persian**, a **QR scanner**, copy and save.

<br>

### 🎨 Theme Builder v3 · Wallpapers · Ambience

- 🏗️ **Theme Builder (GTK3)** — create and manage themes, collections and accents
- 🖼️ **`swww` wallpaper engine** with a horizontal **Teyvat Wallpaper Gallery** in Rofi
- 🔁 Next / previous wallpaper in the active theme from the keyboard
- 🌈 **Dynamic Elemental Resonance** — the whole desktop's accent follows the wallpaper
- 🌙 **Ambience Menu** — Auto-Resonance, glass opacity, night light and HUD reload
- 🎯 Wallpaper hooks (`wallpaper-hooks.d/`) so your own scripts can react to a change

<br>

### 🌙 Atmosphere — boot, login, lock, power

| | |
|:--|:--|
| 🚀 **Boot** | A **1:1 Genshin loading screen** (Plymouth). The hardware clock picks **Day or Night** inside `initramfs`, so it is right from the first frame. |
| 🏰 **Login** | **SDDM Celestia** with four phases — **Dawn · Day · Dusk · Night**. |
| 🔒 **Lock** | **Hyprlock** with Genshin typography, a clock, battery and status widgets. |
| 🧚 **Power** | Paimon's **Quit Game?** dialogue — shutdown, reboot, logout and lock, reachable from the bar or <kbd>Super</kbd>+<kbd>Backspace</kbd> / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Del</kbd>. |

<br>

### 📊 The Bar

A capsule top bar that looks like the in-game HUD:

- 🔥 **7 Elemental Workspaces** — Pyro · Hydro · Anemo · Electro · Dendro · Cryo · Geo
- 🌙 **Resin · Mora · Ping** status capsules
- 🌍 **World Level (`AR`)** — your uptime, levelled up
- ☀️ **Day / Night** indicator and **mail** badge for your notification history
- 📶 Celestia Wi-Fi · 🔵 Bluetooth · 🔊 Sound · 🔋 Battery — all themed
- 🩹 **Auto-recovery** — `start.sh` brings the bar back, and calling it twice is harmless

<br>

### 💻 Terminal & the Traveler card

- 🐱 **Kitty** + **Zsh** with autosuggestions, syntax highlighting and **Starship**
- 🪪 **Fastfetch Traveler card** — a rotating character card built from **85+ Genshin characters**
  `avatar.sh --all` · `avatar.sh <name>` · `avatar.sh --list` · `avatar.sh --wall` *(card from your current wallpaper)*
- 🔔 **Dunst** notifications with circular elemental and Paimon medals
- 🖱️ **Official Genshin cursor** (size 32) locked across Hyprland, GTK3/4, XWayland and `dconf`, with a guard that puts it back if an app changes it
- 🔤 **Official fonts** (`SDK_SC_Web`, `HYWenHei-85W`) with system-wide fontconfig rules

<br>

---

<a id="modules"></a>
## 🧩 Modules

Seventeen independent modules — install all of them or pick only what you need.

### 🌐 Core

| | Module | What it does |
|:-:|:--|:--|
| 🧩 | **`hypr`** | Standalone **Hyprland Lua core**, **Theme Builder v3**, `swww` wallpaper engine, dynamic Elemental Resonance, cursor guard |
| 🔌 | **`wiring`** | Entry-point loader (`~/.config/hypr/hyprland.lua`) |
| 🔤 | **`fonts`** | Official fonts with system-wide fontconfig rules |
| 🖱️ | **`cursor`** | Official cursor, locked across every toolkit |

### 🪟 Shell

| | Module | What it does |
|:-:|:--|:--|
| 📊 | **`waybar`** | Capsule top bar, **Celestia Wi-Fi v4**, animated battery, custom SVG icons, tray & Wi-Fi clean-up tools |
| 🚀 | **`rofi`** | Paimon launcher, **Wallpaper Gallery**, clipboard archive, window switcher, file finder |
| 📸 | **`osd`** | **Kamera** screenshot suite plus volume / brightness HUD |
| 🔔 | **`notif`** | **Dunst** with elemental and Paimon medals |
| 💻 | **`terminal`** | Kitty · Fastfetch Traveler cards · Zsh + Starship |

### 📡 Connectivity & System

| | Module | What it does |
|:-:|:--|:--|
| 🔵 | **`bluetooth`** | **Teyvat Archive** (GTK3 D-Bus manager) and the **Ley Line Network** quick popup |
| 🔊 | **`audio`** | **Irminsul Sound Console** — volume popup, Resonance Archive settings, EQ, Mono, Clear Voice, **Co-op output** |
| 🛡️ | **`polkit`** | Genshin admin-password dialog — Theme / Classic / Gold |
| 🎨 | **`celestia-icons`** | **Celestia** icon theme, file-chooser dialog, sidebar icons, GTK/Qt global theme |

### 🌙 Atmosphere

| | Module | What it does |
|:-:|:--|:--|
| ⏳ | **`boot`** | 1:1 Genshin loading screen with automatic hardware-clock Day / Night sync |
| 🏰 | **`login`** | **SDDM Celestia** with four time-of-day phases |
| 🔒 | **`lock`** | **Hyprlock** with Genshin typography and status widgets |
| 🧚 | **`power`** | Paimon *Quit Game* / power dialogue |

<details>
<summary><b>🗺️ How the pieces fit together</b></summary>
<br>

```mermaid
flowchart TB
    I["install.sh<br/>dry run by default"] --> CORE & SHELL & CONN & ATMO

    subgraph CORE["🌐 Core"]
        hypr --- wiring --- fonts --- cursor
    end
    subgraph SHELL["🪟 Shell"]
        waybar --- rofi --- osd --- notif --- terminal
    end
    subgraph CONN["📡 Connectivity & System"]
        bluetooth --- audio --- polkit --- celestia-icons
    end
    subgraph ATMO["🌙 Atmosphere"]
        boot --- login --- lock --- power
    end

    style CORE stroke:#f5c542,stroke-width:2px
    style SHELL stroke:#4cc2f1,stroke-width:2px
    style CONN stroke:#74c2a8,stroke-width:2px
    style ATMO stroke:#9b7dff,stroke-width:2px
```

</details>

<br>

---

<a id="installation"></a>
## 🚀 Installation

> [!NOTE]
> `install.sh` is a **dry run by default**. Nothing on your system changes until you pass `--apply`.

```bash
git clone https://github.com/R0nov4/irminsul.git
cd irminsul
```

**1 · Preview** what will change

```bash
./install.sh
```

**2 · Install everything** — packages, user configs, SDDM and the Plymouth boot screen

```bash
./install.sh --deps --apply --system --boot
```

**3 · Check** that everything is healthy

```bash
./doctor.sh
```

<details>
<summary><b>Installer flags</b></summary>
<br>

| Flag | Effect |
|:--|:--|
| *(none)* | Dry run, preview only |
| `--deps` | Install required packages |
| `--apply` | Apply user configs |
| `--system` | Install system-level parts (SDDM) |
| `--boot` | Install the Plymouth boot screen |
| `--only a,b,c` | Limit the install to the listed modules |

</details>

<details>
<summary><b>Install only some modules</b></summary>
<br>

```bash
# just the shell
./install.sh --apply --only hypr,waybar,rofi,osd

# just the connectivity apps
./install.sh --apply --only waybar,bluetooth,audio
```

</details>

<details>
<summary><b>Single-file standalone installers</b></summary>
<br>

Every module is also built as a self-extracting script in `dist/`. Each one works on its own:

```bash
./dist/genshin-all.sh --deps --apply --system --boot     # everything
./dist/genshin-bluetooth.sh --apply                       # just Bluetooth
./dist/genshin-audio.sh --apply                           # just the sound console
./dist/genshin-polkit.sh --apply                          # just the Polkit dialog
./dist/genshin-celestia-icons.sh --apply                  # just the icon theme
```

</details>

<br>

---

<a id="keybindings"></a>
## ⌨️ Keybindings

<sub><kbd>Super</kbd> is the Windows / Meta key.</sub>

### 🔥 Elemental Workspaces

<kbd>Super</kbd> + <kbd>1</kbd> … <kbd>7</kbd>

| 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 🔥 Pyro | 💧 Hydro | 🍃 Anemo | ⚡ Electro | 🌱 Dendro | ❄️ Cryo | 🪨 Geo |

<details open>
<summary><b>🚀 Apps & Windows</b></summary>
<br>

| Shortcut | Action |
|:--|:--|
| <kbd>Super</kbd> + <kbd>T</kbd> | Terminal (`kitty`) |
| <kbd>Super</kbd> + <kbd>E</kbd> | File manager (`dolphin`) |
| <kbd>Super</kbd> + <kbd>B</kbd> | Web browser |
| <kbd>Super</kbd> + <kbd>C</kbd> | Code editor |
| <kbd>Super</kbd> + <kbd>A</kbd> | **Paimon Application Launcher** (Rofi) |
| <kbd>Super</kbd> + <kbd>Tab</kbd> | Window switcher |
| <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>E</kbd> | File finder |
| <kbd>Super</kbd> + <kbd>Q</kbd> / <kbd>Alt</kbd> + <kbd>F4</kbd> | Close active window |
| <kbd>Super</kbd> + <kbd>F</kbd> | Toggle maximize |
| <kbd>Shift</kbd> + <kbd>F11</kbd> | Cycle fullscreen |
| <kbd>Super</kbd> + <kbd>W</kbd> | Toggle floating |

</details>

<details open>
<summary><b>🎨 Themes & Wallpapers</b></summary>
<br>

| Shortcut | Action |
|:--|:--|
| <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>T</kbd> | **Genshin Theme Builder v3** — theme, collection and accent manager |
| <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>W</kbd> | **Teyvat Wallpaper Gallery** — horizontal Rofi preview |
| <kbd>Super</kbd> + <kbd>Alt</kbd> + <kbd>→</kbd> / <kbd>←</kbd> | Next / previous wallpaper in the active theme |
| <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>R</kbd> | **Teyvat Ambience Menu** — Auto-Resonance, glass opacity, night light, HUD reload |

</details>

<details open>
<summary><b>🔊 Sound</b></summary>
<br>

| Shortcut | Action |
|:--|:--|
| <kbd>Super</kbd> + <kbd>Alt</kbd> + <kbd>A</kbd> | **Irminsul volume** popup (press again to close) |
| <kbd>Super</kbd> + <kbd>Alt</kbd> + <kbd>Shift</kbd> + <kbd>A</kbd> | **The Resonance Archive** — full sound settings |
| <kbd>F10</kbd> / <kbd>F11</kbd> / <kbd>F12</kbd> and media keys | Mute · volume down · volume up, with the Genshin HUD |

</details>

<details open>
<summary><b>📸 Clipboard & Screenshots</b></summary>
<br>

| Shortcut | Action |
|:--|:--|
| <kbd>Super</kbd> + <kbd>V</kbd> | **Clipboard Archive** — history (`cliphist`) |
| <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd> | Clear / manage clipboard history |
| <kbd>Print</kbd> / <kbd>Super</kbd> + <kbd>P</kbd> | **Kamera** — all monitors / region ➔ Swappy · OCR · QR · Save |
| <kbd>Super</kbd> + <kbd>Ctrl</kbd> + <kbd>P</kbd> | Freeze the screen and snip |
| <kbd>Super</kbd> + <kbd>Alt</kbd> + <kbd>P</kbd> | Screenshot the focused monitor |
| <kbd>Super</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd> | Colour picker (`hyprpicker`) |

</details>

<details open>
<summary><b>⚙️ System</b></summary>
<br>

| Shortcut | Action |
|:--|:--|
| <kbd>Super</kbd> + <kbd>L</kbd> | Lock screen (`hyprlock`) |
| <kbd>Super</kbd> + <kbd>BackSpace</kbd> / <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>Del</kbd> | **Quit Game** / power menu |
| <kbd>Super</kbd> + <kbd>K</kbd> | Switch keyboard layout (set yours in `~/.config/hypr-genshin/keyboard.conf`) |

</details>

<br>

---

<a id="maintenance"></a>
## 🛠 Maintenance

```bash
./capture.sh      # capture live system configs into modules/ (converts $HOME to @HOME@)
./build-dist.sh   # build self-extracting installers into dist/
./doctor.sh       # run full diagnostics
```

> [!TIP]
> Tweaked something on your machine? Run `./capture.sh` and commit — paths are stored as `@HOME@`, so the configs stay portable.

<details>
<summary><b>🧹 Extra tools</b></summary>
<br>

All of them are **generic** and **dry-run by default** — they read what is really on your system instead of assuming a setup.

| Tool | What it does |
|:--|:--|
| `tools/genshin-tray-doctor.py` | Lists every system-tray icon, finds who starts it, and removes the unwanted ones (Wi-Fi applets by default) |
| `tools/genshin-wifi-cleanup.sh` | Removes every *other* Wi-Fi / network UI so only Celestia remains — everything is backed up first |
| `tools/genshin-wifi-icon.sh` | Swaps the plain font glyph of the bar's network module for Genshin SVG icons — safe to re-run |

```bash
python3 tools/genshin-tray-doctor.py            # preview
python3 tools/genshin-tray-doctor.py --apply    # do it
bash tools/genshin-wifi-cleanup.sh --apply
```

</details>

<details>
<summary><b>↩️ Reverting</b></summary>
<br>

- Back up your previous Hyprland config? Restore it with `genshin-hypr-standalone.sh deactivate`
- Icon theme and file chooser: run the module installer with `--undo`
- Global Celestia theme: run `celestia-theme-installer.sh --uninstall`
- Tools back up whatever they change (`*.bak-*`) before touching it

</details>

<br>

## ❖ Repository Layout

```text
irminsul/
├── install.sh                  ✦ installer (dry run by default)
├── doctor.sh                   ✦ diagnostics
├── build-dist.sh               ✦ builds the self-extracting installers
├── dist/                       ✦ build output: genshin-all.sh + one script per module (18)
├── tools/                      ✦ tray doctor · Wi-Fi clean-up · Wi-Fi bar icon
├── shell/                      ✦ zshrc
├── reference/                  ✦ screenshots, package lists, old installers, system notes
└── modules/                    ✦ 17 modules, each laid out like the target filesystem
    │
    ├── hypr/                   home/.config/hypr-genshin/ — Lua core (standalone/), Theme Builder,
    │                           wallpaper engine + wallpaper-hooks.d/, cursor guard, Ambience menu
    ├── wiring/                 home/.config/hypr/hyprland.lua — entry-point loader
    ├── fonts/                  Genshin-UI.ttf + fontconfig alias rules
    ├── cursor/                 Genshin-Official Xcursor theme, GTK 2/3/4, xsettingsd, uwsm env
    │
    ├── waybar/                 waybar-genshin/ — config, styles, scripts/ (Wi-Fi, battery, mail, AR, ping),
    │                           assets/ (elements, bat/, bat-ios/, bluetooth/, wifi/)
    ├── rofi/                   rofi-genshin/ — launcher, clipboard, wallpaper gallery, shot menu
    ├── osd/                    osd-genshin/ — Kamera screenshot suite, volume / brightness HUD,
    │                           GenshinSwappy GTK3 theme
    ├── notif/                  dunst-genshin/ — dunstrc, elemental + Paimon medal icons
    ├── terminal/               kitty-genshin, fastfetch-genshin (avatars/ + cards/), Zsh bits
    │
    ├── bluetooth/              Teyvat Archive (teyvat_archive.py) + desktop entry + quick popup
    ├── audio/                  irminsul-volume · irminsul-settings · pavucontrol shim
    ├── polkit/                 agent.py, launcher, autostart (system agent masked)
    ├── celestia-icons/         install.sh + scripts/ (icon pack, dialogs, sidebar icons, theme installer)
    │
    ├── boot/                   root/ — Plymouth themes (genshin, genshin-loading day/night frames),
    │                           genshin-daynight service + initcpio hook, early-KMS config
    ├── login/                  root/ — SDDM themes (Genshin, genshin-celestia) + sddm.conf.d
    ├── lock/                   home/.config/hyprlock-genshin/ — template, backgrounds, battery widget
    └── power/                  home/.config/power-genshin/ — Quit Game dialogue (launch.sh, theme.rasi, icons)
```

<sub>Inside a module, `home/` is copied into `$HOME` and `root/` into `/` (needs `--system` or `--boot`). `celestia-icons` ships its own installer instead.</sub>

<br>

---

## ⚠️ Known limitations

- **Boot day/night phase** assumes UTC. Set your offset in seconds in `/etc/genshin-daynight.conf` (`GS_UTC_OFFSET=`, e.g. `3600` for UTC+1) and rebuild the initramfs with `sudo mkinitcpio -P`.
- **Early KMS** is set up for `amdgpu` and `i915`. NVIDIA users should edit `/etc/mkinitcpio.conf.d/genshin-kms.conf`.

## ✦ Credits

Genshin Impact, its characters, artwork, fonts and cursor are © **HoYoverse / COGNOSPHERE**. This is an unofficial, non-commercial fan project and is not affiliated with or endorsed by HoYoverse. All game assets belong to their respective owners.

## ⚖️ Disclaimer

**Irminsul is an unofficial, fan-made, non-commercial project.** It is not affiliated with, authorized, sponsored or endorsed by HoYoverse, COGNOSPHERE, miHoYo or any of their subsidiaries or affiliates. Nothing here should be read as an official product, collaboration or partnership.

- **Ownership.** Genshin Impact and everything derived from it, including names, characters, logos, artwork, music, fonts, cursors and related marks, belongs to its respective owners. The author claims no ownership over that material and does not seek to register any copyright, trademark or other right over it.
- **Third-party work.** Wallpapers, fonts, icons and other artwork made by third parties remain the property of their authors and are subject to their own terms. Full credit goes to the original creators.
- **Scope of the license.** The original code, scripts and configuration written by the author are licensed under the [GNU GPL v3.0](LICENSE). That license does not extend to game-derived or third-party material, which is not the author's to license and stays under its owners' terms.
- **Fan content is for personal, non-commercial use.** Game-derived and third-party material included here is shared free of charge for personal, non-commercial use only. Do not sell it or include it in paid products or services.
- **No warranty.** This project installs system-level components (boot splash, login manager, lock screen, polkit agent, initramfs hooks). It is provided *as is*, without warranty of any kind, and the author is not liable for data loss, broken boots, lockouts or any other damage. Run the installer in dry-run mode first, back up your system, and know how to recover from a TTY.

> **Takedown requests.** If you are a rights holder and believe something here infringes your rights, please open an issue titled "Takedown request" listing the affected files. The maintainer will remove them promptly and in good faith.

<br>

<div align="center">

✦ &nbsp; *Made for travelers, by a traveler.* &nbsp; ✦

<sub>If you like it, a ⭐ makes Paimon happy.</sub>

<img src="https://capsule-render.vercel.app/api?type=waving&height=140&color=0:f5c542,55:3b2f6b,100:0d0b1e&section=footer&reversal=true" alt="" width="100%">

</div>
