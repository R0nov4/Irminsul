import QtQuick
import ".."

// TabSlide — one tab page inside the popup: cross-fades (150 ms) with a
// small directional slide (190 ms) when the controller flips `active`.
// The controller sets `dir` (+1 / -1) BEFORE changing `active`:
//   activate:   enters from the side the user moved towards
//   deactivate: drifts out the opposite way while fading
// Non-active pages disable input immediately, so a page that is still
// fading out can never swallow a click meant for the new page.
Item {
    id: root

    property bool active: false
    property int dir: 1                // +1: switch was to the right

    readonly property real s: Theme.s
    opacity: active ? 1 : 0
    visible: opacity > 0.01
    enabled: active

    Behavior on opacity {
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
    }

    transform: Translate { id: slideTr }

    onActiveChanged: {
        slideAnim.stop()
        if (root.active) {
            slideTr.x = 16 * root.s * root.dir
            slideAnim.to = 0
        } else {
            slideAnim.to = -14 * root.s * root.dir
        }
        slideAnim.restart()
    }

    NumberAnimation {
        id: slideAnim
        target: slideTr
        property: "x"
        to: 0
        duration: 190
        easing.type: Easing.OutCubic
    }
}
