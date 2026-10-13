"""PodSieve local desktop UI with direct Python QObject bridge."""
from pathlib import Path
import sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from bridge import PipelineBridge

def main():
    app = QGuiApplication(sys.argv)
    for font in (Path(__file__).resolve().parent / "assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font))
    engine = QQmlApplicationEngine()
    bridge = PipelineBridge()
    engine.rootContext().setContextProperty("pipelineBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
