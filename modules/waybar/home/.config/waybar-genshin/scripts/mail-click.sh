#!/usr/bin/env bash
case "${1:-show}" in
  show)
    if command -v dunstctl >/dev/null 2>&1; then
      dunstctl history-pop
      sleep 6
      dunstctl close
    elif command -v swaync-client >/dev/null 2>&1; then
      swaync-client -t -sw
    fi
    ;;
  clear)
    if command -v dunstctl >/dev/null 2>&1; then
      dunstctl close-all
      dunstctl history-clear
    elif command -v swaync-client >/dev/null 2>&1; then
      swaync-client -C -sw
    fi
    ;;
esac
