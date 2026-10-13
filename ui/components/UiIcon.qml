import QtQuick
import "IconPaths.js" as Icons

Image {
    property string name: ""
    property color tint: "#b2bdcd"
    source: name && Icons.sources[name] ? "data:image/svg+xml," + encodeURIComponent(Icons.sources[name].replace(/#b2bdcd/g, tint.toString())) : ""
    sourceSize.width: width
    sourceSize.height: height
}
