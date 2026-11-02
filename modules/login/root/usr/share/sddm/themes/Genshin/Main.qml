import QtQuick 2.15

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#10131c"

    property int sessionIndex: (sessionModel.lastIndex >= 0) ? sessionModel.lastIndex : 0
    property int userIndex: (userModel.lastIndex >= 0) ? userModel.lastIndex : 0
    property bool failed: false
    property string tod: "day"
    property date now: new Date()
    property real shakeX: 0

    FontLoader { id: gf; source: "assets/font.ttf" }
    readonly property string ff: (gf.status === FontLoader.Ready) ? gf.name : "Noto Sans"

    // ── عکس بر اساس ساعت روز (مثل خود بازی) ──
    function updateTod() {
        var h = new Date().getHours()
        if (h >= 5 && h < 8) root.tod = "dawn"
        else if (h >= 8 && h < 17) root.tod = "day"
        else if (h >= 17 && h < 19) root.tod = "dusk"
        else root.tod = "night"
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: { root.now = new Date(); root.updateTod() }
    }

    Image {
        anchors.fill: parent
        source: "assets/" + root.tod + ".jpg"
        fillMode: Image.PreserveAspectCrop
        smooth: true
    }

    // ── لوگو: اگه logo.png هست اون، وگرنه متن ──
    Image {
        id: logo
        source: "assets/logo.png"
        width: 760
        height: 420
        fillMode: Image.PreserveAspectFit
        smooth: true
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.40 - height / 2
        visible: status === Image.Ready
    }

    Column {
        visible: logo.status !== Image.Ready
        width: 900
        spacing: 4
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.40 - height / 2

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: "GENSHIN"
            color: "#ffffff"
            font.family: root.ff
            font.pixelSize: 104
            font.letterSpacing: 10
            style: Text.Outline
            styleColor: "#661e285a"
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: "IMPACT"
            color: "#f4e8c1"
            font.family: root.ff
            font.pixelSize: 50
            font.letterSpacing: 22
            style: Text.Outline
            styleColor: "#661e285a"
        }
    }

    // ── بالا چپ: ساعت و تاریخ ──
    Column {
        x: 34
        y: 22
        spacing: 2
        Text {
            text: Qt.formatTime(root.now, "HH:mm")
            color: "#f2ffffff"
            font.family: root.ff
            font.pixelSize: 44
            style: Text.Outline
            styleColor: "#40000000"
        }
        Text {
            text: Qt.formatDate(root.now, "dddd, dd MMMM")
            color: "#d9ffffff"
            font.family: root.ff
            font.pixelSize: 18
            style: Text.Outline
            styleColor: "#40000000"
        }
    }

    // ── بالا راست: زبان کیبورد (با کلیک عوض میشه) ──
    Text {
        id: layoutLabel
        anchors.right: parent.right
        anchors.rightMargin: 34
        y: 30
        color: "#f2ffffff"
        font.family: root.ff
        font.pixelSize: 22
        style: Text.Outline
        styleColor: "#40000000"
        text: {
            if (keyboard.layouts && keyboard.layouts.length > 0)
                return "\u2328  " + keyboard.layouts[keyboard.currentLayout].shortName.toUpperCase()
            return ""
        }
        MouseArea {
            anchors.fill: parent
            anchors.margins: -8
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (keyboard.layouts && keyboard.layouts.length > 1)
                    keyboard.currentLayout = (keyboard.currentLayout + 1) % keyboard.layouts.length
            }
        }
    }

    // ── قرص‌های کاربر و جلسه، بالای نوار رمز ──
    Row {
        spacing: 14
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: bar.top
        anchors.bottomMargin: 22

        Pill {
            id: userPill
            onClicked: root.userIndex = (root.userIndex + 1) % Math.max(1, userRep.count)
            Repeater {
                id: userRep
                model: userModel
                delegate: Text {
                    property string uname: model.name
                    anchors.centerIn: parent
                    visible: index === root.userIndex
                    text: ((model.realName && model.realName !== "") ? model.realName : model.name) + "  \u25BE"
                    color: "#ffffff"
                    font.family: root.ff
                    font.pixelSize: 16
                }
            }
        }

        Pill {
            id: sessPill
            onClicked: root.sessionIndex = (root.sessionIndex + 1) % Math.max(1, sessRep.count)
            Repeater {
                id: sessRep
                model: sessionModel
                delegate: Text {
                    anchors.centerIn: parent
                    visible: index === root.sessionIndex
                    text: model.name + "  \u25BE"
                    color: "#ffffff"
                    font.family: root.ff
                    font.pixelSize: 16
                }
            }
        }
    }

    // ── نوار «Click to Start» که اینجا فیلد رمزه ──
    Rectangle {
        id: bar
        width: 440
        height: 54
        radius: height / 2
        color: "#61000000"
        border.width: 1
        border.color: root.failed ? "#ffff7864" : "#99ffffff"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: root.shakeX
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 82

        Text {
            anchors.centerIn: parent
            visible: pw.text.length === 0
            text: root.failed ? "Wrong Password" : "Enter Password to Start"
            color: root.failed ? "#ff7864" : "#ffffff"
            font.family: root.ff
            font.pixelSize: 17
            font.letterSpacing: 2.5
        }

        TextInput {
            id: pw
            anchors.fill: parent
            anchors.leftMargin: 24
            anchors.rightMargin: 24
            horizontalAlignment: TextInput.AlignHCenter
            verticalAlignment: TextInput.AlignVCenter
            echoMode: TextInput.Password
            passwordCharacter: "\u25CF"
            color: "#ffffff"
            font.family: root.ff
            font.pixelSize: 18
            focus: true
            clip: true
            onTextEdited: root.failed = false
            onAccepted: root.doLogin()
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: bar.bottom
        anchors.topMargin: 10
        visible: keyboard.capsLock
        text: "Caps Lock is on"
        color: "#f4d35e"
        font.family: root.ff
        font.pixelSize: 14
    }

    // ── گوشه‌های پایین ──
    Text {
        anchors.left: parent.left
        anchors.leftMargin: 30
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 22
        text: "Ver. 1.0  \u00B7  Arch Linux"
        color: "#bfffffff"
        font.family: root.ff
        font.pixelSize: 14
        style: Text.Outline
        styleColor: "#40000000"
    }

    Row {
        spacing: 10
        anchors.right: parent.right
        anchors.rightMargin: 30
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 16

        Pill {
            width: 96; height: 34
            visible: sddm.canSuspend
            onClicked: sddm.suspend()
            Text { anchors.centerIn: parent; text: "Sleep"; color: "#ffffff"; font.family: root.ff; font.pixelSize: 14 }
        }
        Pill {
            width: 96; height: 34
            visible: sddm.canReboot
            onClicked: sddm.reboot()
            Text { anchors.centerIn: parent; text: "Reboot"; color: "#ffffff"; font.family: root.ff; font.pixelSize: 14 }
        }
        Pill {
            width: 110; height: 34
            visible: sddm.canPowerOff
            onClicked: sddm.powerOff()
            Text { anchors.centerIn: parent; text: "Shut Down"; color: "#ffffff"; font.family: root.ff; font.pixelSize: 14 }
        }
    }

    // ── لاگین ──
    function doLogin() {
        var u = userRep.itemAt(root.userIndex)
        if (!u) return
        sddm.login(u.uname, pw.text, root.sessionIndex)
    }

    SequentialAnimation {
        id: shake
        NumberAnimation { target: root; property: "shakeX"; to: -14; duration: 50 }
        NumberAnimation { target: root; property: "shakeX"; to: 14; duration: 80 }
        NumberAnimation { target: root; property: "shakeX"; to: -8; duration: 70 }
        NumberAnimation { target: root; property: "shakeX"; to: 0; duration: 50 }
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.failed = true
            pw.text = ""
            shake.restart()
            pw.forceActiveFocus()
        }
    }

    Component.onCompleted: pw.forceActiveFocus()
}
