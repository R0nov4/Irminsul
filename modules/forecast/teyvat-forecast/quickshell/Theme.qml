pragma Singleton
import Quickshell
import QtQuick

// Theme — Genshin Impact UI palette, typography and element system colors.
Singleton {
    id: root

    // ── palette ────────────────────────────────────────────────────────────
    readonly property color bg: "#171b26"           // deep navy
    readonly property color bgDeep: "#12151f"
    readonly property color card: "#1e2433"
    readonly property color cardHover: "#262e42"
    readonly property color gold: "#d3bc8e"          // main accent
    readonly property color goldDim: "#8a7a5c"
    readonly property color cream: "#ece5d8"         // ivory text
    readonly property color creamDim: "#a89f8d"
    readonly property color red: "#c81d2d"           // alerts
    readonly property color track: "#2c3448"

    // ── element colors ────────────────────────────────────────────────────
    readonly property color hydro: "#4cc2f1"
    readonly property color cryo: "#9fd6e3"
    readonly property color electro: "#b380ff"
    readonly property color pyro: "#ef7938"
    readonly property color anemo: "#74c2a8"
    readonly property color geo: "#f7b652"
    readonly property color dendro: "#7bb26e"

    // ── typography ────────────────────────────────────────────────────────
    // Font resolution: config "font" first, then the Genshin web font, then
    // HYWenHei (any weight). Names are matched exactly, then fuzzily (case,
    // spaces and underscores ignored), against the families Qt can actually
    // see — so the UI never silently renders a generic face.
    // Find what your system offers with:  fc-list | grep -i -E "sdk|hywen"
    readonly property string fontFamily: resolveFont()

    function normalizeFamily(name) {
        return String(name).toLowerCase().replace(/[\s_-]/g, "")
    }

    function resolveFont() {
        let families = []
        try {
            families = Qt.fontFamilies()      // real Qt global (docs: Qt QML type)
        } catch (e) {
            families = []
        }
        if (!families || families.length === 0)
            return wantedFont()

        const wanted = wantedFont()
        const candidates = [wanted, "SDK_SC_Web", "HYWenHei"]

        // 1. exact family name
        for (let i = 0; i < candidates.length; i++)
            if (families.indexOf(candidates[i]) !== -1)
                return candidates[i]

        // 2. fuzzy: "SDK SC Web" ≡ "sdk_sc_web", "HYWenHei 85W" ⊃ "hywenhei"
        const normAvail = []
        for (let i = 0; i < families.length; i++)
            normAvail.push(normalizeFamily(families[i]))
        for (let c = 0; c < candidates.length; c++) {
            const nc = normalizeFamily(candidates[c])
            if (nc === "")
                continue
            for (let a = 0; a < normAvail.length; a++) {
                if (normAvail[a].indexOf(nc) !== -1 || nc.indexOf(normAvail[a]) !== -1)
                    return families[a]
            }
        }

        // 3. nothing recognizable — ask Qt for the config name anyway
        //    (fontconfig then substitutes glyphs per-character)
        return wanted
    }

    function wantedFont() {
        return (WeatherData.cfg && WeatherData.cfg.font)
               ? WeatherData.cfg.font : "SDK_SC_Web"
    }


    // ── text cleaning ─────────────────────────────────────────────────────
    // SDK_SC_Web / HYWenHei have no glyphs for transliteration letters such
    // as ṣ ā ū ḥ ẓ ʿ, so Qt borrows them from another font with different
    // size and spacing and the word turns illegible ("Eṣfahānak").
    // clean() maps them to plain Latin ("Esfahanak") before display.
    readonly property var _latinMap: ({
        "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE",
        "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
        "ł": "l", "Ł": "L", "ı": "i", "İ": "I", "þ": "th", "Þ": "Th",
        "ħ": "h", "Ħ": "H", "ŋ": "n", "ʿ": "", "ʾ": "", "ʻ": "", "ʼ": "'"
    })

    // strips diacritics inside Latin-script runs only: Arabic/Persian,
    // Cyrillic, CJK, Hangul etc. are returned exactly as they came
    function _latinRun(t) {
        try {
            t = t.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        } catch (e) {
            // engine without String.normalize: small fallback table
            const pairs = {
                "àáâãäåāăąǎ": "a", "ÀÁÂÃÄÅĀĂĄǍ": "A", "çćĉčċ": "c", "ÇĆĈČĊ": "C",
                "ďđ": "d", "èéêëēĕėęě": "e", "ÈÉÊËĒĔĖĘĚ": "E", "ĝğġģ": "g",
                "ĥħḥ": "h", "ìíîïĩīĭįı": "i", "ÌÍÎÏĨĪĬĮİ": "I", "ĵ": "j",
                "ķ": "k", "ĺļľł": "l", "ñńņň": "n", "ÑŃŅŇ": "N",
                "òóôõöøōŏő": "o", "ÒÓÔÕÖØŌŎŐ": "O", "ŕŗř": "r",
                "śŝşšṣ": "s", "ŚŜŞŠṢ": "S", "ţťṭ": "t", "ùúûüũūŭůűų": "u",
                "ÙÚÛÜŨŪŬŮŰŲ": "U", "ŵ": "w", "ýÿŷ": "y", "źżžẓ": "z", "ŹŻŽẒ": "Z"
            }
            let o = ""
            for (let i = 0; i < t.length; i++) {
                let ch = t[i], rep = ch
                for (const k in pairs) if (k.indexOf(ch) !== -1) { rep = pairs[k]; break }
                o += rep
            }
            t = o
        }
        let o = ""
        for (let i = 0; i < t.length; i++) {
            const ch = t[i]
            o += (_latinMap[ch] !== undefined) ? _latinMap[ch] : ch
        }
        return o
    }

    function clean(text) {
        const t = String(text === undefined || text === null ? "" : text)
        return t.replace(/[A-Za-z\u00C0-\u024F\u02B0-\u02FF\u1E00-\u1EFF]+/g,
                         function (run) { return _latinRun(run) })
    }

    // ── scaling ───────────────────────────────────────────────────────────
    readonly property real s: {
        const v = WeatherData.cfg ? Number(WeatherData.cfg.scale) : 1
        return (v && v >= 0.75 && v <= 1.75) ? v : 1.0
    }

    // ── particle budgets by quality setting ───────────────────────────────
    // stars  = individual star ITEMS in the night scene (not particles)
    // sparkles = golden motes in the clear-day scene
    readonly property var particles: {
        const q = (WeatherData.cfg && WeatherData.cfg.quality) || "medium"
        const budgets = {
            low:    { rain: 90,  snow: 60,  stars: 24, sparkles: 16, wind: 22 },
            medium: { rain: 170, snow: 110, stars: 32, sparkles: 28, wind: 46 },
            high:   { rain: 300, snow: 180, stars: 42, sparkles: 42, wind: 80 }
        }
        return budgets[q] || budgets.medium
    }

    // ── glass card styling (scene shows through the tiles) ────────────────
    readonly property real glassAlpha: 0.40        // 35–45 % per design
    readonly property real glassAlphaStrong: 0.55  // tab bar / larger cards
    readonly property real hairline: 0.22          // gold border at rest
    readonly property real hairlineHover: 0.60     // gold border on hover

    // ── helpers ───────────────────────────────────────────────────────────
    function elementColor(key, windyDefault) {
        // "anemo" doubles as the default/gold element when not actually windy
        if (key === "anemo") return windyDefault ? root.anemo : root.gold
        if (key === "hydro") return root.hydro
        if (key === "cryo") return root.cryo
        if (key === "electro") return root.electro
        if (key === "pyro") return root.pyro
        if (key === "geo") return root.geo
        if (key === "dendro") return root.dendro
        return root.gold
    }

    function elementName(key) {
        const names = { hydro: "Hydro", cryo: "Cryo", electro: "Electro",
                        pyro: "Pyro", anemo: "Anemo", geo: "Geo", dendro: "Dendro" }
        return names[key] || "Anemo"
    }

    // color with alpha helper (avoids Qt.rgba float conversions everywhere)
    function alpha(color, a) {
        return Qt.rgba(color.r, color.g, color.b, a)
    }
}
