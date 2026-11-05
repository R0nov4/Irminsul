import QtQuick
import "../.."

// CloudsScene — parallax cloud banks:
//   far  : 4 light clouds, small + slow + faint (88-132 s per pass — they
//          are supposed to feel distant)
//   near : 3 DARKER clouds (cloud_dark.png), larger + clearly moving
//          (47-61 s per pass) so the sky never looks frozen
// Each cloud sits at its own phase of the pass when the popup opens, so the
// sky is already populated instead of starting empty and waiting for clouds
// to drift in from the left. Progress `t` (0..1) drives x; the animation
// plays out the rest of the current pass, then loops full passes.
// The element color wash that tints the cloud edges lives in SceneLayer.
Item {
    id: root

    property bool running: false

    // ── far layer (light sprite) ───────────────────────────────────────────
    Repeater {
        model: 4

        delegate: Image {
            id: farCloud
            required property int index

            readonly property real phase: [0.50, 0.15, 0.78, 0.36][farCloud.index]
            readonly property int pass: [95000, 118000, 88000, 132000][farCloud.index]
            property real t: phase

            source: "../../assets/sprites/cloud.png"
            width: 190 + farCloud.index * 40
            height: width * 0.42
            x: -width + t * (root.width + width)
            y: [0.05, 0.30, 0.52, 0.70][farCloud.index] * root.height
            opacity: [0.60, 0.46, 0.54, 0.42][farCloud.index]
            fillMode: Image.Stretch
            smooth: true

            SequentialAnimation {
                running: root.running
                NumberAnimation {
                    target: farCloud; property: "t"
                    from: farCloud.phase; to: 1
                    duration: Math.max(1, farCloud.pass * (1 - farCloud.phase))
                }
                SequentialAnimation {
                    loops: Animation.Infinite
                    NumberAnimation {
                        target: farCloud; property: "t"
                        from: 0; to: 1; duration: farCloud.pass
                    }
                }
            }
        }
    }

    // ── near layer (darker sprite, faster) ─────────────────────────────────
    Repeater {
        model: 3

        delegate: Image {
            id: nearCloud
            required property int index

            readonly property real phase: [0.32, 0.68, 0.08][nearCloud.index]
            readonly property int pass: [52000, 61000, 47000][nearCloud.index]
            property real t: phase

            source: "../../assets/sprites/cloud_dark.png"
            width: 300 + nearCloud.index * 55
            height: width * 0.40
            x: -width + t * (root.width + width)
            y: [0.14, 0.42, 0.66][nearCloud.index] * root.height
            opacity: [0.70, 0.58, 0.64][nearCloud.index]
            fillMode: Image.Stretch
            smooth: true

            SequentialAnimation {
                running: root.running
                NumberAnimation {
                    target: nearCloud; property: "t"
                    from: nearCloud.phase; to: 1
                    duration: Math.max(1, nearCloud.pass * (1 - nearCloud.phase))
                }
                SequentialAnimation {
                    loops: Animation.Infinite
                    NumberAnimation {
                        target: nearCloud; property: "t"
                        from: 0; to: 1; duration: nearCloud.pass
                    }
                }
            }
        }
    }
}
