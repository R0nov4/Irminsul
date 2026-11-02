import QtQuick
import QtQuick.Controls
import QtMultimedia
import SddmComponents 2.0

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#0d1018"

    property string fontName: config.fontFamily || "SDK_SC_Web"
    property int sessionIndex: (sessionModel && sessionModel.lastIndex >= 0) ? sessionModel.lastIndex : 0
    property string sessionName: sessList.currentItem ? sessList.currentItem.sessName : "Hyprland"
    property string currentUser: (userModel && userModel.lastUser !== "") ? userModel.lastUser : ""
    property bool showLoginModal: false
    property int timeState: 0 // 0: Dawn, 1: Day, 2: Dusk, 3: Night
    property bool hasLogo: (config.logoFile || "") !== ""

    property var bgImages: ["assets/Dawn.webp", "assets/Day.webp", "assets/Dusk.webp", "assets/Night.webp"]
    property var bgVideos: ["assets/Dawn.mp4", "assets/Day.mp4", "assets/Dusk.mp4", "assets/Night.mp4"]
    property var hasTimeVideo: [
        config.hasDawnVideo === "true",
        config.hasDayVideo === "true",
        config.hasDuskVideo === "true",
        config.hasNightVideo === "true"
    ]
    property var timeNames: ["DAWN", "DAY", "DUSK", "NIGHT"]

    property bool shouldPlayVideo: hasTimeVideo[timeState] || (config.hasSingleVideo === "true")
    property string activeVideoSource: hasTimeVideo[timeState] ? bgVideos[timeState] : "assets/bg.mp4"

    function updateTimeBasedBg() {
        if (config.bgMode === "random") {
            timeState = Math.floor(Math.random() * 4)
            return
        }
        var h = new Date().getHours()
        if (h >= 5 && h < 8) timeState = 0
        else if (h >= 8 && h < 17) timeState = 1
        else if (h >= 17 && h < 20) timeState = 2
        else timeState = 3
    }

    // چرخاندن بین سشن‌های نصب‌شده (d = +1 بعدی، -1 قبلی)
    function cycleSession(d) {
        var c = sessList.count
        if (c > 0) root.sessionIndex = (root.sessionIndex + d + c) % c
    }

    Component.onCompleted: {
        updateTimeBasedBg()
        root.forceActiveFocus()
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            statusText.text = "Account or password error. Please try again."
            statusText.color = "#e04a4a"
            passInput.text = ""
            passInput.forceActiveFocus()
            shakeAnim.restart()
        }
        function onLoginSucceeded() {
            statusText.text = "Entering Teyvat..."
            statusText.color = "#d3bc8e"
        }
    }

    // مدل پنهان فقط برای خوندن اسم سشن‌ها (دیده نمی‌شه)
    ListView {
        id: sessList
        width: 200
        height: 200
        opacity: 0
        enabled: false
        model: sessionModel
        currentIndex: root.sessionIndex
        highlightMoveDuration: 0
        delegate: Item {
            width: 200
            height: 20
            property string sessName: model.name
        }
    }

    // ۱. تصویر پس‌زمینه
    Image {
        id: celestiaBg
        anchors.fill: parent
        source: root.bgImages[root.timeState]
        fillMode: Image.PreserveAspectCrop
        smooth: true

        Behavior on source {
            SequentialAnimation {
                NumberAnimation { target: celestiaBg; property: "opacity"; to: 0.2; duration: 250 }
                PropertyAction { target: celestiaBg; property: "source" }
                NumberAnimation { target: celestiaBg; property: "opacity"; to: 1.0; duration: 350 }
            }
        }
    }

    // ۲. ویدیوی پس‌زمینه
    Loader {
        anchors.fill: parent
        active: root.shouldPlayVideo
        sourceComponent: Component {
            Item {
                anchors.fill: parent
                MediaPlayer {
                    id: vidPlayer
                    source: Qt.resolvedUrl(root.activeVideoSource)
                    videoOutput: vidOut
                    loops: MediaPlayer.Infinite
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: vidPlayer.play()
                    onSourceChanged: vidPlayer.play()
                }
                VideoOutput {
                    id: vidOut
                    anchors.fill: parent
                    fillMode: VideoOutput.PreserveAspectCrop
                }
            }
        }
    }

    // سایه بالا و پایین
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#770b0e17" }
            GradientStop { position: 0.18; color: "#00000000" }
            GradientStop { position: 0.80; color: "#00000000" }
            GradientStop { position: 1.0; color: "#990b0e17" }
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // ۳. گوشه بالا چپ: لوگوی رسمی (اگه فایل لوگو باشه) وگرنه نشان پیش‌فرض
    // ═══════════════════════════════════════════════════════════════
    Image {
        id: officialLogo
        visible: root.hasLogo
        source: root.hasLogo ? ("assets/" + config.logoFile) : ""
        anchors.top: parent.top
        anchors.topMargin: 22
        anchors.left: parent.left
        anchors.leftMargin: 32
        width: 300
        height: 80
        sourceSize.height: 240
        fillMode: Image.PreserveAspectFit
        horizontalAlignment: Image.AlignLeft
        verticalAlignment: Image.AlignVCenter
        smooth: true
        mipmap: true
    }

    Row {
        visible: !root.hasLogo
        anchors.top: parent.top
        anchors.topMargin: 28
        anchors.left: parent.left
        anchors.leftMargin: 32
        spacing: 14

        Image {
            width: 58; height: 58
            source: "assets/genshin_emblem.svg"
            anchors.verticalCenter: parent.verticalCenter
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            Text {
                text: "GENSHIN IMPACT"
                color: "#ffffff"
                font.family: root.fontName
                font.pixelSize: 22
                font.bold: true
                font.letterSpacing: 3
                style: Text.Outline
                styleColor: "#88141824"
            }

            Row {
                spacing: 8
                Rectangle {
                    width: 32; height: 1.5
                    color: "#f4e8c1"
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    text: "CELESTIA GATEWAY  ·  " + root.timeNames[root.timeState]
                    color: "#f4e8c1"
                    font.family: root.fontName
                    font.pixelSize: 11
                    font.bold: true
                    font.letterSpacing: 2
                    style: Text.Outline
                    styleColor: "#88141824"
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // ۴. گوشه بالا راست: ساعت و تاریخ
    // ═══════════════════════════════════════════════════════════════
    Rectangle {
        id: clockHud
        width: 245
        height: 58
        radius: 29
        anchors.top: parent.top
        anchors.topMargin: 28
        anchors.right: parent.right
        anchors.rightMargin: 32
        color: "#bf161b28"
        border.color: "#d3bc8e"
        border.width: 1.5

        Rectangle {
            anchors.fill: parent
            anchors.margins: 4
            radius: 25
            color: "transparent"
            border.color: "#44f4e8c1"
            border.width: 1
        }

        Row {
            anchors.centerIn: parent
            spacing: 12

            Image {
                width: 34; height: 34
                anchors.verticalCenter: parent.verticalCenter
                source: "assets/clock_icon.svg"
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 0

                Text {
                    id: topClockText
                    text: Qt.formatTime(new Date(), "hh:mm")
                    color: "#f4e8c1"
                    font.family: root.fontName
                    font.pixelSize: 22
                    font.bold: true
                    font.letterSpacing: 1.5
                }

                Text {
                    id: topDateText
                    text: Qt.formatDate(new Date(), "ddd, dd MMM").toUpperCase()
                    color: "#ece5d8"
                    font.family: root.fontName
                    font.pixelSize: 10
                    font.letterSpacing: 1.5
                }
            }
        }
    }

    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: {
            var now = new Date()
            topClockText.text = Qt.formatTime(now, "hh:mm")
            topDateText.text = Qt.formatDate(now, "ddd, dd MMM").toUpperCase()
        }
    }

    // تار شدن پس‌زمینه هنگام لاگین
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: root.showLoginModal ? 0.38 : 0.0
        Behavior on opacity { NumberAnimation { duration: 220 } }
    }

    MouseArea {
        anchors.fill: parent
        enabled: !root.showLoginModal
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            root.showLoginModal = true
            passInput.forceActiveFocus()
        }
    }

    Keys.onPressed: (event) => {
        if (!root.showLoginModal) {
            root.showLoginModal = true
            passInput.forceActiveFocus()
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            root.showLoginModal = false
            root.forceActiveFocus()
            event.accepted = true
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // ۵. نوار CLICK TO BEGIN
    // ═══════════════════════════════════════════════════════════════
    Item {
        id: clickToBeginBar
        width: parent.width
        height: 110
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 65
        opacity: root.showLoginModal ? 0.0 : 1.0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }

        Rectangle {
            width: 820
            height: 52
            anchors.centerIn: parent
            color: "#a611151f"

            Rectangle {
                width: parent.width; height: 1.5
                anchors.top: parent.top; color: "#ccdfd0b8"
            }
            Rectangle {
                width: parent.width; height: 1.5
                anchors.bottom: parent.bottom; color: "#ccdfd0b8"
            }

            Text {
                anchors.left: parent.left; anchors.leftMargin: 28
                anchors.verticalCenter: parent.verticalCenter
                text: "✦"; color: "#e8d9be"; font.pixelSize: 16
            }
            Text {
                anchors.right: parent.right; anchors.rightMargin: 28
                anchors.verticalCenter: parent.verticalCenter
                text: "✦"; color: "#e8d9be"; font.pixelSize: 16
            }

            Text {
                id: beginText
                anchors.centerIn: parent
                text: "Click to Begin"
                color: "#ffffff"
                font.family: root.fontName
                font.pixelSize: 20
                font.bold: true
                font.letterSpacing: 1.5

                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: !root.showLoginModal
                    NumberAnimation { from: 1.0; to: 0.45; duration: 1200; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 0.45; to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // ۶. مودال لاگین (شامل انتخاب سرور = سشن دسکتاپ)
    // ═══════════════════════════════════════════════════════════════
    Rectangle {
        id: loginModal
        width: 520
        height: 436
        radius: 14
        anchors.centerIn: parent
        color: "#f7f4ee"
        border.color: "#dcd4c4"
        border.width: 2
        visible: opacity > 0
        opacity: root.showLoginModal ? 1.0 : 0.0
        scale: root.showLoginModal ? 1.0 : 0.94

        Behavior on opacity { NumberAnimation { duration: 200 } }
        Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutBack } }

        SequentialAnimation on anchors.horizontalCenterOffset {
            id: shakeAnim
            running: false
            NumberAnimation { to: -12; duration: 45 }
            NumberAnimation { to: 12; duration: 45 }
            NumberAnimation { to: -8; duration: 45 }
            NumberAnimation { to: 0; duration: 45 }
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 7
            radius: 10
            color: "transparent"
            border.color: "#e2d8c5"
            border.width: 1.5
        }

        Text {
            anchors.top: parent.top; anchors.topMargin: 16
            anchors.right: parent.right; anchors.rightMargin: 22
            text: "✕"
            color: "#999a9e"
            font.pixelSize: 18
            font.bold: true
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.showLoginModal = false
                    root.forceActiveFocus()
                }
            }
        }

        Column {
            anchors.fill: parent
            anchors.margins: 36
            spacing: 16

            Column {
                width: parent.width
                spacing: 4

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "✦   GENSHIN IMPACT   ✦"
                    color: "#3b4255"
                    font.family: root.fontName
                    font.pixelSize: 22
                    font.bold: true
                    font.letterSpacing: 2
                }

                Rectangle {
                    width: 180; height: 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: "#d3bc8e"
                }
            }

            Rectangle {
                width: parent.width
                height: 48
                radius: 8
                color: "#ffffff"
                border.color: userInput.activeFocus ? "#d3bc8e" : "#dfdbd2"
                border.width: 1.5

                TextField {
                    id: userInput
                    anchors.fill: parent
                    anchors.leftMargin: 16; anchors.rightMargin: 16
                    verticalAlignment: TextInput.AlignVCenter
                    text: root.currentUser
                    color: "#3b4255"
                    font.family: root.fontName
                    font.pixelSize: 16
                    font.bold: true
                    placeholderText: "Enter Username / UID"
                    placeholderTextColor: "#b0b3ba"
                    background: Rectangle { color: "transparent" }
                    KeyNavigation.tab: passInput
                }
            }

            Rectangle {
                width: parent.width
                height: 48
                radius: 8
                color: "#ffffff"
                border.color: passInput.activeFocus ? "#d3bc8e" : "#dfdbd2"
                border.width: 1.5

                TextField {
                    id: passInput
                    anchors.fill: parent
                    anchors.leftMargin: 16; anchors.rightMargin: 16
                    verticalAlignment: TextInput.AlignVCenter
                    echoMode: TextInput.Password
                    passwordCharacter: "•"
                    color: "#3b4255"
                    font.family: root.fontName
                    font.pixelSize: 16
                    placeholderText: "Enter Password"
                    placeholderTextColor: "#b0b3ba"
                    background: Rectangle { color: "transparent" }
                    Keys.onReturnPressed: sddm.login(userInput.text, passInput.text, root.sessionIndex)
                    Keys.onEnterPressed: sddm.login(userInput.text, passInput.text, root.sessionIndex)
                }
            }

            // ردیف انتخاب سرور (سشن): ‹  Server · Hyprland  ›
            Rectangle {
                id: serverRow
                width: parent.width
                height: 44
                radius: 8
                color: "#ffffff"
                border.color: (prevMouse.containsMouse || centerMouse.containsMouse || nextMouse.containsMouse) ? "#d3bc8e" : "#dfdbd2"
                border.width: 1.5

                Item {
                    id: prevBtn
                    width: 44; height: parent.height
                    anchors.left: parent.left
                    Text {
                        anchors.centerIn: parent
                        text: "‹"
                        color: prevMouse.containsMouse ? "#d3bc8e" : "#3b4255"
                        font.pixelSize: 26
                        font.bold: true
                    }
                    MouseArea {
                        id: prevMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.cycleSession(-1)
                    }
                }

                Text {
                    anchors.left: prevBtn.right
                    anchors.right: nextBtn.left
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: "Server  ·  " + root.sessionName
                    color: "#3b4255"
                    font.family: root.fontName
                    font.pixelSize: 15
                    font.bold: true
                    MouseArea {
                        id: centerMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.cycleSession(1)
                    }
                }

                Item {
                    id: nextBtn
                    width: 44; height: parent.height
                    anchors.right: parent.right
                    Text {
                        anchors.centerIn: parent
                        text: "›"
                        color: nextMouse.containsMouse ? "#d3bc8e" : "#3b4255"
                        font.pixelSize: 26
                        font.bold: true
                    }
                    MouseArea {
                        id: nextMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.cycleSession(1)
                    }
                }
            }

            Text {
                id: statusText
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "Celestia Gateway  ·  " + root.timeNames[root.timeState]
                color: "#888c96"
                font.family: root.fontName
                font.pixelSize: 12
            }

            Rectangle {
                width: parent.width
                height: 50
                radius: 25
                color: loginBtnMouse.containsMouse ? "#4a536b" : "#3b4255"
                border.color: "#d3bc8e"
                border.width: 1.5

                Text {
                    anchors.centerIn: parent
                    text: "Enter Teyvat"
                    color: "#f4e8c1"
                    font.family: root.fontName
                    font.pixelSize: 17
                    font.bold: true
                    font.letterSpacing: 1
                }

                MouseArea {
                    id: loginBtnMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: sddm.login(userInput.text, passInput.text, root.sessionIndex)
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // ۷. دکمه‌های گوشه راست پایین
    // ═══════════════════════════════════════════════════════════════
    Column {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        anchors.right: parent.right
        anchors.rightMargin: 28
        spacing: 12

        Rectangle {
            width: 44; height: 44; radius: 8
            color: cycleMouse.containsMouse ? "#ffffff" : "#d9f4f1ea"
            border.color: "#c8c2b4"; border.width: 1

            Image {
                width: 26; height: 26
                anchors.centerIn: parent
                source: "assets/time_cycle.svg"
            }
            MouseArea {
                id: cycleMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.timeState = (root.timeState + 1) % 4
            }
        }

        Rectangle {
            width: 44; height: 44; radius: 8
            color: rebMouse.containsMouse ? "#ffffff" : "#d9f4f1ea"
            border.color: "#c8c2b4"; border.width: 1

            Image {
                width: 24; height: 24
                anchors.centerIn: parent
                source: "assets/reboot.svg"
            }
            MouseArea {
                id: rebMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sddm.reboot()
            }
        }

        Rectangle {
            width: 44; height: 44; radius: 8
            color: powMouse.containsMouse ? "#ffffff" : "#d9f4f1ea"
            border.color: "#c8c2b4"; border.width: 1

            Image {
                width: 24; height: 24
                anchors.centerIn: parent
                source: "assets/door_exit.svg"
            }
            MouseArea {
                id: powMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: sddm.powerOff()
            }
        }
    }

    // ۸. متن ورژن گوشه چپ پایین (اسم سشن انتخاب‌شده توش میاد)
    Text {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.left: parent.left
        anchors.leftMargin: 32
        text: "OSRELWin5.3.0_R_" + root.sessionName.toUpperCase().replace(/[^A-Z0-9]+/g, "_") + "_TEYVAT"
        color: "#ccffffff"
        font.family: root.fontName
        font.pixelSize: 12
        style: Text.Outline
        styleColor: "#66000000"
    }
}
