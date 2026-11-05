import QtQuick
import "../.."

// FogScene — five layered fog bands, each with its own width, speed,
// direction, opacity breathing and a gentle vertical bob (via a Translate
// transform, so the y binding stays intact). Speeds differ enough that the
// layers visibly shear against each other.
Item {
    id: root

    property bool running: false

    Repeater {
        model: 5

        delegate: Image {
            id: band
            required property int index

            source: "../../assets/sprites/fog.png"
            width: root.width * (1.25 + 0.12 * band.index)
            height: 78 + band.index * 18
            y: [-0.02, 0.18, 0.38, 0.58, 0.74][band.index] * root.height
            fillMode: Image.Stretch
            smooth: true

            // opacity = per-band base × animated breathing
            readonly property real baseOp: [0.40, 0.50, 0.42, 0.55, 0.48][band.index]
            property real breath: 1
            opacity: baseOp * breath

            SequentialAnimation on breath {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { to: 0.68; duration: [9000, 12000, 8000, 13000, 10000][band.index]; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: [9000, 12000, 8000, 13000, 10000][band.index]; easing.type: Easing.InOutSine }
            }

            // horizontal drift: ping-pong (no jump when the loop restarts),
            // alternating directions, varied speeds. The travel is capped at
            // (band width - card width), so a band's edge never slides into
            // view — the old fixed 40 % shift exposed a hard edge on the
            // narrower bands.
            readonly property real travel: width - root.width
            SequentialAnimation on x {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation {
                    from: band.index % 2 === 0 ? -band.travel : 0
                    to: band.index % 2 === 0 ? 0 : -band.travel
                    duration: [21000, 33000, 27000, 39000, 24000][band.index]
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    from: band.index % 2 === 0 ? 0 : -band.travel
                    to: band.index % 2 === 0 ? -band.travel : 0
                    duration: [21000, 33000, 27000, 39000, 24000][band.index]
                    easing.type: Easing.InOutSine
                }
            }

            // gentle vertical bob (±5 px) without touching the y binding
            transform: Translate {
                SequentialAnimation on y {
                    running: root.running
                    loops: Animation.Infinite
                    NumberAnimation { from: -4; to: 5; duration: [11000, 14000, 9500, 15000, 12000][band.index]; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 5; to: -4; duration: [11000, 14000, 9500, 15000, 12000][band.index]; easing.type: Easing.InOutSine }
                }
            }
        }
    }
}
