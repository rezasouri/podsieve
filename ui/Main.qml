import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"

ApplicationWindow {
    id: app
    visible: true
    width: 1440
    height: 900
    minimumWidth: 1180
    minimumHeight: 620
    title: "PodSieve — Local Audio Processing Workspace"
    color: "#0d1118"
    property string pageView: "data"
    property bool compact: height <= 810
    property bool urlMode: false
    property bool optionalOpen: true
    property bool advancedOpen: false
    property bool copied: false
    property var names: ["Ingest", "Convert", "Separate", "Diarize"]
    property var descriptions: ["Import or download source audio", "Prepare the working WAV file", "Extract the vocal audio track", "Create speaker-labeled segments"]
    property var states: pipelineBridge.stageStates
    property int completedCount: states.filter(s => s === "completed").length
    property bool failed: states.indexOf("failed") >= 0
    property bool idsValid: pipelineBridge.validSpeakerName(speaker.text) && /^source_[0-9]{3,6}$/.test(sourceId.text)
    property bool sourceValid: urlMode ? /^https?:\/\/([a-z0-9-]+\.)*(youtube\.com|youtu\.be|castbox\.fm)(\/|$)/i.test(url.text) : file.text.trim().length > 0
    property bool canRun: idsValid && !pipelineBridge.busy
    property bool canFull: canRun && sourceValid && (completedCount === 0 || overwrite.checked)
    function selectSource() {
        pipelineBridge.selectSource(speaker.text, sourceId.text);
    }
    function run(stage) {
        pipelineBridge.execute(stage, {
            speaker_id: speaker.text,
            source_id: sourceId.text,
            output_parent: pipelineBridge.outputParent,
            mode: urlMode ? "url" : "file",
            location: urlMode ? url.text : file.text,
            name: speakerName.text,
            gender: gender.text,
            language: language.currentIndex === 0 ? "fa" : language.currentIndex === 1 ? "en" : "ar",
            overwrite: overwrite.checked,
            evidence: evidence.checked,
            quality: quality.checked,
            num_speakers: count.text.length ? Number(count.text) : null,
            config: {
                audio: {
                    sample_rate: Number(sampleRate.text),
                    chunk_seconds: Number(chunk.text)
                },
                separation: {
                    model: separationModel.text
                },
                diarization: {
                    model: diarizationModel.text,
                    token_env: tokenEnv.text
                },
                download: {
                    format: stream.text,
                    audio_format: audioFormat.text,
                    cookies_from_browser: cookieMode.currentIndex === 1 ? browser.text : null,
                    cookies_file: cookieMode.currentIndex === 2 ? cookies.text : null
                }
            }
        });
    }
    FileDialog {
        id: picker
        title: "Select audio source"
        nameFilters: ["Audio files (*.mp3 *.wav *.m4a *.flac *.ogg *.opus *.aac)", "All files (*)"]
        onAccepted: file.text = decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))
    }
    FolderDialog {
        id: outputPicker
        title: "Select diarized output directory"
        onAccepted: pipelineBridge.setOutputParent(decodeURIComponent(selectedFolder.toString().replace(/^file:\/\//, "")))
    }
    Timer {
        id: copyTimer
        interval: 1800
        onTriggered: app.copied = false
    }
    component Heading: ColumnLayout {
        property string title
        property string description
        spacing: 3
        UiText {
            text: parent.title
            font.pixelSize: 13
            font.weight: Font.DemiBold
        }
        UiText {
            text: parent.description
            color: "#8d9aaf"
            font.pixelSize: 11
            Layout.fillWidth: true
        }
    }
    component Label: UiText {
        color: "#b2bdcd"
        font.pixelSize: 10
    }
    component Rule: Rectangle {
        color: "#303948"
        Layout.fillWidth: true
        implicitHeight: 1
    }

    header: Rectangle {
        height: app.compact ? 58 : 66
        color: "#0d1118"
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: "#2a3443"
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 28
            anchors.rightMargin: 28
            spacing: 12
            Rectangle {
                width: 38
                height: 38
                radius: 10
                color: "#193958"
                border.color: "#2b6fae"
                Image {
                    anchors.centerIn: parent
                    source: "assets/wave.svg"
                    width: 27
                    height: 27
                }
            }
            ColumnLayout {
                spacing: 2
                UiText {
                    text: "PodSieve"
                    font.pixelSize: 17
                    font.bold: true
                }
                UiText {
                    text: "Local Audio Processing Workspace"
                    color: "#8d9aaf"
                    font.pixelSize: 11
                }
            }
            Item {
                Layout.fillWidth: true
            }
            Rectangle {
                implicitWidth: navigation.implicitWidth + 6
                implicitHeight: 36
                color: "#111720"
                border.color: "#2a3443"
                radius: 9
                RowLayout {
                    id: navigation
                    anchors.centerIn: parent
                    spacing: 3
                    UiButton {
                        id: processNav
                        text: "Process Audio"
                        symbol: "wave"
                        implicitHeight: 30
                        selected: app.pageView === "process"
                        background: Rectangle {
                            radius: 6
                            color: processNav.selected ? "#183555" : "transparent"
                            border.color: processNav.selected ? "#274566" : "transparent"
                        }
                        onClicked: app.pageView = "process"
                    }
                    UiButton {
                        id: dataNav
                        text: "Processed Data"
                        symbol: "database"
                        implicitHeight: 30
                        selected: app.pageView === "data"
                        background: Rectangle {
                            radius: 6
                            color: dataNav.selected ? "#183555" : "transparent"
                            border.color: dataNav.selected ? "#274566" : "transparent"
                        }
                        onClicked: {
                            pipelineBridge.refreshSources();
                            app.pageView = "data";
                        }
                    }
                }
            }
            Item {
                Layout.fillWidth: true
            }
            Rectangle {
                width: 7
                height: 7
                radius: 4
                color: "#35b8a9"
            }
            UiText {
                text: "Local processing"
                color: "#b2bdcd"
            }
        }
    }
    Loader {
        anchors.fill: parent
        active: app.pageView === "data"
        sourceComponent: Component {
            ProcessedData {
                onAddSource: app.pageView = "process"
                onProcessSource: (speakerId, selectedSourceId) => {
                    speaker.text = speakerId;
                    sourceId.text = selectedSourceId;
                    app.pageView = "process";
                }
            }
        }
    }
    RowLayout {
        visible: app.pageView === "process"
        anchors.fill: parent
        anchors.leftMargin: width < 1280 ? 20 : 28
        anchors.rightMargin: anchors.leftMargin
        anchors.topMargin: app.compact ? 10 : 16
        anchors.bottomMargin: anchors.topMargin
        spacing: app.compact ? 12 : 16
        ScrollView {
            id: leftScroll
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.preferredWidth: 540
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                width: leftScroll.availableWidth
                height: Math.max(implicitHeight, leftScroll.availableHeight)
                spacing: app.compact ? 9 : 12
                UiCard {
                    Layout.fillWidth: true
                    implicitHeight: inputContent.implicitHeight + 30
                    ColumnLayout {
                        id: inputContent
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10
                        Heading {
                            title: "Input Source"
                            description: "Select a local audio file or provide a supported URL."
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            implicitWidth: switchRow.implicitWidth + 6
                            implicitHeight: 36
                            color: "#121821"
                            radius: 8
                            border.color: "#2a3443"
                            RowLayout {
                                id: switchRow
                                anchors.centerIn: parent
                                spacing: 2
                                UiButton {
                                    text: "Local file"
                                    symbol: "file"
                                    selected: !app.urlMode
                                    implicitHeight: 28
                                    enabled: !pipelineBridge.busy
                                    onClicked: app.urlMode = false
                                }
                                UiButton {
                                    text: "URL"
                                    symbol: "link"
                                    selected: app.urlMode
                                    implicitHeight: 28
                                    enabled: !pipelineBridge.busy
                                    onClicked: app.urlMode = true
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            UiField {
                                id: file
                                objectName: "file"
                                visible: !app.urlMode
                                Layout.fillWidth: true
                                mono: true
                                placeholderText: "Select an audio file"
                                enabled: !pipelineBridge.busy
                                Accessible.name: "Audio file path"
                            }
                            UiField {
                                id: url
                                objectName: "url"
                                visible: app.urlMode
                                Layout.fillWidth: true
                                mono: true
                                placeholderText: "https://www.youtube.com/watch?v=VIDEO_ID"
                                enabled: !pipelineBridge.busy
                                Accessible.name: "Audio URL"
                            }
                            UiButton {
                                visible: !app.urlMode
                                text: "Browse"
                                symbol: "folder"
                                selected: true
                                enabled: !pipelineBridge.busy
                                onClicked: picker.open()
                            }
                        }
                        Label {
                            text: app.urlMode ? "YouTube and Castbox links are supported" : "MP3, WAV, M4A, FLAC, OGG, or other FFmpeg-readable audio"
                            color: app.urlMode && url.text.length && !app.sourceValid ? "#e06c75" : "#718096"
                        }
                        Rule {}
                        Label {
                            text: "Diarized output directory (optional)"
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            UiField {
                                objectName: "outputParent"
                                Layout.fillWidth: true
                                mono: true
                                text: pipelineBridge.outputParent
                                placeholderText: "Default project output — or select a folder"
                                enabled: !pipelineBridge.busy
                                Accessible.name: "Diarized output directory"
                                onTextEdited: pipelineBridge.setOutputParent(text)
                            }
                            UiButton {
                                text: "Browse"
                                symbol: "folder"
                                selected: true
                                enabled: !pipelineBridge.busy
                                onClicked: outputPicker.open()
                            }
                            UiButton {
                                text: "Default"
                                enabled: !pipelineBridge.busy && pipelineBridge.outputParent.length > 0
                                onClicked: pipelineBridge.setOutputParent("")
                            }
                        }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WrapAnywhere
                            text: pipelineBridge.outputParent.length ? "Final audio folder: " + (pipelineBridge.outputPath || "Select an existing directory and a valid speaker name") : "Leave empty to use the default project output."
                            color: "#718096"
                        }
                    }
                }
                UiCard {
                    Layout.fillWidth: true
                    implicitHeight: settingsContent.implicitHeight + 24
                    ColumnLayout {
                        id: settingsContent
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            Image {
                                source: "assets/settings.svg"
                                width: 16
                                height: 16
                            }
                            UiText {
                                text: "Optional Settings"
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                Layout.fillWidth: true
                            }
                            UiButton {
                                text: app.optionalOpen ? "Hide  ⌃" : "Show  ⌄"
                                implicitHeight: 24
                                onClicked: app.optionalOpen = !app.optionalOpen
                            }
                        }
                        ColumnLayout {
                            visible: app.optionalOpen
                            Layout.fillWidth: true
                            spacing: 9
                            Rule {}
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 9
                                enabled: !pipelineBridge.busy
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 5
                                    Label {
                                        text: "Speaker ID"
                                    }
                                    UiField {
                                        id: speaker
                                        objectName: "speaker"
                                        text: "speaker_001"
                                        mono: true
                                        Layout.fillWidth: true
                                        onTextChanged: app.selectSource()
                                        Accessible.name: "Speaker ID"
                                    }
                                    Label {
                                        text: "Any folder name, e.g. hamid"
                                        font.pixelSize: 9
                                        color: pipelineBridge.validSpeakerName(speaker.text) ? "#6f7e93" : "#e06c75"
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 5
                                    Label {
                                        text: "Source ID"
                                    }
                                    UiField {
                                        id: sourceId
                                        objectName: "sourceId"
                                        text: "source_001"
                                        mono: true
                                        Layout.fillWidth: true
                                        onTextChanged: app.selectSource()
                                        Accessible.name: "Source ID"
                                    }
                                    Label {
                                        text: "source_ + 3–6 digits"
                                        font.pixelSize: 9
                                        color: /^source_[0-9]{3,6}$/.test(sourceId.text) ? "#6f7e93" : "#e06c75"
                                    }
                                }
                                ColumnLayout {
                                    Layout.preferredWidth: 130
                                    Layout.maximumWidth: 130
                                    spacing: 5
                                    Label {
                                        text: "Language"
                                    }
                                    UiCombo {
                                        id: language
                                        model: ["Persian (fa)", "English (en)", "Arabic (ar)"]
                                        Layout.fillWidth: true
                                        implicitHeight: 34
                                    }
                                    Label {
                                        text: " "
                                        font.pixelSize: 9
                                    }
                                }
                            }
                            Rule {}
                            UiButton {
                                text: app.advancedOpen ? "Advanced settings   ⌃" : "Advanced settings   ⌄"
                                Layout.fillWidth: true
                                implicitHeight: 26
                                onClicked: app.advancedOpen = !app.advancedOpen
                            }
                            Rectangle {
                                visible: app.advancedOpen
                                Layout.fillWidth: true
                                implicitHeight: advancedContent.implicitHeight + 20
                                color: "#121821"
                                radius: 8
                                border.color: "#2a3443"
                                ColumnLayout {
                                    id: advancedContent
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 8
                                    enabled: !pipelineBridge.busy
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 7
                                        UiField {
                                            id: speakerName
                                            Layout.fillWidth: true
                                            placeholderText: "Speaker name"
                                            Accessible.name: "Speaker name"
                                        }
                                        UiField {
                                            id: gender
                                            Layout.fillWidth: true
                                            placeholderText: "Gender — Not set"
                                            Accessible.name: "Gender"
                                        }
                                        UiField {
                                            id: count
                                            objectName: "count"
                                            Layout.fillWidth: true
                                            placeholderText: "Speakers — Auto"
                                            validator: IntValidator {
                                                bottom: 1
                                                top: 999
                                            }
                                            Accessible.name: "Expected number of speakers"
                                        }
                                    }
                                    UiToggle {
                                        id: overwrite
                                        objectName: "overwrite"
                                        text: "Overwrite existing output"
                                        Layout.fillWidth: true
                                    }
                                    UiToggle {
                                        id: evidence
                                        objectName: "evidence"
                                        text: "Save diarization evidence"
                                        checked: true
                                        Layout.fillWidth: true
                                        onToggled: if (!checked)
                                            quality.checked = false
                                    }
                                    UiToggle {
                                        id: quality
                                        objectName: "quality"
                                        text: "Automatic quality analysis"
                                        checked: true
                                        Layout.fillWidth: true
                                        onToggled: if (checked)
                                            evidence.checked = true
                                    }
                                    UiButton {
                                        text: "Advanced model configuration"
                                        symbol: "settings"
                                        Layout.fillWidth: true
                                        onClicked: modelDialog.open()
                                    }
                                }
                            }
                        }
                    }
                }
                UiCard {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 160
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 9
                        Heading {
                            title: "Pipeline Controls"
                            description: "Run an individual stage or execute the complete pipeline."
                            Layout.fillWidth: true
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 7
                            Repeater {
                                model: app.names
                                UiButton {
                                    required property string modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    text: (app.states[index] === "completed" ? "✓  " : (index + 1) + "  ") + modelData
                                    enabled: app.canRun && (index !== 0 || app.sourceValid) && (index === 0 || app.states[index - 1] === "completed") && (app.states[index] !== "completed" || overwrite.checked)
                                    hint: "Run " + modelData + "; completed stages require overwrite"
                                    onClicked: app.run(modelData.toLowerCase())
                                }
                            }
                        }
                        UiButton {
                            Layout.fillWidth: true
                            primary: true
                            symbol: pipelineBridge.busy ? "loader" : "play"
                            text: pipelineBridge.busy ? pipelineBridge.activeStage + " in progress" : "Run Full Pipeline"
                            enabled: app.canFull
                            onClicked: app.run("full")
                        }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            color: "#e8a44b"
                            text: !app.idsValid ? "Enter valid speaker and source IDs." : app.completedCount > 0 && !overwrite.checked ? "Enable overwrite in Advanced Settings to rerun the full pipeline." : "Ingest → Convert → Separate → Diarize"
                        }
                        Item {
                            Layout.fillHeight: true
                        }
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.preferredWidth: 635
            spacing: app.compact ? 9 : 12
            UiCard {
                Layout.fillWidth: true
                implicitHeight: statusContent.implicitHeight + 30
                ColumnLayout {
                    id: statusContent
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 10
                    Heading {
                        title: "Stage Status"
                        description: "Monitor the current status of each processing stage."
                        Layout.fillWidth: true
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: app.compact ? 4 : 5
                        Repeater {
                            model: app.names
                            Rectangle {
                                id: stageRow
                                required property string modelData
                                required property int index
                                property string stateName: app.states[index] || "not-started"
                                property color accent: stateName === "completed" ? "#35b8a9" : stateName === "processing" ? "#4b9af2" : stateName === "failed" ? "#e06c75" : "#8d9aaf"
                                Layout.fillWidth: true
                                implicitHeight: app.compact ? 43 : 48
                                radius: 8
                                clip: true
                                color: stateName === "processing" ? "#182c42" : "#10161f"
                                border.color: stateName === "processing" ? "#315c88" : "#303948"
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 9
                                    Rectangle {
                                        width: 27
                                        height: 27
                                        radius: 7
                                        color: stageRow.stateName === "completed" ? "#153a39" : "#1a222e"
                                        border.color: "#3b4657"
                                        UiText {
                                            anchors.centerIn: parent
                                            text: stageRow.stateName === "completed" ? "✓" : stageRow.index + 1
                                            color: stageRow.accent
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        UiText {
                                            text: stageRow.modelData
                                            font.weight: Font.DemiBold
                                        }
                                        UiText {
                                            text: app.descriptions[stageRow.index]
                                            color: "#8d9aaf"
                                            font.pixelSize: 9
                                            Layout.fillWidth: true
                                        }
                                    }
                                    Rectangle {
                                        width: 98
                                        height: 23
                                        radius: 12
                                        color: stageRow.stateName === "completed" ? "#153a39" : stageRow.stateName === "processing" ? "#183555" : stageRow.stateName === "failed" ? "#47252c" : "#1c232e"
                                        border.color: stageRow.accent
                                        UiText {
                                            anchors.centerIn: parent
                                            font.pixelSize: 9
                                            color: stageRow.accent
                                            text: stageRow.stateName === "not-started" ? "○  Not started" : stageRow.stateName === "completed" ? "✓  Completed" : stageRow.stateName === "failed" ? "⚠  Failed" : "◌  Processing"
                                        }
                                    }
                                }
                                Item {
                                    objectName: "stageProgress" + stageRow.index
                                    anchors.bottom: parent.bottom
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    height: 2
                                    clip: true
                                    Rectangle {
                                        objectName: "stageCompletedFill" + stageRow.index
                                        anchors.fill: parent
                                        visible: stageRow.stateName === "completed"
                                        color: stageRow.accent
                                    }
                                    Rectangle {
                                        visible: stageRow.stateName === "processing"
                                        height: parent.height
                                        width: parent.width * 0.35
                                        color: stageRow.accent
                                        NumberAnimation on x {
                                            running: stageRow.stateName === "processing"
                                            loops: Animation.Infinite
                                            from: -stageRow.width * 0.35
                                            to: stageRow.width
                                            duration: 1350
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            UiCard {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: app.compact ? 100 : 180
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Heading {
                            title: "Process Log"
                            description: "Live messages from the local processing service."
                            Layout.fillWidth: true
                        }
                        UiButton {
                            text: "Clear logs"
                            symbol: "trash"
                            implicitHeight: 27
                            onClicked: pipelineBridge.clearLogs()
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: "#0b1119"
                        border.color: "#242d3a"
                        ListView {
                            id: logList
                            anchors.fill: parent
                            anchors.margins: 10
                            clip: true
                            model: pipelineBridge.logs
                            spacing: 2
                            ScrollBar.vertical: ScrollBar {}
                            onCountChanged: Qt.callLater(positionViewAtEnd)
                            delegate: RowLayout {
                                required property var modelData
                                width: logList.width - 12
                                spacing: 10
                                UiText {
                                    text: "[" + modelData.time + "]"
                                    color: "#5f6b7e"
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 10
                                    Layout.alignment: Qt.AlignTop
                                }
                                UiText {
                                    text: modelData.text
                                    Layout.fillWidth: true
                                    wrapMode: Text.WrapAnywhere
                                    elide: Text.ElideNone
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 10
                                    color: modelData.tone === "success" ? "#69c9bd" : modelData.tone === "processing" ? "#70adf0" : modelData.tone === "error" ? "#e06c75" : "#aeb8c6"
                                }
                            }
                            UiText {
                                visible: logList.count === 0
                                text: "No process messages yet."
                                color: "#596578"
                                font.pixelSize: 10
                            }
                        }
                    }
                }
            }
            UiCard {
                Layout.fillWidth: true
                implicitHeight: outputContent.implicitHeight + 30
                border.color: pipelineBridge.outputAvailable ? "#2d625e" : "#2a3443"
                ColumnLayout {
                    id: outputContent
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Heading {
                            title: "Diarized Output Location"
                            description: pipelineBridge.outputAvailable ? "Output is available and ready to review." : "Expected location after diarization completes."
                            Layout.fillWidth: true
                        }
                        Label {
                            text: pipelineBridge.outputAvailable ? "●  AVAILABLE" : "●  PENDING"
                            color: pipelineBridge.outputAvailable ? "#76cfc4" : "#8d9aaf"
                            font.pixelSize: 9
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 7
                        UiField {
                            text: pipelineBridge.outputPath
                            mono: true
                            readOnly: true
                            Layout.fillWidth: true
                            Accessible.name: "Diarized output path"
                        }
                        UiButton {
                            text: app.copied ? "Copied" : "Copy path"
                            symbol: app.copied ? "check" : "copy"
                            onClicked: {
                                pipelineBridge.copyOutputPath();
                                app.copied = true;
                                copyTimer.restart();
                            }
                        }
                        UiButton {
                            text: "Open folder"
                            symbol: "external"
                            enabled: pipelineBridge.outputAvailable
                            onClicked: pipelineBridge.openOutputFolder()
                        }
                    }
                }
            }
        }
    }
    footer: Item {
        visible: app.pageView === "process"
        height: visible ? (app.compact ? 58 : 66) : 0
        Rectangle {
            anchors.fill: parent
            anchors.leftMargin: 28
            anchors.rightMargin: 28
            anchors.bottomMargin: app.compact ? 9 : 14
            radius: 11
            color: app.failed ? "#3b2228" : app.completedCount === 4 ? "#163331" : "#172d44"
            border.color: app.failed ? "#7a3942" : app.completedCount === 4 ? "#2d6963" : "#315f8d"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 12
                Rectangle {
                    width: 34
                    height: 34
                    radius: 8
                    color: "#203f5e"
                    Image {
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        source: "assets/" + (app.failed ? "alert" : app.completedCount === 4 ? "check" : pipelineBridge.busy ? "loader" : "spark") + ".svg"
                        RotationAnimator on rotation {
                            running: pipelineBridge.busy
                            from: 0
                            to: 360
                            duration: 1000
                            loops: Animation.Infinite
                        }
                    }
                }
                ColumnLayout {
                    Layout.preferredWidth: 360
                    spacing: 2
                    UiText {
                        text: app.failed ? "Pipeline Failed" : app.completedCount === 4 ? "Pipeline Completed Successfully" : pipelineBridge.busy ? "Pipeline in Progress" : "Ready to Process"
                        font.weight: Font.DemiBold
                    }
                    Label {
                        text: app.failed ? "Review the process log for details." : app.completedCount + " of 4 stages completed. " + (pipelineBridge.busy ? pipelineBridge.activeStage + " is currently running." : app.completedCount === 4 ? "Your diarized audio files are ready." : "Continue when ready.")
                        font.pixelSize: 9
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 4
                    radius: 2
                    color: "#304050"
                    Rectangle {
                        width: parent.width * app.completedCount / 4
                        height: 4
                        radius: 2
                        color: app.completedCount === 4 ? "#35b8a9" : "#4b9af2"
                        Behavior on width {
                            NumberAnimation {
                                duration: 400
                            }
                        }
                    }
                }
                UiText {
                    text: app.completedCount + "/4"
                    font.pixelSize: 14
                    font.bold: true
                }
            }
        }
    }
    Popup {
        id: modelDialog
        objectName: "modelDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 570
        height: Math.min(app.height - 80, 690)
        modal: true
        focus: true
        padding: 20
        Overlay.modal: Rectangle {
            color: "#99000000"
        }
        background: UiCard {}
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            Heading {
                title: "Advanced model configuration"
                description: "Applied to the next run; YAML defaults remain on disk."
                Layout.fillWidth: true
            }
            ScrollView {
                id: modelScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ColumnLayout {
                    width: modelScroll.availableWidth
                    spacing: 8
                    enabled: !pipelineBridge.busy
                    Label {
                        text: "Audio sample rate (Hz)"
                    }
                    UiField {
                        id: sampleRate
                        text: "44100"
                        validator: IntValidator {
                            bottom: 8000
                            top: 192000
                        }
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Processing chunk duration (seconds)"
                    }
                    UiField {
                        id: chunk
                        text: "180"
                        validator: IntValidator {
                            bottom: 1
                        }
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Separation checkpoint"
                    }
                    UiField {
                        id: separationModel
                        text: "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Diarization model"
                    }
                    UiField {
                        id: diarizationModel
                        text: "pyannote/speaker-diarization-3.1"
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Token environment variable name"
                    }
                    UiField {
                        id: tokenEnv
                        text: "HF_TOKEN"
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Download stream format"
                    }
                    UiField {
                        id: stream
                        text: "251/140/bestaudio"
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "Download audio format"
                    }
                    UiField {
                        id: audioFormat
                        text: "opus"
                        Layout.fillWidth: true
                    }
                    Label {
                        text: "YouTube cookie method"
                    }
                    UiCombo {
                        id: cookieMode
                        model: ["No cookies", "From backend browser", "From cookie file"]
                        currentIndex: 1
                        Layout.fillWidth: true
                    }
                    UiField {
                        id: browser
                        visible: cookieMode.currentIndex === 1
                        text: "chrome"
                        placeholderText: "Browser on this computer"
                        Layout.fillWidth: true
                    }
                    UiField {
                        id: cookies
                        visible: cookieMode.currentIndex === 2
                        placeholderText: "/path/to/cookies.txt"
                        Layout.fillWidth: true
                    }
                }
            }
            UiButton {
                text: "Done"
                primary: true
                Layout.alignment: Qt.AlignRight
                onClicked: modelDialog.close()
            }
        }
    }
    onClosing: close => {
        if (pipelineBridge.busy) {
            close.accepted = false;
            pipelineBridge.reportBusyClose();
        }
    }
    Component.onCompleted: app.selectSource()
}
