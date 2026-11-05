import QtQuick
import ".."
import "../components"

// TodayTab — the "scene window" content: a double-width WIND tile with a
// large animated compass, a humidity tile, a four-across detail row, the
// sunrise→sunset arc and the moon phase. All cards are glass (GlassCard)
// so the live weather scene shows through, with staggered entrances.
Flickable {
    id: root

    readonly property real s: Theme.s
    contentWidth: width
    contentHeight: content.height + 8 * s
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    // safe accessors — never null, no startup warnings
    readonly property var cur: WeatherData.current
    readonly property var today: WeatherData.today

    Column {
        id: content
        width: root.width - 8 * root.s
        x: 4 * root.s
        spacing: 8 * root.s

        // ── row 1: wind (double width, big compass) + humidity ───────────
        Row {
            width: parent.width
            spacing: 8 * root.s

            GlassCard {
                id: windTile
                tabIndex: 0
                tabGated: true
                enterIndex: 0
                width: (parent.width - 16 * root.s) / 3 * 2 + 8 * root.s
                height: 88 * root.s
                radius: 12 * root.s

                Image {
                    id: windIcon
                    width: 15 * root.s; height: 15 * root.s
                    x: 10 * root.s; y: 9 * root.s
                    source: "../assets/icons/wind.png"
                    fillMode: Image.PreserveAspectFit
                    smooth: true; mipmap: true
                }
                Text {
                    text: "WIND"
                    color: Theme.creamDim
                    font.family: Theme.fontFamily
                    font.pixelSize: 9 * root.s
                    font.letterSpacing: 1.0
                    anchors.left: windIcon.right
                    anchors.leftMargin: 6 * root.s
                    anchors.verticalCenter: windIcon.verticalCenter
                }

                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: 10 * root.s
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 8 * root.s
                    spacing: 10 * root.s

                    Compass {
                        id: compass
                        width: 54 * root.s; height: 54 * root.s
                        direction: WeatherData.num(root.cur.wind_direction, 0)
                    }

                    Column {
                        spacing: 1 * root.s
                        anchors.verticalCenter: parent.verticalCenter

                        Row {
                            spacing: 4 * root.s
                            Text {
                                id: windSpeedText
                                text: WeatherData.hasData
                                      ? Math.round(WeatherData.num(root.cur.wind_speed, 0)) : "--"
                                color: Theme.cream
                                font.family: Theme.fontFamily
                                font.pixelSize: 21 * root.s
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: WeatherData.windUnit
                                color: Theme.creamDim
                                font.family: Theme.fontFamily
                                font.pixelSize: 10 * root.s
                                anchors.baseline: windSpeedText.baseline
                            }
                        }
                        Text {
                            text: WeatherData.hasData
                                  ? "from " + WeatherData.windDirText(
                                        WeatherData.num(root.cur.wind_direction, 0)) : ""
                            color: Theme.creamDim
                            font.family: Theme.fontFamily
                            font.pixelSize: 10 * root.s
                        }
                        Text {
                            text: WeatherData.hasData
                                  ? "gusts " + Math.round(
                                        WeatherData.num(root.cur.wind_gusts, 0))
                                    + " " + WeatherData.windUnit : ""
                            color: Theme.creamDim
                            font.family: Theme.fontFamily
                            font.pixelSize: 9 * root.s
                        }
                    }
                }
            }

            StatTile {
                tabIndex: 0
                tabGated: true
                enterIndex: 1
                width: (parent.width - 16 * root.s) / 3
                height: 88 * root.s
                icon: "../assets/icons/humidity.png"
                label: "HUMIDITY"
                value: WeatherData.hasData
                       ? WeatherData.num(root.cur.humidity, 0) + "%" : "--"
                sub: WeatherData.hasData && WeatherData.num(root.cur.humidity, 0) >= 70
                      ? "humid" : ""
            }
        }

        // ── row 2: pressure · UV · visibility · precipitation ─────────────
        Row {
            width: parent.width
            spacing: 8 * root.s

            StatTile {
                tabIndex: 0; tabGated: true; enterIndex: 2
                width: (parent.width - 24 * root.s) / 4
                height: 66 * root.s
                icon: "../assets/icons/pressure.png"
                label: "PRESSURE"
                value: WeatherData.hasData
                       ? Math.round(WeatherData.num(root.cur.pressure, 0)) : "--"
                sub: "hPa"
            }
            StatTile {
                tabIndex: 0; tabGated: true; enterIndex: 3
                width: (parent.width - 24 * root.s) / 4
                height: 66 * root.s
                icon: "../assets/icons/uv.png"
                label: "UV INDEX"
                value: WeatherData.hasData
                       ? WeatherData.num(root.cur.uv_index, 0).toFixed(1) : "--"
                sub: WeatherData.hasData ? WeatherData.uvLevel(root.cur.uv_index) : ""
                valueColor: WeatherData.num(root.cur.uv_index, 0) >= 6
                            ? Theme.pyro : Theme.cream
            }
            StatTile {
                tabIndex: 0; tabGated: true; enterIndex: 4
                width: (parent.width - 24 * root.s) / 4
                height: 66 * root.s
                icon: "../assets/icons/visibility.png"
                label: "VISIBILITY"
                value: {
                    if (!WeatherData.hasData) return "--"
                    const m = WeatherData.num(root.cur.visibility_m, 0)
                    return m >= 1000 ? (m / 1000).toFixed(1) + " km"
                                     : Math.round(m) + " m"
                }
                sub: ""
            }
            StatTile {
                tabIndex: 0; tabGated: true; enterIndex: 5
                width: (parent.width - 24 * root.s) / 4
                height: 66 * root.s
                icon: "../assets/icons/precip.png"
                label: "PRECIP."
                value: WeatherData.hasData
                       ? WeatherData.num(root.cur.precipitation, 0).toFixed(1) + " mm" : "--"
                sub: WeatherData.hasData
                      ? WeatherData.num(root.today.precip_prob_max, 0) + "% today" : ""
            }
        }

        // ── sunrise → sunset arc ──────────────────────────────────────────
        GlassCard {
            tabIndex: 0; tabGated: true; enterIndex: 6
            width: parent.width
            height: 132 * root.s

            SunArc {
                anchors.fill: parent
                anchors.margins: 7 * root.s
            }
        }

        // ── moon phase ────────────────────────────────────────────────────
        GlassCard {
            tabIndex: 0; tabGated: true; enterIndex: 7
            width: parent.width
            height: 50 * root.s

            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12 * root.s
                spacing: 10 * root.s

                // drawn moon — exact terminator ellipse (see MoonPhase.qml)
                MoonPhase {
                    width: 30 * root.s; height: 30 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    phase: WeatherData.moonPhase
                    tilt: WeatherData.moonTilt
                    southern: WeatherData.southern
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 1 * root.s
                    Text {
                        text: WeatherData.hasData ? WeatherData.moonName : "--"
                        color: Theme.cream
                        font.family: Theme.fontFamily
                        font.pixelSize: 12.5 * root.s
                    }
                    Text {
                        text: WeatherData.hasData
                              ? WeatherData.moonIllum + "% illuminated" : ""
                        color: Theme.creamDim
                        font.family: Theme.fontFamily
                        font.pixelSize: 10 * root.s
                    }
                    Text {
                        visible: WeatherData.isSupermoon
                        text: "✦ Supermoon"
                        color: Theme.gold
                        font.family: Theme.fontFamily
                        font.pixelSize: 9 * root.s
                    }
                }
            }

            // small ✦-style ornament (drawn, font-independent)
            Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: 16 * root.s
                anchors.verticalCenter: parent.verticalCenter
                width: 7 * root.s; height: 7 * root.s
                radius: 1
                color: Theme.gold
                opacity: 0.7
                rotation: 45
            }
        }
    }
}
