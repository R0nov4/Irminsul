#!/usr/bin/env bash
DIR="$HOME/.config/dunst-genshin"

# کپی در مسیر پیش‌فرض برای سازگاری با ابزارهای جانبی
mkdir -p "$HOME/.config/dunst"
cp -f "$DIR/dunstrc" "$HOME/.config/dunst/dunstrc" 2>/dev/null || true

pkill -x dunst 2>/dev/null || true
sleep 0.2
nohup dunst -config "$DIR/dunstrc" >/dev/null 2>&1 &
