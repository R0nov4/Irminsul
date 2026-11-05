import QtQuick
import Quickshell
import Quickshell.Io
import ".."

// PaimonBar — one cheerful, deterministic Paimon line at the bottom, on a
// glass strip. The avatar is optional: an installer-copied theme image is
// used only after a silent existence probe (no "missing file" warnings);
// otherwise a drawn gold star emblem is shown in its place.
GlassCard {
    id: root

    radius: 10 * s
    hoverEnabled: false
    enterIndex: 9          // enters last, after the tab content

    // geometry (width/height/position) is set by the caller; visibility is
    // controlled by the fixed-height wrapper in WeatherPopup so the layout
    // never jumps while this card's entrance opacity animates

    readonly property real bs: Theme.s

    // silent probe for the theme avatar (also re-checked on every popup
    // open, in case the installer copied one in the meantime)
    FileView {
        id: avatarProbe
        path: Quickshell.shellDir + "/assets/avatars/paimon.user.png"
        printErrors: false
        preload: true
        property bool exists: false
        onLoaded: exists = true
        onLoadFailed: exists = false
    }
    Connections {
        target: PopupState
        function onOpenChanged() { if (PopupState.open) avatarProbe.reload() }
    }

    Item {
        id: avatarBox
        width: 28 * root.bs; height: 28 * root.bs
        x: 10 * root.bs
        anchors.verticalCenter: parent.verticalCenter

        // theme avatar (only requested when it actually exists)
        Image {
            id: avatarImg
            anchors.fill: parent
            visible: avatarProbe.exists
            source: avatarProbe.exists ? "../assets/avatars/paimon.user.png" : ""
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
        }

        // drawn fallback: gold-rimmed disc + star sprite
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            visible: !avatarProbe.exists
            color: Theme.alpha(Theme.gold, 0.10)
            border.color: Theme.alpha(Theme.gold, 0.55)
            border.width: 1
            Image {
                anchors.centerIn: parent
                width: parent.width * 0.58; height: width
                source: "../assets/sprites/star.png"
            }
        }
    }

    Rectangle {
        id: ornament
        visible: true
        width: 6 * root.bs; height: 6 * root.bs; radius: 1
        color: Theme.gold
        rotation: 45
        anchors.left: avatarBox.right
        anchors.leftMargin: 9 * root.bs
        anchors.verticalCenter: parent.verticalCenter
    }

    Text {
        anchors.left: ornament.right
        anchors.leftMargin: 9 * root.bs
        anchors.right: parent.right
        anchors.rightMargin: 12 * root.bs
        anchors.verticalCenter: parent.verticalCenter
        text: "\"" + WeatherData.paimonLine + "\""
        color: Theme.creamDim
        font.family: Theme.fontFamily
        font.pixelSize: 11.5 * root.bs
        font.italic: true
        elide: Text.ElideRight
    }
}
