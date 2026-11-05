import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import "components"
import "components/scenes"
import "tabs"

// WeatherPopup — the layer-shell panel itself. Anchored under the Waybar
// weather module (position configurable), transparent window, Genshin-style
// rounded card. The top ~176 px are a "scene window": the live weather scene
// shows fully, with only the temperature / condition / element emblem over
// it. Below, every card is glass (≈40 % opacity, gold hairline) so the
// scene keeps shining through.
//
// Motion: opens by emerging from the bar side (transform origin on the
// anchor side + slide from the top, 250 ms), cards enter with a 40 ms
// stagger, tabs cross-fade with a directional slide and a gold underline
// that slides between tab buttons.
//
// All Quickshell APIs used here are verified against the v0.3.x docs:
//   PanelWindow (anchors/margins groups, exclusionMode, aboveWindows),
//   WlrLayershell (layer/namespace/keyboardFocus), QsWindow (visible/screen/
//   color/implicitWidth/implicitHeight), HyprlandFocusGrab, Process,
//   Quickshell.env / Quickshell.screens / Quickshell.shellDir.
PanelWindow {
    id: root

    readonly property real s: Theme.s
    readonly property real cardW: 460 * s
    readonly property real cardH: 676 * s
    readonly property real glowPad: 14 * s
    readonly property real headerH: 176 * s

    // ── lifecycle ─────────────────────────────────────────────────────────
    visible: PopupState.open

    // ── geometry & anchoring ──────────────────────────────────────────────
    implicitWidth: cardW + 2 * glowPad
    implicitHeight: cardH + 2 * glowPad

    // position.anchor: "top_right" (default) · "top_left" · "top_center"
    // offset_x means: distance from the right edge / left edge / center.
    readonly property string anchorMode: WeatherData.cfg && WeatherData.cfg.position
                                         ? WeatherData.cfg.position.anchor : "top_right"
    readonly property bool aLeft: anchorMode === "top_left"
    readonly property bool aCenter: anchorMode === "top_center"

    readonly property real offsetX: WeatherData.cfg && WeatherData.cfg.position
                                    ? WeatherData.cfg.position.offset_x : 310
    readonly property real offsetY: WeatherData.cfg && WeatherData.cfg.position
                                    ? WeatherData.cfg.position.offset_y : 54

    anchors {
        top: true
        left: aLeft || aCenter
        right: !aLeft && !aCenter
    }
    margins {
        top: offsetY
        left: aCenter
              // centered: offset_x is a delta from the center
              ? Math.max(0, ((root.screen ? root.screen.width : 1920)
                             - root.implicitWidth) / 2 + offsetX)
              : (aLeft ? offsetX : 0)
        right: (!aLeft && !aCenter) ? offsetX : 0
    }

    // ── layer shell ───────────────────────────────────────────────────────
    exclusionMode: ExclusionMode.Ignore      // never reserves bar space
    aboveWindows: true
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "teyvat-forecast"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    // ── monitor selection ("primary" or a connector name like eDP-1) ──────
    readonly property var targetScreen: {
        const name = WeatherData.cfg ? WeatherData.cfg.monitor : "primary"
        const screens = Quickshell.screens
        if (screens.length === 0)
            return null
        if (name && name !== "primary") {
            for (let i = 0; i < screens.length; i++)
                if (screens[i].name === name)
                    return screens[i]
        }
        return screens[0]
    }
    screen: targetScreen

    // ── click-outside dismissal (Hyprland focus grab protocol) ────────────
    HyprlandFocusGrab {
        windows: [root]
        active: root.visible && !PopupState.closing
        onCleared: PopupState.closePopup()
    }

    // ── optional ambient sound (mpv; disabled by default) ─────────────────
    Process {
        id: ambientSound
        readonly property var snd: WeatherData.cfg ? WeatherData.cfg.sound : null
        readonly property bool wanted: snd && snd.enabled === true
                                       && (snd.player || "") === "mpv"
        readonly property string track: {
            const k = WeatherData.sceneKey
            if (k === "rain" || k === "storm") return "rain.wav"
            if (k === "fog" || k === "snow") return "wind.wav"
            if (WeatherData.windOverlay) return "wind.wav"
            return ""
        }
        running: wanted && PopupState.open && track !== ""
        command: [
            "mpv", "--no-video", "--really-quiet", "--loop-file=inf",
            "--volume=" + ((snd && snd.volume) || 40),
            Quickshell.shellDir + "/assets/audio/" + track
        ]
    }

    function clickSound() {
        const snd = WeatherData.cfg ? WeatherData.cfg.sound : null
        if (!snd || snd.enabled !== true || snd.click !== true) return
        const player = snd.player || ""
        if (player === "mpv" || player === "paplay")
            Quickshell.execDetached([player,
                                     Quickshell.shellDir + "/assets/audio/click.wav"])
    }

    // ── open / close animation ────────────────────────────────────────────
    // The popup emerges from the side the weather pill sits on: the scale
    // transform origin follows the configured anchor, plus a short slide
    // down from the top. 250 ms open, 160 ms close.
    onVisibleChanged: {
        if (visible) {
            contentRoot.forceActiveFocus()
            if (PopupState.citySearch)
                citySearchPanel.focusInput()
            openAnim.restart()
        }
    }
    Connections {
        target: PopupState
        function onClosingChanged() {
            if (PopupState.closing)
                closeAnim.restart()
        }
        function onCitySearchChanged() {
            if (PopupState.citySearch)
                citySearchPanel.focusInput()
            else
                contentRoot.forceActiveFocus()
        }
    }

    ParallelAnimation {
        id: openAnim
        NumberAnimation {
            target: animRoot; property: "opacity"; from: 0; to: 1
            duration: 210; easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: animRoot; property: "scale"; from: 0.94; to: 1
            duration: 250; easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: openSlide; property: "y"; from: -16 * root.s; to: 0
            duration: 250; easing.type: Easing.OutCubic
        }
    }
    ParallelAnimation {
        id: closeAnim
        NumberAnimation {
            target: animRoot; property: "opacity"; to: 0
            duration: 160; easing.type: Easing.InCubic
        }
        NumberAnimation {
            target: animRoot; property: "scale"; to: 0.96
            duration: 160; easing.type: Easing.InCubic
        }
        NumberAnimation {
            target: openSlide; property: "y"; to: -10 * root.s
            duration: 160; easing.type: Easing.InCubic
        }
        onFinished: PopupState.finishClose()
    }

    // ── subtle storm shake (±2 px), restarted on every lightning strike ──
    function shake() {
        if (PopupState.open && WeatherData.sceneKey === "storm")
            shakeAnim.restart()
    }

    SequentialAnimation {
        id: shakeAnim
        NumberAnimation { target: shakeTr; property: "x"; to: 2 * root.s; duration: 40 }
        NumberAnimation { target: shakeTr; property: "x"; to: -1.6 * root.s; duration: 50 }
        NumberAnimation { target: shakeTr; property: "x"; to: 1 * root.s; duration: 45 }
        NumberAnimation { target: shakeTr; property: "x"; to: 0; duration: 60
                          easing.type: Easing.OutQuad }
    }

    // ======================================================================
    //  WINDOW CONTENT
    // ======================================================================
    Item {
        id: animRoot
        anchors.fill: parent
        opacity: 0
        transformOrigin: root.aLeft ? Item.TopLeft
                        : (root.aCenter ? Item.Top : Item.TopRight)
        transform: Translate { id: openSlide; y: 0 }

        // ── soft glow behind the card (element-tinted) ──────────────────
        Rectangle {
            anchors.centerIn: cardArea
            width: cardArea.width + 26 * root.s
            height: cardArea.height + 26 * root.s
            radius: 24 * root.s
            color: Theme.alpha(WeatherData.elementColor, 0.05)
        }
        Rectangle {
            anchors.centerIn: cardArea
            width: cardArea.width + 13 * root.s
            height: cardArea.height + 13 * root.s
            radius: 20 * root.s
            color: Theme.alpha(WeatherData.elementColor, 0.12)
        }

        // ── the card ─────────────────────────────────────────────────────
        Item {
            id: cardArea
            x: glowPad
            y: glowPad
            width: cardW
            height: cardH
            transform: Translate { id: shakeTr; x: 0; y: 0 }

            Rectangle {
                anchors.fill: parent
                radius: 16 * root.s
                color: "#f0171b26"          // deep navy @ 94%
            }

            // live weather scene — fills the WHOLE card (clipped + masked)
            Item {
                id: sceneClip
                anchors.fill: parent
                clip: true

                SceneLayer {
                    anchors.fill: parent
                    onStruck: root.shake()
                }

                // vignette: darken toward the bottom so tab text stays
                // readable over bright scenes
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: parent.height * 0.5
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Theme.alpha(Theme.bg, 0.0) }
                        GradientStop { position: 1.0; color: Theme.alpha(Theme.bgDeep, 0.5) }
                    }
                }
            }

            // corner masks — make the scene respect the rounded corners
            Image {
                x: 0; y: 0
                width: 16 * root.s; height: 16 * root.s
                source: "assets/sprites/corner.png"
                rotation: 90
            }
            Image {
                anchors.right: parent.right; y: 0
                width: 16 * root.s; height: 16 * root.s
                source: "assets/sprites/corner.png"
                rotation: 180
            }
            Image {
                anchors.bottom: parent.bottom; x: 0
                width: 16 * root.s; height: 16 * root.s
                source: "assets/sprites/corner.png"
                rotation: 270
            }
            Image {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 16 * root.s; height: 16 * root.s
                source: "assets/sprites/corner.png"
            }

            // city picker overlay (above the content, below the borders)
            CitySearch {
                id: citySearchPanel
                anchors.fill: parent
                z: 50
            }

            // gold border + inner hairline (element-tinted)
            Rectangle {
                anchors.fill: parent
                radius: 16 * root.s
                color: "transparent"
                border.color: Theme.alpha(WeatherData.elementColor, 0.55)
                border.width: 1
            }
            Rectangle {
                anchors.fill: parent
                anchors.margins: 2 * root.s
                radius: 14 * root.s
                color: "transparent"
                border.color: Theme.alpha(Theme.cream, 0.07)
                border.width: 1
            }

            // ── card content ─────────────────────────────────────────────
            Item {
                id: contentRoot
                anchors.fill: parent
                anchors.margins: 15 * root.s
                focus: true

                Keys.onEscapePressed: {
                    if (PopupState.citySearch) PopupState.citySearch = false
                    else PopupState.closePopup()
                }
                Keys.onLeftPressed: {
                    if (PopupState.citySearch) return
                    PopupState.nextTab(-1); root.clickSound()
                }
                Keys.onRightPressed: {
                    if (PopupState.citySearch) return
                    PopupState.nextTab(1); root.clickSound()
                }

                Column {
                    id: layout
                    anchors.fill: parent
                    spacing: 8 * root.s

                    // ══ header: the scene window ═════════════════════════
                    // No background — the live scene is fully visible here;
                    // temperature / condition / emblem float over it.
                    Item {
                        id: header
                        width: parent.width
                        height: root.headerH

                        // small scrim so the city row reads over bright skies
                        Rectangle {
                            anchors { top: parent.top; left: parent.left; right: parent.right }
                            height: 36 * root.s
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Theme.alpha(Theme.bgDeep, 0.40) }
                                GradientStop { position: 1.0; color: Theme.alpha(Theme.bgDeep, 0.0) }
                            }
                        }

                        // city · updated · stale
                        Item {
                            id: cityRow
                            anchors { top: parent.top; left: parent.left; right: parent.right }
                            anchors.topMargin: 8 * root.s
                            height: 20 * root.s

                            Text {
                                id: cityText
                                text: WeatherData.city !== ""
                                      ? Theme.clean(WeatherData.city).toUpperCase() : "—"
                                color: cityMouse.containsMouse ? Theme.cream : Theme.gold
                                font.family: Theme.fontFamily
                                font.pixelSize: 11 * root.s
                                font.letterSpacing: 2
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            // small drawn magnifier → "click to change city"
                            Item {
                                id: cityLens
                                anchors.left: cityText.right
                                anchors.leftMargin: 7 * root.s
                                anchors.verticalCenter: parent.verticalCenter
                                width: 11 * root.s; height: 11 * root.s
                                opacity: cityMouse.containsMouse ? 1.0 : 0.65
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                Rectangle {
                                    width: 8 * root.s; height: 8 * root.s
                                    radius: width / 2
                                    color: "transparent"
                                    border.color: Theme.gold
                                    border.width: 1.3
                                }
                                Rectangle {
                                    x: 6.2 * root.s; y: 8 * root.s
                                    width: 4.5 * root.s; height: 1.4
                                    radius: 1
                                    color: Theme.gold
                                    rotation: 45
                                    transformOrigin: Item.Left
                                }
                            }

                            // hit area: city name + magnifier
                            MouseArea {
                                id: cityMouse
                                x: 0
                                width: cityText.width + 7 * root.s + cityLens.width + 4 * root.s
                                height: parent.height
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.clickSound()
                                    PopupState.citySearch = !PopupState.citySearch
                                }
                            }
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: cityLens.right
                                anchors.leftMargin: 8 * root.s
                                anchors.right: rightMeta.left
                                anchors.rightMargin: 8 * root.s
                                height: 1
                                color: Theme.alpha(Theme.gold, 0.25)
                            }
                            Row {
                                id: rightMeta
                                spacing: 6 * root.s
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter

                                Image {
                                    width: 11 * root.s; height: 11 * root.s
                                    source: "assets/icons/refresh.png"
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true; mipmap: true
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Text {
                                    text: WeatherData.hasData
                                          ? WeatherData.updatedText() : "No data"
                                    color: Theme.creamDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 9.5 * root.s
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                StaleBadge {
                                    visible: WeatherData.stale
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }

                        // big temperature row — floating over the scene
                        Item {
                            id: tempRow
                            anchors { left: parent.left; right: parent.right }
                            y: 52 * root.s
                            height: 104 * root.s

                            WeatherIcon {
                                id: hdrIcon
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                width: 62 * root.s; height: 62 * root.s
                                code: WeatherData.num(WeatherData.current.code, 0)
                                isDay: WeatherData.num(WeatherData.current.is_day, 1)
                            }

                            AnimatedNumber {
                                id: bigTemp
                                anchors.left: hdrIcon.right
                                anchors.leftMargin: 12 * root.s
                                anchors.verticalCenter: parent.verticalCenter
                                value: WeatherData.hasData
                                       ? WeatherData.tempStr(
                                             WeatherData.current.temperature, false) + "°"
                                       : "--°"
                                pixelSize: 48 * root.s
                            }

                            Column {
                                anchors.left: bigTemp.right
                                anchors.leftMargin: 14 * root.s
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4 * root.s

                                Text {
                                    text: WeatherData.hasData
                                           ? WeatherData.conditionText(
                                                 WeatherData.current.code)
                                           : "No forecast"
                                    color: Theme.cream
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 16 * root.s
                                    style: Text.Outline
                                    styleColor: Theme.alpha(Theme.bgDeep, 0.55)
                                }
                                Text {
                                    text: WeatherData.hasData
                                           ? "Feels like " + WeatherData.tempStr(
                                                 WeatherData.current.feels_like, true)
                                           : ""
                                    color: Theme.creamDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11.5 * root.s
                                    style: Text.Outline
                                    styleColor: Theme.alpha(Theme.bgDeep, 0.55)
                                }
                                Text {
                                    text: WeatherData.hasData
                                           ? "H " + WeatherData.tempStr(
                                                 WeatherData.today.temp_max, true)
                                             + "  ·  L " + WeatherData.tempStr(
                                                 WeatherData.today.temp_min, true)
                                           : ""
                                    color: Theme.creamDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 10.5 * root.s
                                    style: Text.Outline
                                    styleColor: Theme.alpha(Theme.bgDeep, 0.55)
                                }
                            }

                            // element emblem with pulsing glow
                            Column {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4 * root.s

                                ElementEmblem {
                                    element: WeatherData.elementKey
                                    width: 36 * root.s; height: 36 * root.s
                                    anchors.horizontalCenter: parent.horizontalCenter
                                }
                                Text {
                                    text: Theme.elementName(WeatherData.elementKey)
                                    color: WeatherData.elementColor
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 10 * root.s
                                    font.letterSpacing: 1
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    style: Text.Outline
                                    styleColor: Theme.alpha(Theme.bgDeep, 0.55)
                                }
                            }
                        }

                        // bottom hairline + ✦ diamond — the scene window sill
                        Rectangle {
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                            anchors.leftMargin: 2 * root.s
                            anchors.rightMargin: 2 * root.s
                            height: 1
                            color: Theme.alpha(Theme.gold, 0.22)
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: -3 * root.s
                            width: 7 * root.s; height: 7 * root.s
                            radius: 1
                            color: Theme.gold
                            rotation: 45
                            opacity: 0.85
                        }
                    }

                    // ── reaction banner (animated height) ────────────────
                    Item {
                        id: bannerWrap
                        width: parent.width
                        height: WeatherData.reaction !== null ? 32 * root.s : 0
                        clip: true
                        visible: WeatherData.reaction !== null

                        Behavior on height {
                            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
                        }

                        ReactionBanner {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            reaction: WeatherData.reaction
                        }
                    }

                    // ── tab bar + sliding gold underline ──────────────────
                    Item {
                        id: tabBarWrap
                        width: parent.width
                        height: 30 * root.s

                        // entrance: rises + fades just after the tiles start
                        opacity: 0
                        transform: Translate { id: tabEnterTr; y: 8 * root.s }
                        Connections {
                            target: PopupState
                            function onOpenChanged() {
                                if (PopupState.open)
                                    tabBarEnter.restart()
                                else {
                                    tabBarEnter.stop()
                                    tabBarWrap.opacity = 0
                                    tabEnterTr.y = 8 * root.s
                                }
                            }
                        }
                        SequentialAnimation {
                            id: tabBarEnter
                            PauseAnimation { duration: 90 }
                            ParallelAnimation {
                                NumberAnimation { target: tabBarWrap; property: "opacity"; to: 1; duration: 280; easing.type: Easing.OutCubic }
                                NumberAnimation { target: tabEnterTr; property: "y"; to: 0; duration: 280; easing.type: Easing.OutCubic }
                            }
                        }

                        Row {
                            id: tabBarRow
                            anchors.fill: parent
                            spacing: 6 * root.s

                            Repeater {
                                model: ["Today", "Hourly", "Week", "Air"]

                                delegate: Rectangle {
                                    id: tabBtn
                                    required property string modelData
                                    required property int index
                                    readonly property bool selected: PopupState.tab === index
                                    width: (tabBarRow.width - 18 * root.s) / 4
                                    height: 30 * root.s
                                    radius: 9 * root.s
                                    color: selected ? Theme.alpha(Theme.cream, 0.10)
                                                    : Theme.alpha(Theme.card, Theme.glassAlpha)
                                    border.color: selected ? Theme.alpha(Theme.gold, 0.55)
                                                  : (tabMouse.containsMouse
                                                     ? Theme.alpha(Theme.gold, 0.50)
                                                     : Theme.alpha(Theme.gold, 0.16))
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: tabBtn.modelData
                                        color: tabBtn.selected ? Theme.gold
                                                               : Theme.alpha(Theme.cream, 0.6)
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12 * root.s
                                        font.weight: tabBtn.selected ? Font.DemiBold : Font.Normal
                                        font.letterSpacing: 0.5
                                    }

                                    MouseArea {
                                        id: tabMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (PopupState.tab !== tabBtn.index)
                                                root.clickSound()
                                            PopupState.tab = tabBtn.index
                                        }
                                    }

                                    Behavior on color { ColorAnimation { duration: 160 } }
                                }
                            }
                        }

                        // gold underline that slides between the tab buttons
                        Rectangle {
                            id: tabIndicator
                            readonly property real btnW: (tabBarRow.width - 18 * root.s) / 4
                            readonly property real indW: 26 * root.s
                            x: PopupState.tab * (btnW + 6 * root.s) + (btnW - indW) / 2
                            y: parent.height - 3 * root.s
                            width: indW
                            height: 2.5 * root.s
                            radius: 1.25 * root.s
                            color: Theme.gold

                            Behavior on x {
                                NumberAnimation { duration: 240; easing.type: Easing.OutCubic }
                            }
                        }
                    }

                    // ── tab content (cross-fade + directional slide) ──────
                    Item {
                        id: tabArea
                        width: parent.width
                        height: layout.height - header.height - bannerWrap.height
                                - tabBarWrap.height - paimonWrap.height
                                - layout.spacing * root.tabGapCount

                        TabSlide {
                            id: todaySlide
                            anchors.fill: parent
                            TodayTab { anchors.fill: parent }
                        }
                        TabSlide {
                            id: hourlySlide
                            anchors.fill: parent
                            HourlyTab {
                                anchors {
                                    left: parent.left; right: parent.right
                                    verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                        TabSlide {
                            id: weekSlide
                            anchors.fill: parent
                            WeekTab { anchors.fill: parent }
                        }
                        TabSlide {
                            id: airSlide
                            anchors.fill: parent
                            AirTab { anchors.fill: parent }
                        }

                        // ── friendly error state (never crash, never empty) ─
                        GlassCard {
                            id: errorCard
                            visible: !WeatherData.hasData
                            anchors.fill: parent
                            radius: 12 * root.s
                            color: Theme.alpha(Theme.bgDeep, 0.55)
                            hoverEnabled: false
                            enterIndex: 2

                            Column {
                                anchors.centerIn: parent
                                spacing: 10 * root.s

                                Image {
                                    width: 44 * root.s; height: 44 * root.s
                                    source: "assets/icons/alert.png"
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true; mipmap: true
                                    anchors.horizontalCenter: parent.horizontalCenter
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "Weather Network Unreachable"
                                    color: Theme.cream
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 15 * root.s
                                    font.bold: true
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: errorCard.width - 60 * root.s
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.WordWrap
                                    text: WeatherData.errorState === "parse"
                                          ? "The forecast crystal is clouded — the cached "
                                            + "data is damaged. A refresh will try to fix it."
                                          : "Paimon can't find any forecast data yet. "
                                            + "Press Retry, or run 'teyvat-forecast fetch' "
                                            + "in a terminal, then reopen the popup."
                                    color: Theme.creamDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 11 * root.s
                                }
                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: 120 * root.s; height: 30 * root.s
                                    radius: height / 2
                                    color: Theme.alpha(Theme.gold, 0.14)
                                    border.color: Theme.gold
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: "Retry now"
                                        color: Theme.gold
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 11.5 * root.s
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            root.clickSound()
                                            WeatherData.requestRefresh()
                                            retryNote.visible = true
                                        }
                                    }
                                }
                                Text {
                                    id: retryNote
                                    visible: false
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "Fetching… the popup updates itself when data lands."
                                    color: Theme.creamDim
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 9.5 * root.s
                                    font.italic: true
                                }
                            }
                        }
                    }

                    // ── Paimon line (fixed slot so the layout never jumps) ─
                    Item {
                        id: paimonWrap
                        width: parent.width
                        height: (WeatherData.cfg
                                 && WeatherData.cfg.show_paimon !== false
                                 && WeatherData.paimonLine !== "") ? 40 * root.s : 0
                        visible: height > 0
                        clip: true

                        PaimonBar {
                            anchors { top: parent.top; left: parent.left; right: parent.right }
                            height: 40 * root.s
                        }
                    }
                }
            }
        }
    }

    // number of visible gaps in the layout Column (drives tabArea height)
    readonly property int tabGapCount: 2 + (bannerWrap.visible ? 1 : 0)
                                           + (paimonWrap.visible ? 1 : 0)

    // ── tab switch controller ─────────────────────────────────────────────
    // Sets every TabSlide's direction BEFORE flipping its active flag, so
    // the incoming page slides in from the side the user moved towards
    // (wrap-around aware: Air → Today still feels like moving right).
    property int prevTab: 0

    Component.onCompleted: syncTabs(false)

    function syncTabs(animate) {
        const slides = [todaySlide, hourlySlide, weekSlide, airSlide]
        for (let i = 0; i < slides.length; i++) {
            slides[i].dir = animate ? root.tabDir : 0
            slides[i].active = PopupState.tab === i
        }
    }

    property int tabDir: 1

    Connections {
        target: PopupState
        function onTabChanged() {
            let d = PopupState.tab - root.prevTab
            if (d > 2) d -= 4
            if (d < -2) d += 4
            root.tabDir = d >= 0 ? 1 : -1
            root.prevTab = PopupState.tab
            root.syncTabs(true)
        }
    }
}
