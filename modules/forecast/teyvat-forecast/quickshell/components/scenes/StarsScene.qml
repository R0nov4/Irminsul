import QtQuick
import "../.."
import ".."

// StarsScene — clear-night sky:
//   · vertical sky gradient (deep navy → indigo → faint teal horizon)
//   · ~24-42 individual star items, each with its OWN twinkle phase,
//     duration and size (no more ensemble blinking)
//   · a moon whose glow scales with the REAL illumination % from the data
//     layer, with a phase-accurate crescent shadow
//   · 3 very slow drifting aurora bands (plain gradient rectangles)
//   · a rare shooting star every ~8-15 s
// Only items, gradients and property animations — no Canvas, no shaders,
// no per-frame JS. Everything stops when `running` is false (popup closed).
Item {
    id: root

    property bool running: false
    property int count: 32       // Theme.particles.stars (individual items)

    readonly property color skyDark: "#0a0e1c"   // for the crescent shadow

    // deterministic pseudo-random from the star index: stable layout, no
    // re-randomizing if the scene is ever rebuilt
    function rnd(i, salt) {
        const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453
        return x - Math.floor(x)
    }

    // ── sky gradient ───────────────────────────────────────────────────────
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0;  color: "#0a0e1c" }
            GradientStop { position: 0.55; color: "#131b31" }
            GradientStop { position: 1.0;  color: "#1a2c3e" }
        }
    }

    // ── aurora bands (behind the stars) ────────────────────────────────────
    Repeater {
        model: 3

        delegate: Rectangle {
            id: aurora
            required property int index

            width: root.width * (1.35 + 0.25 * index)
            height: 64 + index * 20
            y: root.height * [0.14, 0.30, 0.46][index]
            x: -root.width * 0.15
            rotation: [-7, 5, -3][index]
            opacity: 0

            readonly property int drift: [34000, 46000, 28000][index]
            readonly property int breathe: [11000, 14000, 9000][index]

            gradient: Gradient {
                GradientStop { position: 0.0;  color: Theme.alpha(Theme.anemo, 0.0) }
                GradientStop {
                    position: 0.45
                    color: aurora.index === 1 ? Theme.alpha(Theme.cryo, 0.10)
                                              : Theme.alpha(Theme.anemo, 0.09)
                }
                GradientStop { position: 1.0;  color: Theme.alpha(Theme.anemo, 0.0) }
            }

            // very slow horizontal drift, back and forth
            SequentialAnimation on x {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation {
                    from: -root.width * 0.25; to: 0
                    duration: aurora.drift; easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    from: 0; to: -root.width * 0.25
                    duration: aurora.drift; easing.type: Easing.InOutSine
                }
            }
            // opacity breathing so the bands feel alive
            SequentialAnimation on opacity {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { from: 0.35; to: 0.8; duration: aurora.breathe; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.8; to: 0.35; duration: aurora.breathe; easing.type: Easing.InOutSine }
            }
        }
    }

    // ── stars — each one twinkles on its own clock ─────────────────────────
    Repeater {
        model: root.count

        delegate: Item {
            id: star
            required property int index

            x: root.rnd(star.index, 1) * root.width
            y: Math.pow(root.rnd(star.index, 2), 1.35) * root.height * 0.9
            width: 5 + root.rnd(star.index, 3) * 10
            height: width
            rotation: root.rnd(star.index, 5) * 45

            // per-star twinkle parameters (lo/hi opacity + two durations)
            readonly property real twLo: 0.22 + root.rnd(star.index, 6) * 0.25
            readonly property real twHi: 0.75 + root.rnd(star.index, 7) * 0.25
            readonly property int dUp: 800 + root.rnd(star.index, 8) * 2600
            readonly property int dDown: 800 + root.rnd(star.index, 9) * 2600

            Image {
                anchors.fill: parent
                source: "../../assets/sprites/star.png"
                fillMode: Image.Stretch
                smooth: true
            }

            SequentialAnimation on opacity {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { to: star.twHi; duration: star.dUp; easing.type: Easing.InOutSine }
                NumberAnimation { to: star.twLo; duration: star.dDown; easing.type: Easing.InOutSine }
            }
            // slight scale pulse, also on its own clock
            SequentialAnimation on scale {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { to: 1.15; duration: star.dDown; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: star.dUp; easing.type: Easing.InOutSine }
            }
        }
    }

    // ── moon: glow scaled by real illumination %, phase-accurate shadow ────
    Item {
        id: moon
        x: root.width - 104
        y: 30
        width: 72
        height: 72

        Image {
            id: moonGlow
            anchors.centerIn: moonDisc
            width: 58 + WeatherData.moonIllum * 0.55
            height: width
            source: "../../assets/sprites/glow.png"
            // brightness follows the real moon phase; `breath` gives it life
            property real breath: 1
            opacity: (0.12 + WeatherData.moonIllum / 100 * 0.42) * breath

            SequentialAnimation on breath {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.78; duration: 3600; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.78; to: 1.0; duration: 3600; easing.type: Easing.InOutSine }
            }
        }

        // exact-terminator moon; the unlit side is a faint ghost, not a
        // painted dark disc (that was the "shadow behind the moon")
        MoonPhase {
            id: moonDisc
            anchors.centerIn: parent
            width: 30
            height: 30
            phase: WeatherData.moonPhase
            tilt: WeatherData.moonTilt
            southern: WeatherData.southern
        }
    }

    // ── shooting star: a randomized Timer + a 0.7 s streak ────────────────
    Item {
        id: streak
        opacity: 0
        rotation: 24                       // travel angle (down-right)

        // bright head
        Rectangle {
            x: -5; y: -5
            width: 10; height: 10
            radius: 5
            color: "#eef2ff"
        }
        // tail: a vertical-gradient rectangle rotated to run horizontally
        Item {
            x: -84; y: -1
            width: 84; height: 2
            Rectangle {
                anchors.centerIn: parent
                width: 2; height: 84
                radius: 1
                rotation: 90
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#eef2ff" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        ParallelAnimation {
            id: shootAnim
            NumberAnimation { id: shootX; target: streak; property: "x"; duration: 680; easing.type: Easing.InQuad }
            NumberAnimation { id: shootY; target: streak; property: "y"; duration: 680; easing.type: Easing.InQuad }
            SequentialAnimation {
                NumberAnimation { target: streak; property: "opacity"; to: 0.95; duration: 90 }
                NumberAnimation { target: streak; property: "opacity"; to: 0.6; duration: 260 }
                NumberAnimation { target: streak; property: "opacity"; to: 0; duration: 330 }
            }
        }
    }

    Timer {
        id: shootTimer
        interval: 8000 + Math.random() * 7000
        running: root.running
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const sx = 30 + Math.random() * root.width * 0.55
            const sy = 14 + Math.random() * root.height * 0.30
            streak.x = sx
            streak.y = sy
            shootX.from = sx
            shootX.to = sx + 175
            shootY.from = sy
            shootY.to = sy + 80
            shootAnim.restart()
            interval = 8000 + Math.random() * 7000
        }
    }
}
