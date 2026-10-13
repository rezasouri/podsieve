"""Desktop-only Qt bridge to existing PodSieve Python functions.

No HTTP server or fake processing; real runs happen on a QThread.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import traceback

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class PipelineWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, command: str, params: dict, parent=None):
        super().__init__(parent)
        self.command = command
        self.params = params

    def run(self):
        try:
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
            layout = storage_layout_from_config(ROOT, config)
            speaker = self.params["speaker_id"]
            source = self.params["source_id"]
            overwrite = self.params.get("overwrite", False)
            if self.command == "ingest":
                loc = self.params["location"]
                output = run_ingest(
                    layout=layout, speaker_id=speaker, source_id=source,
                    input_file=Path(loc).expanduser() if self.params["mode"] == "file" else None,
                    url=loc if self.params["mode"] == "url" else None,
                    config=config, name=self.params.get("name", ""),
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
                output = run_diarization(root=ROOT, layout=layout, speaker_id=speaker,
                                         source_id=source, config=config, overwrite=overwrite)
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


class PipelineBridge(QObject):
    sourcesChanged = Signal()
    busyChanged = Signal()
    messageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sources = []
        self._busy = False
        self._message = "Ready"
        self._worker = None
        self.refreshSources()

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
        from src.core.config import load_config
        from run import storage_layout_from_config
        config = load_config(ROOT / "configs/default.yaml")
        layout = storage_layout_from_config(ROOT, config)
        rows = []
        for path in sorted(layout.speakers_root.glob("speaker_*/metadata.json")):
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
                speaker = meta.get("speaker_id", path.parent.name)
                for src in meta.get("sources", []):
                    complete = [n for n in ("raw", "conversion", "separation", "diarization")
                                if src.get(n, {}).get("status") == "completed"]
                    stage = {"raw": "Ingest", "conversion": "Convert", "separation": "Separate",
                             "diarization": "Diarize"}
                    last = stage[complete[-1]] if complete else "Pending"
                    rows.append({
                        "id": src["source_id"], "speaker": speaker,
                        "name": src.get("original_filename") or src["source_id"],
                        "input": src.get("source_type", "local"),
                        "duration": "—", "stage": last,
                        "status": "Completed" if "diarization" in complete else "Pending",
                        "reviewStatus": src.get("manual_review", {}).get("status", "pending"),
                    })
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self._set_message(f"Metadata warning: {path.name}: {exc}")
        self._sources = rows
        self.sourcesChanged.emit()

    @Slot(str, str, str, str, str, str, bool)
    def ingest(self, speaker, source, mode, location, name, language, overwrite):
        self._start("ingest", dict(speaker_id=speaker, source_id=source,
                                   mode=mode, location=location,
                                   name=name, language=language, overwrite=overwrite))

    @Slot(str, str, str, bool)
    def runStage(self, stage, speaker, source, overwrite):
        self._start(stage, dict(speaker_id=speaker, source_id=source, overwrite=overwrite))

    def _start(self, command, params):
        if self._busy:
            self._set_message("A task is already running")
            return
        if not params.get("speaker_id") or not params.get("source_id"):
            self._set_message("Select a valid source first")
            return
        self._busy = True
        self.busyChanged.emit()
        self._set_message(f"Running {command} for {params['speaker_id']}/{params['source_id']}...")
        worker = PipelineWorker(command, params, self)
        self._worker = worker
        worker.completed.connect(self._done)
        worker.failed.connect(self._failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _done(self, output):
        self._busy = False
        self.busyChanged.emit()
        self._set_message(f"Completed: {output}")
        self.refreshSources()
        self._worker = None

    def _failed(self, error):
        self._busy = False
        self.busyChanged.emit()
        self._set_message(f"Failed: {error}")
        self._worker = None
