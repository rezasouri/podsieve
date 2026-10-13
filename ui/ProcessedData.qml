import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import "components"

Item {
    id: manager
    objectName: "processedData"
    signal addSource
    signal processSource(string speaker, string source)
    property string selectedKey: ""
    property var checkedRows: []
    property int page: 1
    property int inspectorTab: 0
    property bool previewOpen: false
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
    component Caption: UiText {
        color: "#8d9aaf"
        font.pixelSize: 9
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
            Layout.preferredWidth: 22
            checked: parent.header ? manager.visibleRecords.length > 0 && manager.visibleRecords.every(r => manager.checkedRows.includes(r.key)) : manager.checkedRows.includes(parent.row.key)
            onToggled: {
                if (parent.header)
                    manager.visibleRecords.forEach(r => manager.toggleChecked(r.key, checked));
                else
                    manager.toggleChecked(parent.row.key, checked);
            }
            Accessible.name: parent.header ? "Select all visible sources" : "Select " + parent.row.id
        }
        UiText {
            Layout.preferredWidth: 88
            text: parent.header ? "SOURCE ID" : parent.row.id || ""
            color: "#aab5c5"
            font.family: "JetBrains Mono"
            font.pixelSize: 9
        }
        ColumnLayout {
            Layout.preferredWidth: 122
            spacing: 4
            UiText {
                Layout.fillWidth: true
                text: parent.parent.header ? "REGISTERED SPEAKER" : parent.parent.row.speakerName || ""
                font.pixelSize: 9
            }
            Caption {
                Layout.fillWidth: true
                visible: !parent.parent.header
                text: parent.parent.row.speaker || ""
                font.pixelSize: 8
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 150
            spacing: 4
            UiText {
                Layout.fillWidth: true
                text: parent.parent.header ? "SOURCE NAME" : parent.parent.row.name || ""
                font.pixelSize: 9
            }
            Caption {
                Layout.fillWidth: true
                visible: !parent.parent.header
                text: parent.parent.row.sourceRef || ""
                font.pixelSize: 8
            }
        }
        UiText {
            Layout.preferredWidth: 74
            text: parent.header ? "INPUT" : parent.row.input || ""
            font.pixelSize: 9
            color: parent.row.input === "YouTube" ? "#e2a0a7" : parent.row.input === "Castbox" ? "#d5b989" : "#9eabba"
        }
        Item {
            Layout.preferredWidth: 109
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
            Layout.preferredWidth: 82
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
            text: parent.header ? "STORAGE" : parent.row.size || ""
            font.family: "JetBrains Mono"
            font.pixelSize: 9
        }
        ColumnLayout {
            Layout.preferredWidth: 83
            spacing: 4
            Caption {
                text: parent.parent.header ? "UPDATED" : (parent.parent.row.updated || "—").split(" ")[0]
            }
            Caption {
                visible: !parent.parent.header
                text: (parent.parent.row.updated || "").split(" ")[1] || ""
                font.pixelSize: 8
            }
        }
        UiButton {
            visible: !parent.header
            Layout.preferredWidth: 27
            implicitHeight: 27
            symbol: "more"
            hint: "View source files"
            onClicked: {
                manager.choose(parent.row);
                manager.inspectorTab = 2;
            }
        }
        Item {
            visible: parent.header
            Layout.preferredWidth: 27
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 13
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 55
            spacing: 12
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                Caption {
                    text: "●  LOCAL SOURCE REGISTRY"
                    font.pixelSize: 9
                }
                UiText {
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
                Layout.preferredWidth: 280
                placeholderText: "Search sources, speakers, files, or URLs…"
                onTextChanged: manager.page = 1
                Accessible.name: "Search processed sources"
            }
            UiButton {
                text: "Refresh"
                symbol: "refresh"
                enabled: !pipelineBridge.busy
                onClicked: pipelineBridge.refreshSources()
            }
            UiButton {
                text: "Add new source"
                symbol: "plus"
                selected: true
                onClicked: manager.addSource()
            }
        }
        UiCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 67
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
                                color: "#192b3e"
                                border.color: "#324256"
                                Image {
                                    anchors.centerIn: parent
                                    source: "assets/" + modelData.icon + ".svg"
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
                                UiText {
                                    text: String(modelData.value)
                                    color: modelData.color
                                    font.pixelSize: 14
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
            UiCard {
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
                        UiText {
                            text: "Registered Sources"
                            font.weight: Font.DemiBold
                            Layout.fillWidth: true
                        }
                        Caption {
                            text: manager.filtered.length + " records"
                        }
                        UiCombo {
                            id: speakers
                            objectName: "speakerFilter"
                            model: ["All speakers"].concat(Array.from(new Set(manager.records.map(r => r.speaker))))
                            Layout.preferredWidth: 112
                            implicitHeight: 28
                            onActivated: manager.page = 1
                        }
                        UiCombo {
                            id: statuses
                            objectName: "statusFilter"
                            model: ["All statuses", "Completed", "Processing", "Failed", "Pending"]
                            Layout.preferredWidth: 105
                            implicitHeight: 28
                            onActivated: manager.page = 1
                        }
                        UiCombo {
                            id: sorting
                            model: ["Newest updated", "Filename A–Z", "Largest storage", "Most processed"]
                            Layout.preferredWidth: 130
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
                        contentWidth: Math.max(width, 1030)
                        contentHeight: Math.max(height, 34 + manager.visibleRecords.length * 58)
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
                                    height: 58
                                    color: manager.selectedKey === modelData.key ? "#1b3045" : rowMouse.containsMouse ? "#202936" : "transparent"
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
                                        height: 44
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
                            UiText {
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
                            implicitHeight: 26
                            enabled: manager.page > 1
                            onClicked: manager.page--
                        }
                        Caption {
                            text: "Page " + manager.page + " of " + manager.pageCount
                        }
                        UiButton {
                            text: "Next"
                            implicitHeight: 26
                            enabled: manager.page < manager.pageCount
                            onClicked: manager.page++
                        }
                    }
                }
            }
            UiCard {
                Layout.preferredWidth: Math.max(365, manager.width * 0.29)
                Layout.minimumWidth: 365
                Layout.fillHeight: true
                clip: true
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0
                    visible: manager.selected !== null
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 69
                        Layout.leftMargin: 13
                        Layout.rightMargin: 13
                        spacing: 10
                        Rectangle {
                            width: 36
                            height: 36
                            radius: 8
                            color: "#19324a"
                            border.color: "#355f86"
                            Image {
                                anchors.centerIn: parent
                                width: 18
                                height: 18
                                source: "assets/" + (manager.selected && manager.selected.input === "Local File" ? "file" : "link") + ".svg"
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Caption {
                                text: "SOURCE INSPECTOR"
                                font.pixelSize: 8
                            }
                            UiText {
                                text: manager.selected ? manager.selected.name : ""
                                Layout.fillWidth: true
                                font.weight: Font.DemiBold
                            }
                            Caption {
                                text: manager.selected ? manager.selected.id : ""
                                font.family: "JetBrains Mono"
                                font.pixelSize: 9
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
                                selected: manager.inspectorTab === index
                                implicitHeight: 30
                                Layout.fillWidth: true
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
                                Layout.margins: 14
                                spacing: 10
                                Repeater {
                                    model: manager.selected ? [["Source ID", manager.selected.id], ["Speaker ID", manager.selected.speaker], ["Registered speaker", manager.selected.speakerName], ["Original filename", manager.selected.name], ["Input type", manager.selected.input], ["Language", manager.selected.language], ["Created", manager.selected.created], ["Last updated", manager.selected.updated], ["Storage used", manager.selected.size]] : []
                                    ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 8
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Caption {
                                                text: modelData[0]
                                                Layout.preferredWidth: 120
                                            }
                                            UiText {
                                                text: modelData[1]
                                                Layout.fillWidth: true
                                                horizontalAlignment: Text.AlignRight
                                                font.pixelSize: 10
                                            }
                                        }
                                        Separator {}
                                    }
                                }
                                Caption {
                                    text: "Original source"
                                }
                                UiField {
                                    readOnly: true
                                    mono: true
                                    text: manager.selected ? manager.selected.sourceRef : ""
                                    Layout.fillWidth: true
                                }
                                Caption {
                                    text: "Output directory"
                                }
                                UiField {
                                    readOnly: true
                                    mono: true
                                    text: manager.selected ? manager.selected.outputPath : ""
                                    Layout.fillWidth: true
                                }
                                UiButton {
                                    text: "Continue in Process Audio"
                                    symbol: "wave"
                                    Layout.fillWidth: true
                                    enabled: !pipelineBridge.busy
                                    onClicked: manager.processSource(manager.selected.speaker, manager.selected.id)
                                }
                            }
                            ColumnLayout {
                                visible: manager.inspectorTab === 1
                                Layout.fillWidth: true
                                Layout.margins: 14
                                spacing: 14
                                Repeater {
                                    model: manager.selected ? manager.selected.stages : []
                                    RowLayout {
                                        required property string modelData
                                        required property int index
                                        Layout.fillWidth: true
                                        Layout.minimumHeight: 60
                                        spacing: 9
                                        StatusBadge {
                                            status: modelData === "not-started" ? "pending" : modelData
                                            implicitWidth: 78
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 5
                                            UiText {
                                                text: (index + 1) + ". " + ["Ingest", "Convert", "Separate", "Diarize"][index]
                                                font.weight: Font.DemiBold
                                            }
                                            Caption {
                                                text: manager.selected ? manager.selected.stageTimes[index] : "—"
                                                Layout.fillWidth: true
                                                wrapMode: Text.WordWrap
                                            }
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
                                        property bool expanded: true
                                        Layout.fillWidth: true
                                        spacing: 5
                                        UiButton {
                                            text: (fileGroup.expanded ? "⌄  " : "›  ") + modelData.name + "  " + modelData.files.filter(f => f.available).length + "/" + modelData.files.length
                                            symbol: "folder"
                                            Layout.fillWidth: true
                                            implicitHeight: 28
                                            onClicked: fileGroup.expanded = !fileGroup.expanded
                                        }
                                        Repeater {
                                            model: fileGroup.expanded ? fileGroup.modelData.files : []
                                            RowLayout {
                                                required property var modelData
                                                Layout.fillWidth: true
                                                spacing: 5
                                                opacity: modelData.available ? 1 : 0.45
                                                UiText {
                                                    text: modelData.name
                                                    Layout.fillWidth: true
                                                    font.pixelSize: 9
                                                    elide: Text.ElideMiddle
                                                }
                                                Caption {
                                                    text: modelData.available ? modelData.size : "Not generated"
                                                    font.pixelSize: 8
                                                }
                                                UiButton {
                                                    symbol: "copy"
                                                    implicitHeight: 26
                                                    Layout.preferredWidth: 26
                                                    enabled: modelData.available
                                                    hint: "Copy artifact path"
                                                    onClicked: pipelineBridge.copyArtifactPath(modelData.path)
                                                }
                                                UiButton {
                                                    symbol: "external"
                                                    implicitHeight: 26
                                                    Layout.preferredWidth: 26
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
                            implicitHeight: 30
                            Layout.fillWidth: true
                            enabled: manager.selected && manager.selected.outputAvailable
                            onClicked: pipelineBridge.openArtifactFolder(manager.selected.outputPath)
                        }
                        UiButton {
                            text: "Preview audio"
                            symbol: "volume"
                            implicitHeight: 30
                            Layout.fillWidth: true
                            enabled: manager.selected && manager.selected.previewUri.length > 0
                            onClicked: {
                                manager.previewOpen = !manager.previewOpen;
                                if (!manager.previewOpen)
                                    player.stop();
                            }
                        }
                    }
                    UiButton {
                        objectName: "deleteSourceButton"
                        text: "Delete source"
                        symbol: "trash"
                        Layout.fillWidth: true
                        Layout.leftMargin: 10
                        Layout.rightMargin: 10
                        Layout.bottomMargin: 10
                        implicitHeight: 30
                        enabled: manager.selected !== null && !pipelineBridge.busy
                        onClicked: {
                            confirmation.text = "";
                            deletion.open();
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
                    UiText {
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
        background: UiCard {
            border.color: "#67343b"
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            UiText {
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
            UiText {
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
