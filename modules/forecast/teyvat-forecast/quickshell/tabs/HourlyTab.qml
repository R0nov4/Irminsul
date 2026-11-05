import QtQuick
import ".."
import "../components"

// HourlyTab — 24 h temperature curve (gold, glowing, smooth) with
// precipitation-probability bars underneath and a hover tooltip.
// The curve DRAWS IN left→right when the tab is shown: the Canvas is
// painted once per data/size change (never per frame), and the reveal is
// an animated CLIP + a small glow dot riding the reveal edge — pure scene
// graph. The tooltip follows the pointer with a short eased animation.
Item {
    id: root

    readonly property real s: Theme.s
    // safe accessor — never null
    readonly property var hours: WeatherData.hourly
    readonly property int n: hours.length

    // plot area
    readonly property real padL: 26 * s
    readonly property real padR: 26 * s
    readonly property real curveTop: 16 * s
    readonly property real curveBot: 108 * s
    readonly property real precipTop: 124 * s
    readonly property real precipBot: 152 * s
    readonly property real slotW: n > 1 ? (width - padL - padR) / (n - 1) : width

    readonly property real tMin: {
        let m = Infinity
        for (let i = 0; i < n; i++)
            m = Math.min(m, WeatherData.num(hours[i].temp, 0))
        return m === Infinity ? 0 : m
    }
    readonly property real tMax: {
        let m = -Infinity
        for (let i = 0; i < n; i++)
            m = Math.max(m, WeatherData.num(hours[i].temp, 0))
        return m === -Infinity ? 1 : m
    }

    function xAt(i) { return padL + i * slotW }
    function yAt(t) {
        const span = Math.max(1, tMax - tMin)
        return curveBot - ((t - tMin) / span) * (curveBot - curveTop)
    }

    implicitHeight: 200 * s

    onWidthChanged: canvas.requestPaint()
    onNChanged: canvas.requestPaint()
    onHoursChanged: canvas.requestPaint()
    Component.onCompleted: canvas.requestPaint()
    Connections {
        target: WeatherData
        function onWeatherChanged() { canvas.requestPaint() }
    }

    // ── draw-in choreography ──────────────────────────────────────────────
    function startReveal() {
        reveal.width = 0
        revealAnim.restart()
    }
    Connections {
        target: PopupState
        function onOpenChanged() {
            if (PopupState.open && PopupState.tab === 1)
                root.startReveal()
        }
        function onTabChanged() {
            if (PopupState.open && PopupState.tab === 1)
                root.startReveal()
        }
    }

    // clipped reveal window — the canvas itself repaints only on data/size
    Item {
        id: reveal
        anchors { top: parent.top; bottom: parent.bottom; left: parent.left }
        width: n > 1 ? root.width : 0
        clip: true

        Canvas {
            id: canvas
            width: root.width          // full-width canvas inside the clip
            height: root.height
            antialiasing: true

            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                const n = root.n
                if (n < 2) return

                const pts = []
                for (let i = 0; i < n; i++)
                    pts.push(Qt.point(root.xAt(i), root.yAt(root.hours[i].temp)))

                // precipitation bars
                for (let i = 0; i < n; i++) {
                    const p = WeatherData.num(root.hours[i].precip_prob, 0)
                    if (p <= 0) continue
                    const h = (root.precipBot - root.precipTop) * (p / 100)
                    ctx.fillStyle = Theme.alpha(Theme.hydro, 0.22 + 0.5 * p / 100)
                    ctx.beginPath()
                    ctx.roundedRect(pts[i].x - root.slotW * 0.26,
                                    root.precipBot - h,
                                    root.slotW * 0.52, Math.max(2, h), 2, 2)
                    ctx.fill()
                }
                ctx.fillStyle = Theme.alpha(Theme.creamDim, 0.9)
                ctx.font = "9px \"" + Theme.fontFamily + "\""   // quote: family may contain spaces
                ctx.fillText("%", 6 * root.s, root.precipTop + 8 * root.s)

                // temperature curve — Catmull-Rom → cubic béziers
                const drawPath = function () {
                    ctx.beginPath()
                    ctx.moveTo(pts[0].x, pts[0].y)
                    for (let i = 0; i < n - 1; i++) {
                        const p0 = pts[Math.max(0, i - 1)]
                        const p1 = pts[i]
                        const p2 = pts[i + 1]
                        const p3 = pts[Math.min(n - 1, i + 2)]
                        const c1x = p1.x + (p2.x - p0.x) / 6
                        const c1y = p1.y + (p2.y - p0.y) / 6
                        const c2x = p2.x - (p3.x - p1.x) / 6
                        const c2y = p2.y - (p3.y - p1.y) / 6
                        ctx.bezierCurveTo(c1x, c1y, c2x, c2y, p2.x, p2.y)
                    }
                    ctx.stroke()
                }

                // glow pass + main pass
                ctx.lineWidth = 7
                ctx.strokeStyle = Theme.alpha(Theme.gold, 0.16)
                drawPath()
                ctx.lineWidth = 2.2
                ctx.strokeStyle = Theme.gold
                drawPath()

                // dots every 3 hours + "now" marker
                for (let i = 0; i < n; i += 3) {
                    ctx.beginPath()
                    ctx.fillStyle = i === 0 ? WeatherData.elementColor : Theme.cream
                    ctx.arc(pts[i].x, pts[i].y, i === 0 ? 3.6 : 2.4, 0, Math.PI * 2)
                    ctx.fill()
                }
            }
        }

        NumberAnimation {
            id: revealAnim
            target: reveal
            property: "width"
            from: 0
            to: root.width
            duration: 640
            easing.type: Easing.OutCubic
        }

        // glow dot riding the reveal edge while the curve draws in
        Image {
            visible: revealAnim.running
            x: reveal.width - width / 2
            y: (root.curveTop + root.curveBot) / 2 - height / 2
            width: 26 * root.s; height: 26 * root.s
            source: "../assets/sprites/glow.png"
            opacity: 0.7
        }
    }

    // hover interaction (event-driven; no canvas repaint needed)
    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: true
        onPositionChanged: {
            const i = Math.round((mouse.x - root.padL) / root.slotW)
            root.hoverIndex = Math.max(0, Math.min(root.n - 1, i))
        }
        onExited: root.hoverIndex = -1
    }
    property int hoverIndex: -1

    // hairline + highlight
    Rectangle {
        visible: root.hoverIndex >= 0 && root.hoverIndex < root.n
        x: root.xAt(root.hoverIndex) - 0.5
        y: root.curveTop - 6 * root.s
        width: 1
        height: root.precipBot - root.curveTop + 8 * root.s
        color: Theme.alpha(Theme.gold, 0.35)

        Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    }

    // tooltip — follows the pointer with a short eased animation
    Rectangle {
        id: tooltip
        visible: root.hoverIndex >= 0 && root.hoverIndex < root.n
        readonly property var h: root.hoverIndex >= 0 && root.hoverIndex < root.n
            ? root.hours[root.hoverIndex] : null
        x: Math.max(4, Math.min(root.width - width - 4,
                                root.xAt(Math.max(0, root.hoverIndex)) - width / 2))
        y: 2 * root.s
        width: 86 * root.s
        height: 56 * root.s
        radius: 8 * root.s
        color: Theme.alpha(Theme.bgDeep, 0.92)
        border.color: Theme.alpha(Theme.gold, 0.45)
        border.width: 1

        Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

        Column {
            anchors.centerIn: parent
            spacing: 1 * root.s
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: tooltip.h ? tooltip.h.label + ":00" : ""
                color: Theme.creamDim
                font.family: Theme.fontFamily
                font.pixelSize: 9.5 * root.s
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.hoverIndex === 0 ? "NOW" : ""
                color: Theme.gold
                font.family: Theme.fontFamily
                font.pixelSize: 8 * root.s
                font.letterSpacing: 1
                visible: text !== ""
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: tooltip.h ? WeatherData.tempStr(tooltip.h.temp, true) : ""
                color: Theme.cream
                font.family: Theme.fontFamily
                font.pixelSize: 16 * root.s
                font.weight: Font.DemiBold
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: tooltip.h ? "Rain " + WeatherData.num(tooltip.h.precip_prob, 0) + "%" : ""
                color: Theme.hydro
                font.family: Theme.fontFamily
                font.pixelSize: 9.5 * root.s
            }
        }
    }

    // x labels every 3 h
    Row {
        y: root.precipBot + 6 * root.s
        x: root.padL
        spacing: root.slotW * 3 - 26 * root.s
        Repeater {
            model: Math.ceil(root.n / 3)
            Item {
                id: labelSlot
                required property int index
                width: 26 * root.s
                height: 14 * root.s
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    readonly property int slot: labelSlot.index * 3
                    text: slot >= root.n ? "" : (slot === 0 ? "Now" : root.hours[slot].label)
                    color: slot === 0 ? Theme.gold : Theme.creamDim
                    font.family: Theme.fontFamily
                    font.pixelSize: 9 * root.s
                }
            }
        }
    }
}
