import QtQuick
import ".."

// WeatherIcon — maps a WMO weather code + day/night to an icon asset.
Item {
    id: root

    property int code: 0
    property int isDay: 1

    Image {
        anchors.fill: parent
        source: root.sourceFor(root.code, root.isDay)
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }

    function sourceFor(code, day) {
        const base = "../assets/icons/"
        const storm = code === 95 || code === 96 || code === 99
        const snow = (code >= 71 && code <= 77) || code === 85 || code === 86
        const rain = (code >= 61 && code <= 67) || code === 80 || code === 81 || code === 82
        const drizzle = code >= 51 && code <= 57
        const fog = code === 45 || code === 48
        if (storm) return base + "storm.png"
        if (snow) return base + "snow.png"
        if (rain) return base + "rain.png"
        if (drizzle) return base + "drizzle.png"
        if (fog) return base + "fog.png"
        if (code === 3) return base + "overcast.png"
        if (code === 2) return base + (day === 1 ? "sun-cloud.png" : "moon-cloud.png")
        if (code === 1) return base + (day === 1 ? "sun-cloud.png" : "moon-cloud.png")
        return base + (day === 1 ? "sun.png" : "moon.png")
    }
}
