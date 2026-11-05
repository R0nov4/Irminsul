import QtQuick
import Quickshell
import Quickshell.Io
import ".."

// CitySearch — city picker overlay for the popup (opened by clicking the
// city name in the header, or `teyvat-forecast city`).
//
// NO network I/O in QML: lookups run through the data layer
//   python3 teyvat-fetch.py search <query>          -> JSON
//   python3 teyvat-fetch.py set-city <lat> <lon> <name>
//   python3 teyvat-fetch.py locate                  (IP geolocation)
// set-city rewrites ~/.config/teyvat-forecast/config.json and refetches;
// WeatherData watches the cache file, so the popup updates by itself.
Item {
    id: root

    readonly property real s: Theme.s
    readonly property bool shown: PopupState.citySearch

    property var results: []
    property string status: "idle"     // idle · searching · empty · error · saving
    property int current: 0
    property string activeQuery: ""
    property string queuedQuery: ""

    visible: opacity > 0.01
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

    function focusInput() { input.forceActiveFocus() }

    function reset() {
        input.text = ""
        results = []
        status = "idle"
        current = 0
        queuedQuery = ""
    }

    onShownChanged: {
        if (shown) {
            reset()
            focusInput()
        }
    }

    // ── search ────────────────────────────────────────────────────────────
    function requestSearch() {
        const q = input.text.trim()
        if (q.length < 2) {
            results = []
            status = "idle"
            return
        }
        if (searchProc.running) {
            queuedQuery = q
            return
        }
        startSearch(q)
    }

    function startSearch(q) {
        activeQuery = q
        status = "searching"
        searchProc.command = ["python3", WeatherData.fetchScript, "search", q]
        searchProc.running = true
    }

    function handleResult(txt) {
        // a newer query is already waiting — its answer will replace this one
        if (queuedQuery !== "" && queuedQuery !== activeQuery)
            return
        let obj = null
        try { obj = JSON.parse(txt) } catch (e) { obj = null }
        if (!obj) { results = []; status = "error"; return }
        if (!obj.ok) {
            results = []
            status = obj.error === "network" ? "error" : "idle"
            return
        }
        results = obj.results || []
        current = 0
        status = results.length === 0 ? "empty" : "idle"
    }

    Process {
        id: searchProc
        stdout: StdioCollector {
            onStreamFinished: root.handleResult(text)
        }
        onExited: {
            if (root.queuedQuery !== "" && root.queuedQuery !== root.activeQuery) {
                const q = root.queuedQuery
                root.queuedQuery = ""
                root.startSearch(q)
            }
        }
    }

    Timer {
        id: debounce
        interval: 380
        onTriggered: root.requestSearch()
    }

    // ── choosing ──────────────────────────────────────────────────────────
    function choose(r) {
        if (status === "saving") return
        status = "saving"
        pickProc.command = ["python3", WeatherData.fetchScript, "set-city",
                            String(r.lat), String(r.lon), r.name]
        pickProc.running = true
    }

    function locate() {
        if (status === "saving") return
        status = "saving"
        pickProc.command = ["python3", WeatherData.fetchScript, "locate"]
        pickProc.running = true
    }

    function activate() {
        if (results.length > 0)
            choose(results[Math.max(0, Math.min(current, results.length - 1))])
        else
            requestSearch()
    }

    Process {
        id: pickProc
        onExited: PopupState.citySearch = false
    }

    // ── visuals ───────────────────────────────────────────────────────────
    // scrim: dims the card, click outside the panel closes the picker
    Rectangle {
        anchors.fill: parent
        radius: 16 * root.s
        color: Theme.alpha(Theme.bgDeep, 0.62)
        MouseArea {
            anchors.fill: parent
            onClicked: PopupState.citySearch = false
        }
    }

    Rectangle {
        id: panel
        x: 15 * root.s
        y: 46 * root.s
        width: parent.width - 30 * root.s
        height: col.implicitHeight + 20 * root.s
        radius: 12 * root.s
        color: "#f4181d2a"
        border.color: Theme.alpha(Theme.gold, 0.5)
        border.width: 1

        MouseArea { anchors.fill: parent }      // swallow clicks inside the panel

        Column {
            id: col
            x: 10 * root.s
            y: 10 * root.s
            width: parent.width - 20 * root.s
            spacing: 6 * root.s
            opacity: root.status === "saving" ? 0.45 : 1
            enabled: root.status !== "saving"

            // ── search field ─────────────────────────────────────────
            Rectangle {
                width: parent.width
                height: 32 * root.s
                radius: 9 * root.s
                color: Theme.alpha(Theme.card, 0.9)
                border.width: 1
                border.color: input.activeFocus ? Theme.alpha(Theme.gold, 0.75)
                                                : Theme.alpha(Theme.gold, 0.25)

                // drawn magnifier (font-independent)
                Item {
                    id: lens
                    x: 10 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    width: 12 * root.s; height: 12 * root.s
                    Rectangle {
                        width: 9 * root.s; height: 9 * root.s
                        radius: width / 2
                        color: "transparent"
                        border.color: Theme.gold
                        border.width: 1.5
                    }
                    Rectangle {
                        x: 7 * root.s; y: 9 * root.s
                        width: 5 * root.s; height: 1.5
                        radius: 1
                        color: Theme.gold
                        rotation: 45
                        transformOrigin: Item.Left
                    }
                }

                TextInput {
                    id: input
                    anchors.left: lens.right
                    anchors.leftMargin: 8 * root.s
                    anchors.right: clearBtn.left
                    anchors.rightMargin: 6 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.cream
                    selectionColor: Theme.alpha(Theme.gold, 0.45)
                    selectedTextColor: Theme.cream
                    font.family: Theme.fontFamily
                    font.pixelSize: 12.5 * root.s
                    maximumLength: 60
                    clip: true
                    selectByMouse: true

                    onTextEdited: debounce.restart()

                    Keys.onEscapePressed: PopupState.citySearch = false
                    Keys.onReturnPressed: root.activate()
                    Keys.onEnterPressed: root.activate()
                    Keys.onDownPressed: root.current = Math.min(root.current + 1,
                                                                 root.results.length - 1)
                    Keys.onUpPressed: root.current = Math.max(root.current - 1, 0)

                    Text {
                        visible: input.text === ""
                        text: "Search city…  (Karaj, Paris, 東京)"
                        color: Theme.alpha(Theme.creamDim, 0.7)
                        font: input.font
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                // drawn ✕ clear button
                Item {
                    id: clearBtn
                    anchors.right: parent.right
                    anchors.rightMargin: 8 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    width: 14 * root.s; height: 14 * root.s
                    visible: input.text !== ""
                    Rectangle {
                        anchors.centerIn: parent
                        width: 10 * root.s; height: 1.5
                        color: clearMouse.containsMouse ? Theme.cream : Theme.creamDim
                        rotation: 45
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 10 * root.s; height: 1.5
                        color: clearMouse.containsMouse ? Theme.cream : Theme.creamDim
                        rotation: -45
                    }
                    MouseArea {
                        id: clearMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.reset(); input.forceActiveFocus() }
                    }
                }
            }

            // ── use my location (IP) ─────────────────────────────────
            Rectangle {
                width: parent.width
                height: 30 * root.s
                radius: 8 * root.s
                color: locMouse.containsMouse ? Theme.alpha(Theme.gold, 0.12) : "transparent"
                border.width: 1
                border.color: locMouse.containsMouse ? Theme.alpha(Theme.gold, 0.4)
                                                     : Theme.alpha(Theme.gold, 0.16)

                Rectangle {
                    x: 12 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7 * root.s; height: 7 * root.s
                    radius: 1
                    color: Theme.gold
                    rotation: 45
                }
                Text {
                    x: 28 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Use my current location (by IP)"
                    color: Theme.cream
                    font.family: Theme.fontFamily
                    font.pixelSize: 11.5 * root.s
                }
                MouseArea {
                    id: locMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.locate()
                }
            }

            // ── status / hint line ───────────────────────────────────
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: text !== ""
                color: root.status === "error" ? Theme.pyro : Theme.creamDim
                font.family: Theme.fontFamily
                font.pixelSize: 10.5 * root.s
                font.italic: true
                topPadding: 2 * root.s
                bottomPadding: 2 * root.s
                text: {
                    if (root.status === "saving")    return "Saving city and fetching the forecast…"
                    if (root.status === "searching") return "Searching…"
                    if (root.status === "empty")     return "No city found — try another spelling."
                    if (root.status === "error")     return "Can't reach the city search — check your connection."
                    if (root.results.length === 0 && input.text.trim().length < 2)
                        return "Type at least 2 letters — any language works."
                    return ""
                }
            }

            // ── results ──────────────────────────────────────────────
            Repeater {
                model: root.results

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property bool active: rowMouse.containsMouse || root.current === index

                    width: col.width
                    height: 38 * root.s
                    radius: 8 * root.s
                    color: active ? Theme.alpha(Theme.gold, 0.12) : "transparent"
                    border.width: 1
                    border.color: active ? Theme.alpha(Theme.gold, 0.4) : "transparent"

                    Column {
                        x: 10 * root.s
                        width: parent.width - 20 * root.s
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 1 * root.s

                        Text {
                            width: parent.width
                            text: Theme.clean(row.modelData.name)
                            elide: Text.ElideRight
                            color: Theme.cream
                            font.family: Theme.fontFamily
                            font.pixelSize: 12.5 * root.s
                        }
                        Text {
                            width: parent.width
                            text: [row.modelData.admin1, row.modelData.country]
                                  .filter(function (x) { return x && x !== "" })
                                  .map(function (x) { return Theme.clean(x) }).join("  ·  ")
                            elide: Text.ElideRight
                            color: Theme.creamDim
                            font.family: Theme.fontFamily
                            font.pixelSize: 9.5 * root.s
                        }
                    }

                    MouseArea {
                        id: rowMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: root.current = row.index
                        onClicked: root.choose(row.modelData)
                    }
                }
            }
        }
    }
}
