import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: 34
    font.family: "Inter"
    font.pixelSize: 11
    leftPadding: 10
    rightPadding: 25
    contentItem: UiText {
        text: control.displayText
        verticalAlignment: Text.AlignVCenter
    }
    indicator: UiText {
        x: control.width - 21
        y: (control.height - height) / 2
        text: "⌄"
        color: "#8d9aaf"
    }
    background: Rectangle {
        radius: 7
        color: "#111720"
        border.color: control.activeFocus ? "#3689e6" : "#374355"
    }
    delegate: ItemDelegate {
        width: control.width
        height: 32
        required property var modelData
        contentItem: UiText {
            text: modelData
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: parent.highlighted ? "#183555" : "#171d27"
        }
        highlighted: control.highlightedIndex === index
        required property int index
    }
    popup: Popup {
        y: control.height + 4
        width: control.width
        padding: 1
        implicitHeight: contentItem.implicitHeight + 2
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
        }
        background: Rectangle {
            color: "#171d27"
            radius: 7
            border.color: "#374355"
        }
    }
}
