import QtQuick
import QtQuick.Particles
import "../.."

// RainScene — two parallax rain layers + splashes + mist:
//   far  : small, slow, faint      (≈40 % of the budget)
//   near : larger, faster, brighter (≈60 %)
//   splash: tiny hydro-tinted droplets bouncing off the bottom edge
//           (emitter strip + Gravity affector — pure particle system)
//   mist : one thin fog band drifting along the bottom
// Steady-state counts = emitRate × lifeSpan, so the Theme.particles.rain
// budget is respected. No per-frame JS anywhere.
Item {
    id: root

    property bool running: false
    property int count: 170          // from Theme.particles.rain
    property bool heavy: false       // storm mode: denser, faster, tilted
    property real tilt: 0            // extra degrees of slant (wind)

    readonly property int farCount: Math.round(count * 0.4)
    readonly property int nearCount: count - farCount

    // ── far layer ──────────────────────────────────────────────────────────
    ParticleSystem {
        id: farSys
        running: root.running
    }
    Emitter {
        anchors.fill: parent
        system: farSys
        enabled: root.running
        emitRate: root.farCount / 2.4
        lifeSpan: 2400
        lifeSpanVariation: 600
        size: 18
        sizeVariation: 6
        endSize: 16
        velocity: AngleDirection {
            angle: 94 + root.tilt
            angleVariation: 5
            magnitude: 480
            magnitudeVariation: 90
        }
    }
    ImageParticle {
        system: farSys
        source: "../../assets/sprites/rain.png"
        alpha: 0.30
        autoRotation: true
        rotation: 90                     // sprite is drawn vertical; autoRotation aligns its X axis with the travel direction
    }

    // ── near layer ─────────────────────────────────────────────────────────
    ParticleSystem {
        id: nearSys
        running: root.running
    }
    Emitter {
        anchors.fill: parent
        system: nearSys
        enabled: root.running
        emitRate: (root.nearCount / 1.0) * (root.heavy ? 1.35 : 1.0)
        lifeSpan: 1000
        lifeSpanVariation: 300
        size: 34
        sizeVariation: 10
        endSize: 30
        velocity: AngleDirection {
            angle: 97 + (root.heavy ? 10 : 0) + root.tilt
            angleVariation: 4
            magnitude: root.heavy ? 1400 : 1000
            magnitudeVariation: 240
        }
    }
    ImageParticle {
        system: nearSys
        source: "../../assets/sprites/rain.png"
        alpha: root.heavy ? 0.65 : 0.50
        autoRotation: true
        rotation: 90                     // sprite is drawn vertical; autoRotation aligns its X axis with the travel direction
    }

    // ── splash: droplets kicked up from the bottom edge ────────────────────
    ParticleSystem {
        id: splashSys
        running: root.running
    }
    Emitter {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 3
        system: splashSys
        enabled: root.running
        emitRate: (root.nearCount + root.farCount) * 0.25
        lifeSpan: 480
        lifeSpanVariation: 140
        size: 7
        sizeVariation: 4
        endSize: 2
        velocity: AngleDirection {
            angle: 270 + root.tilt * 0.5     // up, nudged downwind
            angleVariation: 26
            magnitude: 300
            magnitudeVariation: 130
        }
    }
    Gravity {
        system: splashSys
        angle: 90
        magnitude: 1150
    }
    ImageParticle {
        system: splashSys
        source: "../../assets/sprites/glow.png"
        color: "#4cc2f1"                     // hydro tint
        alpha: 0.38
    }

    // ── thin drifting mist near the ground ─────────────────────────────────
    Image {
        anchors { bottom: parent.bottom; bottomMargin: -8 }
        width: parent.width * 1.35
        height: 70
        opacity: 0.13
        source: "../../assets/sprites/fog.png"
        fillMode: Image.Stretch
        smooth: true

        NumberAnimation on x {
            running: root.running
            loops: Animation.Infinite
            from: -parent.width * 0.35; to: 0
            duration: 26000
        }
    }
}
