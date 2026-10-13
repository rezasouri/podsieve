import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import "components"

Item {
    id: manager
    objectName: "processedData"
    signal addSource
    property string selectedKey: ""
    property var checkedRows: []
    property int page: 1
    property int inspectorTab: 0
    property bool previewOpen: false
    property real displayScale: 1
    property bool compact: width <= 1280
    property int sideMargin: compact ? 18 : 24
    property var records: pipelineBridge.sources
    property var selected: records.find(row => row.key === selectedKey) || null
    property var filtered: {
        const query = search.text.toLowerCase();
        const speaker = speakers.currentIndex === 0 ? "" : speakers.currentText;
        const status = statuses.currentIndex === 0 ? "" : statuses.currentText.toLowerCase();
        return records.filter(row => (!speaker || row.speaker === speaker) && (!status || row.status === status) && [row.id, row.speaker, row.speakerName, row.name, row.sourceRef].some(value => String(value).toLowerCase().includes(query))).sort((a, b) => sorting.currentIndex === 1 ? a.name.localeCompare(b.name) : sorting.currentIndex === 2 ? b.bytes - a.bytes : sorting.currentIndex === 3 ? b.stages.filter(s => s === "completed").length - a.stages.filter(s => s === "completed").length : b.updated.localeCompare(a.updated));
    }
    property int pageCount: Math.max(1, Math.ceil(filtered.length / 6))
    property var visibleRecords: filtered.slice((page - 1) * 6, page * 6)
    property var metrics: [
        {
            label: "Total Sources",
            value: records.length,
            icon: "database",
            color: "#7eb7ef"
        },
        {
            label: "Fully Processed",
            value: records.filter(r => r.status === "completed").length,
            icon: "check",
            color: "#77cfc5"
        },
        {
            label: "In Progress",
            value: records.filter(r => r.status === "processing").length,
            icon: "loader",
            color: "#e8a44b"
        },
        {
            label: "Failed",
            value: records.filter(r => r.status === "failed").length,
            icon: "alert",
            color: "#ed8b94"
        },
        {
            label: "Total Storage Used",
            value: (records.reduce((s, r) => s + r.bytes, 0) / 1024 / 1024 / 1024).toFixed(2) + " GB",
            icon: "folder",
            color: "#7eb7ef"
        }
    ]
    function clearFilters() {
        search.text = "";
        speakers.currentIndex = 0;
        statuses.currentIndex = 0;
        page = 1;
    }
    function choose(row) {
        selectedKey = row.key;
        previewOpen = false;
        player.stop();
    }
    function toggleChecked(key, checked) {
        checkedRows = checked ? Array.from(new Set(checkedRows.concat([key]))) : checkedRows.filter(k => k !== key);
    }
    onRecordsChanged: {
        if (!records.some(row => row.key === selectedKey))
            selectedKey = records.length ? records[0].key : "";
        checkedRows = checkedRows.filter(key => records.some(row => row.key === key));
        page = Math.min(page, pageCount);
    }
    Component.onCompleted: if (filtered.length)
        selectedKey = filtered[0].key
    onFilteredChanged: {
        if (!filtered.some(row => row.key === selectedKey))
            selectedKey = filtered.length ? filtered[0].key : "";
    }
    onPageCountChanged: page = Math.min(page, pageCount)
    onSelectedKeyChanged: {
        player.stop();
        previewOpen = false;
    }
    onVisibleChanged: if (!visible)
        player.stop()
    function clock(milliseconds) {
        const s = Math.floor(milliseconds / 1000);
        return Math.floor(s / 60).toString().padStart(2, "0") + ":" + (s % 60).toString().padStart(2, "0");
    }
    MediaPlayer {
        id: player
        source: manager.previewOpen && manager.selected ? manager.selected.previewUri : ""
        audioOutput: AudioOutput {
            volume: 0.8
        }
        onErrorOccurred: {
            previewError.text = errorString;
            previewError.visible = true;
        }
    }
    component DataText: Text {
        color: "#dbe1ea"
        font.family: "Inter"
        font.pixelSize: 11
        font.weight: Font.Normal
        font.bold: false
        elide: Text.ElideRight
    }
    component Caption: DataText {
        color: "#8d9aaf"
        font.pixelSize: 10
    }
    component DataCard: Rectangle {
        radius: 11
        border.color: "#2a3443"
        gradient: Gradient {
            GradientStop {
                position: 0
                color: "#19202b"
            }
            GradientStop {
                position: 1
                color: "#141b25"
            }
        }
    }
    component Separator: Rectangle {
        Layout.fillWidth: true
        implicitHeight: 1
        color: "#2a3443"
    }
    component TableCells: RowLayout {
        property bool header: false
        property var row: ({})
        spacing: 8
        UiCheck {
            light: true
            Layout.preferredWidth: 28
            Layout.minimumWidth: 28
            Layout.maximumWidth: 28
            checked: parent.header ? manager.visibleRecords.length > 0 && manager.visibleRecords.every(r => manager.checkedRows.includes(r.key)) : manager.checkedRows.includes(parent.row.key)
            onToggled: {
                if (parent.header)
                    manager.visibleRecords.forEach(r => manager.toggleChecked(r.key, checked));
                else
                    manager.toggleChecked(parent.row.key, checked);
            }
            Accessible.name: parent.header ? "Select all visible sources" : "Select " + parent.row.id
        }
        DataText {
            Layout.preferredWidth: 88
            Layout.minimumWidth: 88
            Layout.maximumWidth: 88
            text: parent.header ? "SOURCE ID" : parent.row.id || ""
            color: "#aab5c5"
            font.family: "JetBrains Mono"
            font.pixelSize: 10
        }
        ColumnLayout {
            Layout.preferredWidth: 122
            Layout.minimumWidth: 122
            Layout.maximumWidth: 122
            spacing: 4
            DataText {
                Layout.fillWidth: true
                text: parent.parent.header ? "REGISTERED SPEAKER" : parent.parent.row.speakerName || ""
                color: parent.parent.header ? "#77869b" : "#dbe1ea"
                font.pixelSize: parent.parent.header ? 9 : 11
                font.weight: Font.Medium
            }
            Caption {
                Layout.fillWidth: true
                visible: !parent.parent.header
                text: parent.parent.row.speaker || ""
                font.pixelSize: 10
                color: "#6f7c90"
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 170
            spacing: 4
            DataText {
                Layout.fillWidth: true
                text: parent.parent.header ? "SOURCE NAME" : parent.parent.row.name || ""
                color: parent.parent.header ? "#77869b" : "#dbe1ea"
                font.pixelSize: parent.parent.header ? 9 : 11
                font.weight: Font.Medium
            }
            Caption {
                Layout.fillWidth: true
                visible: !parent.parent.header
                text: parent.parent.row.sourceRef || ""
                font.pixelSize: 10
            }
        }
        Item {
            Layout.preferredWidth: 74
            Layout.minimumWidth: 74
            Layout.maximumWidth: 74
            implicitHeight: 22
            Caption {
                visible: parent.parent.header
                text: "INPUT"
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                visible: !parent.parent.header
                property string provider: parent.parent.row.input || ""
                width: inputLabel.implicitWidth + 12
                height: 20
                radius: 5
                anchors.verticalCenter: parent.verticalCenter
                color: provider === "YouTube" ? "#322127" : provider === "Castbox" ? "#30291e" : "#1b232e"
                border.color: provider === "YouTube" ? "#60353c" : provider === "Castbox" ? "#5e4b2e" : "#3b4655"
                DataText {
                    id: inputLabel
                    anchors.centerIn: parent
                    text: parent.provider
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    color: parent.provider === "YouTube" ? "#e2a0a7" : parent.provider === "Castbox" ? "#d5b989" : "#9eabba"
                }
            }
        }
        Item {
            Layout.preferredWidth: 125
            Layout.minimumWidth: 125
            Layout.maximumWidth: 125
            implicitHeight: 22
            Caption {
                visible: parent.parent.header
                text: "PIPELINE STAGES"
            }
            StagePips {
                visible: !parent.parent.header
                stages: parent.parent.row.stages || []
            }
        }
        Item {
            Layout.preferredWidth: 90
            Layout.minimumWidth: 90
            Layout.maximumWidth: 90
            implicitHeight: 22
            Caption {
                visible: parent.parent.header
                text: "STATUS"
            }
            StatusBadge {
                visible: !parent.parent.header
                status: parent.parent.row.status || "pending"
            }
        }
        Caption {
            Layout.preferredWidth: 67
            Layout.minimumWidth: 67
            Layout.maximumWidth: 67
            text: parent.header ? "STORAGE" : parent.row.size || ""
            font.family: "JetBrains Mono"
            font.pixelSize: 10
        }
        ColumnLayout {
            Layout.preferredWidth: 83
            Layout.minimumWidth: 83
            Layout.maximumWidth: 83
            spacing: 4
            Caption {
                text: parent.parent.header ? "UPDATED" : (parent.parent.row.updated || "—").split(" ")[0]
            }
            Caption {
                visible: !parent.parent.header
                text: (parent.parent.row.updated || "").split(" ")[1] || ""
                font.pixelSize: 10
            }
        }
        UiButton {
            visible: !parent.header
            Layout.preferredWidth: 27
            Layout.minimumWidth: 27
            Layout.maximumWidth: 27
            implicitHeight: 27
            symbol: "more"
            flat: true
            iconSize: 14
            hint: "View source files"
            onClicked: {
                manager.choose(parent.row);
                manager.inspectorTab = 2;
            }
        }
        Item {
            visible: parent.header
            Layout.preferredWidth: 27
            Layout.minimumWidth: 27
            Layout.maximumWidth: 27
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: manager.sideMargin
        anchors.rightMargin: manager.sideMargin
        anchors.topMargin: manager.compact ? 10 : 17
        anchors.bottomMargin: manager.compact ? 12 : 20
        spacing: manager.compact ? 9 : 13
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: manager.compact ? 49 : 60
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Caption {
                    text: "LOCAL SOURCE REGISTRY"
                    leftPadding: 12
                    font.letterSpacing: 0.7
                    Rectangle {
                        x: 0
                        anchors.verticalCenter: parent.verticalCenter
                        width: 5
                        height: 5
                        radius: 3
                        color: "#35b8a9"
                        Rectangle {
                            anchors.centerIn: parent
                            width: 11
                            height: 11
                            radius: 6
                            color: "#1935b8a9"
                        }
                    }
                    font.pixelSize: 10
                }
                DataText {
                    text: "Processed Data"
                    font.pixelSize: 20
                    font.bold: true
                }
                Caption {
                    text: "Browse, inspect, and manage your processed audio sources."
                    font.pixelSize: 11
                }
            }
            Item {
                Layout.fillWidth: true
            }
            UiField {
                id: search
                objectName: "sourceSearch"
                Layout.preferredWidth: Math.max(280, Math.min(430, manager.width * 0.27))
                leftPadding: 34
                font.family: "Inter"
                UiIcon {
                    name: "search"
                    tint: "#718096"
                    width: 16
                    height: 16
                    x: 11
                    anchors.verticalCenter: parent.verticalCenter
                }
                placeholderText: "Search sources, speakers, files, or URLs…"
                onTextChanged: manager.page = 1
                Accessible.name: "Search processed sources"
            }
            UiButton {
                text: "Refresh"
                textSize: 10.5
                iconSize: 14
                symbol: "refresh"
                enabled: !pipelineBridge.busy
                onClicked: pipelineBridge.refreshSources()
            }
            UiButton {
                text: "Add new source"
                textSize: 10.5
                symbol: "plus"
                selected: true
                textColor: "white"
                background: Rectangle {
                    radius: 6
                    color: "#246fb8"
                    border.color: "#367eba"
                }
                onClicked: manager.addSource()
            }
        }
        DataCard {
            Layout.fillWidth: true
            Layout.preferredHeight: manager.compact ? 60 : 67
            RowLayout {
                anchors.fill: parent
                spacing: 0
                Repeater {
                    model: manager.metrics
                    Item {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 10
                            Rectangle {
                                width: 30
                                height: 30
                                radius: 7
                                color: index === 1 ? "#173532" : index === 2 ? "#362b1d" : index === 3 ? "#3c252b" : "#192b3e"
                                border.color: index === 1 ? "#2c625d" : index === 2 ? "#6b512d" : index === 3 ? "#743b43" : "#324256"
                                UiIcon {
                                    anchors.centerIn: parent
                                    name: modelData.icon
                                    tint: modelData.color
                                    width: 16
                                    height: 16
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3
                                Caption {
                                    text: modelData.label
                                    Layout.fillWidth: true
                                }
                                DataText {
                                    text: String(modelData.value)
                                    color: "#f1f4f9"
                                    font.family: index === 4 ? "JetBrains Mono" : "Inter"
                                    font.pixelSize: index === 4 ? 12 : 14
                                    font.bold: true
                                }
                            }
                        }
                        Rectangle {
                            visible: index < 4
                            anchors.right: parent.right
                            height: parent.height
                            width: 1
                            color: "#2a3443"
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12
            DataCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 460
                Layout.preferredWidth: 950
                clip: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 51
                        Layout.leftMargin: 15
                        Layout.rightMargin: 12
                        spacing: 6
                        DataText {
                            text: "Registered Sources"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                        Caption {
                            text: manager.filtered.length + " records"
                            Layout.fillWidth: true
                        }
                        UiCombo {
                            id: speakers
                            objectName: "speakerFilter"
                            model: ["All speakers"].concat(Array.from(new Set(manager.records.map(r => r.speaker))))
                            Layout.preferredWidth: 108
                            textSize: 10
                            implicitHeight: 28
                            onActivated: manager.page = 1
                        }
                        UiCombo {
                            id: statuses
                            objectName: "statusFilter"
                            model: ["All statuses", "Completed", "Processing", "Failed", "Pending"]
                            Layout.preferredWidth: 103
                            textSize: 10
                            implicitHeight: 28
                            onActivated: manager.page = 1
                        }
                        UiCombo {
                            id: sorting
                            model: ["Newest updated", "Filename A–Z", "Largest storage", "Most processed"]
                            Layout.preferredWidth: 122
                            textSize: 10
                            implicitHeight: 28
                            onActivated: manager.page = 1
                        }
                    }
                    Separator {}
                    Flickable {
                        id: table
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        contentWidth: Math.max(width, 969)
                        contentHeight: Math.max(height, 34 + manager.visibleRecords.length * (manager.compact ? 53 : 58))
                        ScrollBar.horizontal: ScrollBar {}
                        ScrollBar.vertical: ScrollBar {}
                        Rectangle {
                            width: table.contentWidth
                            height: 34
                            color: "#141b24"
                            TableCells {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                header: true
                            }
                        }
                        Column {
                            y: 34
                            width: table.contentWidth
                            Repeater {
                                model: manager.visibleRecords
                                Rectangle {
                                    required property var modelData
                                    width: table.contentWidth
                                    height: manager.compact ? 53 : 58
                                    color: rowMouse.containsMouse ? "#202936" : "transparent"
                                    gradient: manager.selectedKey === modelData.key ? selectionGradient : null
                                    Gradient {
                                        id: selectionGradient
                                        orientation: Gradient.Horizontal
                                        GradientStop {
                                            position: 0
                                            color: "#6b1d476f"
                                        }
                                        GradientStop {
                                            position: 1
                                            color: "#52192a3b"
                                        }
                                    }
                                    MouseArea {
                                        id: rowMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: manager.choose(modelData)
                                    }
                                    TableCells {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        row: modelData
                                    }
                                    Rectangle {
                                        width: parent.width
                                        height: 1
                                        anchors.bottom: parent.bottom
                                        color: "#2a3443"
                                    }
                                    Rectangle {
                                        visible: manager.selectedKey === modelData.key
                                        y: 7
                                        width: 2
                                        height: parent.height - 14
                                        color: "#4b9af2"
                                    }
                                }
                            }
                        }
                        ColumnLayout {
                            visible: manager.filtered.length === 0
                            x: Math.max(0, (table.width - width) / 2)
                            y: Math.max(70, (table.height - height) / 2)
                            spacing: 10
                            Image {
                                source: "assets/search.svg"
                                Layout.alignment: Qt.AlignHCenter
                                width: 32
                                height: 32
                            }
                            DataText {
                                text: manager.records.length ? "No matching sources" : "No registered sources"
                                Layout.alignment: Qt.AlignHCenter
                            }
                            Caption {
                                text: manager.records.length ? "Try changing your search or filter criteria." : "Add an audio source to begin processing."
                            }
                            UiButton {
                                text: manager.records.length ? "Clear filters" : "Add new source"
                                Layout.alignment: Qt.AlignHCenter
                                onClicked: manager.records.length ? manager.clearFilters() : manager.addSource()
                            }
                        }
                    }
                    Separator {}
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 43
                        Layout.leftMargin: 15
                        Layout.rightMargin: 11
                        Caption {
                            text: manager.checkedRows.length ? manager.checkedRows.length + " selected" : "Showing " + manager.visibleRecords.length + " of " + manager.filtered.length
                            Layout.fillWidth: true
                        }
                        UiButton {
                            text: "Previous"
                            textSize: 10
                            padding: 9
                            implicitHeight: 26
                            enabled: manager.page > 1
                            onClicked: manager.page--
                        }
                        Caption {
                            text: "Page " + manager.page + " of " + manager.pageCount
                        }
                        UiButton {
                            text: "Next"
                            textSize: 10
                            padding: 9
                            implicitHeight: 26
                            enabled: manager.page < manager.pageCount
                            onClicked: manager.page++
                        }
                    }
                }
            }
            DataCard {
                Layout.preferredWidth: Math.max(manager.compact ? 350 : 365, (manager.width - manager.sideMargin * 2 - 12) * (manager.compact ? 0.9 / 2.75 : 0.95 / 3))
                Layout.minimumWidth: manager.compact ? 350 : 365
                Layout.maximumWidth: Layout.preferredWidth
                Layout.fillHeight: true
                clip: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    visible: manager.selected !== null
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: manager.compact ? 62 : 69
                        Layout.leftMargin: 13
                        Layout.rightMargin: 13
                        spacing: 10
                        Rectangle {
                            width: 36
                            height: 36
                            radius: 8
                            color: manager.selected && manager.selected.input === "YouTube" ? "#3c252b" : manager.selected && manager.selected.input === "Castbox" ? "#362b1d" : "#19324a"
                            border.color: manager.selected && manager.selected.input === "YouTube" ? "#743b43" : manager.selected && manager.selected.input === "Castbox" ? "#6b512d" : "#355f86"
                            UiIcon {
                                anchors.centerIn: parent
                                tint: manager.selected && manager.selected.input === "YouTube" ? "#ed8b94" : "#7eb7ef"
                                width: 18
                                height: 18
                                name: manager.selected && manager.selected.input === "Local File" ? "file" : "link"
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Caption {
                                text: "SOURCE INSPECTOR"
                                font.pixelSize: 10
                            }
                            DataText {
                                text: manager.selected ? manager.selected.name : ""
                                Layout.fillWidth: true
                                font.weight: Font.DemiBold
                            }
                            Caption {
                                text: manager.selected ? manager.selected.id : ""
                                font.family: "JetBrains Mono"
                                font.pixelSize: 10
                            }
                        }
                        StatusBadge {
                            status: manager.selected ? manager.selected.status : "pending"
                        }
                    }
                    Separator {}
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 39
                        Layout.leftMargin: 10
                        Layout.rightMargin: 10
                        spacing: 3
                        Repeater {
                            model: ["Overview", "Processing Stages", "Files"]
                            UiButton {
                                required property string modelData
                                required property int index
                                text: modelData + (index === 2 && manager.selected ? "  " + manager.selected.artifacts : "")
                                contentItem: Row {
                                    spacing: 5
                                    DataText {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        color: manager.inspectorTab === index ? "#dcecff" : "#8d9aaf"
                                    }
                                    Rectangle {
                                        visible: index === 2
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: Math.max(17, countText.implicitWidth + 8)
                                        height: 15
                                        radius: 8
                                        color: "#283241"
                                        Caption {
                                            id: countText
                                            anchors.centerIn: parent
                                            text: manager.selected ? manager.selected.artifacts : 0
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                                textSize: 10
                                textColor: manager.inspectorTab === index ? "#dcecff" : "#8d9aaf"
                                padding: 9
                                implicitHeight: 38
                                flat: true
                                background: Item {
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.leftMargin: 7
                                        anchors.rightMargin: 7
                                        height: 2
                                        visible: manager.inspectorTab === index
                                        color: "#4b9af2"
                                    }
                                }
                                onClicked: manager.inspectorTab = index
                            }
                        }
                    }
                    Separator {}
                    ScrollView {
                        id: inspector
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ColumnLayout {
                            width: inspector.availableWidth
                            spacing: 0
                            ColumnLayout {
                                visible: manager.inspectorTab === 0
                                Layout.fillWidth: true
                                Layout.leftMargin: 14
                                Layout.rightMargin: 14
                                Layout.topMargin: 4
                                Layout.bottomMargin: 14
                                spacing: 0
                                Repeater {
                                    model: manager.selected ? [["Source ID", manager.selected.id], ["Speaker ID", manager.selected.speaker], ["Registered speaker", manager.selected.speakerName], ["Original filename", manager.selected.name], ["Input type", manager.selected.input], ["Language", ({
                                                    fa: "Persian (fa)",
                                                    en: "English (en)"
                                                })[manager.selected.language] || manager.selected.language], ["Created", manager.selected.created], ["Last updated", manager.selected.updated], ["Storage used", manager.selected.size]] : []
                                    ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 0
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 35
                                            Caption {
                                                text: modelData[0]
                                                Layout.preferredWidth: 120
                                            }
                                            DataText {
                                                text: modelData[1]
                                                Layout.fillWidth: true
                                                horizontalAlignment: Text.AlignRight
                                                font.pixelSize: 10
                                                font.weight: Font.Medium
                                                color: "#c8d0dc"
                                            }
                                        }
                                        Separator {}
                                    }
                                }
                                Caption {
                                    text: "Original source"
                                    Layout.topMargin: 11
                                    Layout.bottomMargin: 5
                                }
                                UiField {
                                    readOnly: true
                                    mono: true
                                    implicitHeight: 31
                                    font.pixelSize: 10
                                    text: manager.selected ? manager.selected.sourceRef : ""
                                    Layout.fillWidth: true
                                }
                                Caption {
                                    text: "Output directory"
                                    Layout.topMargin: 11
                                    Layout.bottomMargin: 5
                                }
                                UiField {
                                    readOnly: true
                                    mono: true
                                    implicitHeight: 31
                                    font.pixelSize: 10
                                    text: manager.selected ? manager.selected.outputPath : ""
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                visible: manager.inspectorTab === 1
                                Layout.fillWidth: true
                                Layout.leftMargin: 14
                                Layout.rightMargin: 14
                                Layout.topMargin: 12
                                spacing: 0
                                Repeater {
                                    model: manager.selected ? manager.selected.stages : []
                                    Item {
                                        id: historyRow
                                        required property string modelData
                                        required property int index
                                        Layout.fillWidth: true
                                        implicitHeight: 70
                                        Rectangle {
                                            visible: historyRow.index < 3
                                            x: 13
                                            y: 26
                                            width: 1
                                            height: 44
                                            color: "#34404f"
                                        }
                                        Rectangle {
                                            width: 27
                                            height: 27
                                            radius: 14
                                            color: historyRow.modelData === "completed" ? "#173532" : historyRow.modelData === "failed" ? "#3b252b" : historyRow.modelData === "processing" ? "#183555" : "#19212b"
                                            border.color: historyRow.modelData === "completed" ? "#2b625c" : historyRow.modelData === "failed" ? "#713a42" : historyRow.modelData === "processing" ? "#346da4" : "#3c4655"
                                            UiIcon {
                                                visible: historyRow.modelData === "completed" || historyRow.modelData === "failed"
                                                anchors.centerIn: parent
                                                width: 12
                                                height: 12
                                                name: historyRow.modelData === "completed" ? "check" : "x"
                                                tint: historyRow.modelData === "completed" ? "#75cfc5" : "#ef9099"
                                            }
                                            Caption {
                                                visible: historyRow.modelData !== "completed" && historyRow.modelData !== "failed"
                                                anchors.centerIn: parent
                                                text: historyRow.index + 1
                                            }
                                        }
                                        Column {
                                            x: 36
                                            y: 2
                                            width: Math.max(0, parent.width - 145)
                                            spacing: 4
                                            DataText {
                                                text: ["Ingest", "Convert", "Separate", "Diarize"][historyRow.index]
                                                font.pixelSize: 10
                                                font.weight: Font.DemiBold
                                            }
                                            Caption {
                                                width: parent.width
                                                wrapMode: Text.WordWrap
                                                text: ["Import or download source audio", "Prepare the working WAV file", "Extract the vocal audio track", "Create speaker-labeled segments"][historyRow.index]
                                            }
                                        }
                                        Caption {
                                            anchors.right: parent.right
                                            y: 4
                                            width: 100
                                            horizontalAlignment: Text.AlignRight
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 10
                                            text: manager.selected ? manager.selected.stageTimes[historyRow.index] : "—"
                                            wrapMode: Text.WordWrap
                                        }
                                    }
                                }
                                Caption {
                                    visible: manager.selected && manager.selected.failure.length > 0
                                    text: manager.selected ? manager.selected.failure : ""
                                    color: "#e06c75"
                                    wrapMode: Text.WrapAnywhere
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                visible: manager.inspectorTab === 2
                                Layout.fillWidth: true
                                Layout.margins: 10
                                spacing: 7
                                Repeater {
                                    model: manager.selected ? manager.selected.fileGroups : []
                                    ColumnLayout {
                                        id: fileGroup
                                        required property var modelData
                                        property bool expanded: ["Raw Audio", "Separated Audio", "Diarization"].includes(modelData.name)
                                        Layout.fillWidth: true
                                        spacing: 5
                                        UiButton {
                                            contentItem: RowLayout {
                                                spacing: 7
                                                Caption {
                                                    text: fileGroup.expanded ? "⌄" : "›"
                                                    font.pixelSize: 12
                                                }
                                                UiIcon {
                                                    name: "folder"
                                                    tint: "#d5b989"
                                                    Layout.preferredWidth: 15
                                                    Layout.preferredHeight: 15
                                                }
                                                DataText {
                                                    text: fileGroup.modelData.name
                                                    font.pixelSize: 10
                                                    Layout.fillWidth: true
                                                }
                                                Caption {
                                                    text: fileGroup.modelData.files.filter(f => f.available).length + "/" + fileGroup.modelData.files.length
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: 10
                                                }
                                            }
                                            symbol: "folder"
                                            flat: true
                                            textSize: 10
                                            Layout.fillWidth: true
                                            implicitHeight: 28
                                            onClicked: fileGroup.expanded = !fileGroup.expanded
                                        }
                                        Repeater {
                                            model: fileGroup.expanded ? fileGroup.modelData.files : []
                                            RowLayout {
                                                required property var modelData
                                                Layout.fillWidth: true
                                                Layout.leftMargin: 26
                                                Layout.preferredHeight: 30
                                                spacing: 5
                                                opacity: modelData.available ? 1 : 0.45
                                                UiIcon {
                                                    name: "file"
                                                    Layout.preferredWidth: 15
                                                    Layout.preferredHeight: 15
                                                    tint: "#718096"
                                                }
                                                DataText {
                                                    text: modelData.name
                                                    Layout.fillWidth: true
                                                    font.pixelSize: 10
                                                    elide: Text.ElideMiddle
                                                }
                                                Caption {
                                                    text: modelData.available ? modelData.size : "Not generated"
                                                    font.pixelSize: 10
                                                }
                                                UiButton {
                                                    symbol: "copy"
                                                    implicitHeight: 22
                                                    flat: true
                                                    iconSize: 11
                                                    Layout.preferredWidth: 22
                                                    enabled: modelData.available
                                                    hint: "Copy artifact path"
                                                    onClicked: pipelineBridge.copyArtifactPath(modelData.path)
                                                }
                                                UiButton {
                                                    symbol: "external"
                                                    implicitHeight: 22
                                                    flat: true
                                                    iconSize: 11
                                                    Layout.preferredWidth: 22
                                                    enabled: modelData.available
                                                    hint: "Open containing folder"
                                                    onClicked: pipelineBridge.openArtifactFolder(modelData.path)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Rectangle {
                        visible: manager.previewOpen
                        Layout.fillWidth: true
                        implicitHeight: 90
                        color: "#101923"
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 9
                            spacing: 5
                            RowLayout {
                                Layout.fillWidth: true
                                UiButton {
                                    text: player.playbackState === MediaPlayer.PlayingState ? "Pause" : "Play"
                                    symbol: "play"
                                    implicitHeight: 28
                                    onClicked: {
                                        previewError.visible = false;
                                        player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play();
                                    }
                                }
                                Caption {
                                    text: manager.selected ? manager.selected.previewName : ""
                                    Layout.fillWidth: true
                                }
                                Caption {
                                    text: manager.clock(player.position) + " / " + manager.clock(player.duration)
                                }
                                UiButton {
                                    symbol: "x"
                                    Layout.preferredWidth: 27
                                    implicitHeight: 27
                                    onClicked: {
                                        player.stop();
                                        manager.previewOpen = false;
                                    }
                                }
                            }
                            Slider {
                                from: 0
                                to: Math.max(1, player.duration)
                                value: player.position
                                Layout.fillWidth: true
                                onMoved: player.setPosition(value)
                            }
                            Caption {
                                id: previewError
                                visible: false
                                color: "#e06c75"
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                    Separator {}
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 10
                        spacing: 5
                        UiButton {
                            text: "Open output"
                            symbol: "folder"
                            implicitHeight: 32
                            textSize: 10
                            iconSize: 13
                            padding: 7
                            Layout.fillWidth: true
                            enabled: manager.selected && manager.selected.outputAvailable
                            onClicked: pipelineBridge.openArtifactFolder(manager.selected.outputPath)
                        }
                        UiButton {
                            text: "Preview audio"
                            symbol: "volume"
                            implicitHeight: 32
                            textSize: 10
                            iconSize: 13
                            padding: 7
                            Layout.fillWidth: true
                            enabled: manager.selected && manager.selected.previewUri.length > 0
                            onClicked: {
                                manager.previewOpen = !manager.previewOpen;
                                if (!manager.previewOpen)
                                    player.stop();
                            }
                        }
                        UiButton {
                            objectName: "deleteSourceButton"
                            text: "Delete source"
                            symbol: "trash"
                            Layout.fillWidth: true
                            danger: true
                            implicitHeight: 32
                            textSize: 10
                            iconSize: 13
                            padding: 7
                            enabled: manager.selected !== null && !pipelineBridge.busy
                            onClicked: {
                                confirmation.text = "";
                                deletion.open();
                            }
                        }
                    }
                    Caption {
                        visible: pipelineBridge.busy
                        text: "Deletion is unavailable while processing is active."
                        Layout.margins: 10
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
                ColumnLayout {
                    visible: manager.selected === null
                    anchors.centerIn: parent
                    spacing: 10
                    Image {
                        source: "assets/database.svg"
                        Layout.alignment: Qt.AlignHCenter
                        width: 36
                        height: 36
                    }
                    DataText {
                        text: "No source selected"
                        Layout.alignment: Qt.AlignHCenter
                    }
                    Caption {
                        text: "Select a source to inspect its metadata and artifacts."
                        Layout.maximumWidth: 250
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
    Popup {
        id: deletion
        scale: manager.displayScale
        objectName: "deleteSourceDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 490
        height: 430
        padding: 24
        modal: true
        focus: true
        closePolicy: pipelineBridge.busy ? Popup.NoAutoClose : Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle {
            color: "#99000000"
        }
        background: DataCard {
            border.color: "#67343b"
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            DataText {
                text: pipelineBridge.busy ? "Deleting Source Data…" : "Delete Source and Generated Data?"
                font.pixelSize: 17
                font.bold: true
                Layout.fillWidth: true
            }
            Caption {
                text: "The source and its generated files will move to local trash. Other sources and shared speaker metadata remain intact."
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 11
            }
            Separator {}
            DataText {
                text: manager.selected ? manager.selected.id + "  ·  " + manager.selected.speaker : ""
                font.family: "JetBrains Mono"
            }
            Caption {
                text: manager.selected ? manager.selected.name : ""
                Layout.fillWidth: true
            }
            Caption {
                text: manager.selected ? manager.selected.size + "  ·  " + manager.selected.artifacts + " artifacts" : ""
            }
            Caption {
                text: "Type the Source ID to confirm"
                font.pixelSize: 11
            }
            UiField {
                id: confirmation
                objectName: "deleteConfirmation"
                Layout.fillWidth: true
                mono: true
                placeholderText: manager.selected ? manager.selected.id : ""
                enabled: !pipelineBridge.busy
            }
            Caption {
                text: pipelineBridge.message
                color: "#e8a44b"
                Layout.fillWidth: true
                wrapMode: Text.WrapAnywhere
            }
            Item {
                Layout.fillHeight: true
            }
            RowLayout {
                Layout.fillWidth: true
                UiButton {
                    text: "Cancel"
                    Layout.fillWidth: true
                    enabled: !pipelineBridge.busy
                    onClicked: deletion.close()
                }
                UiButton {
                    objectName: "confirmDeleteSourceButton"
                    text: pipelineBridge.busy ? "Deleting…" : "Delete source"
                    Layout.fillWidth: true
                    enabled: manager.selected !== null && confirmation.text === manager.selected.id && !pipelineBridge.busy
                    onClicked: {
                        player.stop();
                        manager.previewOpen = false;
                        pipelineBridge.deleteSource(manager.selected.speaker, manager.selected.id, confirmation.text);
                    }
                }
            }
        }
        Connections {
            target: pipelineBridge
            function onSourcesChanged() {
                if (deletion.opened && !manager.records.some(row => row.key === manager.selectedKey))
                    deletion.close();
            }
            function onBusyChanged() {
                if (!pipelineBridge.busy && pipelineBridge.message.startsWith("Completed:") && deletion.opened)
                    deletion.close();
            }
        }
    }
}
