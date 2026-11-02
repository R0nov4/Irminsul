#!/usr/bin/env bash
# استفاده:
#   avatar.sh --all              (دانلود موازی و ساخت کارت بیش از ۸۵ کاراکتر جنشین)
#   avatar.sh <character-name>   (مثلاً: furina, arlecchino, mavuika, skirk, capitano, ...)
#   avatar.sh --list             (نمایش تمام کارت‌های موجود)
#   avatar.sh --wall             (ساخت کارت از والپیپر فعلی سیستم)

set -u
FF_DIR="$HOME/.config/fastfetch-genshin"
mkdir -p "$FF_DIR/avatars" "$FF_DIR/cards"

python3 - "$FF_DIR" "${1:---all}" << 'PY'
import os, sys, json, base64, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageOps

ff_dir = sys.argv[1]
arg = sys.argv[2]
avatars_dir = os.path.join(ff_dir, "avatars")
cards_dir = os.path.join(ff_dir, "cards")
LANCZOS = getattr(Image, "Resampling", Image).LANCZOS

# لیست جامع بیش از ۸۵ کاراکتر اصلی Genshin Impact (همراه با ID دقیق سرورهای بازی و المنت)
ROSTER = {
    # Pyro
    "arlecchino": ("Arlecchino", "Pyro"), "mavuika": ("Mavuika", "Pyro"), "hu-tao": ("Hutao", "Pyro"),
    "lyney": ("Liney", "Pyro"), "yoimiya": ("Yoimiya", "Pyro"), "diluc": ("Diluc", "Pyro"),
    "klee": ("Klee", "Pyro"), "dehya": ("Dehya", "Pyro"), "Gaming": ("Gaming", "Pyro"),
    "chevreuse": ("Chevreuse", "Pyro"), "yanfei": ("Feiyan", "Pyro"), "xiangling": ("Xiangling", "Pyro"),
    "bennett": ("Bennett", "Pyro"), "amber": ("Ambor", "Pyro"), "thoma": ("Tohma", "Pyro"),
    "xinyan": ("Xinyan", "Pyro"),
    # Hydro
    "furina": ("Furina", "Hydro"), "neuvillette": ("Neuvillette", "Hydro"), "yelan": ("Yelan", "Hydro"),
    "mualani": ("Mualani", "Hydro"), "sigewinne": ("Sigewinne", "Hydro"), "nilou": ("Nilou", "Hydro"),
    "kokomi": ("Kokomi", "Hydro"), "ayato": ("Ayato", "Hydro"), "tartaglia": ("Tartaglia", "Hydro"),
    "mona": ("Mona", "Hydro"), "xingqiu": ("Xingqiu", "Hydro"), "barbara": ("Barbara", "Hydro"),
    "candace": ("Candace", "Hydro"),
    # Anemo
    "kazuha": ("Kazuha", "Anemo"), "xiao": ("Xiao", "Anemo"), "wanderer": ("Wanderer", "Anemo"),
    "chasca": ("Chasca", "Anemo"), "xianyun": ("Liuyun", "Anemo"), "venti": ("Venti", "Anemo"),
    "jean": ("Qin", "Anemo"), "faruzan": ("Faruzan", "Anemo"), "lynette": ("Linette", "Anemo"),
    "sucrose": ("Sucrose", "Anemo"), "heizou": ("Heizo", "Anemo"), "sayu": ("Sayu", "Anemo"),
    "lanyan": ("Lanyan", "Anemo"), "mizuki": ("Mizuki", "Anemo"), "lumine": ("PlayerGirl", "Anemo"),
    # Electro
    "raiden": ("Shougun", "Electro"), "clorinde": ("Clorinde", "Electro"), "yae": ("Yae", "Electro"),
    "cyno": ("Cyno", "Electro"), "keqing": ("Keqing", "Electro"), "ororon": ("Olorun", "Electro"),
    "sethos": ("Sethos", "Electro"), "fischl": ("Fischl", "Electro"), "beidou": ("Beidou", "Electro"),
    "kuki": ("Shinobu", "Electro"), "sara": ("Sara", "Electro"), "lisa": ("Lisa", "Electro"),
    "razor": ("Razor", "Electro"), "dori": ("Dori", "Electro"), "varesa": ("Varesa", "Electro"),
    "iansan": ("Iansan", "Electro"),
    # Dendro
    "nahida": ("Nahida", "Dendro"), "alhaitham": ("Alhatham", "Dendro"), "kinich": ("Kinich", "Dendro"),
    "emilie": ("Emilie", "Dendro"), "baizhu": ("Baizhuer", "Dendro"), "tighnari": ("Tighnari", "Dendro"),
    "kirara": ("Momoka", "Dendro"), "kaveh": ("Kaveh", "Dendro"), "yaoyao": ("Yaoyao", "Dendro"),
    "collei": ("Collei", "Dendro"),
    # Cryo
    "citlali": ("Citlali", "Cryo"), "wriothesley": ("Wriothesley", "Cryo"), "ayaka": ("Ayaka", "Cryo"),
    "ganyu": ("Ganyu", "Cryo"), "shenhe": ("Shenhe", "Cryo"), "eula": ("Eula", "Cryo"),
    "qiqi": ("Qiqi", "Cryo"), "charlotte": ("Charlotte", "Cryo"), "layla": ("Layla", "Cryo"),
    "rosaria": ("Rosaria", "Cryo"), "kaeya": ("Kaeya", "Cryo"), "diona": ("Diona", "Cryo"),
    "chongyun": ("Chongyun", "Cryo"), "freminet": ("Freminet", "Cryo"), "mika": ("Mika", "Cryo"),
    # Geo
    "zhongli": ("Zhongli", "Geo"), "xilonen": ("Xilonen", "Geo"), "navia": ("Navia", "Geo"),
    "chiori": ("Chiori", "Geo"), "itto": ("Itto", "Geo"), "albedo": ("Albedo", "Geo"),
    "kachina": ("Kachina", "Geo"), "ningguang": ("Ningguang", "Geo"), "noelle": ("Noel", "Geo"),
    "yunjin": ("Yunjin", "Geo"), "gorou": ("Gorou", "Geo"), "aether": ("PlayerBoy", "Geo"),
}

ELEM_COLORS = {
    "Pyro":     ("#ff7b54", "#b83b2b"),
    "Hydro":    ("#4cc2f1", "#1d5c96"),
    "Anemo":    ("#74c2a8", "#2b7a66"),
    "Electro":  ("#b38bd6", "#5e368a"),
    "Dendro":   ("#a5c83b", "#4e6e18"),
    "Cryo":     ("#90e0ef", "#367588"),
    "Geo":      ("#fab632", "#9c6615"),
    "Celestia": ("#d3bc8e", "#6e5835"),
}

def download_avatar(key, char_id):
    dest = os.path.join(avatars_dir, f"{key}.png")
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return dest
    urls = [
        f"https://api.hakush.in/gi/UI/UI_AvatarIcon_{char_id}.png",
        f"https://enka.network/ui/UI_AvatarIcon_{char_id}.png",
        f"https://gi.yatta.moe/assets/UI/UI_AvatarIcon_{char_id}.png",
    ]
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
                if len(data) > 1024:
                    with open(dest, "wb") as f:
                        f.write(data)
                    return dest
        except Exception:
            pass
    return None

def render_card(src_img, out_card, title, elem):
    c1, c2 = ELEM_COLORS.get(elem, ELEM_COLORS["Celestia"])
    b64_data = ""
    if src_img and os.path.exists(src_img):
        try:
            im = Image.open(src_img).convert("RGBA")
            im = ImageOps.fit(im, (520, 520), method=LANCZOS, centering=(0.5, 0.35))
            tmp_p = out_card + ".crop.png"
            im.save(tmp_p, "PNG")
            with open(tmp_p, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("ascii")
            os.remove(tmp_p)
        except Exception:
            b64_data = ""

    if b64_data:
        center_art = f'<image x="75" y="65" width="350" height="350" preserveAspectRatio="xMidYMid slice" clip-path="url(#avatarClip)" xlink:href="data:image/png;base64,{b64_data}"/>'
    else:
        center_art = '<use xlink:href="#spark" transform="translate(250,240) scale(9)" fill="#f4e8c1"/>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 500 540" width="750" height="810"
     font-family="'SDK_SC_Web','HYWenHei-85W','Noto Sans','DejaVu Sans',sans-serif">
  <defs>
    <linearGradient id="cardBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#2c3347"/>
      <stop offset="1" stop-color="#141824"/>
    </linearGradient>
    <radialGradient id="glow" cx="250" cy="240" r="260" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{c1}" stop-opacity="0.42"/>
      <stop offset="0.65" stop-color="{c2}" stop-opacity="0.12"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="fiveStarBg" cx="250" cy="240" r="170" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{c1}" stop-opacity="0.65"/>
      <stop offset="0.6" stop-color="#c98a3e" stop-opacity="0.45"/>
      <stop offset="1" stop-color="#222738" stop-opacity="0.95"/>
    </radialGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fff8e3"/>
      <stop offset="0.5" stop-color="#d3bc8e"/>
      <stop offset="1" stop-color="#9e824c"/>
    </linearGradient>
    <clipPath id="avatarClip"><circle cx="250" cy="240" r="162"/></clipPath>
    <path id="spark" d="M0,-10 C1.5,-3 3,-1.5 10,0 C3,1.5 1.5,3 0,10 C-1.5,3 -3,1.5 -10,0 C-3,-1.5 -1.5,-3 0,-10 Z"/>
  </defs>

  <path d="M42,12 H458 L488,42 V498 L458,528 H42 L12,498 V42 Z" fill="url(#cardBg)" stroke="url(#gold)" stroke-width="4"/>
  <path d="M48,24 H452 L476,48 V492 L452,516 H48 L24,492 V48 Z" fill="url(#glow)" stroke="#d3bc8e" stroke-width="1.2" stroke-opacity="0.5"/>

  <g fill="url(#gold)">
    <use xlink:href="#spark" transform="translate(38,38) scale(1.2)"/>
    <use xlink:href="#spark" transform="translate(462,38) scale(1.2)"/>
    <use xlink:href="#spark" transform="translate(38,502) scale(1.2)"/>
    <use xlink:href="#spark" transform="translate(462,502) scale(1.2)"/>
    <use xlink:href="#spark" transform="translate(190,46) scale(0.9)"/>
    <use xlink:href="#spark" transform="translate(220,42) scale(1.1)"/>
    <use xlink:href="#spark" transform="translate(250,38) scale(1.5)"/>
    <use xlink:href="#spark" transform="translate(280,42) scale(1.1)"/>
    <use xlink:href="#spark" transform="translate(310,46) scale(0.9)"/>
  </g>

  <circle cx="250" cy="240" r="180" fill="none" stroke="#d3bc8e" stroke-width="1.5" stroke-dasharray="8 6" opacity="0.55"/>
  <circle cx="250" cy="240" r="168" fill="url(#fiveStarBg)" stroke="url(#gold)" stroke-width="4.5"/>
  {center_art}
  <circle cx="250" cy="240" r="162" fill="none" stroke="url(#gold)" stroke-width="3.5"/>

  <rect x="110" y="386" width="280" height="42" rx="21" fill="#ece5d8" stroke="url(#gold)" stroke-width="2.5"/>
  <text x="250" y="413" text-anchor="middle" font-size="19" font-weight="bold" letter-spacing="2" fill="#3b4255">Lv. 90  ·  {title.upper()}</text>

  <line x1="70" y1="448" x2="430" y2="448" stroke="#d3bc8e" stroke-width="1.5" opacity="0.55"/>
  <use xlink:href="#spark" transform="translate(250,448) scale(1.1)" fill="#f4e8c1"/>

  <text x="250" y="476" text-anchor="middle" font-size="15.5" font-weight="bold" letter-spacing="2.5" fill="#f4e8c1">AR 60  ·  WL 9  ·  {elem.upper()}</text>
  <rect x="135" y="488" width="230" height="26" rx="13" fill="#141824" stroke="#d3bc8e" stroke-width="1" stroke-opacity="0.6"/>
  <text x="250" y="506" text-anchor="middle" font-size="13" letter-spacing="2" fill="#d3bc8e">UID: 800404999</text>
</svg>"""
    svg_p = out_card + ".svg"
    with open(svg_p, "w", encoding="utf-8") as f:
        f.write(svg)
    subprocess.run(["rsvg-convert", "-w", "750", "-h", "810", svg_p, "-o", out_card], check=True)
    os.remove(svg_p)

if arg == "--list":
    keys = sorted(ROSTER.keys())
    print(f"✦ لیست {len(keys)} کاراکتر آماده:")
    for i in range(0, len(keys), 5):
        print("  " + "  ".join(f"{k:<13}" for k in keys[i:i+5]))
    sys.exit(0)

if arg == "--wall":
    wall = ""
    for w in [
        os.path.expanduser("~/.config/rofi-genshin/art.png"),
        os.path.expanduser("~/.cache/hyde/wall.set"),
        os.path.expanduser("~/.cache/hyde/wall.thmb"),
    ]:
        if os.path.exists(w):
            wall = os.path.realpath(w)
            break
    out = os.path.join(ff_dir, "traveler-card.png")
    render_card(wall, out, "TRAVELER", "Celestia")
    subprocess.run(["cp", "-f", out, os.path.join(ff_dir, "current.png")])
    print("[ok] کارت والپیپر ساخته شد.")
    sys.exit(0)

if arg == "--all":
    def worker(item):
        k, (cid, elem) = item
        out_c = os.path.join(cards_dir, f"{k}.png")
        if os.path.exists(out_c) and os.path.getsize(out_c) > 2048:
            return k, True
        av = download_avatar(k, cid)
        if not av:
            return k, False
        try:
            render_card(av, out_c, k, elem)
            return k, True
        except Exception:
            return k, False

    total = len(ROSTER)
    done = 0
    ok = 0
    print(f"[i] دانلود و رندر موازی {total} کارت کاراکتر Genshin Impact (8x Fast)...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(worker, item) for item in ROSTER.items()]
        for fut in as_completed(futs):
            done += 1
            k, status = fut.result()
            if status:
                ok += 1
            sys.stdout.write(f"\r  ✦ پیشرفت: {done}/{total}  (ساخته شده: {ok} کارت — آخرین: {k:<12})")
            sys.stdout.flush()
    print(f"\n[ok] در مجموع {ok} کارت پروفایل مسافر در {cards_dir} آماده است!")
    sys.exit(0)

# تک کاراکتر یا مسیر فایل دلخواه
k = arg.lower()
if os.path.isfile(arg):
    out = os.path.join(ff_dir, "traveler-card.png")
    render_card(arg, out, "TRAVELER", "Celestia")
    subprocess.run(["cp", "-f", out, os.path.join(ff_dir, "current.png")])
else:
    cid, elem = ROSTER.get(k, (k.capitalize(), "Celestia"))
    av = download_avatar(k, cid)
    out_c = os.path.join(cards_dir, f"{k}.png")
    render_card(av, out_c, k, elem)
    subprocess.run(["cp", "-f", out_c, os.path.join(ff_dir, "traveler-card.png")])
    subprocess.run(["cp", "-f", out_c, os.path.join(ff_dir, "current.png")])
    print(f"[ok] کارت {k.upper()} ساخته و فعال شد.")
PY
