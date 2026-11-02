#!/usr/bin/env bash
T=Genshin-Official; S=32
LOG=/tmp/cursor-fix.log
echo "start $(date +%T)" > "$LOG"

apply() { hyprctl setcursor "$T" $((S-1)) >> "$LOG" 2>&1; hyprctl setcursor "$T" "$S" >> "$LOG" 2>&1; }
nudge() {
  local pos x y
  pos=$(hyprctl cursorpos 2>/dev/null)
  x=${pos%%,*}; y=${pos##*, }
  hyprctl dispatch 'hl.dsp.cursor.move({ x = 700, y = 25 })' >> "$LOG" 2>&1
  sleep 0.25
  hyprctl dispatch "hl.dsp.cursor.move({ x = ${x:-960}, y = ${y:-400} })" >> "$LOG" 2>&1
}

# phase 1: early, no waiting for waybar
for d in 2 3; do sleep "$d"; apply; nudge; echo "early $d $(date +%T)" >> "$LOG"; done

# phase 2: after waybar is up (as before)
for i in $(seq 1 180); do pgrep -x waybar >/dev/null && break; sleep 0.5; done
echo "waybar up $(date +%T)" >> "$LOG"
n=0
for d in 1 3 6 12 25; do
  sleep "$d"; n=$((n+1)); apply
  if [ "$n" = 1 ] || [ "$n" = 5 ]; then nudge; fi
  echo "round $n $(date +%T)" >> "$LOG"
done
