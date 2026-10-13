import QtQuick

Rectangle {
    property string status: "pending"
    property color accent: status === "completed" ? "#79d0c6" : status === "processing" ? "#84bef7" : status === "failed" ? "#ef9099" : "#b0a27f"
    implicitWidth: 82
    implicitHeight: 21
    radius: 11
    color: status === "completed" ? "#173532" : status === "processing" ? "#183555" : status === "failed" ? "#3b252b" : "#2b281f"
    border.color: status === "completed" ? "#2b605b" : status === "processing" ? "#346da4" : status === "failed" ? "#713941" : "#5b5139"
    UiText {
        anchors.centerIn: parent
        font.pixelSize: 9
        color: parent.accent
        text: (parent.status === "completed" ? "✓  " : parent.status === "failed" ? "⚠  " : "○  ") + parent.status.charAt(0).toUpperCase() + parent.status.slice(1)
    }
}
