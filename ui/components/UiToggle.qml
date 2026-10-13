import QtQuick
import QtQuick.Controls

Switch {
    id: control
    implicitHeight: 24
    spacing: 8
    font.pixelSize: 10
    indicator: Rectangle {
        x: control.width - width
        y: (control.height - height) / 2
        width: 28
        height: 16
        radius: 8
        color: control.checked ? "#3689e6" : "#3a4453"
        border.color: control.activeFocus ? "#8fc5fb" : color
        Rectangle {
            x: control.checked ? 14 : 2
            y: 2
            width: 12
            height: 12
            radius: 6
            color: control.checked ? "white" : "#aeb8c7"
            Behavior on x {
                NumberAnimation {
                    duration: 160
                }
            }
        }
    }
    contentItem: UiText {
        text: control.text
        color: "#8d9aaf"
        rightPadding: 38
        verticalAlignment: Text.AlignVCenter
    }
}
