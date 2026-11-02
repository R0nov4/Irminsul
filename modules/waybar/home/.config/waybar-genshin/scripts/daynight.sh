#!/usr/bin/env bash
h=$(date +%-H)
if [ "$h" -ge 6 ] && [ "$h" -lt 18 ]; then c=day; t="Day"; else c=night; t="Night"; fi
echo "{\"text\":\"  \",\"class\":\"$c\",\"tooltip\":\"$t\"}"
