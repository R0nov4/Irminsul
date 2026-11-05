import QtQuick
import ".."

// Compass — wind direction dial. The needle swings to the wind direction
// with a damped SPRING (SpringAnimation with modulus 360, so it always
// takes the shortest wrap-around path and settles with a slight overshoot
// instead of snapping). Sized generously (56 px in the wind tile) with
// large cardinal letters and a readable tick ring.
Item {
    id: root

    property real direction: 0        // meteorological degrees (wind FROM)

    readonly property real s: Theme.s
    readonly property real dialSize: Math.min(width, height)

    // dial face — double ring for depth
    Rectangle {
        anchors.centerIn: parent
        width: root.dialSize
        height: root.dialSize
        radius: width / 2
        color: Theme.alpha(Theme.bgDeep, 0.45)
        border.color: Theme.alpha(Theme.gold, 0.40)
        border.width: 1
    }
    Rectangle {
        anchors.centerIn: parent
        width: root.dialSize - 8 * root.s
        height: width
        radius: width / 2
        color: "transparent"
        border.color: Theme.alpha(Theme.gold, 0.14)
        border.width: 1
    }

    // tick marks — each rotates around the dial center
    Repeater {
        model: 12
        Item {
            required property int index
            anchors.centerIn: parent
            width: 0; height: 0
            rotation: index * 30

            Rectangle {
                x: -width / 2
                y: -(root.dialSize / 2 - 3 * root.s)
                width: index % 3 === 0 ? 2 * root.s : 1.3 * root.s
                height: (index % 3 === 0) ? 8 * root.s : 4.5 * root.s
                color: (index % 3 === 0) ? Theme.gold : Theme.goldDim
                opacity: 0.8
            }
        }
    }

    // cardinal labels
    Text {
        text: "N"; color: Theme.gold; font.family: Theme.fontFamily
        font.pixelSize: 11 * s; font.bold: true
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 5 * s
    }
    Text {
        text: "S"; color: Theme.creamDim; font.family: Theme.fontFamily
        font.pixelSize: 9 * s
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 5 * s
    }
    Text {
        text: "E"; color: Theme.creamDim; font.family: Theme.fontFamily
        font.pixelSize: 9 * s
        anchors.right: parent.right
        anchors.rightMargin: 5 * s
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        text: "W"; color: Theme.creamDim; font.family: Theme.fontFamily
        font.pixelSize: 9 * s
        anchors.left: parent.left
        anchors.leftMargin: 5 * s
        anchors.verticalCenter: parent.verticalCenter
    }

    // needle — points where the wind is GOING (direction + 180°).
    // SpringAnimation: modulus 360 → shortest path across N; damping < 1
    // gives the springy settle.
    Item {
        id: needle
        anchors.centerIn: parent
        width: 0; height: 0
        rotation: root.direction + 180

        Behavior on rotation {
            SpringAnimation {
                spring: 3.2
                damping: 0.34
                mass: 1.1
                modulus: 360
                epsilon: 0.3
            }
        }

        // head — toward where the wind blows
        Rectangle {
            x: -1.7 * s
            y: -(root.dialSize / 2 - 10 * s)
            width: 3.4 * s
            height: root.dialSize / 2 - 10 * s
            radius: 1.7 * s
            color: Theme.gold
        }
        // diamond tip
        Rectangle {
            y: -(root.dialSize / 2 - 7 * s)
            width: 5.5 * s; height: 5.5 * s; radius: 1
            color: Theme.gold
            rotation: 45
            anchors.horizontalCenter: parent.horizontalCenter
        }
        // tail
        Rectangle {
            x: -1.1 * s
            y: 0
            width: 2.2 * s
            height: root.dialSize / 2 - 14 * s
            radius: 1.1 * s
            color: Theme.goldDim
        }
    }

    // pivot
    Rectangle {
        anchors.centerIn: parent
        width: 6 * s; height: 6 * s
        radius: 3 * s
        color: Theme.cream
        Rectangle {
            anchors.centerIn: parent
            width: 2.5 * root.s; height: 2.5 * root.s
            radius: 1.25 * root.s
            color: Theme.bgDeep
        }
    }
}
