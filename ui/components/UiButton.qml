import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property string symbol: ""
    property bool primary: false
    property bool selected: false
    property string hint: ""
    implicitHeight: primary ? 42 : 34
    implicitWidth: contentItem.implicitWidth + 24
    padding: 12
    opacity: enabled ? 1 : 0.42
    hoverEnabled: true
    ToolTip.visible: hovered && hint.length > 0
    ToolTip.text: hint
    Accessible.name: text
    contentItem: Item {
        implicitWidth: buttonRow.implicitWidth
        implicitHeight: buttonRow.implicitHeight
        RowLayout {
            id: buttonRow
            anchors.centerIn: parent
            spacing: 7
            Image {
                visible: control.symbol.length > 0
                source: control.symbol.length ? "../assets/" + control.symbol + ".svg" : ""
                sourceSize.width: 16
                sourceSize.height: 16
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
            }
            UiText {
                text: control.text
                color: control.primary ? "white" : control.selected ? "#dcecff" : "#b2bdcd"
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
    background: Rectangle {
        radius: 7
        border.color: control.activeFocus ? "#66adf3" : control.primary ? "#3d94ed" : control.selected ? "#316da6" : control.hovered ? "#4a5b72" : "#374355"
        gradient: Gradient {
            GradientStop {
                position: 0
                color: control.primary ? "#3c91ea" : control.selected ? "#1a3a59" : control.hovered ? "#273243" : "#202937"
            }
            GradientStop {
                position: 1
                color: control.primary ? "#2879cf" : control.selected ? "#183555" : "#202937"
            }
        }
    }
}
