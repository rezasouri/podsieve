import QtQuick

Rectangle {
    radius: 12
    border.color: "#2a3443"
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop {
            position: 0
            color: "#1b2330"
        }
        GradientStop {
            position: 1
            color: "#161d27"
        }
    }
}
