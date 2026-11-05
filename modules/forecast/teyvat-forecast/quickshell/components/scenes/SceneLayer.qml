import QtQuick
import "../.."

// SceneLayer — the live weather backdrop. Exactly one base scene is active
// at a time (chosen by WeatherData.sceneKey), plus optional overlays.
// Everything is gated by PopupState.open, so the closed popup costs nothing.
// The scene fills the WHOLE card: the top ~176 px header shows it fully
// ("scene window"), the glass tiles below let it shine through.
Item {
    id: root

    // forwarded to WeatherPopup → subtle panel shake on each strike
    signal struck()

    // subtle element tint over the whole panel (tints cloud edges etc.)
    Rectangle {
        anchors.fill: parent
        color: WeatherData.elementColor
        opacity: 0.05
    }

    RainScene {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "rain" || WeatherData.sceneKey === "storm"
        running: visible && root.visible && PopupState.open
        count: Theme.particles.rain
        heavy: WeatherData.sceneKey === "storm"
        tilt: Math.min(14, WeatherData.num(WeatherData.current.wind_kmh, 0) / 6)
    }

    SnowScene {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "snow"
        running: visible && root.visible && PopupState.open
        count: Theme.particles.snow
        tilt: Math.min(12, WeatherData.num(WeatherData.current.wind_kmh, 0) / 8)
    }

    StarsScene {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "night"
        running: visible && root.visible && PopupState.open
        count: Theme.particles.stars
    }

    CloudsScene {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "clouds"
        running: visible && root.visible && PopupState.open
    }

    FogScene {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "fog"
        running: visible && root.visible && PopupState.open
    }

    SparklesScene {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "clear"
                 || WeatherData.sceneKey === "hot"
        running: visible && root.visible && PopupState.open
        count: Theme.particles.sparkles
    }

    WindOverlay {
        anchors.fill: parent
        visible: WeatherData.windOverlay
        running: visible && root.visible && PopupState.open
        count: Theme.particles.wind
    }

    // hot scene: warm vignette from the top
    Rectangle {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "hot"
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.alpha(Theme.pyro, 0.16) }
            GradientStop { position: 0.55; color: Theme.alpha(Theme.pyro, 0.0) }
        }
    }

    // storm: darker, moodier base
    Rectangle {
        anchors.fill: parent
        visible: WeatherData.sceneKey === "storm"
        color: "#0b0e18"
        opacity: 0.35
    }

    LightningFlash {
        anchors.fill: parent
        active: root.visible && PopupState.open
                && WeatherData.sceneKey === "storm"
        onStruck: root.struck()
    }
}
