pragma Singleton
import Quickshell
import QtQuick

// PopupState — the single source of truth for popup visibility and animation
// phase. IPC handlers and the window itself both talk to this object.
Singleton {
    id: root

    property bool open: false        // window mapped?
    property bool closing: false     // close animation in flight?
    property int tab: 0              // 0 Today · 1 Hourly · 2 Week · 3 Air
    property bool citySearch: false  // city picker overlay visible?

    // "click sound" hook — the popup calls this on open & tab switch so the
    // audio process stays in one place (WeatherPopup).
    signal interacted()

    function openPopup() {
        if (!open) {
            closing = false
            open = true
        } else if (closing) {
            closing = false   // re-open mid-close-animation: cancel it
        }
    }

    function closePopup() {
        if (open && !closing)
            closing = true    // WeatherPopup plays the animation, then finishClose()
    }

    function finishClose() {
        closing = false
        open = false
        citySearch = false
    }

    // open the popup straight into the city picker (IPC: `search`)
    function openCitySearch() {
        openPopup()
        citySearch = true
    }

    function toggle() {
        open ? closePopup() : openPopup()
    }

    function nextTab(delta) {
        tab = ((tab + delta) % 4 + 4) % 4
    }
}
