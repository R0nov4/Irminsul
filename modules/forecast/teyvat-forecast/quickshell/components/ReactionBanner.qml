import QtQuick
import ".."

// ReactionBanner — small animated banner shown only when an elemental
// reaction applies (Electro-Charged, Frozen, Vaporize, Swirl, Overloaded).
Rectangle {
    id: root

    property var reaction: null          // WeatherData.reaction
    readonly property color accent: reaction ? reaction.color : Theme.gold
    readonly property real s: Theme.s

    // sized by the caller (anchored left+right inside the popup)
    height: 34 * s
    radius: 10 * s
    color: Theme.bgDeep
    border.color: Theme.alpha(accent, 0.75)
    border.width: 1

    Rectangle {
        id: pulse
        anchors.fill: parent
        radius: parent.radius
        color: root.accent
        opacity: 0.0
        SequentialAnimation on opacity {
            running: PopupState.open && root.reaction !== null
            loops: Animation.Infinite
            NumberAnimation { from: 0.0; to: 0.10; duration: 1100
                              easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.10; to: 0.0; duration: 1100
                              easing.type: Easing.InOutSine }
        }
    }

    Row {
        anchors.centerIn: parent
        spacing: 10 * s

        // ✦ ornament (drawn: rotated square)
        Rectangle {
            width: 7 * s; height: 7 * s; radius: 1
            color: root.accent
            rotation: 45
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.reaction ? "Elemental Reaction — " + root.reaction.name : ""
            color: Theme.cream
            font.family: Theme.fontFamily
            font.pixelSize: 12.5 * s
            font.letterSpacing: 0.6
            anchors.verticalCenter: parent.verticalCenter
        }

        Rectangle {
            width: 7 * s; height: 7 * s; radius: 1
            color: root.accent
            rotation: 45
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // entrance: slide down + fade in whenever a reaction appears
    opacity: reaction ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
    transform: Translate { y: reaction ? 0 : -8 * s
                             Behavior on y { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } } }
}
