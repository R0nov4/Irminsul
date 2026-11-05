#!/usr/bin/env bash
# =============================================================================
# install.sh — Teyvat Forecast installer
#
#   install.sh --deps-check    verify dependencies, change nothing
#   install.sh --install       install / update everything (idempotent)
#   install.sh --uninstall     remove everything, restore what was changed
#   install.sh --purge         uninstall + delete config & cache too
#
# Hard dependencies: qs (quickshell), python3, curl, jq
# Optional: systemctl (refresh timer), mpv or paplay (sound, off by default)
#
# The installer NEVER touches Waybar modules other than custom/weather, and
# only that module's "on-click" key. Everything it modifies is backed up.
# =============================================================================
set -u

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HOME_="${HOME:?HOME not set}"
XDG_CONFIG_HOME_="${XDG_CONFIG_HOME:-$HOME_/.config}"
XDG_CACHE_HOME_="${XDG_CACHE_HOME:-$HOME_/.cache}"

QS_DIR="$XDG_CONFIG_HOME_/quickshell/teyvat-forecast"
TF_CONF_DIR="$XDG_CONFIG_HOME_/teyvat-forecast"
TF_CACHE_DIR="$XDG_CACHE_HOME_/teyvat-forecast"
BIN_DIR="$HOME_/.local/bin"
SYSTEMD_DIR="$XDG_CONFIG_HOME_/systemd/user"
STATE_FILE="$TF_CONF_DIR/install-state.json"
CLICK_CMD="$BIN_DIR/teyvat-forecast toggle"

C_GOLD=$'\033[38;2;211;188;142m'; C_GREEN=$'\033[32m'; C_RED=$'\033[31m'
C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'

say()    { printf '%s\n' "${C_GOLD}✦${C_OFF} $*"; }
ok()     { printf '  %s\n' "${C_GREEN}✔${C_OFF} $*"; }
warn()   { printf '  %s\n' "${C_RED}✖${C_OFF} $*" >&2; }
info()   { printf '    %s\n' "${C_DIM}$*${C_OFF}"; }
die()    { warn "$*"; exit 1; }

# ── locate the Waybar config dir (your setup: waybar-genshin) ───────────────
WB_DIR=""
WB_CFG=""
for d in "$XDG_CONFIG_HOME_/waybar-genshin" "$XDG_CONFIG_HOME_/waybar"; do
    for c in "$d/config.jsonc" "$d/config.json"; do
        if [ -f "$c" ]; then WB_DIR="$d"; WB_CFG="$c"; break 2; fi
    done
done
WB_SCRIPTS_DIR="$WB_DIR/scripts"
WB_WEATHER_SH="$WB_SCRIPTS_DIR/weather.sh"

# ════════════════════════════════════════════════════════════════════════════
# dependency check
# ════════════════════════════════════════════════════════════════════════════
deps_check() {
    say "Checking dependencies"
    local missing=0

    if command -v qs >/dev/null 2>&1; then
        ok "qs found: $(command -v qs)$(qs --version 2>/dev/null | head -1 | sed 's/^/ — /' || true)"
    elif command -v quickshell >/dev/null 2>&1; then
        ok "quickshell found: $(command -v quickshell)"
    else
        warn "qs / quickshell NOT found  (pacman -S quickshell · apt install quickshell)"
        missing=1
    fi

    command -v python3 >/dev/null 2>&1 \
        && ok "python3 found ($(python3 -V 2>&1))" \
        || { warn "python3 NOT found (>= 3.8 required)"; missing=1; }

    command -v curl >/dev/null 2>&1 \
        && ok "curl found" || { warn "curl NOT found"; missing=1; }

    command -v jq >/dev/null 2>&1 \
        && ok "jq found" || { warn "jq NOT found (used by the Waybar shim)"; missing=1; }

    if command -v systemctl >/dev/null 2>&1; then
        ok "systemctl found (user timer refresh)"
    else
        warn "systemctl NOT found — the timer will be skipped; the Waybar shim self-heals instead"
    fi

    if command -v mpv >/dev/null 2>&1; then
        ok "mpv found (ambient sound available)"
    elif command -v paplay >/dev/null 2>&1; then
        ok "paplay found (UI click sounds only; ambient loops need mpv)"
    else
        warn "mpv / paplay NOT found — sound features disabled (they are OFF by default anyway)"
    fi

    if [ "$missing" = 1 ]; then
        warn "Missing hard dependencies — install them, then re-run."
        return 1
    fi
    ok "All hard dependencies satisfied"
}

# ════════════════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════════════════
state_set() {  # state_set <key> <json-value>
    python3 - "$STATE_FILE" "$1" "$2" <<'PYEOF'
import json, os, sys
path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
state = {}
if os.path.isfile(path):
    try:
        state = json.load(open(path))
    except ValueError:
        state = {}
state[key] = json.loads(value)
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(state, open(path, "w"), indent=2)
PYEOF
}

state_get() {  # state_get <key> -> prints value or empty
    [ -f "$STATE_FILE" ] || return 0
    python3 - "$STATE_FILE" "$1" <<'PYEOF'
import json, sys
try:
    state = json.load(open(sys.argv[1]))
    v = state.get(sys.argv[2])
    print("" if v is None else (v if isinstance(v, str) else json.dumps(v)))
except (ValueError, OSError):
    pass
PYEOF
}

# ════════════════════════════════════════════════════════════════════════════
# install
# ════════════════════════════════════════════════════════════════════════════
do_install() {
    deps_check || die "Aborting: install the missing tools first."

    # 1 ─ Quickshell config ──────────────────────────────────────────────────
    say "Installing Quickshell config → $QS_DIR"
    mkdir -p "$QS_DIR"
    cp -r "$SRC_DIR/quickshell/." "$QS_DIR/"
    ok "QML + assets copied"
    info "note: if 'qs -c teyvat-forecast' is running it will hot-reload now"

    # 2 ─ data layer ─────────────────────────────────────────────────────────
    say "Installing data layer"
    mkdir -p "$TF_CONF_DIR" "$TF_CACHE_DIR"
    install -m 755 "$SRC_DIR/data/teyvat-fetch.py" "$TF_CONF_DIR/teyvat-fetch.py"
    ok "fetch script → $TF_CONF_DIR/teyvat-fetch.py"

    # 3 ─ config file (never overwrite an existing one) ─────────────────────
    if [ ! -f "$TF_CONF_DIR/config.json" ]; then
        cp "$SRC_DIR/config/config.json" "$TF_CONF_DIR/config.json"
        ok "default config written → $TF_CONF_DIR/config.json"
    else
        ok "config already exists — kept your $TF_CONF_DIR/config.json"
    fi

    # fill in the sound player detection (only if the key is missing)
    PLAYER=""
    command -v mpv >/dev/null 2>&1 && PLAYER="mpv"
    [ -z "$PLAYER" ] && command -v paplay >/dev/null 2>&1 && PLAYER="paplay"
    python3 - "$TF_CONF_DIR/config.json" "$PLAYER" <<'PYEOF'
import json, sys
path, player = sys.argv[1], sys.argv[2]
try:
    cfg = json.load(open(path))
except ValueError:
    sys.exit(0)
snd = cfg.setdefault("sound", {})
if "player" not in snd:
    snd["player"] = player
    json.dump(cfg, open(path, "w"), indent=2)
    print(f"  sound player set to '{player or 'none (sound disabled)'}'")
PYEOF

    # 4 ─ CLI wrapper ────────────────────────────────────────────────────────
    say "Installing CLI"
    mkdir -p "$BIN_DIR"
    install -m 755 "$SRC_DIR/bin/teyvat-forecast" "$BIN_DIR/teyvat-forecast"
    ok "teyvat-forecast → $BIN_DIR/teyvat-forecast"
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) warn "$BIN_DIR is not in your PATH — add it to use 'teyvat-forecast' anywhere" ;;
    esac

    # 5 ─ Waybar: weather.sh shim + on-click hook ────────────────────────────
    say "Hooking into Waybar"
    if [ -z "$WB_DIR" ]; then
        warn "No Waybar config found (looked in waybar-genshin/ and waybar/)"
        info "skip: hook manually — see README 'Waybar hook'"
    else
        info "Waybar config: $WB_CFG"

        # 5a. weather.sh — backup the original exactly once, then install shim
        if [ ! -f "$WB_WEATHER_SH" ]; then
            mkdir -p "$WB_SCRIPTS_DIR"
            install -m 755 "$SRC_DIR/waybar/weather.sh" "$WB_WEATHER_SH"
            ok "weather.sh installed (no previous script found)"
        elif grep -q "teyvat-forecast shim" "$WB_WEATHER_SH" 2>/dev/null; then
            install -m 755 "$SRC_DIR/waybar/weather.sh" "$WB_WEATHER_SH"
            ok "weather.sh updated (already managed by Teyvat Forecast)"
        else
            cp -n "$WB_WEATHER_SH" "$WB_WEATHER_SH.teyvat-orig.bak" 2>/dev/null
            state_set weather_backup "\"$WB_WEATHER_SH.teyvat-orig.bak\""
            install -m 755 "$SRC_DIR/waybar/weather.sh" "$WB_WEATHER_SH"
            ok "original weather.sh backed up → weather.sh.teyvat-orig.bak"
            ok "shared-cache shim installed (same output format as before)"
        fi

        # 5b. config.jsonc — surgical on-click edit with backup
        state_set waybar_config "\"$WB_CFG\""
        PREV="$(python3 "$SRC_DIR/tools/waybar_edit.py" get "$WB_CFG" | jq -r '.value // ""')"
        OUT="$(python3 "$SRC_DIR/tools/waybar_edit.py" set "$WB_CFG" "$CLICK_CMD")"
        if [ "$(echo "$OUT" | jq -r '.ok')" != "true" ]; then
            warn "could not edit $WB_CFG ($(echo "$OUT" | jq -r '.error'))"
            info "add this key inside the \"custom/weather\" block yourself:"
            info "  \"on-click\": \"$CLICK_CMD\""
        elif [ "$(echo "$OUT" | jq -r '.changed')" = "true" ]; then
            cp "$WB_CFG" "$WB_CFG.teyvat.bak"
            state_set waybar_backup "\"$WB_CFG.teyvat.bak\""
            [ -n "$PREV" ] && state_set prev_on_click "$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$PREV")"
            ok "on-click added to custom/weather (backup: config.jsonc.teyvat.bak)"
        else
            ok "on-click already correct — nothing changed"
        fi
        info "restart Waybar (your usual reload keybind) so it picks up the click hook"
    fi

    # 6 ─ element icons + Paimon avatar from your theme ──────────────────────
    say "Theme integration"
    if [ -n "$WB_DIR" ] && [ -d "$WB_DIR" ]; then
        for el in hydro pyro cryo electro anemo geo dendro; do
            hit="$(find "$WB_DIR" -type f \( -iname "*${el}*" \) \( -iname '*.svg' -o -iname '*.png' \) 2>/dev/null | head -1)"
            if [ -n "$hit" ]; then
                ext="${hit##*.}"; ext="${ext,,}"
                cp "$hit" "$QS_DIR/assets/elements/${el}.user.${ext}"
                ok "$el: using your theme icon ($(basename "$hit"))"
            else
                info "$el: no theme icon found — bundled emblem in use"
            fi
        done
        paimon="$(find "$WB_DIR" -type f \( -iname 'paimon*' \) \( -iname '*.svg' -o -iname '*.png' -o -iname '*.webp' \) 2>/dev/null | head -1)"
        if [ -n "$paimon" ]; then
            ext="${paimon##*.}"; ext="${ext,,}"
            cp "$paimon" "$QS_DIR/assets/avatars/paimon.user.${ext}"
            ok "Paimon avatar: using your theme's $(basename "$paimon")"
        else
            info "Paimon avatar: none found in theme — the line shows without an avatar"
        fi
    else
        info "skipped (no Waybar theme dir found)"
    fi

    # 7 ─ systemd user timer (refresh every 12 min) ──────────────────────────
    say "Refresh timer (systemd user units)"
    if command -v systemctl >/dev/null 2>&1; then
        mkdir -p "$SYSTEMD_DIR"
        install -m 644 "$SRC_DIR/systemd/teyvat-forecast-fetch.service" "$SYSTEMD_DIR/"
        install -m 644 "$SRC_DIR/systemd/teyvat-forecast-fetch.timer" "$SYSTEMD_DIR/"
        systemctl --user daemon-reload
        systemctl --user enable --now teyvat-forecast-fetch.timer >/dev/null 2>&1 \
            && ok "timer enabled (fetch every 12 min)" \
            || warn "could not enable timer (no systemd user session?) — the Waybar shim self-heals instead"
    else
        warn "systemctl not found — skipping timer"
        info "the Waybar shim re-fetches on its own when the cache is >25 min old"
    fi

    # 8 ─ first fetch ────────────────────────────────────────────────────────
    say "Fetching first weather data"
    if python3 "$TF_CONF_DIR/teyvat-fetch.py" fetch >/dev/null 2>&1; then
        ok "weather data cached ($(python3 "$TF_CONF_DIR/teyvat-fetch.py" status | sed -n 2p | sed 's/^ *city: *//'))"
    else
        warn "first fetch failed (offline?) — the popup will show a friendly error and self-heal"
    fi

    # 9 ─ autostart instructions ─────────────────────────────────────────────
    say "Done! Final steps (manual)"
    cat <<EOF

  1) Start the popup shell now:
       ${C_BOLD}teyvat-forecast start${C_OFF}     (or:  qs -c teyvat-forecast)

  2) Autostart it with Hyprland — in your ${C_BOLD}hyprland.lua${C_OFF}:

       ${C_DIM}-- preferred (verified pattern for Hyprland 0.55+/0.56 Lua configs):${C_OFF}
       hl.on("hyprland.start", function()
           hl.exec_cmd("qs -c teyvat-forecast")
       end)

       ${C_DIM}-- universal fallback that always works in a Lua config:${C_OFF}
       os.execute("qs -c teyvat-forecast &")

       ${C_DIM}-- plain-syntax equivalent, if you still have a hyprland.conf:${C_OFF}
       exec-once = qs -c teyvat-forecast

  3) Restart Waybar so the click hook activates.

  4) Click the weather module in your bar. Enjoy, Traveler!
     Preview every scene:  teyvat-forecast --preview storm
EOF
}

# ════════════════════════════════════════════════════════════════════════════
# uninstall
# ════════════════════════════════════════════════════════════════════════════
do_uninstall() {
    purge="${1:-}"

    say "Stopping the Quickshell shell"
    (command -v qs >/dev/null 2>&1 && qs ipc call teyvat quit >/dev/null 2>&1 && ok "shell stopped") \
        || info "shell not running"

    say "Removing the refresh timer"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now teyvat-forecast-fetch.timer >/dev/null 2>&1
        rm -f "$SYSTEMD_DIR/teyvat-forecast-fetch.service" \
              "$SYSTEMD_DIR/teyvat-forecast-fetch.timer"
        systemctl --user daemon-reload >/dev/null 2>&1
        ok "timer removed"
    fi

    say "Restoring your Waybar setup"
    WB_CFG="$(state_get waybar_config)"
    if [ -n "$WB_CFG" ] && [ -f "$WB_CFG" ]; then
        PREV="$(state_get prev_on_click)"
        if [ -n "$PREV" ]; then
            python3 "$SRC_DIR/tools/waybar_edit.py" set "$WB_CFG" "$PREV" >/dev/null \
                && ok "on-click restored to your previous value"
        else
            python3 "$SRC_DIR/tools/waybar_edit.py" remove "$WB_CFG" >/dev/null \
                && ok "on-click key removed from custom/weather"
        fi
        info "your keys and all other modules were never touched"
    else
        info "no recorded Waybar config — nothing to restore"
    fi

    WSH_BACKUP="$(state_get weather_backup)"
    if [ -n "$WSH_BACKUP" ] && [ -f "$WSH_BACKUP" ]; then
        cp "$WSH_BACKUP" "${WSH_BACKUP%.teyvat-orig.bak}"
        ok "original weather.sh restored"
    elif [ -f "$WB_WEATHER_SH" ] && grep -q "teyvat-forecast shim" "$WB_WEATHER_SH" 2>/dev/null; then
        warn "shim found but no backup — restore your weather.sh from your dotfiles"
    else
        info "weather.sh untouched"
    fi

    say "Removing files"
    rm -rf "$QS_DIR"
    rm -f "$BIN_DIR/teyvat-forecast"
    ok "removed: $QS_DIR"
    ok "removed: $BIN_DIR/teyvat-forecast"

    if [ "$purge" = "--purge" ]; then
        rm -rf "$TF_CONF_DIR" "$TF_CACHE_DIR"
        ok "purged: $TF_CONF_DIR and $TF_CACHE_DIR"
    else
        info "kept your config + cache: $TF_CONF_DIR (delete manually or use --purge)"
    fi

    ok "Uninstalled. Restart Waybar to finish. Goodbye, Traveler."
}

# ════════════════════════════════════════════════════════════════════════════
usage() {
    cat <<'EOF'
Teyvat Forecast installer

  install.sh --deps-check   check dependencies, change nothing
  install.sh --install      install / update (idempotent, safe to re-run)
  install.sh --uninstall    remove everything and restore modified files
  install.sh --purge        uninstall + delete ~/.config/teyvat-forecast
                            and ~/.cache/teyvat-forecast as well
EOF
}

case "${1:---help}" in
    --deps-check) deps_check ;;
    --install)    do_install ;;
    --uninstall)  do_uninstall "" ;;
    --purge)      do_uninstall "--purge" ;;
    -h|--help|*)  usage ;;
esac
