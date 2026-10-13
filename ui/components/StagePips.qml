import QtQuick
import QtQuick.Layouts

RowLayout {
    id: pips
    property var stages: []
    spacing: 7
    Repeater {
        model: 4
        Rectangle {
            required property int index
            property string stateName: pips.stages[index] || "not-started"
            implicitWidth: 22
            implicitHeight: 22
            radius: 11
            color: stateName === "completed" ? "#173532" : stateName === "failed" ? "#3c252b" : stateName === "processing" ? "#183555" : "#1a222d"
            border.color: stateName === "completed" ? "#2c625d" : stateName === "failed" ? "#743b43" : stateName === "processing" ? "#346da5" : "#3a4554"
            UiIcon {
                visible: parent.stateName === "completed" || parent.stateName === "failed"
                anchors.centerIn: parent
                width: 11
                height: 11
                name: parent.stateName === "completed" ? "check" : "x"
                tint: parent.stateName === "completed" ? "#75cfc4" : "#ef8f98"
            }
            UiText {
                visible: parent.stateName !== "completed" && parent.stateName !== "failed"
                anchors.centerIn: parent
                font.pixelSize: 9
                color: parent.stateName === "processing" ? "#7ebaf5" : "#718096"
                text: parent.index + 1
            }
            Rectangle {
                visible: parent.index < 3
                x: 22
                y: 11
                width: 7
                height: 1
                color: "#394454"
            }
        }
    }
}
