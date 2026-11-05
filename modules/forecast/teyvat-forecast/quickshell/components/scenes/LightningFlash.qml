import QtQuick
import "../.."

// LightningFlash — storm strikes: a randomized Timer fires a short
// double-flicker on a white sky overlay PLUS a jagged bolt silhouette
// (chain of thin rotated rectangles, re-randomized per strike — event JS
// only, nothing per frame) and emits `struck()` so the popup can shake.
// Costs nothing unless the popup is open on a thunderstorm scene.
Item {
    id: root

    property bool active: false

    // the popup connects this to its (subtle) panel-shake animation
    signal struck()

    // ── sky flash overlay ──────────────────────────────────────────────────
    Rectangle {
        id: flash
        anchors.fill: parent
        color: "#e8ecff"
        opacity: 0
    }

    // ── jagged bolt silhouette ─────────────────────────────────────────────
    Item {
        id: bolt
        anchors.fill: parent
        opacity: 0
        visible: opacity > 0.01

        Repeater {
            id: boltRepeater
            model: 6

            delegate: Item {
                id: seg
                required property int index
                width: 9
                height: 60
                transformOrigin: Item.Top          // pivot = start point of the segment

                // outer glow stroke
                Rectangle {
                    anchors.fill: parent
                    radius: 4
                    color: Theme.alpha(Theme.electro, 0.35)
                }
                // bright core stroke
                Rectangle {
                    x: (parent.width - 2.5) / 2
                    width: 2.5
                    height: parent.height
                    radius: 1
                    color: "#f4f6ff"
                }
            }
        }
    }

    // ── strike scheduler ───────────────────────────────────────────────────
    Timer {
        id: strikeTimer
        interval: 2800 + Math.random() * 5200
        running: root.active
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.randomizeBolt()
            boltAnim.restart()
            strikeAnim.restart()
            root.struck()
            interval = 2800 + Math.random() * 5200
        }
    }

    // rebuild the zigzag: a chain of segments where each one starts at the
    // end of the previous, alternating lean. Runs once per strike.
    function randomizeBolt() {
        const segCount = boltRepeater.count
        const segH = root.height * 0.55 / segCount
        let cx = 30 + Math.random() * (root.width - 60)
        let cy = 0
        for (let i = 0; i < segCount; i++) {
            const seg = boltRepeater.itemAt(i)
            if (!seg)
                continue
            const dev = (12 + Math.random() * 22) * (i % 2 === 0 ? 1 : -1)
            const angDeg = Math.atan2(dev, segH) * 180 / Math.PI
            const angRad = angDeg * Math.PI / 180
            seg.height = segH
            seg.x = cx - seg.width / 2
            seg.y = cy
            // QML rotation is clockwise on screen: rotating a downward segment
            // by +a points it LEFT (-sin a). The chain below advances by +sin a,
            // so the angle must be negated or the segments detach from each other.
            seg.rotation = -angDeg
            cx += Math.sin(angRad) * segH
            cy += Math.cos(angRad) * segH
        }
    }

    // ── animations ─────────────────────────────────────────────────────────
    SequentialAnimation {
        id: strikeAnim
        NumberAnimation { target: flash; property: "opacity"; to: 0.75; duration: 60 }
        NumberAnimation { target: flash; property: "opacity"; to: 0.05; duration: 90 }
        NumberAnimation { target: flash; property: "opacity"; to: 0.5;  duration: 70 }
        NumberAnimation { target: flash; property: "opacity"; to: 0.0;  duration: 320
                          easing.type: Easing.OutQuad }
    }
    SequentialAnimation {
        id: boltAnim
        NumberAnimation { target: bolt; property: "opacity"; to: 0.95; duration: 50 }
        NumberAnimation { target: bolt; property: "opacity"; to: 0.2;  duration: 80 }
        NumberAnimation { target: bolt; property: "opacity"; to: 0.8;  duration: 60 }
        NumberAnimation { target: bolt; property: "opacity"; to: 0.0;  duration: 260
                          easing.type: Easing.OutQuad }
    }
}
