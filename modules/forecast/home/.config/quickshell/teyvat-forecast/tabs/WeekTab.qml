import QtQuick
import ".."
import "../components"

// WeekTab — 7 day cards: icon, min/max temperature and a range bar whose
// fill is positioned within the week's overall min→max span. Cards are
// glass (GlassCard) and enter with a per-card stagger.
Flickable {
    id: root

    readonly property real s: Theme.s
    // safe accessor — never null
    readonly property var days: WeatherData.daily

    // week-wide span for bar normalization
    readonly property real wMin: {
        let m = Infinity
        for (let i = 0; i < days.length; i++)
            m = Math.min(m, WeatherData.num(days[i].t_min, 0))
        return m === Infinity ? 0 : m
    }
    readonly property real wMax: {
        let m = -Infinity
        for (let i = 0; i < days.length; i++)
            m = Math.max(m, WeatherData.num(days[i].t_max, 0))
        return m === -Infinity ? 1 : m
    }

    contentWidth: width
    contentHeight: column.height + 8 * s
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
        id: column
        width: root.width - 8 * root.s
        x: 4 * root.s
        spacing: 6 * root.s

        Repeater {
            model: root.days.length

            delegate: GlassCard {
                id: dayCard
                required property int index
                readonly property var day: root.days[index]

                tabIndex: 2
                tabGated: true
                enterIndex: index
                radius: 10 * root.s
                width: parent.width
                height: 40 * root.s
                color: day.is_today ? Theme.alpha(Theme.gold, 0.10)
                                    : Theme.alpha(Theme.card, Theme.glassAlpha)
                border.color: day.is_today ? Theme.alpha(Theme.gold, 0.55)
                                           : Theme.alpha(Theme.gold, Theme.hairline)

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 10 * root.s
                    anchors.rightMargin: 10 * root.s
                    spacing: 8 * root.s

                    Text {
                        text: dayCard.day.is_today ? "Today" : dayCard.day.label
                        color: dayCard.day.is_today ? Theme.gold : Theme.cream
                        font.family: Theme.fontFamily
                        font.pixelSize: 11.5 * root.s
                        font.bold: dayCard.day.is_today
                        width: 58 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    WeatherIcon {
                        code: dayCard.day.code
                        isDay: 1
                        width: 26 * root.s; height: 26 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: WeatherData.tempStr(dayCard.day.t_min, false) + "°"
                        color: Theme.creamDim
                        font.family: Theme.fontFamily
                        font.pixelSize: 11 * root.s
                        width: 26 * root.s
                        horizontalAlignment: Text.AlignRight
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    // range bar
                    Item {
                        readonly property real span: Math.max(1, root.wMax - root.wMin)
                        readonly property real x0: (dayCard.day.t_min - root.wMin) / span
                        readonly property real x1: (dayCard.day.t_max - root.wMin) / span
                        width: parent.width - 58 * root.s - 26 * root.s - 26 * root.s
                               - 30 * root.s - 32 * root.s - 5 * 8 * root.s
                        height: 6 * root.s
                        anchors.verticalCenter: parent.verticalCenter

                        Rectangle {
                            anchors.fill: parent
                            radius: height / 2
                            color: Theme.alpha(Theme.cream, 0.08)
                        }
                        Rectangle {
                            x: parent.x0 * parent.width
                            width: Math.max(8 * root.s,
                                            (parent.x1 - parent.x0) * parent.width)
                            height: parent.height
                            radius: height / 2
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Theme.alpha(Theme.cryo, 0.9) }
                                GradientStop { position: 1.0; color: Theme.gold }
                            }
                        }
                        // today marker
                        Rectangle {
                            visible: dayCard.day.is_today
                            anchors.centerIn: parent
                            width: 2 * root.s; height: 12 * root.s
                            radius: 1 * root.s
                            color: Theme.cream
                        }
                    }

                    Text {
                        text: WeatherData.tempStr(dayCard.day.t_max, false) + "°"
                        color: Theme.cream
                        font.family: Theme.fontFamily
                        font.pixelSize: 11.5 * root.s
                        font.weight: Font.DemiBold
                        width: 30 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Text {
                        text: WeatherData.num(dayCard.day.precip_prob, 0) > 5
                              ? WeatherData.num(dayCard.day.precip_prob, 0) + "%" : ""
                        color: Theme.hydro
                        font.family: Theme.fontFamily
                        font.pixelSize: 9.5 * root.s
                        width: 32 * root.s
                        horizontalAlignment: Text.AlignRight
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}
