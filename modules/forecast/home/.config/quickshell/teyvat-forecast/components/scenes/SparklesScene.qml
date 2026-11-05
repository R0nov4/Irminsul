import QtQuick
import QtQuick.Particles
import "../.."

// SparklesScene — clear-day ambience:
//   · a soft sun glow at the top of the card
//   · three god rays: long gradient slats leaning from the top edge, each
//     with its own width, tilt and slow opacity breathing (plain rotated
//     Rectangles — a shader-free light shaft)
//   · golden four-point motes drifting upward (particle system; count from
//     Theme.particles.sparkles — raised vs. the old 18-faint-dots look)
Item {
    id: root

    property bool running: false
    property int count: 28

    // ── soft sun glow ──────────────────────────────────────────────────────
    Image {
        x: root.width * 0.60
        y: -64
        width: 210
        height: 210
        source: "../../assets/sprites/glow.png"

        property real breath: 1
        opacity: 0.42 * breath
        SequentialAnimation on breath {
            running: root.running
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.72; duration: 4200; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.72; to: 1.0; duration: 4200; easing.type: Easing.InOutSine }
        }
    }

    // ── god rays ───────────────────────────────────────────────────────────
    Repeater {
        model: 3

        delegate: Rectangle {
            id: ray
            required property int index

            width: [46, 72, 34][ray.index]
            height: root.height * 1.25
            x: root.width * [0.52, 0.66, 0.80][ray.index]
            y: -height * 0.28
            rotation: [14, 22, 30][ray.index]
            transformOrigin: Item.Top

            readonly property real baseOp: [0.55, 0.75, 0.45][ray.index]
            property real breath: 1
            opacity: baseOp * breath

            gradient: Gradient {
                GradientStop { position: 0.0;  color: Theme.alpha(Theme.gold, 0.15) }
                GradientStop { position: 0.5;  color: Theme.alpha(Theme.gold, 0.05) }
                GradientStop { position: 1.0;  color: Theme.alpha(Theme.gold, 0.0) }
            }

            SequentialAnimation on breath {
                running: root.running
                loops: Animation.Infinite
                NumberAnimation { to: 0.55; duration: [6400, 7800, 5600][ray.index]; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: [6400, 7800, 5600][ray.index]; easing.type: Easing.InOutSine }
            }
        }
    }

    // ── golden motes ───────────────────────────────────────────────────────
    ParticleSystem {
        id: sys
        running: root.running
    }
    Emitter {
        anchors.fill: parent
        system: sys
        enabled: root.running
        emitRate: root.count / 6
        lifeSpan: 14000
        lifeSpanVariation: 3000
        size: 4
        sizeVariation: 3
        endSize: 1
        velocity: PointDirection {
            x: 4
            xVariation: 6
            y: -5
            yVariation: 3
        }
    }
    Wander {
        system: sys
        enabled: root.running
        xVariance: 8
        yVariance: 4
        pace: 120
    }
    ImageParticle {
        system: sys
        source: "../../assets/sprites/spark.png"
        color: Theme.gold
        colorVariation: 0.10
        alpha: 0.45
        rotation: 0
        rotationVariation: 20
        autoRotation: false
    }
}
