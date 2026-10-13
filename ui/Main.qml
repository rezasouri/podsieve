import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
 id: app
 width: 1440; height: 900; minimumWidth: 1050; minimumHeight: 700
 visible: true; title: "PodSieve — UI Prototype (Mock Data)"
 color: "#11151D"
 property string page: "Dataset"
 property int selected: 0
 property int issue: 0
 property int stage: 4
 property bool runningDemo: false
 property string query: ""
 property bool urlMode: true
 property bool advanced: false
 property real playPosition: 42.15
 property bool playing: false
 readonly property color panel: "#1D2430"
 readonly property color sidebar: "#151B25"
 readonly property color textMain: "#F1F4F9"
 readonly property color subdued: "#97A3B6"
 readonly property color blue: "#3689E6"
 readonly property color teal: "#1DA99D"
 readonly property color amber: "#E8A44B"
 readonly property color purple: "#9877DA"
 property var sourceRows: [
  {id:"source_001",speaker:"speaker_001",name:"Podcast A",input:"YouTube",duration:"02:31:48",stage:"Diarize",status:"Needs review"},
  {id:"source_002",speaker:"speaker_003",name:"Interview",input:"Local",duration:"00:46:12",stage:"Separate",status:"Completed"},
  {id:"source_003",speaker:"speaker_004",name:"Audiobook",input:"Castbox",duration:"01:12:05",stage:"Convert",status:"Pending"},
  {id:"source_004",speaker:"speaker_001",name:"Episode 12",input:"YouTube",duration:"00:56:41",stage:"Diarize",status:"Completed"},
  {id:"source_005",speaker:"speaker_008",name:"Session",input:"Local",duration:"03:18:27",stage:"Quality",status:"Needs review"},
  {id:"source_006",speaker:"speaker_009",name:"Talk",input:"Castbox",duration:"01:04:33",stage:"Ingest",status:"Completed"}
 ]
 property var issueRows: [
  {time:"00:42–00:45",type:"Speaker ambiguity",assigned:"SPEAKER_00",candidate:"SPEAKER_01",score:"0.86"},
  {time:"01:12–01:14",type:"Detected overlap",assigned:"SPEAKER_01",candidate:"SPEAKER_00",score:"0.74"},
  {time:"02:08–02:09",type:"Short turn",assigned:"SPEAKER_00",candidate:"—",score:"0.68"}
 ]
 Timer { interval: 1000; running: playing; repeat: true; onTriggered: playPosition+=1 }
 Timer { interval: 1700; running: runningDemo; repeat: false; onTriggered: runningDemo=false }
 component Caption: Text {color: app.subdued; font.pixelSize: 12}
 component Heading: Text {color: app.textMain; font.pixelSize: 26; font.bold: true}
 component Card: Rectangle {color: app.panel; radius: 11}
 component UiButton: Button {
  id: control
  property bool primary: false
  font.pixelSize: 13
  contentItem: Text {text: control.text; color: "#F1F4F9"; font: control.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter}
  background: Rectangle {radius: 8; color: control.primary ? app.blue : "#303948"}
 }
 component UiField: TextField {
  color: app.textMain; font.pixelSize: 13; selectByMouse: true
  background: Rectangle {color:"#11151D"; radius:7; border.color: parent.activeFocus ? app.blue : "#303948"}
  implicitHeight: 39; leftPadding: 12
 }
 RowLayout {
  anchors.fill: parent; spacing: 0
  Rectangle {
   Layout.preferredWidth: 222; Layout.fillHeight: true; color: app.sidebar
   ColumnLayout {
    anchors.fill: parent; anchors.margins: 17; spacing: 12
    Text {text:"◉  PodSieve"; color: app.textMain; font.pixelSize:23; font.bold:true; Layout.topMargin:17}
    Caption {text:"AUDIO DATA WORKSPACE"; Layout.bottomMargin:34}
    Repeater {
     model:["Dataset","Processing","Review","Settings"]
     delegate: Rectangle {
      required property string modelData
      Layout.fillWidth:true; height:42; radius:8; color:page===modelData?app.panel:"transparent"
      Text {anchors.verticalCenter:parent.verticalCenter; x:15; text:modelData; color: page===modelData?app.textMain:app.subdued; font.pixelSize:14}
      MouseArea {anchors.fill:parent; onClicked:page=modelData}
     }
    }
    Item {Layout.fillHeight:true}
    Caption {text:"● UI DEMO • NO BACKEND"; color: app.amber}
   }
  }
  ColumnLayout {
   Layout.fillWidth:true; Layout.fillHeight:true; spacing: 0
   Rectangle {
    Layout.fillWidth:true; height:66; color: app.sidebar
    RowLayout {anchors.fill:parent; anchors.leftMargin:27; anchors.rightMargin:27
     Caption {text:"Workspace / " + page}
     Item {Layout.fillWidth:true}
     Caption {text:"Local mock workspace"}
    }
   }
   StackLayout {
    Layout.fillWidth:true; Layout.fillHeight:true; currentIndex: page==="Dataset"?0:page==="Processing"?1:page==="Review"?2:3
    Item {
     ColumnLayout {anchors.fill:parent; anchors.margins:27; spacing:18
      RowLayout {
       ColumnLayout {Heading {text:"Dataset Manager"} Caption {text:"Manage source audio, registered speakers, and pipeline states"}}
       Item {Layout.fillWidth:true}
       UiButton {text:"+ Add source"; primary:true; onClicked:ingestDialog.open()}
      }
      RowLayout {spacing:14
       Repeater {model:[["REGISTERED SPEAKERS","24"],["AUDIO SOURCES","186"],["PROCESSED","142"],["NEEDS REVIEW","17"]]
        delegate: Card {required property var modelData; Layout.fillWidth:true; height:110
         Column {anchors.left:parent.left; anchors.verticalCenter:parent.verticalCenter; anchors.leftMargin:20; spacing:12
          Caption {text:modelData[0]} Text {text:modelData[1]; color:app.textMain; font.pixelSize:30; font.bold:true}
         }
        }
       }
      }
      Card {Layout.fillWidth:true; Layout.fillHeight:true
       ColumnLayout {anchors.fill:parent; anchors.margins:19; spacing:10
        RowLayout {Text {text:"All audio sources"; color:app.textMain; font.pixelSize:18; font.bold:true} Item{Layout.fillWidth:true} Caption{text:"Example data"}}
        UiField {Layout.fillWidth:true; placeholderText:"Search by source ID, speaker or title"; onTextChanged: app.query=text}
        Rectangle {Layout.fillWidth:true; height:36; color:app.sidebar; radius:5
         RowLayout {anchors.fill:parent; anchors.leftMargin:12
          Repeater {model:["SOURCE","SPEAKER","INPUT","DURATION","STAGE","STATUS"]
           delegate: Caption {required property string modelData; Layout.fillWidth:true; text:modelData}
          }
         }
        }
        Repeater {model: app.sourceRows.filter(r=>(r.id+" "+r.speaker+" "+r.name).toLowerCase().includes(app.query.toLowerCase()))
         delegate: Rectangle {
          required property var modelData; required property int index
          Layout.fillWidth:true; height:53; color:index%2?"#202836":"transparent"; radius:5
          RowLayout {anchors.fill:parent; anchors.leftMargin:12
           Repeater {model:[modelData.id,modelData.speaker,modelData.input,modelData.duration,modelData.stage,modelData.status]
            delegate: Text {required property string modelData; Layout.fillWidth:true; text:modelData; font.pixelSize:12; color:modelData==="Needs review"?app.amber:app.textMain; elide:Text.ElideRight}
           }
          }
          MouseArea {anchors.fill:parent; onClicked:{app.selected=index;app.page="Review"}}
         }
        }
        Item {Layout.fillHeight:true}
       }
      }
     }
    }
    Item {
     ColumnLayout {anchors.fill:parent; anchors.margins:27; spacing:18
      Heading {text:"Processing Workspace"}
      Caption {text:app.sourceRows[app.selected].id+" · "+app.sourceRows[app.selected].name+"  — simulation only"}
      RowLayout {Layout.fillWidth:true; Layout.fillHeight:true; spacing:16
       Card {Layout.preferredWidth:300; Layout.fillHeight:true
        ColumnLayout {anchors.fill:parent; anchors.margins:18; spacing:15
         Caption {text:"PIPELINE STAGES"}
         Repeater {model:["Ingest","Convert","Separate","Diarize","Quality Analysis"]
          delegate: Rectangle {required property string modelData; required property int index
           Layout.fillWidth:true; height:62; radius:8; color:app.stage===index?"#303948":"transparent"
           Column {anchors.left:parent.left; anchors.verticalCenter:parent.verticalCenter; anchors.leftMargin:12; spacing:6
            Text {text:(index+1)+". "+modelData; color:app.textMain; font.pixelSize:14; font.bold:true}
            Caption {text:index<4?"Completed (mock)":"Ready (mock)"}
           }
           MouseArea {anchors.fill:parent; onClicked:app.stage=index}
          }
         }
         Item {Layout.fillHeight:true}
        }
       }
       Card {Layout.fillWidth:true; Layout.fillHeight:true
        ColumnLayout {anchors.fill:parent; anchors.margins:23; spacing:17
         Heading {text:["Ingest","Convert","Separate","Diarize","Quality Analysis"][app.stage]}
         Caption {text:"Configuration preview · No real files are accessed"}
         Repeater {model:app.stage===1?[["Sample rate (Hz)","44100"],["Output","Stereo PCM 16-bit"]]:app.stage===2?[["Model","model_bs_roformer_ep_317_sdr_12.9755.ckpt"],["Processing chunk (seconds)","180"]]:app.stage===3?[["Speaker count","Auto"],["Model","pyannote/speaker-diarization-3.1"]]:app.stage===4?[["Top K candidates","30"],["Minimum score","0"],["Review clips","Enabled"]]:[["Input","Selected source"],["Overwrite","Off"]]
          delegate: ColumnLayout {required property var modelData; Layout.fillWidth:true
           Caption {text:modelData[0]}
           UiField {Layout.fillWidth:true; text:modelData[1]}
          }
         }
         CheckBox {text:"Overwrite selected stage (demo)"; palette.windowText:app.textMain}
         Item {Layout.fillHeight:true}
         Caption {text:app.runningDemo?"Simulated processing...":"No backend connected. Actions are demonstrations."}
         UiButton {text:app.runningDemo?"Running...":"Simulate stage run"; primary:true; enabled:!app.runningDemo; onClicked:app.runningDemo=true}
        }
       }
      }
     }
    }
    Item {
     ColumnLayout {anchors.fill:parent; anchors.margins:27; spacing:13
      Heading {text:"Audio Review Studio"}
      Caption {text:app.sourceRows[app.selected].id+" / "+app.sourceRows[app.selected].name+" · Source-local diarization labels · Mock audio"}
      Card {Layout.fillWidth:true; height:52
       RowLayout {anchors.fill:parent; anchors.margins:12
        UiButton {text:app.playing?"Pause":"Play"; onClicked:app.playing=!app.playing}
        Caption {text:app.playPosition.toFixed(1)+"s / 02:31:48"}
        Item {Layout.fillWidth:true}
        Caption {text:"Playback simulated"}
        UiButton {text:"−"; onClicked:waveform.scaleX=Math.max(.65,waveform.scaleX-.1)}
        UiButton {text:"+"; onClicked:waveform.scaleX=Math.min(1.5,waveform.scaleX+.1)}
       }
      }
      RowLayout {Layout.fillWidth:true; Layout.fillHeight:true; spacing:13
       Card {Layout.fillWidth:true; Layout.fillHeight:true
        ColumnLayout {anchors.fill:parent; anchors.margins:17; spacing:13
         Caption {text:"WAVEFORM · VOCALS (SYNTHETIC)"}
         Rectangle {Layout.fillWidth:true; Layout.preferredHeight:170; color:"#151B25"; radius:7; clip:true
          Canvas {id:waveform; anchors.fill:parent; property real scaleX:1
           onPaint:{var ctx=getContext("2d");ctx.reset();let w=width,h=height;ctx.fillStyle="#151B25";ctx.fillRect(0,0,w,h);
            for(let i=0;i<Math.floor(w/4);i++){let hh=6+(Math.abs(Math.sin(i*.41)*Math.cos(i*.11))*90+Math.abs(Math.sin(i*1.31))*31)*scaleX;
             ctx.fillStyle=i<w/16?"#1DA99D":"#97A3B6";ctx.fillRect(i*4,h/2-hh/2,2,hh);}
            ctx.fillStyle="#3689E6";ctx.fillRect(w*.29,0,2,h);
           }
          }
          MouseArea {anchors.fill:parent; onClicked:app.playPosition=mouse.x/width*100}
         }
         Caption {text:"00:30                     00:40                     00:50                     01:00"}
         Repeater {model:[["SPEAKER_00",app.teal],["SPEAKER_01",app.purple],["QUALITY FLAGS",app.amber]]
          delegate: RowLayout {required property var modelData; Layout.fillWidth:true; spacing:12
           Caption {text:modelData[0]; Layout.preferredWidth:105}
           Rectangle {Layout.fillWidth:true; height:38; color:"#151B25"; radius:5
            Row {anchors.fill:parent; anchors.margins:6; spacing:8
             Repeater {model:4
              delegate: Rectangle {width:Math.max(30,(parent.width-35)/4); height:26; radius:5; color:modelData[1]; opacity:index===1?.4:.9}
             }
            }
           }
          }
         }
         Item {Layout.fillHeight:true}
        }
       }
       Card {Layout.preferredWidth:288; Layout.fillHeight:true
        ColumnLayout {anchors.fill:parent; anchors.margins:17; spacing:13
         Caption {text:"SEGMENT INSPECTOR"}
         Text {text:"#0"+(app.issue+1)+" · "+app.issueRows[app.issue].type; color:app.textMain; font.bold:true; font.pixelSize:15; wrapMode:Text.WordWrap; Layout.fillWidth:true}
         Caption {text:"REVIEW SCORE (NOT PROBABILITY)"}
         Text {text:app.issueRows[app.issue].score; color:app.amber; font.pixelSize:24; font.bold:true}
         Caption {text:"TIME RANGE"}
         Text {text:app.issueRows[app.issue].time; color:app.textMain}
         Caption {text:"ASSIGNED SPEAKER"}
         Text {text:app.issueRows[app.issue].assigned; color:app.teal}
         Caption {text:"CANDIDATE SPEAKER"}
         Text {text:app.issueRows[app.issue].candidate; color:app.purple}
         Item {Layout.fillHeight:true}
         Caption {text:"Evidence details require backend integration"; wrapMode:Text.WordWrap; Layout.fillWidth:true}
        }
       }
      }
      Card {Layout.fillWidth:true; height:190
       ColumnLayout {anchors.fill:parent; anchors.margins:13; spacing:6
        Caption {text:"REVIEW QUEUE · PRIORITIZED CANDIDATES"}
        Repeater {model:app.issueRows
         delegate: Rectangle {required property var modelData; required property int index; Layout.fillWidth:true; height:42; color:app.issue===index?"#303948":"transparent"; radius:6
          RowLayout {anchors.fill:parent; anchors.leftMargin:12
           Text {text:modelData.time; color:app.textMain; Layout.preferredWidth:170}
           Text {text:modelData.type; color:app.textMain; Layout.fillWidth:true}
           Caption {text:modelData.assigned+" → "+modelData.candidate; Layout.preferredWidth:270}
           Text {text:modelData.score; color:app.amber; Layout.preferredWidth:60}
          }
          MouseArea {anchors.fill:parent; onClicked:app.issue=index}
         }
        }
       }
      }
     }
    }
    Item {
     ColumnLayout {anchors.fill:parent; anchors.margins:27; spacing:16
      Heading {text:"Settings"}
      Caption {text:"Non-persistent configuration preview · no YAML changes"}
      Card {Layout.fillWidth:true; Layout.fillHeight:true
       ScrollView {anchors.fill:parent; anchors.margins:23; clip:true
        ColumnLayout {width:Math.min(750,parent.width-24); spacing:13
         Repeater {model:[["General / storage root","data"],["Audio sample rate","44100"],["Diarization sample rate","16000"],["Separation chunk seconds","180"],["Download format","251/140/bestaudio"],["Download audio format","opus"],["YouTube cookie browser","chrome"],["Diarization model","pyannote/speaker-diarization-3.1"],["Token environment","HF_TOKEN"],["Separation checkpoint","model_bs_roformer_ep_317_sdr_12.9755.ckpt"],["Speaker chunker","Future / not connected"]]
          delegate: ColumnLayout {required property var modelData; Layout.fillWidth:true
           Caption {text:modelData[0]}
           UiField {Layout.fillWidth:true; text:modelData[1]}
          }
         }
        }
       }
      }
     }
    }
   }
  }
 }
 Dialog {
  id:ingestDialog; title:"Add source · UI preview"; modal:true; anchors.centerIn:Overlay.overlay; width:560; standardButtons:Dialog.Close
  background:Rectangle{color:app.panel; radius:12}
  contentItem: ColumnLayout {spacing:12
   Caption {text:"Source and speaker IDs must contain 3–6 digits."}
   UiField {Layout.fillWidth:true; text:"speaker_001"}
   UiField {Layout.fillWidth:true; text:"source_007"}
   RowLayout {RadioButton{text:"URL"; checked:app.urlMode; onClicked:app.urlMode=true} RadioButton{text:"Local backend path"; checked:!app.urlMode; onClicked:app.urlMode=false}}
   UiField {Layout.fillWidth:true; placeholderText:app.urlMode?"https://youtube.com/watch?v=...":"/home/user/audio.mp3"}
   UiButton {text:app.advanced?"Hide advanced":"Advanced settings"; onClicked:app.advanced=!app.advanced}
   UiField {Layout.fillWidth:true; visible:app.advanced; text:"251/140/bestaudio"}
   Caption {text:"Demo form only; no audio import or network calls."}
  }
 }
}
