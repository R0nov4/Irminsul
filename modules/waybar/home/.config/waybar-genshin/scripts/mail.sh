#!/usr/bin/env bash
n=0
if command -v dunstctl >/dev/null 2>&1; then
  n=$(dunstctl count history 2>/dev/null || echo 0)
elif command -v swaync-client >/dev/null 2>&1; then
  n=$(swaync-client -c 2>/dev/null || echo 0)
fi
[ -z "$n" ] && n=0
cls=empty; [ "$n" -gt 0 ] && cls=full
echo "{\"text\":\"$n\",\"class\":\"$cls\",\"tooltip\":\"Notifications: $n\"}"
