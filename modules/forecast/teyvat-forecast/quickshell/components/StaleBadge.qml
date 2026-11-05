import QtQuick
import ".."

// StaleBadge — red "STALE DATA" pill with a gentle pulse (only while open).
Rectangle {
    id: root

    readonly property real s: Theme.s
    width: staleText.implicitWidth + 22 * s
    height: 20 * s
    radius: height / 2
    color: Theme.alpha(Theme.red, 0.22)
    border.color: Theme.red
    border.width: 1

    Text {
        id: staleText
        anchors.centerIn: parent
        text: "STALE DATA"
        color: Theme.cream
        font.family: Theme.fontFamily
        font.pixelSize: 10 * s
        font.letterSpacing: 1.5
        font.bold: true
    }

    SequentialAnimation on opacity {
        running: PopupState.open
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.55; duration: 900
                          easing.type: Easing.InOutSine }
        NumberAnimation { from: 0.55; to: 1.0; duration: 900
                          easing.type: Easing.InOutSine }
    }
}
