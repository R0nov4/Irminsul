import QtQuick
import ".."
import "../components"

// AirTab — "Abyssal Corruption" AQI meter + "Original Resin" UV meter,
// with plain-language levels and the four main pollutants. Cards are glass
// (GlassCard) with staggered entrances.
Flickable {
    id: root

    readonly property real s: Theme.s
    // safe accessor — never null
    readonly property var air: WeatherData.air
    readonly property bool airMissing: air.available !== true

    contentWidth: width
    contentHeight: column.height + 8 * s
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
        id: column
        width: root.width - 8 * root.s
        x: 4 * root.s
        spacing: 8 * root.s

        GlassCard {
            tabIndex: 3; tabGated: true; enterIndex: 0
            width: parent.width
            height: 148 * root.s

            AqiMeter {
                anchors.fill: parent
                anchors.margins: 12 * root.s
            }
        }

        GlassCard {
            tabIndex: 3; tabGated: true; enterIndex: 1
            width: parent.width
            height: 118 * root.s

            UvMeter {
                anchors.fill: parent
                anchors.margins: 12 * root.s
            }
        }

        // friendly notice when the air-quality service has no data
        GlassCard {
            tabIndex: 3; tabGated: true; enterIndex: 2
            visible: root.airMissing
            width: parent.width
            height: 64 * root.s
            color: Theme.alpha(Theme.red, 0.08)
            border.color: Theme.alpha(Theme.red, 0.35)
            hoverEnabled: false

            Row {
                anchors.centerIn: parent
                spacing: 10 * root.s

                Image {
                    width: 22 * root.s; height: 22 * root.s
                    source: "../assets/icons/alert.png"
                    fillMode: Image.PreserveAspectFit
                    smooth: true; mipmap: true
                    anchors.verticalCenter: parent.verticalCenter
                }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        text: "Air quality data unavailable"
                        color: Theme.cream
                        font.family: Theme.fontFamily
                        font.pixelSize: 11.5 * root.s
                    }
                    Text {
                        text: root.air && root.air.reason
                              ? root.air.reason
                              : "The air-quality service could not be reached."
                        color: Theme.creamDim
                        font.family: Theme.fontFamily
                        font.pixelSize: 9.5 * root.s
                    }
                }
            }
        }
    }
}
