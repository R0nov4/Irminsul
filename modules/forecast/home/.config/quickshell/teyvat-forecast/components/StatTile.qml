import QtQuick
import ".."

// StatTile — small glass card with icon, label, value and optional sub-line.
// Used for humidity / pressure / UV / visibility / precipitation.
// The glass look, hover lift and staggered entrance all come from GlassCard.
// (The wind tile is a custom GlassCard too, with a Compass inside.)
//
// Layout: value and sub-line sit side by side when they fit; when the tile is
// too narrow (e.g. "0.0 mm" + "0% today" in the four-across row) the sub-line
// drops UNDER the value instead of overlapping it.
GlassCard {
    id: root

    property string icon: ""
    property string label: ""
    property string value: ""
    property string sub: ""
    property alias valueColor: valueText.color

    readonly property real padX: 10 * s
    // does value + sub fit on one line?
    readonly property bool stacked: root.sub !== ""
        && (valueText.implicitWidth + subText.implicitWidth + 8 * s > root.width - 2 * padX)

    Image {
        id: iconImg
        width: 17 * s; height: 17 * s
        x: 10 * s; y: 9 * s
        source: root.icon
        visible: root.icon !== ""
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }

    Text {
        text: root.label
        color: Theme.creamDim
        font.family: Theme.fontFamily
        font.pixelSize: 9 * s
        font.letterSpacing: 1.0
        anchors.left: iconImg.visible ? iconImg.right : parent.left
        anchors.leftMargin: iconImg.visible ? 7 * s : 10 * s
        anchors.verticalCenter: iconImg.verticalCenter
    }

    Text {
        id: valueText
        text: root.value
        color: Theme.cream
        font.family: Theme.fontFamily
        font.pixelSize: 15 * s
        font.weight: Font.DemiBold
        elide: Text.ElideRight
        width: Math.min(implicitWidth, root.width - 2 * root.padX)
        x: root.padX
        y: root.height - (root.stacked ? 6 * s + subText.height : 8 * s) - height
    }

    Text {
        id: subText
        text: root.sub
        color: Theme.creamDim
        font.family: Theme.fontFamily
        font.pixelSize: 9 * s
        elide: Text.ElideRight
        width: Math.min(implicitWidth, root.width - 2 * root.padX)
        x: root.stacked ? root.padX : root.width - root.padX - width
        y: root.stacked
           ? root.height - 6 * s - height
           : valueText.y + (valueText.height - height) / 2
    }
}
