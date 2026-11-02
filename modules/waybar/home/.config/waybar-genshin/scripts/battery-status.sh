#!/usr/bin/env bash
PS_DIR="${BAT_PS:-/sys/class/power_supply}"
FORCE="/tmp/bat-force"          # echo charging / normal  > /tmp/bat-force   (test without a charger)

plugged=0; cap=100; status=""
read_state() {
  plugged=0; cap=-1; status=""
  local d t v
  for d in "$PS_DIR"/*; do
    [ -r "$d/type" ] || continue
    read -r t < "$d/type"
    case "$t" in
      Battery)
        v=""; [ -r "$d/scope" ] && read -r v < "$d/scope"
        [ "$v" = "Device" ] && continue
        if [ "$cap" -lt 0 ] && [ -r "$d/capacity" ]; then read -r cap < "$d/capacity"; fi
        [ -r "$d/status" ] && read -r status < "$d/status"
        [ "$status" = "Charging" ] && plugged=1 ;;
      *)
        if [ -r "$d/online" ]; then read -r v < "$d/online"; [ "$v" = "1" ] && plugged=1; fi ;;
    esac
  done
  [ "$cap" -lt 0 ] && cap=100
  if [ -r "$FORCE" ]; then
    read -r v < "$FORCE"
    [ "$v" = "charging" ] && plugged=1
    [ "$v" = "normal" ] && plugged=0
  fi
}

emit() {   # classes (space separated), tooltip
  local c="${1// /\",\"}"
  printf '{"text":"\\u00a0","class":["bat","%s"],"tooltip":"%s"}\n' "$c" "$2"
}

BSEQ=(0 0 0 0 0 0 1 2 3 3 4 4 5 5 5 5 5 5 5 5 5)
play_anim() {   # target step 0..20 : fill sweeps up (ease-out), bolt pops in with overshoot
  local tgt=$1 i x inv e f lastf=""
  for i in $(seq 0 20); do
    x=$((i * 50)); inv=$((1000 - x))
    e=$((1000 - inv * inv * inv / 1000000))
    f=$((tgt * e / 1000))
    if [ "$f.${BSEQ[$i]}" = "$lastf" ]; then
      :
    else
      emit "chg f${f}b${BSEQ[$i]}" "$cap% - Charging"; lastf="$f.${BSEQ[$i]}"
    fi
    sleep 0.035
  done
}

prev=""; first=1; lastcls=""
while :; do
  read_state
  step=$(( (cap + 2) / 5 )); [ "$step" -gt 20 ] && step=20
  if [ "$plugged" = "1" ]; then
    if [ "$prev" = "0" ] && [ "$first" = "0" ]; then play_anim "$step"; fi
    cls="chg f${step}b5"; tip="$cap% - Charging"
  elif [ "$cap" -le 15 ]; then
    cls="low l$step"; [ "$step" -gt 4 ] && cls="low l4"; tip="$cap% - Low battery"
  else
    cls="n$step"; tip="$cap%"
  fi
  if [ "$cls|$tip" = "$lastcls" ]; then
    :
  else
    emit "$cls" "$tip"; lastcls="$cls|$tip"
  fi
  prev="$plugged"; first=0
  sleep 0.4
done
