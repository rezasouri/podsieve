import QtQuick
import QtQuick.Controls

TextField {
    property bool mono: false
    implicitHeight: 34
    color: "#f1f4f9"
    placeholderTextColor: "#68758a"
    font.family: mono ? "JetBrains Mono" : "Inter"
    font.pixelSize: 11
    leftPadding: 10
    selectByMouse: true
    opacity: enabled ? 1 : 0.45
    background: Rectangle {
        radius: 7
        color: "#111720"
        border.color: parent.activeFocus ? "#3689e6" : parent.hovered ? "#46546a" : "#374355"
        border.width: parent.activeFocus ? 2 : 1
    }
}
