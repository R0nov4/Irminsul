import QtQuick
import ".."

// AqiMeter — air quality as a Genshin-style "Abyssal Corruption" meter.
// EU AQI drives the 12-segment bar; plain-language level is shown too.
Column {
    id: root

    readonly property real s: Theme.s
    // WeatherData.air is NEVER null ({} / {available:false} fallback), so
    // every binding below is warning-free even before the first data load
    readonly property var air: WeatherData.air
    readonly property bool ok: air.available === true
    readonly property real aqi: ok ? WeatherData.num(air.eu_aqi, 0) : 0
    readonly property int activeSegs: Math.min(12, Math.ceil(aqi / 100 * 12))

    spacing: 7 * s

    // header: title (left) · hairline (fills the gap) · value (right)
    // anchored, so the number can never be pushed out of the card
    Item {
        width: parent.width
        height: Math.max(aqiTitle.implicitHeight, aqiValue.implicitHeight)

        Text {
            id: aqiTitle
            text: "Abyssal Corruption"
            color: Theme.gold
            font.family: Theme.fontFamily
            font.pixelSize: 12 * s
            font.letterSpacing: 0.8
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
        }
        Rectangle {
            height: 1
            anchors.left: aqiTitle.right
            anchors.leftMargin: 8 * s
            anchors.right: aqiValue.left
            anchors.rightMargin: 8 * s
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.alpha(Theme.gold, 0.25)
        }
        Text {
            id: aqiValue
            text: ok ? Math.round(root.aqi) : "--"
            color: root.aqi > 80 ? Theme.red : Theme.cream
            font.family: Theme.fontFamily
            font.pixelSize: 20 * s
            font.weight: Font.DemiBold
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // segmented corruption bar
    Item {
        width: parent.width
        height: 14 * s
        clip: true

        Row {
            spacing: 3 * s
            Repeater {
                model: 12
                Rectangle {
                    required property int index
                    width: (root.width - 11 * 3 * root.s) / 12
                    height: index < root.activeSegs ? 14 * root.s : 10 * root.s
                    y: index < root.activeSegs ? 0 : 2 * root.s
                    radius: 2 * root.s
                    color: index < root.activeSegs ? root.segColor(index)
                                                   : Theme.alpha(Theme.cream, 0.08)
                    Behavior on color { ColorAnimation { duration: 350 } }
                }
            }
        }

        // slow sheen sweep (only while the popup is open)
        Rectangle {
            visible: PopupState.open
            width: 30 * root.s
            height: parent.height
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.alpha(Theme.cream, 0.0) }
                GradientStop { position: 0.5; color: Theme.alpha(Theme.cream, 0.10) }
                GradientStop { position: 1.0; color: Theme.alpha(Theme.cream, 0.0) }
            }
            NumberAnimation on x {
                running: PopupState.open
                loops: Animation.Infinite
                from: -30 * root.s
                to: root.width
                duration: 2600
            }
        }
    }

    Row {
        spacing: 10 * root.s
        Text {
            text: root.ok ? WeatherData.aqiLevel(root.aqi) : "No data for this region"
            color: root.aqi > 80 ? Theme.red : root.aqi > 60 ? Theme.pyro : Theme.cream
            font.family: Theme.fontFamily
            font.pixelSize: 11 * root.s
            font.bold: true
        }
        Text {
            visible: root.ok
            text: "·  " + WeatherData.aqiCorruption(root.aqi) + " corruption"
            color: Theme.creamDim
            font.family: Theme.fontFamily
            font.pixelSize: 10 * root.s
            font.italic: true
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            visible: root.ok && WeatherData.num(root.air.us_aqi, 0) > 0
            text: "·  US AQI " + Math.round(WeatherData.num(root.air.us_aqi, 0))
            color: Theme.creamDim
            font.family: Theme.fontFamily
            font.pixelSize: 10 * root.s
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // main pollutants — values in µg/m³, bars scaled to indicative EU maxima
    Grid {
        width: parent.width
        columns: 2
        rowSpacing: 6 * root.s
        columnSpacing: 8 * root.s

        Repeater {
            model: ListModel {
                ListElement { name: "PM2.5"; key: "pm2_5"; scaleMax: 50 }
                ListElement { name: "PM10";  key: "pm10";  scaleMax: 100 }
                ListElement { name: "O3"; key: "o3";  scaleMax: 160 }
                ListElement { name: "NO2"; key: "no2"; scaleMax: 150 }
            }
            delegate: Row {
                id: pollutantRow
                required property string name
                required property string key
                required property real scaleMax
                width: (root.width - 8 * root.s) / 2
                spacing: 6 * root.s

                Text {
                    text: pollutantRow.name
                    color: Theme.creamDim
                    font.family: Theme.fontFamily
                    font.pixelSize: 10 * root.s
                    width: 38 * root.s
                }
                Text {
                    text: {
                        const v = root.ok ? root.air[pollutantRow.key] : null
                        return (v === null || v === undefined) ? "--" : v.toFixed(1)
                    }
                    color: Theme.cream
                    font.family: Theme.fontFamily
                    font.pixelSize: 10.5 * root.s
                    width: 36 * root.s
                }
                Item {
                    width: pollutantRow.width - 92 * root.s
                    height: 5 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    Rectangle {
                        anchors.fill: parent
                        radius: 2 * root.s
                        color: Theme.alpha(Theme.cream, 0.08)
                    }
                    Rectangle {
                        readonly property real fracv: {
                            const v = root.ok ? root.air[pollutantRow.key] : null
                            if (v === null || v === undefined) return 0
                            return Math.min(1, v / pollutantRow.scaleMax)
                        }
                        width: parent.width * fracv
                        height: parent.height
                        radius: 2 * root.s
                        color: fracv > 0.8 ? Theme.red
                                : fracv > 0.5 ? Theme.pyro : Theme.gold
                        Behavior on width {
                            NumberAnimation { duration: 350; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }
        }
    }

    function segColor(i) {
        if (i < 4) return Theme.dendro
        if (i < 6) return Theme.gold
        if (i < 8) return Theme.pyro
        if (i < 10) return Theme.red
        return Theme.electro
    }
}
