"""Native QML data-manager navigation and selection regression checks."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class DataPageTests(unittest.TestCase):
    def test_filters_inspection_confirmation_and_busy_guard(self):
        script = r'''
import tempfile, wave
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, QUrl, QMetaObject, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQml import QQmlApplicationEngine
import shiboken6
from ui import bridge as desktop
from run import run_ingest

app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory()
root = Path(temporary.name)
(root / "configs").mkdir()
(root / "configs/default.yaml").write_text("storage:\n  data_root: data\n")
audio = root / "audio.wav"
with wave.open(str(audio), "wb") as out:
    out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000)
    out.writeframes(b"\x00\x00" * 1600)
desktop.ROOT = root
bridge = desktop.PipelineBridge()
for speaker in ("speaker_001", "speaker_002"):
    run_ingest(layout=bridge._layout(), speaker_id=speaker, source_id="source_001",
               input_file=audio, config={}, name=speaker, gender="", language="fa", overwrite=False)
bridge.refreshSources()
messages = []
qInstallMessageHandler(lambda kind, context, msg: messages.append(msg) if ".qml" in msg or ".qml" in (context.file or "") else None)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("pipelineBridge", bridge)
engine.load(QUrl.fromLocalFile(str(Path("ui/Main.qml").resolve())))
assert engine.rootObjects(), messages
window = engine.rootObjects()[0]
window.setProperty("pageView", "data")

def value(obj, prop):
    v = obj.property(prop)
    return v.toVariant() if hasattr(v, "toVariant") else v

def inspect():
    try:
        setup = window.findChild(QObject, "tokenSetupDialog")
        assert setup is not None and setup.property("visible")
        token_input = window.findChild(QObject, "huggingFaceTokenInput")
        assert token_input.property("text") == ""
        assert not window.findChild(QObject, "saveHuggingFaceTokenButton").property("enabled")
        assert QMetaObject.invokeMethod(setup, "close")
        manager = window.findChild(QObject, "processedData")
        assert manager is not None
        assert len(value(manager, "records")) == 2
        # Same source_id under two speakers must select distinct records.
        manager.setProperty("selectedKey", bridge.sources[1]["key"])
        assert value(manager, "selected")["internalSpeaker"] == "speaker_002"
        manager.findChild(QObject, "sourceSearch").setProperty("text", "no match")
        assert value(manager, "filtered") == []
        assert value(manager, "selected") is None
        manager.findChild(QObject, "sourceSearch").setProperty("text", "")
        assert len(value(manager, "filtered")) == 2
        manager.findChild(QObject, "speakerFilter").setProperty("currentIndex", 1)
        assert len(value(manager, "filtered")) == 1
        manager.setProperty("inspectorTab", 2)
        manager.setProperty("previewOpen", True)
        # Opening confirmation does not remove data.
        button = manager.findChild(QObject, "deleteSourceButton")
        QMetaObject.invokeMethod(button, "clicked")
        assert manager.findChild(QObject, "deleteSourceDialog").property("opened")
        confirmation = manager.findChild(QObject, "deleteConfirmation")
        confirm = manager.findChild(QObject, "confirmDeleteSourceButton")
        confirmation.setProperty("text", "wrong")
        assert not confirm.property("enabled")
        confirmation.setProperty("text", "source_001")
        assert confirm.property("enabled")
        bridge._busy = True; bridge.busyChanged.emit()
        assert not button.property("enabled")
        assert not confirm.property("enabled")
        bridge._busy = False; bridge.busyChanged.emit()
        assert len(bridge.sources) == 2
        QTimer.singleShot(200, finish)
    except Exception:
        import traceback; traceback.print_exc(); app.exit(1)

def finish():
    try:
        assert not messages, messages
        window.setProperty("pageView", "process")
        QTimer.singleShot(100, check_unloaded)
    except Exception:
        import traceback; traceback.print_exc(); app.exit(1)

def check_unloaded():
    try:
        assert not window.findChild(QObject, "processedData")
        app.quit()
    except Exception:
        import traceback; traceback.print_exc(); app.exit(1)

QTimer.singleShot(200, inspect)
result = app.exec()
shiboken6.delete(engine)
raise SystemExit(result)
'''
        result = subprocess.run([sys.executable, "-c", script],
                                cwd=Path(__file__).resolve().parents[1],
                                env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
