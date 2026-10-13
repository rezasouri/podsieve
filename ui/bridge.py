"""Desktop-only Qt bridge to existing PodSieve Python functions.

No HTTP server or fake processing; real runs happen on a QThread.
"""
from __future__ import annotations

import logging
import tempfile
import re
from datetime import datetime
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QGuiApplication, QDesktopServices

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.storage_adapter import (
    speaker_name, internal_speaker, read_preferences, write_preferences,
    output_key, output_directory, check_destination, ExportLayout, publish_output,
)


class PipelineWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, command: str, params: dict, parent=None):
        super().__init__(parent)
        self.command = command
        self.params = params

    def run(self):
        class ForwardLogs(logging.Handler):
            def emit(handler, record):
                self.log.emit(handler.format(record))
        handler = ForwardLogs()
        logger = logging.getLogger()
        old_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        try:
            if self.command == "delete-source":
                from src.core.config import load_config
                from run import storage_layout_from_config
                from ui.data_registry import remove_source
                layout = storage_layout_from_config(ROOT, load_config(ROOT / "configs/default.yaml"))
                trash = remove_source(layout, self.params["internal_speaker_id"], self.params["speaker_id"], self.params["source_id"])
                self.completed.emit(str(trash))
                return
            from dotenv import load_dotenv
            from src.core.config import load_config
            from run import (
                storage_layout_from_config, run_ingest, run_convert,
                run_separation, run_diarization,
            )
            from src.diarization.quality import QualityConfig, analyze_source
            from src.diarization.quality.saved_evidence import SavedEvidenceAdapter

            load_dotenv(ROOT / ".env", override=False)
            config = load_config(ROOT / "configs/default.yaml")
            for section, values in self.params.get("config", {}).items():
                config.setdefault(section, {}).update(values)
            if self.params.get("quality", True):
                config.setdefault("diarization_quality", {})["enabled"] = True
            layout = storage_layout_from_config(ROOT, config)
            speaker = self.params.get("internal_speaker_id", self.params["speaker_id"])
            source = self.params["source_id"]
            overwrite = self.params.get("overwrite", False)
            if self.command == "ingest":
                loc = self.params["location"]
                output = run_ingest(
                    layout=layout, speaker_id=speaker, source_id=source,
                    input_file=Path(loc).expanduser() if self.params["mode"] == "file" else None,
                    url=loc if self.params["mode"] == "url" else None,
                    config=config, name=self.params.get("name", "") or (self.params["speaker_id"] if speaker != self.params["speaker_id"] else ""),
                    gender=self.params.get("gender", ""),
                    language=self.params.get("language", "fa"),
                    overwrite=overwrite,
                )
            elif self.command == "convert":
                output = run_convert(layout=layout, speaker_id=speaker,
                                     source_id=source, config=config, overwrite=overwrite)
            elif self.command == "separate":
                output = run_separation(root=ROOT, layout=layout, speaker_id=speaker,
                                        source_id=source, config=config, overwrite=overwrite,
                                        keep_work_dir=False)
            elif self.command == "diarize":
                def diarize(active_layout):
                    return run_diarization(root=ROOT, layout=active_layout, speaker_id=speaker,
                                           source_id=source, config=config, overwrite=overwrite,
                                           num_speakers=self.params.get("num_speakers"),
                                           save_evidence=self.params.get("evidence", True),
                                           quality_analysis=self.params.get("quality", True))
                if self.params.get("output_parent"):
                    if not config.get("diarization", {}).get("save_segments", True):
                        raise ValueError("Custom output requires diarization.save_segments to be enabled")
                    name = self.params["speaker_id"]
                    target = output_directory(self.params["output_parent"], name)
                    check_destination(target, name, source, overwrite)
                    with tempfile.TemporaryDirectory(prefix=".podsieve-diarization-", dir=target.parent) as temporary:
                        stage = Path(temporary) / "final"
                        export_layout = ExportLayout(layout.data_root, layout.schema_version, stage)
                        output = diarize(export_layout)
                        if not (stage / "segments").is_dir():
                            raise ValueError("Diarization did not produce final segments")
                        publish_output(stage, target, name, source, overwrite=overwrite)
                    self.log.emit("Published diarized files: " + str(target))
                    output = target
                else:
                    output = diarize(layout)
            elif self.command == "analyze-diarization":
                quality = QualityConfig.from_mapping(config.get("diarization_quality", {}))
                annotation = layout.diarization_json_path(speaker, source)
                if not annotation.is_file():
                    annotation = layout.diarization_rttm_path(speaker, source)
                evidence_dir = layout.diarization_evidence_dir(speaker, source)
                adapter = (SavedEvidenceAdapter(
                    evidence_dir, audio_path=layout.vocals_path(speaker, source),
                    annotation_path=annotation
                ) if evidence_dir.is_dir() else None)
                output_dir = layout.diarization_quality_dir(speaker, source)
                analyze_source(
                    source_id=source,
                    audio_path=layout.vocals_path(speaker, source),
                    diarization_path=annotation,
                    output_dir=output_dir, config=quality,
                    evidence_adapter=adapter,
                    top_k=30, min_score=0.0, export_clips=None,
                    overwrite=overwrite,
                    configured_backend=str(config.get("diarization", {}).get("model", "pyannote/speaker-diarization-3.1")),
                )
                output = output_dir / "quality_summary.json"
            else:
                raise ValueError(f"Unknown stage: {self.command}")
            self.completed.emit(str(output))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)


class PipelineBridge(QObject):
    stateChanged = Signal()
    sourcesChanged = Signal()
    busyChanged = Signal()
    messageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._states = ["not-started"] * 4
        self._logs = []
        self._queue = []
        self._failures = {}
        self._selected = ("speaker_001", "source_001")
        self._active = ""
        self._output = ""
        self._output_parent = ""
        self._params = {}
        self._sources = []
        self._busy = False
        self._message = "Ready"
        self._worker = None
        self.refreshSources()
        self.selectSource(*self._selected)
        self._append_log("PodSieve initialized.")

    @Property("QVariantList", notify=stateChanged)
    def stageStates(self):
        return self._states

    @Property("QVariantList", notify=stateChanged)
    def logs(self):
        return self._logs

    @Property(str, notify=stateChanged)
    def outputPath(self):
        return self._output

    @Property(str, notify=stateChanged)
    def outputParent(self):
        return self._output_parent

    @Slot(str, result=bool)
    def validSpeakerName(self, value):
        try:
            speaker_name(value)
            return True
        except ValueError:
            return False

    @Slot(str)
    def setOutputParent(self, value):
        if not self._busy:
            self._output_parent = value.strip()
            self._update_output()
            self.stateChanged.emit()

    def _layout(self):
        from src.core.config import load_config
        from run import storage_layout_from_config
        return storage_layout_from_config(ROOT, load_config(ROOT / "configs/default.yaml"))

    def _update_output(self):
        name, source = self._selected
        layout = self._layout()
        try:
            key = internal_speaker(layout, name)
            if self._output_parent:
                self._output = str(output_directory(self._output_parent, name))
            else:
                self._output = str(layout.diarization_segments_dir(key, source)) if key and re.fullmatch(r"source_\d{3,6}", source) else ""
        except (ValueError, OSError):
            self._output = ""

    @Property(str, notify=stateChanged)
    def activeStage(self):
        return self._active

    @Property(bool, notify=stateChanged)
    def outputAvailable(self):
        if self._states[3] != "completed" or not self._output or not Path(self._output).is_dir():
            return False
        if self._output_parent:
            try:
                owner = json.loads((Path(self._output) / ".podsieve-export.json").read_text(encoding="utf-8"))
                return owner.get("speaker") == self._selected[0] and self._selected[1] in owner.get("sources", {})
            except (OSError, ValueError):
                return False
        return True

    @Slot(str)
    def _append_log(self, message, tone="neutral"):
        self._logs = (self._logs + [{"time": datetime.now().strftime("%H:%M:%S"),
                                   "text": message, "tone": tone}])[-2000:]
        self.stateChanged.emit()

    @Slot()
    def reportBusyClose(self):
        self._append_log("Wait for the running stage to finish before closing.")

    @Slot()
    def clearLogs(self):
        self._logs = []
        self.stateChanged.emit()

    @Slot(str, str)
    def selectSource(self, speaker, source):
        if self._busy:
            return
        layout = self._layout()
        speaker = speaker.strip()
        self._selected = (speaker, source)
        self._states = ["not-started"] * 4
        try:
            key = internal_speaker(layout, speaker)
            prefs = read_preferences(layout)
            saved_output = prefs["outputs"].get(output_key(speaker, source), "")
            if saved_output:
                self._output_parent = saved_output
            if key and re.fullmatch(r"source_\d{3,6}", source):
                path = layout.speakers_root / key / "metadata.json"
                if path.is_file():
                    meta = json.loads(path.read_text())
                    row = next((r for r in meta.get("sources", []) if r.get("source_id") == source), {})
                    self._states = ["completed" if row.get(k, {}).get("status") == "completed"
                                    else "not-started" for k in ("raw", "conversion", "separation", "diarization")]
        except (OSError, ValueError, TypeError) as exc:
            if self.validSpeakerName(speaker):
                self._append_log(str(exc), "error")
        self._update_output()
        self.stateChanged.emit()

    @Slot()
    def copyOutputPath(self):
        QGuiApplication.clipboard().setText(self._output)

    @Slot()
    def openOutputFolder(self):
        if self.outputAvailable:
            if QDesktopServices.openUrl(QUrl.fromLocalFile(self._output)):
                self._append_log("Opened output folder: " + self._output)
            else:
                self._append_log("Could not open output folder.", "error")

    @Slot(str, "QVariantMap")
    def execute(self, command, options):
        if self._busy:
            return
        params = dict(options)
        speaker, source = params.get("speaker_id", ""), params.get("source_id", "")
        if not self.validSpeakerName(speaker) or not re.fullmatch(r"source_\d{3,6}", source):
            self._append_log("Invalid speaker or source ID.", "error")
            return
        speaker = speaker.strip()
        params["speaker_id"] = speaker
        count = params.get("num_speakers")
        if count is not None and (not isinstance(count, (int, float)) or count < 1 or int(count) != count):
            self._append_log("Expected speaker count must be a positive integer.", "error")
            return
        if count is not None:
            params["num_speakers"] = int(count)
        audio = params.get("config", {}).get("audio", {})
        if any(not isinstance(value, (int, float)) or value <= 0 for value in audio.values()):
            self._append_log("Sample rate and chunk duration must be positive numbers.", "error")
            return
        if params.get("quality", True) and not params.get("evidence", True):
            self._append_log("Quality analysis requires saved evidence.", "error")
            return
        names = ["ingest", "convert", "separate", "diarize"]
        if command not in names + ["full"]:
            return
        self.selectSource(speaker, source)
        indexes = list(range(4)) if command == "full" else [names.index(command)]
        if not params.get("overwrite") and any(self._states[i] == "completed" for i in indexes):
            self._append_log("Enable overwrite to rerun completed stages.", "error")
            return
        if command != "full" and indexes[0] > 0 and self._states[indexes[0]-1] != "completed":
            self._append_log("Complete the preceding stage first.", "error")
            return
        if command in ("full", "ingest"):
            location = params.get("location", "").strip()
            if params.get("mode") == "file":
                valid = Path(location).expanduser().is_file()
            else:
                from urllib.parse import urlparse
                parsed = urlparse(location)
                host = parsed.hostname or ""
                valid = parsed.scheme in ("http", "https") and any(
                    host == h or host.endswith("." + h) for h in ("youtube.com", "youtu.be", "castbox.fm"))
            if not valid:
                self._append_log("Select an existing local file or a supported URL.", "error")
                return
        try:
            layout = self._layout()
            parent = params.get("output_parent", self._output_parent).strip()
            if parent:
                target = output_directory(parent, speaker)
                check_destination(target, speaker, source, params.get("overwrite", False))
            params["output_parent"] = parent
            params["internal_speaker_id"] = internal_speaker(layout, speaker, create=True)
            prefs = read_preferences(layout)
            prefs["outputs"][output_key(speaker, source)] = parent
            write_preferences(layout, prefs)
            self._output_parent = parent
            self._update_output()
        except (OSError, ValueError) as exc:
            self._append_log(str(exc), "error")
            return
        self._params = params
        self._queue = [names[i] for i in indexes]
        self._next_stage()

    def _next_stage(self):
        if self._queue:
            self._start(self._queue.pop(0), self._params)
        else:
            self._busy = False
            self._active = ""
            self.busyChanged.emit()
            self.stateChanged.emit()

    @Property("QVariantList", notify=sourcesChanged)
    def sources(self):
        return self._sources

    @Property(bool, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self):
        return self._message

    def _set_message(self, value):
        self._message = value
        self.messageChanged.emit()

    @Slot()
    def refreshSources(self):
        from ui.data_registry import scan_sources
        try:
            rows = scan_sources(self._layout())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._set_message("Metadata warning: " + str(exc))
            self._append_log(self._message, "error")
            return
        for row in rows:
            failure = self._failures.get(row["key"])
            if failure:
                row["status"] = "failed"
                row["failure"] = failure[1]
                if failure[0] in ("ingest", "convert", "separate", "diarize"):
                    row["stages"][["ingest", "convert", "separate", "diarize"].index(failure[0])] = "failed"
            if self._busy and self._active != "delete-source" and row["speaker"] == self._params.get("speaker_id") and row["id"] == self._params.get("source_id"):
                row["status"] = "processing"
                if self._active in ("ingest", "convert", "separate", "diarize"):
                    row["stages"][["ingest", "convert", "separate", "diarize"].index(self._active)] = "processing"
        self._sources = rows
        self.sourcesChanged.emit()

    @Slot(str, str, str)
    def deleteSource(self, name, source, confirmation):
        if self._busy or confirmation != source:
            return
        key = internal_speaker(self._layout(), name)
        if not key:
            self._set_message("Select a registered source")
            return
        self._params = dict(speaker_id=name, source_id=source, internal_speaker_id=key)
        self._start("delete-source", self._params)

    def _registered_path(self, value):
        from ui.data_registry import scan_sources
        rows = scan_sources(self._layout())
        allowed = {row["outputPath"] for row in rows}
        allowed.update(f["path"] for row in rows for group in row["fileGroups"] for f in group["files"])
        path = Path(value)
        if str(path) not in allowed or not path.exists():
            raise ValueError("Artifact is unavailable or is not registered")
        return path

    @Slot(str)
    def copyArtifactPath(self, value):
        try:
            QGuiApplication.clipboard().setText(str(self._registered_path(value)))
        except (OSError, ValueError) as exc:
            self._set_message(str(exc))

    @Slot(str)
    def openArtifactFolder(self, value):
        try:
            path = self._registered_path(value)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path if path.is_dir() else path.parent))):
                raise OSError("Could not open artifact folder")
        except (OSError, ValueError) as exc:
            self._set_message(str(exc))

    @Slot(str, str, str, str, str, str, bool)
    def ingest(self, speaker, source, mode, location, name, language, overwrite):
        self.execute("ingest", dict(speaker_id=speaker, source_id=source,
                                   mode=mode, location=location,
                                   name=name, language=language, overwrite=overwrite))

    @Slot(str, str, str, bool)
    def runStage(self, stage, speaker, source, overwrite):
        self.execute(stage, dict(speaker_id=speaker, source_id=source, overwrite=overwrite))

    def _start(self, command, params):
        if self._busy:
            self._set_message("A task is already running")
            return
        if not params.get("speaker_id") or not params.get("source_id"):
            self._set_message("Select a valid source first")
            return
        self._busy = True
        self._active = command
        if command in ("ingest", "convert", "separate", "diarize"):
            self._states[["ingest", "convert", "separate", "diarize"].index(command)] = "processing"
        self._append_log(command.title() + " started.", "processing")
        self.busyChanged.emit()
        self._set_message(f"Running {command} for {params['speaker_id']}/{params['source_id']}...")
        worker = PipelineWorker(command, params, self)
        self._worker = worker
        worker.log.connect(self._append_log)
        worker.completed.connect(self._done)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self.refreshSources()

    @Slot(str)
    def _done(self, output):
        if self._params.get("internal_speaker_id"):
            self._failures.pop(self._params["internal_speaker_id"] + "/" + self._params["source_id"], None)
        if self._active in ("ingest", "convert", "separate", "diarize"):
            self._states[["ingest", "convert", "separate", "diarize"].index(self._active)] = "completed"
        self._set_message(f"Completed: {output}")
        self._append_log(self._active.title() + " completed successfully.", "success")
        self.refreshSources()

    @Slot(str)
    def _failed(self, error):
        if self._params.get("internal_speaker_id") and self._active != "delete-source":
            self._failures[self._params["internal_speaker_id"] + "/" + self._params["source_id"]] = (self._active, error)
        if self._active in ("ingest", "convert", "separate", "diarize"):
            self._states[["ingest", "convert", "separate", "diarize"].index(self._active)] = "failed"
        self._queue = []
        self._set_message(f"Failed: {error}")
        self._append_log(error, "error")

    @Slot()
    def _worker_finished(self):
        was_deletion = self._active == "delete-source"
        self._worker = None
        self._busy = False
        self._next_stage()
        if was_deletion:
            self.selectSource(*self._selected)
        self.refreshSources()
