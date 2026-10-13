import QtQuick

Rectangle {
    id: badge
    property string status: "pending"
    property color accent: status === "completed" ? "#79d0c6" : status === "processing" ? "#84bef7" : status === "failed" ? "#ef9099" : "#b0a27f"
    implicitWidth: 90
    implicitHeight: 21
    radius: 11
    color: status === "completed" ? "#173532" : status === "processing" ? "#183555" : status === "failed" ? "#3b252b" : "#2b281f"
    border.color: status === "completed" ? "#2b605b" : status === "processing" ? "#346da4" : status === "failed" ? "#713941" : "#5b5139"
    Row {
        anchors.centerIn: parent
        spacing: 4
        UiIcon {
            anchors.verticalCenter: parent.verticalCenter
            width: 10
            height: 10
            name: badge.status === "completed" ? "check" : badge.status === "failed" ? "alert" : "loader"
            tint: badge.accent
        }
        Text {
            font.family: "Inter"
            font.pointSize: 9 * 0.75
            font.weight: Font.Medium
            color: badge.accent
            text: badge.status.charAt(0).toUpperCase() + badge.status.slice(1)
        }
    }
}
