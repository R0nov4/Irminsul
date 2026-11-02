#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ✦ genshin-bluetooth — Teyvat Ley Line Network (quick rofi popup) ✦  ║
# ╚══════════════════════════════════════════════════════════════════════╝
# Needs : bluez, bluez-utils (bluetoothctl), rofi ≥ 1.7 (or rofi-wayland)
# Opt.  : libnotify (notify-send), rfkill, pkexec, busctl, teyvat-archive (advanced GTK app)
# Keys  : Alt+1 Elemental Sight · Alt+2 Power · Alt+3 open the Archive · Alt+4 Refresh
# Env   : GENSHIN_BT_SCAN=25  GENSHIN_BT_NAMELESS=0  GENSHIN_BT_LOW=20  GENSHIN_BT_LINES=12
# Debug : genshin-bluetooth --classify "NAME" [ICON] [CLASS] [APPEARANCE]   → which form it gets
VERSION=1.2.3

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/genshin-bluetooth"
ICONS="$CACHE/icons-v2"
RUN="${XDG_RUNTIME_DIR:-/tmp}/genshin-bluetooth-$UID"
THEME="$RUN/theme.rasi"
SCAN_PID="$RUN/scan.pid"; SCAN_T0="$RUN/scan.t0"
SCAN_SECONDS="${GENSHIN_BT_SCAN:-25}"
SHOW_NAMELESS="${GENSHIN_BT_NAMELESS:-0}"
LOW_BATTERY="${GENSHIN_BT_LOW:-20}"
MAX_ROWS="${GENSHIN_BT_LINES:-12}"
SELF_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ARCHIVE_CONF="${XDG_CONFIG_HOME:-$HOME/.config}/genshin-bluetooth/archive.json"
mkdir -p "$RUN" "$CACHE"

KINDS_ALL="headphones earbuds headset speaker soundbar tv car microphone mouse keyboard gamepad console vr
           phone computer watch tablet camera printer remote pen health tag light generic"
declare -A ELEM=( [headphones]=Hydro [earbuds]=Hydro [headset]=Hydro [speaker]=Pyro [soundbar]=Pyro
                  [tv]=Electro [car]=Geo [microphone]=Hydro [mouse]=Anemo [keyboard]=Geo [gamepad]=Pyro
                  [console]=Electro [vr]=Electro [phone]=Electro [computer]=Cryo [watch]=Dendro [tablet]=Cryo
                  [camera]=Cryo [printer]=Geo [remote]=Anemo [pen]=Dendro [health]=Dendro [tag]=Anemo
                  [light]=Geo [generic]=Anemo )
declare -A LABEL=( [headphones]="Headphones" [earbuds]="Earbuds" [headset]="Headset" [speaker]="Speaker"
                   [soundbar]="Soundbar" [tv]="Television" [car]="Car Audio" [microphone]="Microphone"
                   [mouse]="Mouse" [keyboard]="Keyboard" [gamepad]="Controller" [console]="Game Console"
                   [vr]="VR Headset" [phone]="Phone" [computer]="Computer" [watch]="Wearable" [tablet]="Tablet"
                   [camera]="Camera" [printer]="Printer" [remote]="Remote" [pen]="Stylus"
                   [health]="Health Sensor" [tag]="Tracker Tag" [light]="Smart Light" [generic]="Wanderer" )
declare -A STARS=( [headphones]=5 [earbuds]=5 [speaker]=5 [soundbar]=5 [tv]=5 [car]=5 [gamepad]=5
                   [console]=5 [vr]=5 [printer]=3 [remote]=3 [pen]=3 [tag]=3 [light]=3 [generic]=3 )
declare -A ECOL=( [Hydro]="#4CC2F1" [Pyro]="#EF7A35" [Anemo]="#5CD8B8" [Geo]="#F2B723"
                  [Electro]="#B98CFF" [Cryo]="#9FD6E3" [Dendro]="#A5C83B" )

# ───────────────────────────────────────────── icons (generated once, SVG) ──
glyph() { local c="$2"
  case "$1" in
    headphones) echo "<path d='M18 37v-5a14 14 0 0 1 28 0v5'/><rect x='14' y='34' width='8' height='13' rx='3.5' fill='$c'/><rect x='42' y='34' width='8' height='13' rx='3.5' fill='$c'/>";;
    headset)    echo "<path d='M18 37v-5a14 14 0 0 1 28 0v5'/><rect x='14' y='34' width='8' height='13' rx='3.5' fill='$c'/><rect x='42' y='34' width='8' height='13' rx='3.5' fill='$c'/><path d='M18 47q1 5 9 5'/><circle cx='28' cy='52' r='1.8' fill='$c'/>";;
    earbuds)    echo "<circle cx='24' cy='27' r='6.5' fill='$c' fill-opacity='.35'/><path d='M25.5 33v11'/><circle cx='40' cy='27' r='6.5' fill='$c' fill-opacity='.35'/><path d='M38.5 33v11'/>";;
    speaker)    echo "<rect x='21' y='14' width='22' height='36' rx='5'/><circle cx='32' cy='38' r='6.5'/><circle cx='32' cy='23' r='2.5' fill='$c'/>";;
    soundbar)   echo "<rect x='9' y='27' width='46' height='12' rx='5'/><circle cx='19' cy='33' r='2.3' fill='$c'/><circle cx='28' cy='33' r='2.3' fill='$c'/><circle cx='36' cy='33' r='2.3' fill='$c'/><circle cx='45' cy='33' r='2.3' fill='$c'/><path d='M24 20q8-5 16 0' stroke-opacity='.7'/>";;
    tv)         echo "<rect x='13' y='16' width='38' height='26' rx='3'/><path d='M26 49h12M32 42v7'/><path d='M18 37q5-7 9-3t8-2 11 3' stroke-width='1.8'/><circle cx='39' cy='24' r='2.4' fill='$c'/>";;
    car)        echo "<path d='M12 40v-6q0-3 3-4l4-1 5-7q1.5-2 4-2h9q2.5 0 4 2l5 7 4 1q3 1 3 4v6z'/><path d='M24 29h17' stroke-width='1.6'/><circle cx='21' cy='41' r='3.6' fill='$c'/><circle cx='43' cy='41' r='3.6' fill='$c'/>";;
    microphone) echo "<rect x='26' y='11' width='12' height='23' rx='6'/><path d='M20 29a12 12 0 0 0 24 0M32 41v8M25 50h14'/>";;
    mouse)      echo "<rect x='23' y='14' width='18' height='36' rx='9'/><path d='M32 14v11'/><path d='M32 19v3' stroke='#ECE5D8'/>";;
    keyboard)   echo "<rect x='12' y='22' width='40' height='22' rx='4'/><path d='M18 29h2M24 29h2M30 29h2M36 29h2M42 29h2M21 34h2M27 34h2M33 34h2M39 34h2M24 39h16'/>";;
    gamepad)    echo "<path d='M22 24h20q9 0 10 10l1 7q0 5-5 5q-3 0-5-4l-2-3H23l-2 3q-2 4-5 4q-5 0-5-5l1-7q1-10 10-10z'/><path d='M19 33h7M22.5 29.5v7'/><circle cx='41' cy='30.5' r='1.6' fill='$c'/><circle cx='45' cy='34.5' r='1.6' fill='$c'/>";;
    console)    echo "<rect x='10' y='22' width='44' height='21' rx='7'/><rect x='21' y='26' width='22' height='13' rx='1.5' fill='$c' fill-opacity='.3'/><circle cx='15.5' cy='29' r='1.6' fill='$c'/><circle cx='48.5' cy='36' r='1.6' fill='$c'/>";;
    vr)         echo "<path d='M12 25h40v12q0 5-5 5h-9l-3-5h-6l-3 5h-9q-5 0-5-5z'/><circle cx='23' cy='32' r='3' fill='$c'/><circle cx='41' cy='32' r='3' fill='$c'/>";;
    phone)      echo "<rect x='23' y='12' width='18' height='40' rx='4'/><path d='M29 16h6'/><path d='M32 26l1.6 4.4L38 32l-4.4 1.6L32 38l-1.6-4.4L26 32l4.4-1.6z' fill='$c' stroke='none'/>";;
    computer)   echo "<rect x='16' y='17' width='32' height='22' rx='2'/><path d='M11 45h42l-3-4H14z'/><path d='M21 24h12M21 29h18M21 34h8' stroke-width='1.8'/>";;
    watch)      echo "<circle cx='32' cy='32' r='10'/><path d='M27 22.5l1-7.5h8l1 7.5M27 41.5l1 7.5h8l1-7.5M32 27v5l3.5 2'/>";;
    tablet)     echo "<rect x='18' y='13' width='28' height='38' rx='4'/><path d='M23 36q4-10 8-2t9-4'/>";;
    camera)     echo "<path d='M13 24h9l3-5h14l3 5h9v22H13z'/><circle cx='32' cy='35' r='7'/><circle cx='32' cy='35' r='2.4' fill='$c'/>";;
    printer)    echo "<path d='M22 26V15h20v11'/><rect x='13' y='26' width='38' height='15' rx='3'/><path d='M22 36h20v13H22z'/><path d='M26 41h12M26 45h8' stroke-width='1.6'/>";;
    remote)     echo "<rect x='25' y='11' width='14' height='42' rx='6'/><circle cx='32' cy='19' r='2.4' fill='$c'/><circle cx='32' cy='29' r='4'/><path d='M29 39h6M29 44h6' stroke-width='1.8'/>";;
    pen)        echo "<path d='M42 14l8 8-21 21-10 3 3-10z'/><path d='M38 18l8 8'/><path d='M14 52q6-4 12-1' stroke-width='1.8'/>";;
    health)     echo "<path d='M32 48q-17-10-17-22a8.5 8.5 0 0 1 17-4a8.5 8.5 0 0 1 17 4q0 12-17 22z'/><path d='M19 33h7l3-6 4 11 3-5h9' stroke-width='1.8'/>";;
    tag)        echo "<circle cx='32' cy='36' r='12'/><circle cx='32' cy='36' r='3.5' fill='$c'/><path d='M24 19q8-6 16 0M27.5 23.5q4.5-3 9 0'/>";;
    light)      echo "<path d='M27 40q0-4-3-7.5a11 11 0 1 1 16 0q-3 3.5-3 7.5z'/><path d='M27 45h10M28.5 49.5h7'/><path d='M32 9v3M17 15l2 2M47 15l-2 2' stroke-opacity='.7'/>";;
    generic|pact) echo "<path d='M32 13l3.6 15.4L51 32l-15.4 3.6L32 51l-3.6-15.4L13 32l15.4-3.6z' fill='$c' fill-opacity='.35'/>";;
    power-on|power-off) echo "<path d='M32 16v13'/><path d='M23.5 21.5a13 13 0 1 0 17 0'/>";;
    sight)      echo "<path d='M12 32q20-19 40 0q-20 19-40 0z'/><circle cx='32' cy='32' r='5.5' fill='$c'/>";;
    sight-on)   echo "<path d='M12 32q20-19 40 0q-20 19-40 0z'/><circle cx='32' cy='32' r='5.5' fill='$c'/><path d='M32 11v4M18 15l2.5 3M46 15l-2.5 3M32 49v4'/>";;
    archive)    echo "<path d='M16 19h12q4 0 4 4v24q0-3-4-3H16z'/><path d='M48 19H36q-4 0-4 4v24q0-3 4-3h12z'/>";;
    statue)     echo "<path d='M32 12l4 8h-8z' fill='$c'/><circle cx='32' cy='27' r='5.5'/><path d='M21 51h22M25 51l2.5-15h9L39 51'/>";;
    wind)       echo "<path d='M14 27h20a5 5 0 1 0-5-5'/><path d='M14 34h27a5 5 0 1 1-5 5'/><path d='M14 41h11'/>";;
    back)       echo "<path d='M37 20L25 32l12 12'/>";;
    link)       echo "<path d='M27 37l10-10'/><path d='M24 31l-3 3a6.5 6.5 0 0 0 9 9l3-3'/><path d='M40 33l3-3a6.5 6.5 0 0 0-9-9l-3 3'/>";;
    unlink)     echo "<path d='M24 31l-3 3a6.5 6.5 0 0 0 9 9l3-3'/><path d='M40 33l3-3a6.5 6.5 0 0 0-9-9l-3 3'/><path d='M22 22l-3-3M45 45l-3-3M27 18v-3M37 46v3'/>";;
    trust)      echo "<path d='M32 13l13 5v10q0 13-13 19q-13-6-13-19V18z'/><path d='M26 30l4.5 4.5L39 26'/>";;
    untrust)    echo "<path d='M32 13l13 5v10q0 13-13 19q-13-6-13-19V18z'/><path d='M27 25l10 10M37 25L27 35'/>";;
    block)      echo "<circle cx='32' cy='32' r='13'/><path d='M23 41l18-18'/>";;
    unblock)    echo "<circle cx='32' cy='32' r='13'/><path d='M26 32l4.5 4.5L39 28'/>";;
    rename)     echo "<path d='M20 44l3-9 16-16 6 6-16 16z'/><path d='M36 22l6 6'/>";;
    forget)     echo "<path d='M23 23l18 18M41 23L23 41'/>";;
    info)       echo "<circle cx='32' cy='21' r='2' fill='$c'/><path d='M32 28v15'/>";;
    refresh)    echo "<path d='M44 28a13 13 0 1 0 1 9'/><path d='M45 17v11H34'/>";;
    adapter)    echo "<path d='M24 24l16 16-8 7V17l8 7-16 16'/>";;
  esac
}
write_svg() { # file color inner opacity
  cat >"$1" <<EOF
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<defs><radialGradient id='g'><stop offset='0' stop-color='$2' stop-opacity='.42'/><stop offset='.72' stop-color='#232839' stop-opacity='.96'/><stop offset='1' stop-color='#1B1F2E'/></radialGradient></defs>
<circle cx='32' cy='32' r='28.5' fill='url(#g)' stroke='#D3BC8E' stroke-width='1.5'/>
<circle cx='32' cy='32' r='25' fill='none' stroke='#D3BC8E' stroke-opacity='.4' stroke-width='.8' stroke-dasharray='1 2.6'/>
<g fill='#D3BC8E'><path d='M32 .8l2.2 2.7L32 6.2l-2.2-2.7z'/><path d='M32 57.8l2.2 2.7L32 63.2l-2.2-2.7z'/><path d='M.8 32l2.7-2.2L6.2 32l-2.7 2.2z'/><path d='M57.8 32l2.7-2.2 2.7 2.2-2.7 2.2z'/></g>
<g fill='none' stroke='$2' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round' opacity='$4'>$3</g>
</svg>
EOF
}
gen_icons() {
  [[ -f "$ICONS/.done" ]] && return
  mkdir -p "$ICONS"
  local k c u
  for k in $KINDS_ALL; do
    c="${ECOL[${ELEM[$k]}]}"
    write_svg "$ICONS/$k.svg" "$c" "$(glyph "$k" "$c")" 1
    write_svg "$ICONS/$k-dim.svg" "#8E95A8" "$(glyph "$k" "#8E95A8")" .75
  done
  for u in power-on sight archive statue wind back link pact trust untrust block unblock rename info refresh adapter; do
    write_svg "$ICONS/$u.svg" "#D3BC8E" "$(glyph "$u" "#D3BC8E")" 1
  done
  write_svg "$ICONS/power-off.svg" "#EF7A35" "$(glyph power-off "#EF7A35")" 1
  write_svg "$ICONS/sight-on.svg" "#5CD8B8" "$(glyph sight-on "#5CD8B8")" 1
  write_svg "$ICONS/unlink.svg" "#EF7A35" "$(glyph unlink "#EF7A35")" 1
  write_svg "$ICONS/forget.svg" "#EF7A35" "$(glyph forget "#EF7A35")" 1
  touch "$ICONS/.done"
}

# ───────────────────────────────────────────────────────────── rofi theme ──
write_theme() { cat > "$THEME" <<'EOF'
* {
    fg:      #ECE5D8;
    dim:     #9AA3B8;
    gold:    #D3BC8E;
    sel-fg:  #2B3047;
    font:    "HYWenHei-85W, Noto Serif 11";
    background-color: transparent;
    text-color: @fg;
}
window {
    width: 600px;
    location: northeast; anchor: northeast;
    x-offset: -12px; y-offset: 46px;
    background-image: linear-gradient(to bottom, #1A1E2CF7, #2B3150F7);
    border: 2px; border-color: @gold; border-radius: 18px;
}
mainbox  { children: [ message, inputbar, listview ]; padding: 14px; spacing: 10px; }
message  { padding: 6px 10px 12px 10px; border: 0 0 1px 0; border-color: #D3BC8E66; }
textbox  { horizontal-align: 0.5; markup: true; }
inputbar { children: [ prompt, entry ]; padding: 8px 16px; spacing: 10px;
           border: 1px; border-radius: 999px; border-color: #D3BC8E55; background-color: #11141FCC; }
prompt   { text-color: @gold; }
entry    { placeholder: "Search the Ley Lines…"; placeholder-color: #8E95A8; cursor-color: @gold; }
listview { lines: 12; dynamic: true; scrollbar: false; spacing: 5px; fixed-height: false; cycle: true; }
element  { padding: 6px 12px; spacing: 14px; border: 1px; border-radius: 14px;
           border-color: #D3BC8E22; background-color: #3B425555; children: [ element-icon, element-text ]; }
element normal.active, element alternate.active {
           border-color: @gold; background-image: linear-gradient(to right, #D3BC8E30, #3B425555); }
element normal.urgent, element alternate.urgent { border-color: #EF7A35; }
element selected.normal, element selected.active, element selected.urgent {
           background-image: linear-gradient(to right, #F3ECDF, #D3BC8E); text-color: @sel-fg; border-color: #FFF3D6; }
element-icon { size: 38px; vertical-align: 0.5; }
element-text { text-color: inherit; vertical-align: 0.5; markup: true; }
EOF
}

# ──────────────────────────────────────────────────────────────── helpers ──
note() { command -v notify-send >/dev/null && notify-send -a "Teyvat · Ley Lines" -i "${3:-bluetooth}" "$1" "${2:-}"; }
esc()  { local s="${1//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"; s="${s//|/¦}"; printf '%s' "$s"; }
bar()  { local n=$(( ($1 + 10) / 20 )) s="" i; for ((i=0;i<5;i++)); do ((i<n)) && s+="▰" || s+="▱"; done; printf '%s' "$s"; }
ley()  { local r=$1 n w s="" i
         if   ((r >= -55)); then n=5 w=Resonant; elif ((r >= -65)); then n=4 w=Strong
         elif ((r >= -75)); then n=3 w=Steady;   elif ((r >= -85)); then n=2 w=Faint
         else n=1 w=Fading; fi
         for ((i=0;i<5;i++)); do ((i<n)) && s+="◆" || s+="◇"; done; printf '%s %s' "$s" "$w"; }
stars() { local n=${STARS[$1]:-4} s="" i; for ((i=0;i<n;i++)); do s+="★"; done; printf '%s' "$s"; }

# ─────────────────────────────────────────────────────── companion forms ──
# Same order and the very same "kind|regex" hints as teyvat_archive.py:
#   strong name hints → Class of Device → BLE Appearance → weak (brand) hints → BlueZ icon.
RX_STRONG=(
  'headphones|airpods max'
  'earbuds|airpods|buds|earbud|earphone|earpods| wf [0-9c]| tws |freebuds|pods |elite [0-9]| liberty'
  'remote| remote| rcu? |clicker|presenter|selfie|shutter| spotlight '
  'pen|stylus|pencil| s ?pen | pen |wacom'
  'gamepad|dualsense|dualshock|controller|gamepad|joy ?con|8bitdo|stadia|xbox wireless|xbox elite'
  'console|steam ?deck|nintendo switch|playstation| ps[345] |rog ally|legion go|xbox (series|one)'
  'vr|oculus|meta quest| quest [0-9p]| vive | pico [0-9]|valve index| vr |xreal|nreal|viture|rokid|vision pro'
  'health|heart ?rate| hrm|polar h[0-9]|tickr|wahoo| scale |thermometer|blood pressure|oximeter|glucose|omron|cadence|speed sensor| oura | whoop '
  'watch|watch| band |amazfit|garmin|fitbit'
  'tag|airtag| tile |smart ?tag|chipolo|pebblebee| nut |find my'
  'keyboard|keyboard|keychron|mx keys| k[0-9]{3} '
  'mouse|mouse|mx master|mx anywhere|mx ergo|trackball|trackpad'
  'soundbar|sound ?bar|playbar|sonos (beam|arc|ray)|jbl bar| hw [a-z][0-9]| ht [a-z]| sb[0-9]{2}| yas [0-9]| signa s|magnifi|tv speaker|home ?theat'
  'tv| tv |television|bravia|webos|android ?tv|google ?tv|fire ?tv| roku |chromecast| qled | oled |vidaa| mi ?tv|mitv| mi box|shield tv|smart ?tv|tizen'
  'car| car |car ?kit|car ?audio|car ?multimedia|carplay|android auto|uconnect| my ?car |toyota|honda|nissan|mazda| mzd |hyundai| kia | ford | sync |chevrolet| chevy | bmw | audi |mercedes| mb bluetooth|volkswagen| vw |skoda|peugeot|renault|citroen|tesla|subaru|lexus|volvo| jeep |porsche|kenwood|head ?unit|car stereo| mmi |entune|mylink| dacia | fiat | opel |suzuki|mitsubishi|geely|chery| byd |haval| xav '
  'microphone| mic |microphone| rode |wireless go|hollyland| lark | boya |shure'
  'camera|camera| cam |gopro| hero ?[0-9]|insta360| dji |osmo| ilce |canon eos| eos |nikon|fujifilm|lumix|ricoh|webcam'
  'printer|printer|deskjet|officejet|laserjet|selphy|pixma|epson|instax|phomemo|niimbot|sprocket|zink|label ?maker'
  'light| bulb|lamp | lamp| light|govee|lifx|yeelight| hue |nanoleaf|led ?strip|elk bledom|triones| qhm |magic ?home'
  'headset|headset|hands ?free|plantronics|jabra (evolve|talk|engage)'
  'headphones|headphone| wh [0-9]| wh ch| mdr | ath |quietcomfort| qc ?[0-9]|momentum|beats (studio|solo|executive|flex|ep)|powerbeats|bose 700|shokz|openrun|soundcore (life|space|q[0-9])|jbl (tune|live|quantum|club)| hd [0-9]{3}| px[0-9]'
  'speaker|speaker|soundlink| boom | flip [0-9]| charge [0-9]| go [0-9]| clip [0-9]| pill| srs |homepod| echo |nest (audio|mini)|soundcore (motion|flare|boom|select)|wonderboom|megaboom|emberton|stanmore|acton|woburn|kilburn|middleton|tufton|willen|beosound|bose home'
  'tablet|ipad|tablet| tab |matepad|mediapad| pad [0-9]|xiaomi pad|redmi pad|kindle|remarkable|boox'
  'computer|laptop|desktop|macbook|imac|mac ?mini|mac ?studio|notebook|thinkpad|ideapad|galaxy book|chromebook|pixelbook|matebook|zenbook|vivobook|surface (pro|book|go|studio|laptop)| pc | linux | ubuntu | arch | archlinux | fedora | manjaro | debian | mint | nixos | windows | cachyos | endeavouros '
  'phone|iphone|phone|galaxy [asmzn][0-9]|galaxy note| pixel [0-9]|oneplus| poco |redmi note|realme'
)
RX_WEAK=(
  'speaker| jbl |marshall|ultimate ears| ue |tribit| sonos |harman| bose |anker|soundcore|olufsen| b o |edifier'
  'headphones| sony |sennheiser|audio technica|akg|skullcandy|jabra|jlab|baseus| qcy |haylou'
  'phone|xiaomi|huawei| oppo | vivo |motorola| moto |honor|samsung|galaxy|redmi|google'
)
norm() { local s=" ${1,,} "; s=${s//[^a-z0-9]/ }; while [[ $s == *"  "* ]]; do s=${s//  / }; done; printf '%s' "$s"; }
rx_pick() { local n=$1 e; shift
  for e in "$@"; do [[ $n =~ ${e#*|} ]] && { printf '%s' "${e%%|*}"; return 0; }; done; return 1; }
num_ok() { [[ $1 =~ ^(0x[0-9a-fA-F]+|[0-9]+)$ ]]; }
class_kind() { # Bluetooth Class of Device → form
  local c=$1 major minor low ptr
  num_ok "$c" || return 1; c=$((c)); ((c)) || return 1
  major=$(( (c >> 8) & 0x1f )); minor=$(( (c >> 2) & 0x3f ))
  case $major in
    1) ((minor == 7)) && echo tablet || echo computer ;;
    2) echo phone ;;
    4) case $minor in 1|2) echo headset;; 4) echo microphone;; 5|7|10) echo speaker;; 6) echo headphones;;
                      8) echo car;; 9|14|15) echo tv;; 11|12|13|16) echo camera;; 18) echo console;; *) return 1;; esac ;;
    5) low=$(( (c >> 2) & 0xf )); ptr=$(( (c >> 6) & 3 ))
       if ((low == 1 || low == 2)); then echo gamepad; elif ((low == 3 || low == 9)); then echo remote
       elif ((low == 5 || low == 7)); then echo pen; elif ((ptr == 1 || ptr == 3)); then echo keyboard
       elif ((ptr == 2)); then echo mouse; else return 1; fi ;;
    6) if ((c & 0x80)); then echo printer; elif ((c & 0x20)); then echo camera; elif ((c & 0x10)); then echo tv
       else return 1; fi ;;
    7) ((minor == 5)) && echo vr || echo watch ;;
    8) case $minor in 4) echo gamepad;; 5) echo console;; *) return 1;; esac ;;
    9) echo health ;;
    *) return 1 ;;
  esac
}
appearance_kind() { # BLE GAP Appearance → form
  local a=$1 cat sub
  num_ok "$a" || return 1; a=$((a)); ((a)) || return 1
  cat=$(( a >> 6 )); sub=$(( a & 0x3f ))
  case $cat in
    1) echo phone ;; 2) ((sub == 7)) && echo tablet || echo computer ;; 3) echo watch ;;
    5|40) echo tv ;; 6) echo remote ;; 7) echo vr ;; 8|9) echo tag ;; 10) echo speaker ;;
    12|13|14|16|17|18|49|50|52) echo health ;;
    15) case $sub in 1) echo keyboard;; 3|4) echo gamepad;; 5|7) echo pen;; 10) echo remote;; *) echo mouse;; esac ;;
    22|31) echo light ;; 33) ((sub == 2)) && echo soundbar || echo speaker ;;
    34) ((sub <= 1)) && echo microphone || echo speaker ;; 35) echo car ;;
    37) case $sub in 1) echo earbuds;; 2) echo headset;; *) echo headphones;; esac ;;
    39) ((sub == 10)) && echo tv || echo speaker ;; 42) echo console ;;
    *) return 1 ;;
  esac
}
classify() { # icon name class appearance
  local i="${1,,}" n
  n=$(norm "$2")
  rx_pick "$n" "${RX_STRONG[@]}" && return
  class_kind "$3" && return
  appearance_kind "$4" && return
  rx_pick "$n" "${RX_WEAK[@]}" && return
  case "$i" in
    *headset*) echo headset ;;     *headphone*) echo headphones ;; *gaming*) echo gamepad ;;
    *keyboard*) echo keyboard ;;   *mouse*) echo mouse ;;          input-tablet) echo pen ;;
    *video-display*|*television*) echo tv ;; *camera*) echo camera ;; *printer*) echo printer ;;
    *phone*) echo phone ;;         *tablet*) echo tablet ;;        computer) echo computer ;;
    audio-card|multimedia-player) echo speaker ;; input-*) echo mouse ;; audio-*) echo headphones ;;
    *) echo generic ;;
  esac
}
# "Form" chosen in the Archive (Companions → FORM) wins over any guess
declare -A OVR=()
load_overrides() {
  local line on=0 re='"([0-9A-Fa-f:]{17})"[[:space:]]*:[[:space:]]*"([a-z]+)"'
  [[ -f $ARCHIVE_CONF ]] || return 0
  while IFS= read -r line; do
    if ((on)); then
      [[ $line == *"}"* ]] && break
      [[ $line =~ $re ]] && OVR[${BASH_REMATCH[1]^^}]=${BASH_REMATCH[2]}
    elif [[ $line == *'"kind_overrides"'* ]]; then
      [[ $line == *"{}"* ]] && break
      on=1
    fi
  done < "$ARCHIVE_CONF"
}
kind_for() { # mac icon name class appearance
  local o=${OVR[${1^^}]:-}
  if [[ -n $o && -n ${LABEL[$o]:-} ]]; then printf '%s' "$o"; else classify "$2" "$3" "$4" "$5"; fi
}

# TSV: alias name icon paired bonded trusted blocked connected battery rssi class appearance   ('-' = unknown)
dev_info() {
  bluetoothctl info "$1" 2>/dev/null | awk '
    function val(s){ sub(/^[^:]*: /, "", s); return s }
    function num(s){ if (s ~ /\(/) { sub(/.*\(/, "", s); sub(/\).*/, "", s) } else s = val(s); return s }
    function d(x){ return x == "" ? "-" : x }
    /^[ \t]*Alias:/      { alias = val($0) }
    /^[ \t]*Name:/       { name = val($0) }
    /^[ \t]*Icon:/       { icon = val($0) }
    /^[ \t]*Class:/      { cls = num($0) }
    /^[ \t]*Appearance:/ { appr = num($0) }
    /^[ \t]*Paired:/     { paired = val($0) }
    /^[ \t]*Bonded:/     { bonded = val($0) }
    /^[ \t]*Trusted:/    { trusted = val($0) }
    /^[ \t]*Blocked:/    { blocked = val($0) }
    /^[ \t]*Connected:/  { conn = val($0) }
    /^[ \t]*Battery Percentage:/ { bat = num($0) }
    /^[ \t]*RSSI:/       { rssi = num($0) }
    END { if (alias == "") alias = name; gsub(/\t/, " ", alias)
          if (alias == "") exit
          printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", alias, d(name), d(icon), d(paired), d(bonded),
                 d(trusted), d(blocked), d(conn), d(bat), d(rssi), d(cls), d(appr) }'
}

adapter_show() { bluetoothctl show 2>/dev/null; }
scan_active()  { [[ -f $SCAN_PID ]] && kill -0 "$(cat "$SCAN_PID")" 2>/dev/null; }
start_scan()   { scan_active && return
                 bluetoothctl --timeout "$SCAN_SECONDS" scan on >/dev/null 2>&1 &
                 echo $! > "$SCAN_PID"; date +%s > "$SCAN_T0"; disown 2>/dev/null; }
stop_scan()    { scan_active && kill "$(cat "$SCAN_PID")" 2>/dev/null; rm -f "$SCAN_PID"
                 bluetoothctl scan off >/dev/null 2>&1; }
dev_path()     { local p; p=$(busctl --system --list tree org.bluez 2>/dev/null | grep -m1 "/dev_${1//:/_}$")
                 echo "${p:-/org/bluez/hci0/dev_${1//:/_}}"; }

open_archive() {
  local cmd=()
  if command -v teyvat-archive >/dev/null; then cmd=(teyvat-archive)
  elif [[ -f "$SELF_DIR/teyvat_archive.py" ]]; then cmd=(python3 "$SELF_DIR/teyvat_archive.py")
  elif [[ -f "$HOME/.local/share/genshin-bluetooth/teyvat_archive.py" ]]; then
       cmd=(python3 "$HOME/.local/share/genshin-bluetooth/teyvat_archive.py")
  else note "The Archive is missing" "Run install.sh to summon teyvat-archive"; return 1; fi
  if command -v setsid >/dev/null; then setsid -f "${cmd[@]}" "$@" >/dev/null 2>&1
  else ( "${cmd[@]}" "$@" >/dev/null 2>&1 & ); fi
}

# Mouse: one click = pick (rofi's default needs a double-click), hovering highlights the row,
# and the wheel / touchpad scroll no longer moves the selection (keyboard arrows still do)
MOUSE=(-hover-select -me-select-entry '' -me-accept-entry MousePrimary
       -ml-row-up '' -ml-row-down '' -ml-row-left '' -ml-row-right '')

# rows: ROWS (markup) · ICON (file) · ACTS (action id)
add()  { ROWS+=("$1"); ICON+=("$ICONS/$2.svg"); ACTS+=("$3"); }
emit() { local i n=${#ROWS[@]}
         for ((i=0;i<n;i++)); do printf '%s\0icon\x1f%s' "${ROWS[i]}" "${ICON[i]}"; ((i<n-1)) && printf '|'; done; }
menu() { # mesg prompt active urgent
  local args=(-dmenu -i -sep '|' -markup-rows -show-icons -format i -no-custom
              "${MOUSE[@]}" -p "$2" -mesg "$1" -theme "$THEME"
              -theme-str "listview { lines: $MAX_ROWS; }")
  [[ -n $3 ]] && args+=(-a "$3")
  [[ -n $4 ]] && args+=(-u "$4")
  emit | rofi "${args[@]}"
}
sub()  { printf "<span size='small' alpha='62%%'>%s</span>" "$1"; }

# ─────────────────────────────────────────────────────────── device menu ──
do_connect() {
  local out; note "Opening a Ley Line…" "$2" "$3"
  out=$(timeout 20 bluetoothctl connect "$1" 2>&1)
  if grep -qi "successful" <<<"$out"; then note "◆ Resonance established" "$2" "$3"
  else note "✕ Resonance failed" "$2 didn't answer — is it awake and in range?" "$3"; fi
}
do_pair() { # mac name icon kind
  case "$4" in phone|computer|tablet|tv|car|console)
      note "Sigil exchange required" "Opening the Archive to forge a pact with $2" "$3"
      open_archive --pair "$1"; exit 0 ;;
  esac
  note "Forging a pact…" "Put $2 in pairing mode" "$3"
  local out; out=$(timeout 30 bluetoothctl pair "$1" 2>&1)
  if grep -qiE "successful|AlreadyExists" <<<"$out"; then
      bluetoothctl trust "$1" >/dev/null 2>&1
      note "✦ A new pact is forged" "$2 has answered your call" "$3"
      do_connect "$1" "$2" "$3"
  else note "✕ Pact failed" "$(tail -n1 <<<"$out")" "$3"; fi
}

device_menu() {
  local mac=$1 alias rname icon paired bonded trusted blocked conn bat rssi cls appr kind el col ic hdr sel rc act new yn
  while true; do
    IFS=$'\t' read -r alias rname icon paired bonded trusted blocked conn bat rssi cls appr < <(dev_info "$mac")
    [[ -z $alias ]] && { note "That companion vanished"; return 0; }
    kind=$(kind_for "$mac" "$icon" "$alias $rname" "$cls" "$appr"); el=${ELEM[$kind]}; col=${ECOL[$el]}
    ic="$ICONS/$kind.svg"
    hdr="<span size='x-large' weight='bold' foreground='#D3BC8E'>$(esc "$alias")</span>"$'\n'
    hdr+="<span foreground='#FFB13F'>$(stars "$kind")</span>  <span foreground='$col'>$el</span> · ${LABEL[$kind]} · <tt>$mac</tt>"$'\n'
    local meta=()
    [[ $conn == yes ]] && meta+=("◆ Resonating") || { [[ $paired == yes ]] && meta+=("◇ Bonded") || meta+=("· Wandering"); }
    [[ $trusted == yes ]] && meta+=("✓ Trusted")
    [[ $blocked == yes ]] && meta+=("⊘ Sealed")
    [[ $bat != - ]] && meta+=("⚡ $bat% $(bar "$bat")")
    [[ $rssi != - ]] && meta+=("Ley Line $(ley "$rssi")")
    local joined="" m
    for m in "${meta[@]}"; do joined+="${joined:+   ·   }$m"; done
    hdr+="<span size='small' alpha='75%'>$joined</span>"

    ROWS=(); ICON=(); ACTS=()
    if   [[ $conn == yes ]];   then add "<b>Sever resonance</b>"$'\n'"$(sub "disconnect")" unlink disconnect
    elif [[ $paired == yes ]]; then add "<b>Resonate</b>"$'\n'"$(sub "connect")" link connect
    else                            add "<b>Forge a pact</b>"$'\n'"$(sub "pair, trust &amp; connect")" pact pair; fi
    [[ $trusted == yes ]] && add "<b>Revoke trust</b>"$'\n'"$(sub "require authorization again")" untrust untrust \
                          || add "<b>Grant trust</b>"$'\n'"$(sub "auto-accept connections")" trust trust
    [[ $blocked == yes ]] && add "<b>Unseal</b>"$'\n'"$(sub "allow connections")" unblock unblock \
                          || add "<b>Seal away</b>"$'\n'"$(sub "block this companion")" block block
    add "<b>Bestow a new name</b>"$'\n'"$(sub "set alias")" rename rename
    add "<b>Read the Codex</b>"$'\n'"$(sub "full bluetoothctl info")" info codex
    add "<b>Open in Teyvat Archive</b>"$'\n'"$(sub "battery · services · form · voice &amp; volume · file transfer")" archive archive
    add "<b>Forget companion</b>"$'\n'"$(sub "remove pairing forever")" forget forget
    add "<b>Back</b>"$'\n'"$(sub "to the Ley Line Network")" back back

    sel=$(menu "$hdr" "✦" "" ""); rc=$?
    [[ $rc -ne 0 || -z $sel ]] && exit 0
    act=${ACTS[$sel]}
    case "$act" in
      disconnect) bluetoothctl disconnect "$mac" >/dev/null 2>&1 && note "Resonance faded" "$alias" "$ic"; return 0 ;;
      connect)    do_connect "$mac" "$alias" "$ic"; return 0 ;;
      pair)       do_pair "$mac" "$alias" "$ic" "$kind"; return 0 ;;
      trust)      bluetoothctl trust "$mac" >/dev/null 2>&1 && note "✓ Trust granted" "$alias" "$ic" ;;
      untrust)    bluetoothctl untrust "$mac" >/dev/null 2>&1 && note "Trust revoked" "$alias" "$ic" ;;
      block)      bluetoothctl block "$mac" >/dev/null 2>&1 && note "⊘ Sealed away" "$alias" "$ic" ;;
      unblock)    bluetoothctl unblock "$mac" >/dev/null 2>&1 && note "Unsealed" "$alias" "$ic" ;;
      rename)
        new=$(rofi -dmenu "${MOUSE[@]}" -p "✎" -mesg "Bestow a new name upon <b>$(esc "$alias")</b>" -theme "$THEME" \
                   -theme-str 'listview { lines: 0; } entry { placeholder: "New name…"; }' </dev/null)
        [[ -n $new ]] && busctl --system set-property org.bluez "$(dev_path "$mac")" org.bluez.Device1 Alias s "$new" \
            && note "✎ Name bestowed" "$alias → $new" "$ic" ;;
      codex)
        bluetoothctl info "$mac" 2>/dev/null | sed -e 's/^\s*//' -e 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g' \
          | rofi -dmenu -i -markup-rows "${MOUSE[@]}" -p "⌕" -mesg "<b>Codex</b> · $(esc "$alias")" -theme "$THEME" \
                 -theme-str 'element-icon { enabled: false; } listview { lines: 12; }' >/dev/null ;;
      archive) open_archive --device "$mac"; exit 0 ;;
      forget)
        ROWS=(); ICON=(); ACTS=()
        add "<b>Yes — sever the pact forever</b>"$'\n'"$(sub "you will need to pair again")" forget yes
        add "<b>No — keep $(esc "$alias")</b>" back no
        yn=$(menu "<span weight='bold' foreground='#EF7A35'>Forget $(esc "$alias")?</span>" "⚠" "" "0") || exit 0
        [[ ${ACTS[$yn]} == yes ]] && { bluetoothctl remove "$mac" >/dev/null 2>&1 && note "Companion forgotten" "$alias"; return 0; } ;;
      back) return 0 ;;
    esac
  done
}

# ────────────────────────────────────────────────────── statue (repairs) ──
statue_menu() {
  local rf svc hdr sel act
  rf=$(rfkill list bluetooth 2>/dev/null)
  svc=$(systemctl is-active bluetooth 2>/dev/null)
  hdr="<span size='large' weight='bold' foreground='#D3BC8E'>⚚  Statue of the Seven</span>"$'\n'
  hdr+="<span size='small'>service: <b>${svc:-unknown}</b> · rfkill: <b>$(grep -q 'Soft blocked: yes' <<<"$rf" && echo soft-sealed || (grep -q 'Hard blocked: yes' <<<"$rf" && echo HARD-sealed || echo free))</b></span>"
  ROWS=(); ICON=(); ACTS=()
  add "<b>Break the rfkill seal</b>"$'\n'"$(sub "rfkill unblock bluetooth")" unblock rfkill
  add "<b>Power-cycle the adapter</b>"$'\n'"$(sub "power off → on")" refresh cycle
  add "<b>Restart the bluetooth service</b>"$'\n'"$(sub "pkexec systemctl restart bluetooth")" statue restart
  add "<b>Forget all wanderers</b>"$'\n'"$(sub "remove unpaired cached devices")" forget purge
  add "<b>Full divination in the Archive</b>"$'\n'"$(sub "logs · drivers · corrupted pacts · report")" archive archive
  add "<b>Back</b>" back back
  sel=$(menu "$hdr" "⚚" "" "") || exit 0
  act=${ACTS[$sel]}
  case "$act" in
    rfkill)  { rfkill unblock bluetooth 2>/dev/null || pkexec rfkill unblock bluetooth; } && note "Seal broken ✦" ;;
    cycle)   bluetoothctl power off >/dev/null 2>&1; sleep 1.2; bluetoothctl power on >/dev/null 2>&1 && note "Adapter reborn ✦" ;;
    restart) pkexec systemctl restart bluetooth && note "bluetoothd restarted ✦" ;;
    purge)   local n=0 m
             while read -r _ m _; do
               bluetoothctl info "$m" 2>/dev/null | grep -qE "Paired: yes|Connected: yes" && continue
               bluetoothctl remove "$m" >/dev/null 2>&1 && ((n++))
             done < <(bluetoothctl devices 2>/dev/null)
             note "Forgot $n wanderer(s)" ;;
    archive) open_archive --page statue; exit 0 ;;
  esac
}

# ────────────────────────────────────────────────────────────── main menu ──
main_menu() {
  local show powered disc discov alias nconn npaired active urgent idx mac alias_ rname icon paired bonded trusted blocked conn bat rssi cls appr
  while true; do
    ROWS=(); ICON=(); ACTS=(); active=""; urgent=""
    show=$(adapter_show)
    if [[ -z $show ]] || grep -q "No default controller" <<<"$show"; then
      local hdr="<span size='large' weight='bold' foreground='#D3BC8E'>✦  T E Y V A T  ·  L E Y   L I N E S  ✦</span>"$'\n'
      hdr+="<span size='small' foreground='#EF7A35'>No Ley Line adapter answers — sealed, driverless, or bluetoothd asleep</span>"
      add "<b>Statue of the Seven</b>"$'\n'"$(sub "repair the Ley Lines")" statue statue
      add "<b>Teyvat Archive</b>"$'\n'"$(sub "full diagnostics")" archive archive
      idx=$(menu "$hdr" "✦" "" "") || exit 0
      case "${ACTS[$idx]}" in statue) statue_menu ;; archive) open_archive --page statue; exit 0 ;; esac
      continue
    fi
    alias=$(awk -F': ' '/^\s*Alias:/{print $2; exit}' <<<"$show")
    grep -q "Powered: yes" <<<"$show" && powered=1 || powered=0
    grep -q "Discoverable: yes" <<<"$show" && discov=1 || discov=0
    scan_active && disc=1 || disc=0

    if ((powered)); then
      add "<b>Seal the Ley Lines</b>"$'\n'"$(sub "turn Bluetooth off")" power-off off
      if ((disc)); then
        local left=$(( SCAN_SECONDS - ($(date +%s) - $(cat "$SCAN_T0" 2>/dev/null || date +%s)) ))
        add "<b>Elemental Sight is active</b>  <span size='small' foreground='#5CD8B8'>${left}s</span>"$'\n'"$(sub "select to close your eyes")" sight-on scanstop
        add "<b>Refresh the vision</b>"$'\n'"$(sub "re-read nearby companions")" refresh refresh
      else
        add "<b>Elemental Sight</b>"$'\n'"$(sub "search for nearby companions (${SCAN_SECONDS}s)")" sight scan
      fi
      nconn=0; npaired=0
      while IFS=$'\t' read -r _rank _key mac alias_ rname icon paired bonded trusted blocked conn bat rssi cls appr; do
        [[ -z $mac ]] && continue
        local kind el col line1 line2 st meta=() ic m
        kind=$(kind_for "$mac" "$icon" "$alias_ $rname" "$cls" "$appr"); el=${ELEM[$kind]}; col=${ECOL[$el]}
        if   [[ $conn == yes ]];   then st="<span foreground='$col'>◆</span> Resonating"; ((nconn++)); ic=$kind
        elif [[ $paired == yes ]]; then st="◇ Bonded"; ic=$kind
        else st="· Wandering"; ic=$kind-dim; fi
        [[ $paired == yes ]] && ((npaired++))
        line1="<b>$(esc "$alias_")</b>   <span size='small' alpha='75%'>$st</span>"
        meta+=("${LABEL[$kind]} · <span foreground='$col'>$el</span>")
        [[ $bat != - ]] && meta+=("⚡ $bat% $(bar "$bat")")
        [[ $rssi != - ]] && meta+=("Ley Line $(ley "$rssi")")
        line2=""; for m in "${meta[@]}"; do line2+="${line2:+   ·   }$m"; done
        [[ $conn == yes ]] && active+="${active:+,}${#ROWS[@]}"
        [[ $bat != - ]] && ((bat <= LOW_BATTERY)) && urgent+="${urgent:+,}${#ROWS[@]}"
        add "$line1"$'\n'"$(sub "$line2")" "$ic" "dev:$mac"
      done < <(collect_devices)
      ((discov)) && add "<b>Fold the Wind Glider</b>"$'\n'"$(sub "stop being visible to others")" wind undiscover \
                 || add "<b>Spread the Wind Glider</b>"$'\n'"$(sub "become visible to others (3 min)")" wind discover
    else
      add "<b>Awaken the Ley Lines</b>"$'\n'"$(sub "turn Bluetooth on")" power-on on
      nconn=0; npaired=0
    fi
    add "<b>Statue of the Seven</b>"$'\n'"$(sub "rfkill · reset adapter · restart service")" statue statue
    add "<b>Teyvat Archive</b>  <span size='small' foreground='#D3BC8E'>✦ Advanced</span>"$'\n'"$(sub "cards · radar · audio &amp; volume · file transfer · diagnostics")" archive archive

    local state; ((powered)) && state="<span foreground='#A5C83B'>Awakened</span>" || state="<span foreground='#EF7A35'>Dormant</span>"
    local hdr="<span size='large' weight='bold' foreground='#D3BC8E'>✦  T E Y V A T  ·  L E Y   L I N E S  ✦</span>"$'\n'
    hdr+="<span size='small'>⟡ <b>$(esc "${alias:-adapter}")</b> · $state"
    ((powered)) && hdr+=" · ◆ $nconn resonating · ◇ $npaired bonded"
    ((disc)) && hdr+=" · <span foreground='#5CD8B8'>◈ Sight</span>"
    hdr+="</span>"$'\n'"<span size='x-small' alpha='50%'>Alt+1 Sight · Alt+2 Power · Alt+3 Archive · Alt+4 Refresh</span>"

    idx=$(menu "$hdr" "✦" "$active" "$urgent"); local rc=$?
    case $rc in
      0) ;;
      10) ((powered)) && { ((disc)) && stop_scan || { start_scan; sleep 2.5; }; }; continue ;;
      11) if ((powered)); then stop_scan; bluetoothctl power off >/dev/null; note "Ley Lines sealed"
          else rfkill unblock bluetooth 2>/dev/null; bluetoothctl power on >/dev/null && note "Ley Lines awakened ✦"; fi; continue ;;
      12) open_archive; exit 0 ;;
      13) continue ;;
      *) exit 0 ;;
    esac
    [[ -z $idx ]] && exit 0
    case "${ACTS[$idx]}" in
      on)         rfkill unblock bluetooth 2>/dev/null; bluetoothctl power on >/dev/null && note "Ley Lines awakened ✦" "" "$ICONS/power-on.svg" ;;
      off)        stop_scan; bluetoothctl power off >/dev/null && note "Ley Lines sealed" "" "$ICONS/power-off.svg" ;;
      scan)       start_scan; note "◈ Elemental Sight" "Searching for ${SCAN_SECONDS}s…" "$ICONS/sight-on.svg"; sleep 2.5 ;;
      scanstop)   stop_scan ;;
      refresh)    sleep 0.3 ;;
      discover)   bluetoothctl discoverable on >/dev/null && note "Wind Glider spread" "Visible to others" "$ICONS/wind.svg" ;;
      undiscover) bluetoothctl discoverable off >/dev/null ;;
      statue)     statue_menu ;;
      archive)    open_archive; exit 0 ;;
      dev:*)      device_menu "${ACTS[$idx]#dev:}" ;;
    esac
  done
}

collect_devices() {
  local mac name alias rname icon paired bonded trusted blocked conn bat rssi cls appr rank key
  while read -r _ mac name; do
    [[ $mac =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]] || continue
    IFS=$'\t' read -r alias rname icon paired bonded trusted blocked conn bat rssi cls appr < <(dev_info "$mac")
    [[ -z $alias ]] && continue
    if   [[ $conn == yes ]];   then rank=0
    elif [[ $paired == yes ]]; then rank=1
    else
      rank=2
      if [[ $SHOW_NAMELESS != 1 && $rname == - && $alias =~ ^([0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}$ ]]; then continue; fi
    fi
    if ((rank == 2)); then [[ $rssi != - ]] && key=$(printf '%03d' $(( -rssi ))) || key=999
    else key="${alias,,}"; fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$rank" "$key" "$mac" "$alias" "$rname" \
           "$icon" "$paired" "$bonded" "$trusted" "$blocked" "$conn" "$bat" "$rssi" "$cls" "$appr"
  done < <(bluetoothctl devices 2>/dev/null) | sort -t$'\t' -k1,1n -k2,2
}

# ─────────────────────────────────────────────────────────────── entry ──
case "${1:-}" in
  --gen-icons) rm -f "$ICONS/.done"; gen_icons; echo "$ICONS"; exit 0 ;;
  --archive)   shift; open_archive "$@"; exit $? ;;
  --classify)  shift; printf '%s\n' "$(classify "${2:-}" "${1:-}" "${3:--}" "${4:--}")"; exit 0 ;;
  --version)   echo "genshin-bluetooth $VERSION"; exit 0 ;;
  -h|--help)   sed -n '2,10p' "$0"; exit 0 ;;
esac

# Toggle: a second press closes the popup
pgrep -x rofi >/dev/null && { pkill -x rofi; exit 0; }
command -v bluetoothctl >/dev/null || { note "bluetoothctl missing" "Install bluez-utils"; exit 1; }
gen_icons
write_theme
load_overrides
main_menu
