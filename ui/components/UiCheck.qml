import QtQuick
import QtQuick.Controls

CheckBox {
    id: control
    implicitWidth: 22
    implicitHeight: 22
    indicator: Rectangle {
        anchors.centerIn: parent
        width: 13
        height: 13
        radius: 3
        color: control.checked ? "#3689e6" : "#111720"
        border.color: control.activeFocus ? "#84bef7" : "#435168"
        UiText {
            anchors.centerIn: parent
            text: control.checked ? "✓" : ""
            font.pixelSize: 10
        }
    }
}
