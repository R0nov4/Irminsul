import QtQuick
import ".."

// UvMeter — UV index as an "Original Resin"-style fluid meter (amber fill,
// glowing cap). Purely event-driven except a gentle sheen while open.
Column {
    id: root

    readonly property real s: Theme.s
    // safe accessors — never null, no startup warnings
    readonly property real uv: WeatherData.num(WeatherData.current.uv_index, 0)
    readonly property real uvMax: WeatherData.num(WeatherData.today.uv_max, 0)
    readonly property real frac: Math.min(1, uv / 11)

    spacing: 7 * s

    // header: icon · title (left) · hairline (fills the gap) · value (right)
    // anchored, so the number can never be pushed out of the card
    Item {
        width: parent.width
        height: Math.max(uvTitle.implicitHeight, uvValue.implicitHeight)

        Image {
            id: uvIcon
            width: 16 * s; height: 16 * s
            source: "../assets/icons/uv.png"
            fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: uvTitle
            text: "Original Resin · UV"
            color: Theme.gold
            font.family: Theme.fontFamily
            font.pixelSize: 12 * s
            font.letterSpacing: 0.8
            anchors.left: uvIcon.right
            anchors.leftMargin: 8 * s
            anchors.verticalCenter: parent.verticalCenter
        }
        Rectangle {
            height: 1
            anchors.left: uvTitle.right
            anchors.leftMargin: 8 * s
            anchors.right: uvValue.left
            anchors.rightMargin: 8 * s
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.alpha(Theme.gold, 0.25)
        }
        Text {
            id: uvValue
            text: uv.toFixed(1)
            color: uv >= 8 ? Theme.red : uv >= 6 ? Theme.pyro : Theme.cream
            font.family: Theme.fontFamily
            font.pixelSize: 20 * s
            font.weight: Font.DemiBold
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // resin fluid bar
    Item {
        width: parent.width
        height: 16 * s
        clip: true

        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: Theme.alpha(Theme.bgDeep, 0.8)
            border.color: Theme.alpha(Theme.gold, 0.3)
            border.width: 1
        }

        Rectangle {
            width: Math.max(root.frac > 0 ? 16 * root.s : 0, parent.width * root.frac)
            height: parent.height
            radius: height / 2
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.gold }
                GradientStop { position: 1.0; color: "#f7b652" }
            }
            Behavior on width { NumberAnimation { duration: 500; easing.type: Easing.OutCubic } }

            // sheen
            Rectangle {
                visible: PopupState.open
                width: 22 * root.s; height: parent.height
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.alpha(Theme.cream, 0.0) }
                    GradientStop { position: 0.5; color: Theme.alpha(Theme.cream, 0.22) }
                    GradientStop { position: 1.0; color: Theme.alpha(Theme.cream, 0.0) }
                }
                NumberAnimation on x {
                    running: PopupState.open
                    loops: Animation.Infinite
                    from: -22 * root.s; to: root.width
                    duration: 2200
                }
            }
        }
    }

    Row {
        spacing: 8 * s
        Text {
            text: WeatherData.uvLevel(root.uv)
            color: root.uv >= 8 ? Theme.red : root.uv >= 6 ? Theme.pyro : Theme.cream
            font.family: Theme.fontFamily
            font.pixelSize: 11 * s
            font.bold: true
        }
        Text {
            text: "·  Peak today " + root.uvMax.toFixed(1)
            color: Theme.creamDim
            font.family: Theme.fontFamily
            font.pixelSize: 10 * s
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: {
                if (root.uv >= 11) return "·  Avoid the sun entirely!"
                if (root.uv >= 8) return "·  Sunscreen + shade required"
                if (root.uv >= 6) return "·  Sunscreen recommended"
                if (root.uv >= 3) return "·  Light protection is enough"
                return "·  No protection needed"
            }
            color: Theme.creamDim
            font.family: Theme.fontFamily
            font.pixelSize: 10 * s
            font.italic: true
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
