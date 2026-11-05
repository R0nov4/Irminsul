import QtQuick
import QtQuick.Particles
import "../.."

// SnowScene — two parallax snow layers:
//   far  : small, slow, faint flakes drifting almost straight down
//   near : larger, faster, brighter flakes with a gentle horizontal sway
//          (Wander affector) and slow rotation.
// Steady-state counts = emitRate × lifeSpan (Theme.particles.snow budget).
Item {
    id: root

    property bool running: false
    property int count: 110
    property real tilt: 0

    readonly property int farCount: Math.round(count * 0.45)
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
        emitRate: root.farCount / 13.0
        lifeSpan: 13000
        lifeSpanVariation: 3000
        size: 9
        sizeVariation: 5
        endSize: 6
        velocity: AngleDirection {
            angle: 92 + root.tilt * 0.6
            angleVariation: 5
            magnitude: 52
            magnitudeVariation: 24
        }
    }
    ImageParticle {
        system: farSys
        source: "../../assets/sprites/snow.png"
        alpha: 0.35
        rotation: 0
        rotationVariation: 180
        rotationVelocity: 10
        rotationVelocityVariation: 18
    }

    // ── near layer (with sway) ─────────────────────────────────────────────
    ParticleSystem {
        id: nearSys
        running: root.running
    }
    Emitter {
        anchors.fill: parent
        system: nearSys
        enabled: root.running
        emitRate: root.nearCount / 6.0
        lifeSpan: 6000
        lifeSpanVariation: 2000
        size: 20
        sizeVariation: 10
        endSize: 10
        velocity: AngleDirection {
            angle: 94 + root.tilt
            angleVariation: 7
            magnitude: 120
            magnitudeVariation: 48
        }
    }
    Wander {
        system: nearSys
        enabled: root.running
        xVariance: 75
        pace: 480
    }
    ImageParticle {
        system: nearSys
        source: "../../assets/sprites/snow.png"
        alpha: 0.7
        rotation: 0
        rotationVariation: 180
        rotationVelocity: 14
        rotationVelocityVariation: 26
    }
}
