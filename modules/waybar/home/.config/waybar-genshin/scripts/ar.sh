#!/usr/bin/env bash
s=$(cut -d. -f1 /proc/uptime)
h=$((s/3600)); m=$(((s%3600)/60))
echo "{\"text\":\"AR $((h+1))\",\"tooltip\":\"Uptime: ${h}h ${m}m\"}"
