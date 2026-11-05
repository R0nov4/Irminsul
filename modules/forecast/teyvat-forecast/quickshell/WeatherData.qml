pragma Singleton
import Quickshell
import Quickshell.Io
import QtQuick
import "lib/paimon.js" as PaimonLines

// WeatherData — reads config + the shared weather cache written by
// teyvat-fetch.py. The popup NEVER performs network I/O; it only watches
// ~/.cache/teyvat-forecast/weather.json (FileView + inotify) and derives
// everything else reactively.
Singleton {
    id: root

    // ── paths ─────────────────────────────────────────────────────────────
    readonly property string home: Quickshell.env("HOME") || ""
    readonly property string xdgCache: Quickshell.env("XDG_CACHE_HOME")
                                       || (home + "/.cache")
    readonly property string xdgConfig: Quickshell.env("XDG_CONFIG_HOME")
                                        || (home + "/.config")
    readonly property string cachePath: xdgCache + "/teyvat-forecast/weather.json"
    readonly property string fetchScript: xdgConfig + "/teyvat-forecast/teyvat-fetch.py"
    readonly property string cliPath: home + "/.local/bin/teyvat-forecast"

    // ── defaults (mirrors config/config.json) ─────────────────────────────
    readonly property var defaultCfg: ({
        city: "", lat: null, lon: null, units: "metric",
        quality: "medium", refresh_minutes: 12,
        position: { anchor: "top_right", offset_x: 310, offset_y: 54 },
        monitor: "primary", scale: 1.0, font: "SDK_SC_Web",
        show_paimon: true,
        sound: { enabled: false, volume: 40, click: true }
    })

    property var cfg: defaultCfg

    FileView {
        id: cfgFile
        path: xdgConfig + "/teyvat-forecast/config.json"
        watchChanges: true
        blockLoading: true     // docs-recommended pattern for config files
        onFileChanged: this.reload()
        onLoadFailed: { /* keep defaults */ }
    }

    // merge file over defaults (one level deep for object keys)
    readonly property var cfgMerged: {
        const raw = cfgFile.loaded ? parseSafe(cfgFile.text()) : null
        if (raw === null)
            return defaultCfg
        const out = {}
        for (const k in defaultCfg)
            out[k] = (raw[k] === undefined) ? defaultCfg[k] : raw[k]
        const deepKeys = ["position", "sound"]
        for (let i = 0; i < deepKeys.length; i++) {
            const k = deepKeys[i]
            if (raw[k] && typeof raw[k] === "object")
                out[k] = Object.assign({}, defaultCfg[k], raw[k])
        }
        return out
    }
    onCfgMergedChanged: cfg = cfgMerged
    Component.onCompleted: cfg = cfgMerged

    // ── weather cache ─────────────────────────────────────────────────────
    FileView {
        id: wxFile
        path: root.cachePath
        watchChanges: true
        preload: true
        onFileChanged: this.reload()
        onLoadFailed: { /* error UI handles it */ }
    }

    readonly property var parsed: {
        const loaded = wxFile.loaded
        if (!loaded)
            return null
        const txt = wxFile.text()
        if (!txt || txt.length === 0)
            return null
        return parseSafe(txt)
    }

    readonly property var weather: parsed          // null until first parse
    readonly property bool hasData: weather !== null
                                  && weather.current !== undefined
                                  && weather.current !== null
    // "" ok · "missing" no file yet · "parse" malformed json
    readonly property string errorState: !wxFile.loaded ? "missing"
                                         : (parsed === null ? "parse" : "")

    // ── SAFE sub-object views ─────────────────────────────────────────────
    // These can NEVER be null, so bindings like WeatherData.current.temperature
    // never throw — even during the startup frame where `weather` is still
    // null or mid-notification. Missing keys come back as `undefined`, which
    // num()/str() turn into defaults. This is what removes every
    // "Cannot read property of null" warning at startup.
    readonly property var current: (weather && weather.current) || {}
    readonly property var today: (weather && weather.today) || {}
    readonly property var hourly: (weather && weather.hourly) || []
    readonly property var daily: (weather && weather.daily) || []
    readonly property var air: (weather && weather.air) || { "available": false }

    // moon helpers (used by the night scene + Today tab)
    readonly property real moonPhase: num(today.moon_phase, 0.5)   // 0 new · 0.5 full
    readonly property int moonIllum: num(today.moon_illum, 50)     // %
    readonly property string moonName: str(today.moon_name, "--")
    readonly property real moonTilt: num(today.moon_tilt, 0)       // bright-limb tilt (degrees)
    readonly property real moonAge: num(today.moon_age, 0)         // days since new moon
    readonly property int moonDistanceKm: num(today.moon_distance_km, 384400)
    readonly property bool isSupermoon: today.is_supermoon === true

    // location extras (hemisphere flips the lit side of the moon; the UTC
    // offset lets the sun/moon arc use the CITY's clock instead of the PC's)
    readonly property var locInfo: (weather && weather.location) || ({})
    readonly property bool southern: num(locInfo.lat, 0) < 0
    readonly property var utcOffset: (locInfo.utc_offset_seconds === undefined
                                      || locInfo.utc_offset_seconds === null)
                                     ? null : Number(locInfo.utc_offset_seconds)

    // "now" as the selected city's wall-clock time: a Date whose LOCAL fields
    // equal the city's time, so it compares correctly with Open-Meteo's
    // offset-less "2026-11-04T06:41" strings (parsed as local). null offset
    // (preview data / old cache) → plain system time.
    function cityNow() {
        const d = new Date()
        if (utcOffset === null)
            return d
        return new Date(d.getTime() + d.getTimezoneOffset() * 60000 + utcOffset * 1000)
    }

    // Fallback re-check: covers the case where the cache file did not exist
    // when the shell started (so no watch could be established) or the atomic
    // replace slipped past the watcher. Called by a popup-open-gated Timer.
    function poke() { wxFile.reload() }

    // ── safe value helpers (JSON holes: 0 is a VALID value everywhere) ────
    function num(v, d) {
        return (v === undefined || v === null || v === "" || isNaN(v)) ? d : v
    }
    function str(v, d) {
        return (v === undefined || v === null) ? d : v
    }
    function parseSafe(txt) {
        try { return JSON.parse(txt) } catch (e) { return null }
    }

    // ── basics ────────────────────────────────────────────────────────────
    // `tick` gives age-dependent bindings (stale badge, "updated X min ago")
    // something reactive to depend on; Date.now() alone is not reactive.
    property int tick: 0
    Timer {
        interval: 30000
        running: PopupState.open          // zero cost while the popup is closed
        repeat: true
        onTriggered: {
            root.tick++
            if (root.errorState !== "")
                root.poke()
        }
    }
    readonly property real ageMinutes: {
        const _ = tick
        if (!hasData) return 99999
        return Math.max(0, (Date.now() / 1000 - num(weather.fetched_at, 0)) / 60)
    }
    readonly property bool stale: hasData
        && (weather.stale === true || ageMinutes > 30)

    function updatedText() {
        if (!hasData) return ""
        if (ageMinutes < 1) return "Updated just now"
        if (ageMinutes < 60) return "Updated " + Math.floor(ageMinutes) + " min ago"
        return "Updated " + Math.floor(ageMinutes / 60) + " h ago"
    }

    readonly property string city: hasData
        ? str(weather.location ? weather.location.city : "", "") : ""
    readonly property string tempSymbol: hasData
        ? str(weather.units ? weather.units.temperature_symbol : "", "°C") : "°C"
    readonly property string windUnit: hasData
        ? str(weather.units ? weather.units.wind : "", "km/h") : "km/h"

    // ── code tables (same wording as the bar module) ──────────────────────
    function conditionText(code) {
        const map = {
            0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
            56: "Drizzle", 57: "Drizzle", 61: "Rain", 63: "Rain", 65: "Rain",
            66: "Rain", 67: "Rain", 71: "Snow", 73: "Snow", 75: "Snow",
            77: "Snow", 80: "Rain", 81: "Rain", 82: "Rain", 85: "Snow",
            86: "Snow", 95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"
        }
        return map[code] || "Unknown"
    }

    // ── element system ────────────────────────────────────────────────────
    // Priority per spec: thunder→Electro · snow/freezing→Cryo · rain→Hydro ·
    // fog/overcast→Geo · hot(≥32°)clear→Pyro · strong wind(≥35)→Anemo ·
    // humid warm greenery→Dendro · default clear→Anemo/gold.
    readonly property string elementKey: hasData ? computeElement(weather) : "anemo"
    readonly property bool isWindy: hasData && num(weather.current.wind_kmh, 0) >= 35
    // NOTE: computed locally (not via Theme) to keep the singleton
    // dependency chain one-directional: PopupState ← WeatherData ← Theme.
    readonly property color elementColor: elementColorFor(elementKey, isWindy)

    function elementColorFor(key, windy) {
        if (key === "hydro") return "#4cc2f1"
        if (key === "cryo") return "#9fd6e3"
        if (key === "electro") return "#b380ff"
        if (key === "pyro") return "#ef7938"
        if (key === "geo") return "#f7b652"
        if (key === "dendro") return "#7bb26e"
        if (key === "anemo") return windy ? "#74c2a8" : "#d3bc8e"   // default = gold
        return "#d3bc8e"
    }

    function computeElement(w) {
        const c = w.current
        const code = num(c.code, 0)
        const t = num(c.temperature, 15)
        const wind = num(c.wind_kmh, 0)
        const hum = num(c.humidity, 50)
        const precip = num(c.precipitation, 0)
        if (code === 95 || code === 96 || code === 99) return "electro"
        if ((code >= 71 && code <= 77) || code === 85 || code === 86
            || (t <= 0 && precip > 0)) return "cryo"
        if ((code >= 51 && code <= 67) || code === 80 || code === 81
            || code === 82) return "hydro"
        if (code === 45 || code === 48 || code === 3) return "geo"
        if ((code === 0 || code === 1) && t >= 32) return "pyro"
        if (wind >= 35) return "anemo"
        if (hum >= 75 && t >= 20 && (code === 0 || code === 1 || code === 2)) return "dendro"
        return "anemo"
    }

    // ── live scene ────────────────────────────────────────────────────────
    readonly property string sceneKey: hasData ? computeScene(weather) : "clear"
    readonly property bool windOverlay: hasData && num(weather.current.wind_kmh, 0) >= 35

    function computeScene(w) {
        const c = w.current
        const code = num(c.code, 0)
        const day = num(c.is_day, 1) === 1
        if (code === 95 || code === 96 || code === 99) return "storm"
        if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow"
        if ((code >= 51 && code <= 67) || code === 80 || code === 81
            || code === 82) return "rain"
        if (code === 45 || code === 48) return "fog"
        if (code === 2 || code === 3) return "clouds"
        if (!day) return "night"
        if (num(c.temperature, 0) >= 32) return "hot"
        return "clear"
    }

    // ── elemental reactions ───────────────────────────────────────────────
    readonly property var reaction: hasData ? computeReaction(weather) : null

    function computeReaction(w) {
        const c = w.current
        const code = num(c.code, 0)
        const t = num(c.temperature, 15)
        const wind = num(c.wind_kmh, 0)
        const hum = num(c.humidity, 50)
        const storm = code === 95 || code === 96 || code === 99
        const rainy = (code >= 51 && code <= 67) || code === 80 || code === 81 || code === 82
        const snowy = (code >= 71 && code <= 77) || code === 85 || code === 86

        if (storm && t >= 30)
            return { key: "overloaded", name: "Overloaded", color: "#ef7938" }
        if (storm)
            return { key: "electro-charged", name: "Electro-Charged", color: "#b380ff" }
        if ((rainy || snowy) && t <= 2)
            return { key: "frozen", name: "Frozen", color: "#9fd6e3" }
        if (t >= 28 && hum >= 70)
            return { key: "vaporize", name: "Vaporize", color: "#ef7938" }
        if (rainy && wind >= 35)
            return { key: "swirl", name: "Swirl", color: "#74c2a8" }
        return null
    }

    // ── Paimon ────────────────────────────────────────────────────────────
    readonly property string paimonLine: hasData ? PaimonLines.pick(weather, new Date()) : ""

    // ── formatting helpers used across tabs ───────────────────────────────
    function tempStr(v, withSymbol) {
        if (v === undefined || v === null || isNaN(v)) return "--"
        const r = Math.round(v)
        return withSymbol ? r + "°" : String(r)
    }

    function windDirText(deg) {
        const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        if (deg === undefined || deg === null || isNaN(deg)) return "-"
        return dirs[Math.floor(((deg % 360) + 22.5) / 45) % 8]
    }

    function uvLevel(uv) {
        const v = num(uv, 0)
        if (v < 3) return "Low"
        if (v < 6) return "Moderate"
        if (v < 8) return "High"
        if (v < 11) return "Very High"
        return "Extreme"
    }

    function aqiLevel(aqi) {
        const v = num(aqi, 0)
        if (v <= 20) return "Good"
        if (v <= 40) return "Fair"
        if (v <= 60) return "Moderate"
        if (v <= 80) return "Poor"
        if (v <= 100) return "Very Poor"
        return "Extremely Poor"
    }

    function aqiCorruption(aqi) {
        const v = num(aqi, 0)
        if (v <= 20) return "Pure"
        if (v <= 40) return "Faint"
        if (v <= 60) return "Spreading"
        if (v <= 80) return "Malignant"
        if (v <= 100) return "Abyssal"
        return "Cataclysmic"
    }

    // ── actions ───────────────────────────────────────────────────────────
    // Refresh data without network I/O in QML: spawn the data-layer CLI.
    function requestRefresh() {
        Quickshell.execDetached(["python3", fetchScript, "fetch"])
    }
}
