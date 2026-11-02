#!/usr/bin/env bash
# خروجی: یک PNG با اندازه‌ی 920x232 (نمایش 460x116 روی صفحه، دو برابر برای وضوح)
KIND="${1:-vol}"
PCT="${2:-0}"
ICONS="$HOME/.config/dunst-genshin/icons"
CACHE="$HOME/.cache/osd-genshin"
mkdir -p "$CACHE"

[ "$PCT" -gt 100 ] 2>/dev/null && PCT=100
[ "$PCT" -lt 0 ] 2>/dev/null && PCT=0

OUT="$CACHE/$KIND-$PCT.png"
[ -s "$OUT" ] && { echo "$OUT"; exit 0; }

# ── رنگ و متن هر عنصر ──
VALMAIN="$PCT"; VALSUF="%"; ICON_NAME="volume"
case "$KIND" in
    vol)  ACC="#74c2a8"; TITLE="VOICE OF TEYVAT"; SUB="Anemo resonance  ·  wind current output" ;;
    mute) ACC="#90e0ef"; TITLE="VOICE OF TEYVAT"; SUB="Cryo seal  ·  elemental resonance silenced"
          VALMAIN="Sealed"; VALSUF=""; ICON_NAME="muted" ;;
    bri)  ACC="#fab632"; TITLE="SACRED LIGHT";    SUB="Geo  ·  Celestia luminescence"; ICON_NAME="brightness" ;;
    *)    ACC="#d3bc8e"; TITLE="TEYVAT"; SUB="" ;;
esac

# ── پیدا کردن مدال (custom اولویت دارد) و embed کردن به‌صورت data-URI ──
ICON_FILE=""
for f in "$ICONS/custom/$ICON_NAME.png" "$ICONS/$ICON_NAME.png" "$ICONS/$ICON_NAME.svg"; do
    [ -f "$f" ] && { ICON_FILE="$f"; break; }
done
ICON_IMG=""
if [ -n "$ICON_FILE" ]; then
    case "$ICON_FILE" in *.svg) MIME="image/svg+xml" ;; *) MIME="image/png" ;; esac
    B64=$(base64 -w0 "$ICON_FILE")
    ICON_IMG="<image x=\"20\" y=\"16\" width=\"84\" height=\"84\" xlink:href=\"data:$MIME;base64,$B64\"/>"
fi

# ── موقعیت اسلایدر: از x=124 تا x=426 ──
FX=$(awk -v p="$PCT" 'BEGIN{printf "%.1f", 124 + p*3.02}')
FILL=""; GLOW=""
if [ "$KIND" != "mute" ] && [ "$PCT" -gt 0 ]; then
    GLOW="<line x1=\"124\" y1=\"74\" x2=\"$FX\" y2=\"74\" stroke=\"$ACC\" stroke-width=\"8\" stroke-linecap=\"round\" opacity=\"0.55\" filter=\"url(#blur)\"/>"
    FILL="<line x1=\"124\" y1=\"74\" x2=\"$FX\" y2=\"74\" stroke=\"url(#fill)\" stroke-width=\"2.8\" stroke-linecap=\"round\"/>"
fi

# اندازه‌ی عدد: «Sealed» کوچکتر از اعداد
if [ "$KIND" = "mute" ]; then VALSIZE=22; VALX=426; else VALSIZE=30; VALX=414; fi

SVG_FILE="$CACHE/$KIND-$PCT.svg"
cat > "$SVG_FILE" << SVG
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 460 116" width="460" height="116"
     font-family="Marcellus, Cinzel, 'Cormorant Garamond', 'Trajan Pro', 'Noto Serif', 'DejaVu Serif', serif">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0"    stop-color="#2b3145" stop-opacity="0"/>
      <stop offset="0.10" stop-color="#2b3145" stop-opacity="0.93"/>
      <stop offset="0.90" stop-color="#2b3145" stop-opacity="0.93"/>
      <stop offset="1"    stop-color="#2b3145" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0"    stop-color="#d3bc8e" stop-opacity="0"/>
      <stop offset="0.22" stop-color="#d3bc8e" stop-opacity="0.95"/>
      <stop offset="0.78" stop-color="#d3bc8e" stop-opacity="0.95"/>
      <stop offset="1"    stop-color="#d3bc8e" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="fill" gradientUnits="userSpaceOnUse" x1="124" y1="0" x2="426" y2="0">
      <stop offset="0" stop-color="#d3bc8e"/>
      <stop offset="1" stop-color="$ACC"/>
    </linearGradient>
    <radialGradient id="aura" cx="62" cy="58" r="46" gradientUnits="userSpaceOnUse">
      <stop offset="0.55" stop-color="$ACC" stop-opacity="0.28"/>
      <stop offset="1"    stop-color="$ACC" stop-opacity="0"/>
    </radialGradient>
    <filter id="blur" x="-20%" y="-400%" width="140%" height="900%"><feGaussianBlur stdDeviation="3"/></filter>
  </defs>

  <!-- بدنه‌ی تیره‌ی محو شونده، مثل نوتیف‌های داخل بازی -->
  <rect x="0" y="6" width="460" height="104" fill="url(#bg)"/>

  <!-- خطوط طلایی بالا و پایین + لوزی وسط -->
  <rect x="14" y="9.5"   width="432" height="1.2" fill="url(#rule)"/>
  <rect x="14" y="105.5" width="432" height="1.2" fill="url(#rule)"/>
  <polygon points="230,5.5 235,10 230,14.5 225,10"   fill="#d3bc8e"/>
  <polygon points="230,101.5 235,106 230,110.5 225,106" fill="#d3bc8e"/>
  <polygon points="230,8 232.2,10 230,12 227.8,10"   fill="#2b3145"/>
  <polygon points="230,104 232.2,106 230,108 227.8,106" fill="#2b3145"/>

  <!-- مدال عنصر -->
  <circle cx="62" cy="58" r="46" fill="url(#aura)"/>
  $ICON_IMG

  <!-- عنوان و مقدار -->
  <text x="124" y="42" font-size="12.5" letter-spacing="3.2" fill="#d3bc8e">$TITLE</text>
  <text x="$VALX" y="50" text-anchor="end" font-size="$VALSIZE" fill="#ece5d8">$VALMAIN</text>
  <text x="418" y="50" font-size="15" fill="#d3bc8e">$VALSUF</text>

  <!-- اسلایدر شبیه منوی Settings بازی: خط نازک + دسته‌ی لوزی -->
  <line x1="124" y1="74" x2="426" y2="74" stroke="#ece5d8" stroke-opacity="0.22" stroke-width="2" stroke-linecap="round"/>
  <g fill="#ece5d8" fill-opacity="0.38">
    <polygon points="124,70.5 127.5,74 124,77.5 120.5,74"/>
    <polygon points="199.5,71 202.5,74 199.5,77 196.5,74"/>
    <polygon points="275,71 278,74 275,77 272,74"/>
    <polygon points="350.5,71 353.5,74 350.5,77 347.5,74"/>
    <polygon points="426,70.5 429.5,74 426,77.5 422.5,74"/>
  </g>
  $GLOW
  $FILL
  <circle cx="$FX" cy="74" r="12" fill="$ACC" opacity="0.22" filter="url(#blur)"/>
  <polygon points="$FX,64.5 $(awk -v x="$FX" 'BEGIN{printf "%.1f",x+8.5}'),74 $FX,83.5 $(awk -v x="$FX" 'BEGIN{printf "%.1f",x-8.5}'),74" fill="#ece5d8" stroke="$ACC" stroke-width="1.8" stroke-linejoin="round"/>
  <polygon points="$FX,69.5 $(awk -v x="$FX" 'BEGIN{printf "%.1f",x+4.5}'),74 $FX,78.5 $(awk -v x="$FX" 'BEGIN{printf "%.1f",x-4.5}'),74" fill="$ACC"/>

  <!-- توضیح کوچک -->
  <text x="124" y="97" font-size="11" font-style="italic" letter-spacing="0.6" fill="#ece5d8" fill-opacity="0.55">$SUB</text>
</svg>
SVG

if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w 920 -h 232 "$SVG_FILE" -o "$OUT" 2>/dev/null
elif command -v magick >/dev/null 2>&1; then
    magick -background none -density 192 "$SVG_FILE" -resize 920x232 "$OUT" 2>/dev/null
fi
rm -f "$SVG_FILE"
[ -s "$OUT" ] && echo "$OUT"
