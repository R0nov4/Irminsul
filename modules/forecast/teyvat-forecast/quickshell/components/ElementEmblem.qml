import QtQuick
import Quickshell
import Quickshell.Io
import ".."

// ElementEmblem — the element icon for the current weather, with a soft
// pulsing glow behind it (slow and subtle, only while the popup is open).
// Tries installer-copied theme icons first (assets/elements/<key>.user.*),
// falling back to the bundled vector-drawn PNGs. The theme icons are only
// ever requested after a silent FileView existence probe, so a machine
// without theme icons produces zero QML warnings.
Item {
    id: root

    property string element: "anemo"

    // soft glow behind the emblem — breathes slowly while the popup is open
    Image {
        anchors.centerIn: parent
        width: parent.width * 1.9
        height: parent.height * 1.9
        source: "../assets/sprites/glow.png"

        property real breath: 1
        opacity: 0.22 * breath
        SequentialAnimation on breath {
            running: PopupState.open
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.45; duration: 1500; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.45; to: 1.0; duration: 1500; easing.type: Easing.InOutSine }
        }
    }

    // silent existence probes (printErrors: false → nothing logged when the
    // theme asset is absent; Quickshell.Io FileView)
    FileView {
        id: svgProbe
        path: Quickshell.shellDir + "/assets/elements/" + root.element + ".user.svg"
        printErrors: false
        preload: true
        property bool exists: false
        onLoaded: exists = true
        onLoadFailed: exists = false
    }
    FileView {
        id: pngProbe
        path: Quickshell.shellDir + "/assets/elements/" + root.element + ".user.png"
        printErrors: false
        preload: true
        property bool exists: false
        onLoaded: exists = true
        onLoadFailed: exists = false
    }

    Image {
        id: img
        anchors.fill: parent
        source: svgProbe.exists
                ? "../assets/elements/" + root.element + ".user.svg"
                : (pngProbe.exists
                   ? "../assets/elements/" + root.element + ".user.png"
                   : "../assets/elements/" + root.element + ".png")
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
