"""Regression check for completed bars after indeterminate animation stops."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class ProgressBarTests(unittest.TestCase):
    def test_completion_fills_track_after_animation(self):
        script = r'''
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQml import QQmlApplicationEngine
from ui.bridge import PipelineBridge

app = QGuiApplication([])
engine = QQmlApplicationEngine()
bridge = PipelineBridge()
engine.rootContext().setContextProperty("pipelineBridge", bridge)
engine.load(QUrl.fromLocalFile(str(Path("ui/Main.qml").resolve())))
assert engine.rootObjects()
window = engine.rootObjects()[0]
window.setProperty("pageView", "process")
import tempfile
output_tmp = tempfile.TemporaryDirectory()
assert window.findChild(QObject, "speaker").property("text") == ""
assert window.findChild(QObject, "sourceId").property("text") == ""
assert bridge.stageStates == ["not-started"] * 4
assert bridge.outputPath == ""
window.findChild(QObject, "sourceId").setProperty("text", "source_001")
window.findChild(QObject, "speaker").setProperty("text", "hamid")
assert window.property("idsValid")
bridge.setOutputParent(output_tmp.name)
assert bridge.outputPath == str(Path(output_tmp.name) / "hamid")
window.findChild(QObject, "sourceId").setProperty("text", "bad")
assert not window.property("idsValid")
window.findChild(QObject, "sourceId").setProperty("text", "source_001")
assert window.property("idsValid")
def find_item(name):
    def visit(item):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = visit(child)
            if found is not None:
                return found
        return None
    return visit(window.contentItem())

bridge._states = ["processing"] * 4
bridge.stateChanged.emit()

def complete():
    bridge._states = ["completed"] * 4
    bridge.stateChanged.emit()
    QTimer.singleShot(100, check)

def check():
    try:
        for i in range(4):
            track = find_item("stageProgress" + str(i))
            fill = find_item("stageCompletedFill" + str(i))
            assert track is not None and fill is not None
            assert fill.property("visible")
            assert fill.property("x") == 0
            assert abs(fill.property("width") - track.property("width")) < 0.01
        # Verify bindings remain correct on resizing, and non-completed bars hide.
        window.setWidth(1180)
        bridge._states = ["completed", "failed", "not-started", "completed"]
        bridge.stateChanged.emit()
        QTimer.singleShot(100, check_resize)
    except Exception:
        import traceback
        traceback.print_exc()
        app.exit(1)

def check_resize():
    try:
        for i in (0, 3):
            track = find_item("stageProgress" + str(i))
            fill = find_item("stageCompletedFill" + str(i))
            assert fill.property("x") == 0
            assert abs(fill.property("width") - track.property("width")) < 0.01
        for i in (1, 2):
            assert not find_item("stageCompletedFill" + str(i)).property("visible")
        assert window.property("minimumWidth") == 1180
        assert window.property("minimumHeight") == 720
        window.setWidth(1920)
        window.setHeight(1080)
        app.processEvents()
        scale = window.property("uiScale")
        assert 1 < scale <= 1.75
        nav = window.findChild(QObject, "headerNavigation")
        assert abs(nav.property("x") + nav.property("width") / 2 - nav.parentItem().width() / 2) < 0.1
        canvas = window.findChild(QObject, "responsiveCanvas")
        assert abs(canvas.property("width") * scale - window.width()) < 0.1
        window.setWidth(1180)
        window.setHeight(720)
        app.processEvents()
        assert window.property("uiScale") == 1
        assert abs(nav.property("x") + nav.property("width") / 2 - nav.parentItem().width() / 2) < 0.1
        from PySide6.QtCore import QMetaObject
        window.findChild(QObject, "file").setProperty("text", "/tmp/input.wav")
        window.findChild(QObject, "overwrite").setProperty("checked", True)
        button = window.findChild(QObject, "clearProcessingButton")
        bridge._busy = True
        bridge.busyChanged.emit()
        assert not button.property("enabled")
        bridge._busy = False
        bridge.busyChanged.emit()
        assert button.property("enabled")
        assert QMetaObject.invokeMethod(button, "clicked")
        assert window.findChild(QObject, "file").property("text") == ""
        assert window.findChild(QObject, "speaker").property("text") == ""
        assert window.findChild(QObject, "sourceId").property("text") == ""
        assert not window.findChild(QObject, "overwrite").property("checked")
        assert window.findChild(QObject, "evidence").property("checked")
        assert window.findChild(QObject, "quality").property("checked")
        assert bridge.stageStates == ["not-started"] * 4
        assert bridge.logs == []
        assert bridge.outputPath == "" and bridge.outputParent == ""
        assert not window.property("canFull")
        app.quit()
    except Exception:
        import traceback
        traceback.print_exc()
        app.exit(1)

# Stop midway through an animation, as in a real stage transition.
QTimer.singleShot(450, complete)
result = app.exec()
import shiboken6
shiboken6.delete(engine)
raise SystemExit(result)
'''
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_LOGGING_RULES="qt.multimedia.*=false")
        result = subprocess.run([sys.executable, "-c", script],
                                cwd=Path(__file__).resolve().parents[1], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Headless CI runners do not have a PulseAudio server. Qt Multimedia may\n        # emit this harmless warning even when the offscreen UI behaves correctly.\n        stderr = result.stderr.replace("PulseAudioService: pa_context_connect() failed\\n", "")\n        self.assertEqual(stderr, "")
