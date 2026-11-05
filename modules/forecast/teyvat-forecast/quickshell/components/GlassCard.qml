import QtQuick
import ".."

// GlassCard — the shared surface for every tile/card in the popup.
//  · glass background (Theme.card @ ~40 %) so the live weather scene shows
//    through, gold hairline border, slightly lighter top edge
//  · hover: lifts 2 px, border brightens
//  · entrance: rises 9 px + fades in, staggered by `enterIndex` (40 ms steps),
//    replayed on every popup open (and, if `tabGated`, whenever its tab is
//    (re)shown while the popup is open). All one-shot — zero cost when closed.
Rectangle {
    id: root

    property int enterIndex: 0        // stagger order within its group
    property int tabIndex: 0          // which tab page this card lives on
    property bool tabGated: false     // also replay when that tab becomes active
    property bool hoverEnabled: true  // decorative hover lift

    readonly property real s: Theme.s
    radius: 12 * s
    color: Theme.alpha(Theme.card, Theme.glassAlpha)
    border.color: hover.hovered && root.hoverEnabled
                  ? Theme.alpha(Theme.gold, Theme.hairlineHover)
                  : Theme.alpha(Theme.gold, Theme.hairline)
    border.width: 1

    Behavior on border.color { ColorAnimation { duration: 160 } }

    // slightly lighter top edge — the "glass" sheen
    Rectangle {
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: parent.height * 0.45
        radius: parent.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.alpha(Theme.cream, 0.055) }
            GradientStop { position: 1.0; color: Theme.alpha(Theme.cream, 0.0) }
        }
    }
    Rectangle {
        // crisp 1 px highlight along the very top edge
        anchors { top: parent.top; left: parent.left; right: parent.right }
        anchors.leftMargin: 2 * root.s
        anchors.rightMargin: 2 * root.s
        height: 1
        color: Theme.alpha(Theme.cream, 0.10)
    }

    // entrance + hover transforms (a list — they compose)
    transform: [
        Translate { id: enterTr; y: 9 * root.s },
        Translate {
            id: hoverTr
            y: (hover.hovered && root.hoverEnabled) ? -2 * root.s : 0
            Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        }
    ]

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.hoverEnabled
        acceptedButtons: Qt.NoButton      // decorative only
    }

    // ── entrance choreography ─────────────────────────────────────────────
    opacity: 0

    function playEntrance() {
        resetEntrance()      // arm (opacity 0, raised) so replays fade in again
        enter.restart()
    }

    function resetEntrance() {
        enter.stop()
        root.opacity = 0
        enterTr.y = 9 * root.s
    }

    Component.onCompleted: {
        // cards created while the popup is already open (data refresh)
        // animate in immediately instead of waiting for the next open
        if (PopupState.open && (!root.tabGated || PopupState.tab === root.tabIndex))
            root.playEntrance()
    }

    Connections {
        target: PopupState
        function onOpenChanged() {
            if (PopupState.open) {
                // only the visible tab's cards enter on open; the others
                // enter when their tab is first shown
                if (!root.tabGated || PopupState.tab === root.tabIndex)
                    root.playEntrance()
            } else {
                root.resetEntrance()      // arm for the next open
            }
        }
        function onTabChanged() {
            if (root.tabGated && PopupState.open && PopupState.tab === root.tabIndex)
                root.playEntrance()
        }
    }

    SequentialAnimation {
        id: enter
        PauseAnimation { duration: Math.min(root.enterIndex * 40, 480) }
        ParallelAnimation {
            NumberAnimation {
                target: root; property: "opacity"
                to: 1; duration: 300; easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: enterTr; property: "y"
                to: 0; duration: 300; easing.type: Easing.OutCubic
            }
        }
    }
}
