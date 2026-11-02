import QtQuick 2.15

// قرص گرد نیمه‌شفاف با قاب سفید، مثل دکمه‌های صفحه‌ی شروع بازی
Rectangle {
    id: pill
    signal clicked()
    width: 200
    height: 40
    radius: height / 2
    color: ma.containsMouse ? "#5c000000" : "#47000000"
    border.width: 1
    border.color: ma.containsMouse ? "#ffffffff" : "#80ffffff"

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pill.clicked()
    }
}
