#!/bin/bash
# Quick moon phase preview — patches the cache JSON in-place.
# Usage:
#   ./moon_preview.sh <phase>
#   ./moon_preview.sh list        — show all named phases
#   ./moon_preview.sh reset       — restore the real data
#
# phase is a float 0.0–1.0:
#   0.00  New Moon          (invisible)
#   0.10  Waxing Crescent   (thin sliver, right side lit)
#   0.25  First Quarter     (right half lit)
#   0.40  Waxing Gibbous    (mostly lit, right side)
#   0.50  Full Moon          (fully lit)
#   0.60  Waning Gibbous    (mostly lit, left side)
#   0.75  Last Quarter      (left half lit)
#   0.90  Waning Crescent   (thin sliver, left side lit)
#   0.05  Very thin crescent (barely visible)

CACHE="$HOME/.cache/teyvat-forecast/weather.json"

if [[ "$1" == "list" ]]; then
    echo "Named phases:"
    echo "  0.00  New Moon           (invisible)"
    echo "  0.05  Very thin crescent (waxing, barely visible)"
    echo "  0.10  Waxing Crescent    (thin sliver, right lit)"
    echo "  0.15  Waxing Crescent    (wider crescent)"
    echo "  0.25  First Quarter      (right half lit)"
    echo "  0.40  Waxing Gibbous     (mostly lit, right)"
    echo "  0.50  Full Moon          (fully lit)"
    echo "  0.60  Waning Gibbous     (mostly lit, left)"
    echo "  0.75  Last Quarter       (left half lit)"
    echo "  0.85  Waning Crescent    (wider crescent, left)"
    echo "  0.90  Waning Crescent    (thin sliver, left lit)"
    echo "  0.95  Very thin crescent (waning, barely visible)"
    exit 0
fi

if [[ "$1" == "reset" ]]; then
    teyvat-forecast preview off
    echo "Restored real data."
    exit 0
fi

if [[ -z "$1" ]]; then
    echo "Usage: $0 <phase 0.0-1.0>  |  list  |  reset"
    exit 1
fi

PHASE="$1"

# Compute name and illumination from phase
read -r NAME ILLUM < <(python3 -c "
import math
phase = float($PHASE)
c = math.cos(2 * math.pi * phase)
illum = round((1 - c) / 2 * 100)
names = [(0.033,'New Moon'),(0.216,'Waxing Crescent'),(0.283,'First Quarter'),
         (0.466,'Waxing Gibbous'),(0.533,'Full Moon'),(0.716,'Waning Gibbous'),
         (0.783,'Last Quarter'),(0.966,'Waning Crescent'),(1.01,'New Moon')]
name = 'New Moon'
for limit, n in names:
    if phase <= limit:
        name = n
        break
print(name.replace(' ','_'), illum)
")

NAME="${NAME//_/ }"

python3 -c "
import json
with open('$CACHE') as f:
    d = json.load(f)
d['today']['moon_phase'] = $PHASE
d['today']['moon_name'] = '$NAME'
d['today']['moon_illum'] = $ILLUM
d['preview'] = True
d['preview_scene'] = 'moon-test'
with open('$CACHE', 'w') as f:
    json.dump(d, f)
"

echo "Moon set to: phase=$PHASE  $NAME  ${ILLUM}% illuminated"
echo "Open/toggle the popup to see it."
