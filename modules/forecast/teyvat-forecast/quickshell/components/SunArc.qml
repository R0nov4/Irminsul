import QtQuick
import ".."

// SunArc — sunrise → sunset arc with a sun (day) or moon (night) marker.
//
// SYNC FIX (root cause of "icon ahead of bar / bar ahead of icon after
// changing city; reopening the popup fixes it"):
//
//   Before, the marker and the glowing bar were driven by TWO different
//   things:
//     · marker  → fracShown, animated by fracAnim whose `to:` was a binding
//                 that could still hold the OLD frac when onFracChanged ran
//     · bar     → a Canvas painted once with whatever `frac` was at paint
//                 time, and NEVER repainted when `frac` changed afterwards
//                 (60 s clock tick, a second weather update, …)
//   On top of that `now` was assigned imperatively inside onWeatherChanged,
//   so on a city change `frac` was evaluated first with the NEW city's
//   sunrise/sunset but the OLD city's clock, then again after `now` moved.
//
//   Now there is ONE source of truth:
//     · `now`  is a pure binding (clockTick + the city's UTC offset), so
//              `frac` is always computed from a consistent snapshot
//     · `fracShown` (the animated value) drives BOTH the marker position and
//              the width of the clip that reveals the bar. The bar is the
//              full arc painted once, clipped at the marker's x — so the bar
//              always ends exactly under the icon, whatever the animation or
//              the data are doing. No repaint is needed when frac changes.
Item {
    id: root

    readonly property real s: Theme.s
    readonly property var w: WeatherData.weather
    readonly property bool hasSun: !!(w && w.today && w.today.sunrise)

    // bumped by the 60 s timer and on every popup open; `now` re-evaluates
    // from it. The UTC offset is read inside the binding on purpose: when
    // the city (and so the offset) changes, `now` follows in the SAME
    // binding pass as the sunrise/sunset times.
    property int clockTick: 0
    readonly property date now: {
        const _t = clockTick
        const _o = WeatherData.utcOffset
        return WeatherData.cityNow()
    }

    readonly property date sunrise: hasSun ? new Date(Date.parse(w.today.sunrise)) : new Date()
    readonly property date sunset: hasSun ? new Date(Date.parse(w.today.sunset)) : new Date()
    readonly property bool isNight: {
        if (!hasSun) return false
        return now < sunrise || now > sunset
    }

    // 0..1 along the arc (real position)
    readonly property real frac: {
        if (!hasSun) return 0.5
        if (!isNight) {
            const span = sunset - sunrise
            if (span <= 0) return 0.5
            return Math.max(0, Math.min(1, (now - sunrise) / span))
        }
        // night: approximate the night span with tomorrow's sunrise from daily[1]
        let nightEnd = isNaN(Date.parse(WeatherData.daily && WeatherData.daily[1]
                                        ? WeatherData.daily[1].sunrise : ""))
            ? new Date(sunset.getTime() + 11 * 3600 * 1000)
            : new Date(Date.parse(WeatherData.daily[1].sunrise))
        let nightStart = sunset
        if (now < sunrise) {                     // pre-dawn
            nightStart = new Date(sunset.getTime() - 24 * 3600 * 1000)
            nightEnd = sunrise
        }
        const span = nightEnd - nightStart
        if (span <= 0) return 0.5
        return Math.max(0, Math.min(1, (now - nightStart) / span))
    }

    // the ONE animated value: marker position AND bar length both follow it
    property real fracShown: 0

    // ── geometry: a wide ellipse that fills the card ───────────────────────
    readonly property real padX: 30 * s
    readonly property real cy: height - 30 * s
    readonly property real rx: Math.max(10, (width - 2 * padX) / 2)
    readonly property real ry: Math.max(10, Math.min(cy - 16 * s, 92 * s))
    readonly property real cx: width / 2

    // point along the half-ellipse: f=0 → left horizon, f=1 → right horizon
    function pt(f) {
        const a = Math.PI * (1 - f)
        return Qt.point(cx + rx * Math.cos(a), cy - ry * Math.sin(a))
    }
    readonly property point markerPt: pt(fracShown)

    // glide fracShown to the CURRENT frac. `to` is assigned right here, not
    // bound, so it can never be one update behind.
    function glide() {
        fracAnim.stop()
        if (!PopupState.open) {
            fracShown = frac
            return
        }
        fracAnim.to = frac
        fracAnim.start()
    }

    // callLater coalesces several frac changes in one pass into ONE glide
    // that reads the final value
    onFracChanged: Qt.callLater(glide)

    onWidthChanged: { trackCanvas.requestPaint(); progressCanvas.requestPaint() }
    onHeightChanged: { trackCanvas.requestPaint(); progressCanvas.requestPaint() }
    // the bar colour depends on day/night
    onIsNightChanged: progressCanvas.requestPaint()

    Component.onCompleted: {
        fracShown = frac
        trackCanvas.requestPaint()
        progressCanvas.requestPaint()
    }

    // replay the reveal + marker glide every time the popup opens
    Connections {
        target: PopupState
        function onOpenChanged() {
            fracAnim.stop()
            if (PopupState.open) {
                root.clockTick++                       // fresh clock on open
                if (PopupState.tab === 0) {
                    root.fracShown = 0                 // bar + marker grow from sunrise
                    Qt.callLater(root.glide)
                } else {
                    root.fracShown = root.frac
                }
            } else {
                root.fracShown = root.frac             // closed: stay in sync
            }
        }
    }

    // keep the marker moving while the popup is open
    Timer {
        interval: 60000
        running: PopupState.open
        repeat: true
        onTriggered: root.clockTick++
    }

    // ── static track (dashed horizon + dim full arc + end dots) ────────────
    Canvas {
        id: trackCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            if (root.rx <= 0 || root.ry <= 0)
                return
            const cy = root.cy

            // horizon
            ctx.strokeStyle = Theme.alpha(Theme.creamDim, 0.25)
            ctx.lineWidth = 1
            ctx.setLineDash([4, 4])
            ctx.beginPath()
            ctx.moveTo(root.cx - root.rx - 10, cy)
            ctx.lineTo(root.cx + root.rx + 10, cy)
            ctx.stroke()
            ctx.setLineDash([])

            // full arc (parametric polyline — uniform stroke width)
            ctx.strokeStyle = Theme.alpha(Theme.gold, 0.28)
            ctx.lineWidth = 2.5
            ctx.beginPath()
            for (let i = 0; i <= 48; i++) {
                const p = root.pt(i / 48)
                if (i === 0) ctx.moveTo(p.x, p.y)
                else ctx.lineTo(p.x, p.y)
            }
            ctx.stroke()

            // horizon end dots
            ctx.fillStyle = Theme.alpha(Theme.gold, 0.55)
            const l = root.pt(0), r = root.pt(1)
            ctx.beginPath(); ctx.arc(l.x, l.y, 2.5, 0, Math.PI * 2); ctx.fill()
            ctx.beginPath(); ctx.arc(r.x, r.y, 2.5, 0, Math.PI * 2); ctx.fill()
        }
    }

    // ── glowing path: the FULL arc, painted once, clipped at the marker ────
    // The clip's right edge is the marker's x, so the bar ends exactly under
    // the icon at every frame. x grows monotonically along the half-ellipse,
    // so "clip at x" is the same as "draw up to fracShown".
    Item {
        id: progressReveal
        anchors { top: parent.top; bottom: parent.bottom; left: parent.left }
        width: root.fracShown <= 0.0005 ? 0
             : Math.min(root.width,
                        root.markerPt.x + (root.fracShown >= 0.995 ? 8 * root.s : 0))
        clip: true

        Canvas {
            id: progressCanvas
            width: root.width            // full width even though parent clips
            height: root.height
            antialiasing: true

            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                if (root.rx <= 0 || root.ry <= 0)
                    return

                const steps = 64
                const drawPath = function () {
                    ctx.beginPath()
                    for (let i = 0; i <= steps; i++) {
                        const p = root.pt(i / steps)
                        if (i === 0) ctx.moveTo(p.x, p.y)
                        else ctx.lineTo(p.x, p.y)
                    }
                    ctx.stroke()
                }

                // 3-pass glow: wide halo → mid → bright core
                const progColor = root.isNight ? Theme.cryo : Theme.gold
                ctx.lineCap = "round"
                ctx.strokeStyle = Theme.alpha(progColor, 0.13)
                ctx.lineWidth = 9
                drawPath()
                ctx.strokeStyle = Theme.alpha(progColor, 0.30)
                ctx.lineWidth = 4.5
                drawPath()
                ctx.strokeStyle = progColor
                ctx.lineWidth = 2.2
                drawPath()
            }
        }
    }

    // marker: glows, follows fracShown (same value as the bar's clip)
    Item {
        x: root.markerPt.x - width / 2
        y: root.markerPt.y - height / 2
        width: 40 * root.s
        height: 40 * root.s

        Image {
            anchors.fill: parent
            source: "../assets/sprites/glow.png"
            opacity: root.isNight ? 0.55 : 0.9
        }
        // day: gold sun dot
        Rectangle {
            visible: !root.isNight
            anchors.centerIn: parent
            width: 11 * root.s; height: 11 * root.s
            radius: width / 2
            color: Theme.gold
        }
        // night: the real moon (exact terminator formula, real phase)
        MoonPhase {
            visible: root.isNight
            anchors.centerIn: parent
            width: 15 * root.s; height: 15 * root.s
            phase: WeatherData.moonPhase
            southern: WeatherData.southern
        }
    }

    NumberAnimation {
        id: fracAnim
        target: root
        property: "fracShown"
        duration: 900
        easing.type: Easing.OutCubic
    }

    // sunrise / sunset labels
    Row {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        spacing: 5 * s
        Image {
            width: 15 * s; height: 15 * s
            source: root.isNight ? "../assets/icons/sunset.png"
                                 : "../assets/icons/sunrise.png"
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true
        }
        Text {
            // day: sunrise → sunset.  night: the arc runs sunset → sunrise
            text: root.hasSun ? Qt.formatDateTime(root.isNight ? root.sunset : root.sunrise, "HH:mm") : "--:--"
            color: Theme.creamDim
            font.family: Theme.fontFamily
            font.pixelSize: 10.5 * s
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: 5 * s
        Text {
            text: root.hasSun ? Qt.formatDateTime(root.isNight ? root.sunrise : root.sunset, "HH:mm") : "--:--"
            color: Theme.creamDim
            font.family: Theme.fontFamily
            font.pixelSize: 10.5 * s
            anchors.verticalCenter: parent.verticalCenter
        }
        Image {
            width: 15 * s; height: 15 * s
            source: root.isNight ? "../assets/icons/sunrise.png"
                                 : "../assets/icons/sunset.png"
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true
        }
    }
}
