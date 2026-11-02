#!/usr/bin/env bash
# Builds dist/genshin-<module>.sh (one self-extracting file per module) and dist/genshin-all.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rm -rf "$REPO/dist"; mkdir -p "$REPO/dist"
pack() {   # name  paths...
  local name=$1; shift
  local out="$REPO/dist/genshin-$name.sh" tgz; tgz=$(mktemp)
  tar -czf "$tgz" -C "$REPO" "$@"
  cat > "$out" <<'HEAD'
#!/usr/bin/env bash
# Genshin theme (__NAME__). Usage: ./genshin-__NAME__.sh [--apply] [--system] [--boot]   (no flags = dry run)
set -e
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
N=$(awk '/^__PAYLOAD__$/{print NR+1; exit}' "$0")
tail -n +"$N" "$0" | tar -xzf - -C "$T"
bash "$T/install.sh" "$@" __ONLY__
exit 0
__PAYLOAD__
HEAD
  if [ "$name" = all ]; then sed -i 's/ __ONLY__//' "$out"; else sed -i "s/__ONLY__/--only $name/" "$out"; fi
  sed -i "s/__NAME__/$name/g" "$out"
  cat "$tgz" >> "$out"; rm -f "$tgz"; chmod +x "$out"
}
for d in "$REPO"/modules/*/; do n=$(basename "$d"); pack "$n" install.sh shell "modules/$n"; done
pack all install.sh doctor.sh shell modules
ls -lh "$REPO/dist"
