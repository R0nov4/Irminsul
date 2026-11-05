import QtQuick
import ".."

// AnimatedNumber — text that pops briefly whenever its value changes
// (the "number tick" for the big temperature). Purely event-driven.
Item {
    id: root

    property string value: ""
    property int pixelSize: 44
    property color color: Theme.cream
    signal changed()

    implicitHeight: label.implicitHeight
    implicitWidth: label.implicitWidth

    onValueChanged: {
        tick.restart()
        root.changed()
    }

    Text {
        id: label
        text: root.value
        color: root.color
        font.family: Theme.fontFamily
        font.pixelSize: root.pixelSize
        font.weight: Font.DemiBold
        anchors.centerIn: parent
    }

    SequentialAnimation {
        id: tick
        ParallelAnimation {
            NumberAnimation { target: label; property: "scale"; to: 1.09; duration: 110
                              easing.type: Easing.OutCubic }
            NumberAnimation { target: label; property: "opacity"; to: 0.55; duration: 110
                              easing.type: Easing.OutCubic }
        }
        ParallelAnimation {
            NumberAnimation { target: label; property: "scale"; to: 1.0; duration: 150
                              easing.type: Easing.InOutCubic }
            NumberAnimation { target: label; property: "opacity"; to: 1.0; duration: 150
                              easing.type: Easing.InOutCubic }
        }
    }
}
