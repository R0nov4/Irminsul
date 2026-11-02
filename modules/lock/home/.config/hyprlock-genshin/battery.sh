#!/usr/bin/env bash
for b in /sys/class/power_supply/BAT*; do
  [ -r "$b/capacity" ] || continue
  c=$(cat "$b/capacity")
  s=$(cat "$b/status" 2>/dev/null)
  icon="▮"; [ "$s" = "Charging" ] && icon="⚡"
  echo "$icon $c%"
  exit 0
done
echo ""
