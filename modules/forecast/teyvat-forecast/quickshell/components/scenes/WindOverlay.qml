import QtQuick
import QtQuick.Particles

// WindOverlay — fast horizontal streaks (+ a few leaves) whenever the real
// wind is ≥ 35 km/h. Independent of the base scene, stacks on top of it.
Item {
    id: root

    property bool running: false
    property int count: 46

    ParticleSystem {
        id: sys
        running: root.running
    }

    Emitter {
        height: parent.height
        width: 1
        x: -40
        system: sys
        enabled: root.running
        emitRate: root.count / 1.6
        lifeSpan: 1600
        lifeSpanVariation: 400
        size: 64
        sizeVariation: 28
        endSize: 48
        velocity: AngleDirection {
            angle: 4
            angleVariation: 3
            magnitude: 900
            magnitudeVariation: 260
        }
    }

    ImageParticle {
        system: sys
        source: "../../assets/sprites/wind.png"
        alpha: 0.28
    }

    // occasional leaves tumbling in the wind
    ParticleSystem {
        id: leafSys
        running: root.running
    }
    Emitter {
        height: parent.height
        width: 1
        x: -60
        system: leafSys
        enabled: root.running
        emitRate: 1.6
        lifeSpan: 2600
        lifeSpanVariation: 700
        size: 22
        sizeVariation: 8
        velocity: AngleDirection {
            angle: 8
            angleVariation: 8
            magnitude: 780
            magnitudeVariation: 200
        }
    }
    ImageParticle {
        system: leafSys
        source: "../../assets/sprites/leaf.png"
        alpha: 0.6
        rotation: 0
        rotationVariation: 180
        rotationVelocity: 220
        rotationVelocityVariation: 260
    }
}
