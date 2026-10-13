import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property string symbol: ""
    property bool primary: false
    property bool selected: false
    property string hint: ""
    property real textSize: 11
    property int iconSize: 16
    property bool danger: false
    property color textColor: danger ? "#ec959d" : primary ? "white" : selected ? "#dcecff" : "#b2bdcd"
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
            UiIcon {
                visible: control.symbol.length > 0
                name: control.symbol
                tint: control.textColor
                sourceSize.width: control.iconSize
                sourceSize.height: control.iconSize
                Layout.preferredWidth: control.iconSize
                Layout.preferredHeight: control.iconSize
            }
            Text {
                font.family: "Inter"
                font.pointSize: control.textSize * 0.75
                text: control.text
                color: control.textColor
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
    background: Rectangle {
        radius: 7
        border.width: control.flat ? 0 : 1
        border.color: control.danger ? "#6e3a41" : control.activeFocus ? "#66adf3" : control.primary ? "#3d94ed" : control.selected ? "#316da6" : control.hovered ? "#4a5b72" : "#374355"
        gradient: Gradient {
            GradientStop {
                position: 0
                color: control.flat ? (control.hovered ? "#202937" : "transparent") : control.danger ? (control.hovered ? "#472a31" : "#35242a") : control.primary ? "#3c91ea" : control.selected ? "#1a3a59" : control.hovered ? "#273243" : "#202937"
            }
            GradientStop {
                position: 1
                color: control.flat ? (control.hovered ? "#202937" : "transparent") : control.danger ? (control.hovered ? "#472a31" : "#35242a") : control.primary ? "#2879cf" : control.selected ? "#183555" : "#202937"
            }
        }
    }
}
