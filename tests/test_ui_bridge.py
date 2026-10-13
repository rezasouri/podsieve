"""Desktop state and actual local ingest/convert checks without running models."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import wave

from PySide6.QtCore import QCoreApplication
from ui import bridge as desktop


class DesktopBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "configs").mkdir()
        (self.root / "configs/default.yaml").write_text(
            "storage:\n  data_root: data\naudio:\n  sample_rate: 44100\n")
        self.root_patch = patch.object(desktop, "ROOT", self.root)
        self.root_patch.start()
        self.bridge = desktop.PipelineBridge()
        self.audio = self.root / "input.wav"
        with wave.open(str(self.audio), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * 1600)
        self.options = dict(speaker_id="speaker_001", source_id="source_001",
                            mode="file", location=str(self.audio), overwrite=False,
                            evidence=True, quality=True)

    def tearDown(self):
        self.root_patch.stop()
        self.tmp.cleanup()

    def wait_for_worker(self):
        deadline = time.monotonic() + 30
        while self.bridge.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(self.bridge.busy, "Worker did not finish")
        self.app.processEvents()

    def test_real_ingest_and_convert(self):
        self.bridge.execute("ingest", self.options)
        self.wait_for_worker()
        self.assertEqual(self.bridge.stageStates[0], "completed")
        self.bridge.execute("convert", self.options)
        self.wait_for_worker()
        self.assertEqual(self.bridge.stageStates[:2], ["completed", "completed"])
        wav = self.root / "data/speakers/speaker_001/wav/source_001.wav"
        with wave.open(str(wav)) as output:
            self.assertEqual(output.getframerate(), 44100)
            self.assertEqual(output.getnchannels(), 2)
        self.bridge.execute("ingest", self.options)
        self.assertFalse(self.bridge.busy)
        self.assertIn("overwrite", self.bridge.logs[-1]["text"])

    def test_full_pipeline_stops_after_failure(self):
        with patch("run.run_separation", side_effect=RuntimeError("test separation failure")), \
             patch("run.run_diarization") as diarize:
            self.bridge.execute("full", self.options)
            self.wait_for_worker()
            self.assertEqual(self.bridge.stageStates,
                             ["completed", "completed", "failed", "not-started"])
            diarize.assert_not_called()
            self.assertTrue(any("test separation failure" in r["text"] for r in self.bridge.logs))

    def test_full_pipeline_chains_and_passes_options(self):
        options = dict(self.options, num_speakers=2, quality=False)
        with patch("run.run_separation", return_value={}), \
             patch("run.run_diarization", return_value={}) as diarize:
            self.bridge.execute("full", options)
            self.wait_for_worker()
            self.assertEqual(self.bridge.stageStates, ["completed"] * 4)
            self.assertEqual(diarize.call_args.kwargs["num_speakers"], 2)
            self.assertFalse(diarize.call_args.kwargs["quality_analysis"])

    def test_free_speaker_id_is_ui_only_and_survives_restart(self):
        from src.core.storage_layout import validate_speaker_id
        from ui.storage_adapter import internal_speaker
        options = dict(self.options, speaker_id="حمید تست")
        self.bridge.execute("ingest", options)
        self.wait_for_worker()
        self.assertEqual(self.bridge.stageStates[0], "completed")
        key = internal_speaker(self.bridge._layout(), "حمید تست")
        self.assertRegex(key, r"^speaker_[0-9]{6}$")
        with self.assertRaises(ValueError):
            validate_speaker_id("حمید تست")
        restarted = desktop.PipelineBridge()
        restarted.selectSource("حمید تست", "source_001")
        self.assertEqual(restarted.stageStates[0], "completed")
        self.bridge.execute("convert", options)
        self.wait_for_worker()
        self.assertEqual(self.bridge.stageStates[1], "completed")
        self.assertEqual(self.bridge.sources[0]["speaker"], "حمید تست")
        self.bridge.execute("ingest", dict(options, source_id="anything"))
        self.assertFalse(self.bridge.busy)

    def test_custom_output_uses_speaker_folder_without_default_segments(self):
        from src.diarization.finalize import publish_clean_segments
        from ui.storage_adapter import internal_speaker
        desktop_folder = self.root / "Desktop"
        desktop_folder.mkdir()
        options = dict(self.options, speaker_id="hamid", output_parent=str(desktop_folder))
        def fake_model(**kwargs):
            # Use the production final publisher, replacing only model inference.
            annotation = kwargs["rttm_output"]
            annotation.parent.mkdir(parents=True, exist_ok=True)
            annotation.write_text("test annotation")
            kwargs["json_output"].write_text("{}")
            clips = self.root / "model-clips"
            clips.mkdir(exist_ok=True)
            (clips / "SPEAKER_00_0001.wav").write_bytes(self.audio.read_bytes())
            publish_clean_segments(source_id=kwargs["source_id"], temporary_segments_dir=clips,
                                   segments=[dict(index=1, speaker="SPEAKER_00", start=0, end=0.1)],
                                   quality_dir=self.root / "quality", final_dir=kwargs["segments_dir"].parent,
                                   padding_seconds=0, overwrite=kwargs["overwrite"], quality_analysis=False)
            return dict(json=kwargs["json_output"], segments_dir=kwargs["segments_dir"])
        with patch("run.run_separation", return_value={}), patch("run.diarize_audio", side_effect=fake_model):
            self.bridge.execute("full", options)
            self.wait_for_worker()
        self.assertEqual(self.bridge.stageStates, ["completed"] * 4, self.bridge.logs)
        target = desktop_folder / "hamid"
        self.assertEqual(Path(self.bridge.outputPath), target)
        self.assertTrue(self.bridge.outputAvailable)
        self.assertTrue((target / "SPEAKER_00/source_001_SPEAKER_00_0001.wav").is_file())
        self.assertTrue((target / ".podsieve/source_001/manifest.csv").is_file())
        key = internal_speaker(self.bridge._layout(), "hamid")
        self.assertFalse(self.bridge._layout().diarization_segments_dir(key, "source_001").exists())
        self.assertFalse(list(desktop_folder.glob(".podsieve-diarization-*")))
        restarted = desktop.PipelineBridge()
        restarted.selectSource("hamid", "source_001")
        self.assertEqual(restarted.outputParent, str(desktop_folder))
        self.assertEqual(Path(restarted.outputPath), target)
        self.assertTrue(restarted.outputAvailable)

    def test_registry_distinguishes_duplicate_source_ids_and_counts_files(self):
        for name in ("hamid", "reza"):
            self.bridge.execute("ingest", dict(self.options, speaker_id=name))
            self.wait_for_worker()
        rows = self.bridge.sources
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["speaker"] for row in rows}, {"hamid", "reza"})
        self.assertEqual(len({row["key"] for row in rows}), 2)
        for row in rows:
            self.assertEqual(row["artifacts"], 1)
            self.assertEqual(row["bytes"], self.audio.stat().st_size)
            self.assertEqual(row["stages"], ["completed"] + ["not-started"] * 3)
            self.assertTrue(row["previewUri"].startswith("file:"))

    def test_source_deletion_requires_confirmation_and_preserves_other_sources(self):
        for source in ("source_001", "source_002"):
            self.bridge.execute("ingest", dict(self.options, source_id=source))
            self.wait_for_worker()
        self.bridge.deleteSource("speaker_001", "source_001", "wrong")
        self.assertFalse(self.bridge.busy)
        self.assertEqual(len(self.bridge.sources), 2)
        self.bridge.deleteSource("speaker_001", "source_001", "source_001")
        self.wait_for_worker()
        self.assertEqual([row["id"] for row in self.bridge.sources], ["source_002"])
        layout = self.bridge._layout()
        self.assertFalse(layout.raw_source_path("speaker_001", "source_001", ".wav").exists())
        self.assertTrue(layout.raw_source_path("speaker_001", "source_002", ".wav").exists())
        self.assertTrue(list((layout.data_root / ".podsieve-trash").glob("*/restore.json")))

    def test_deletion_removes_only_owned_external_source_files(self):
        from ui.data_registry import remove_source
        from ui.storage_adapter import publish_output, read_preferences, write_preferences, output_key
        parent = self.root / "Desktop"
        parent.mkdir()
        stage = self.root / "export"
        (stage / "segments/SPEAKER_00").mkdir(parents=True)
        (stage / "segments/SPEAKER_00/SPEAKER_00_0001.wav").write_bytes(self.audio.read_bytes())
        for source in ("source_001", "source_002"):
            self.bridge.execute("ingest", dict(self.options, source_id=source))
            self.wait_for_worker()
            publish_output(stage, parent / "speaker_001", "speaker_001", source, overwrite=False)
            prefs = read_preferences(self.bridge._layout())
            prefs["outputs"][output_key("speaker_001", source)] = str(parent)
            write_preferences(self.bridge._layout(), prefs)
        remove_source(self.bridge._layout(), "speaker_001", "speaker_001", "source_001")
        target = parent / "speaker_001/SPEAKER_00"
        self.assertFalse((target / "source_001_SPEAKER_00_0001.wav").exists())
        self.assertTrue((target / "source_002_SPEAKER_00_0001.wav").is_file())
        self.bridge.refreshSources()
        self.assertEqual([row["id"] for row in self.bridge.sources], ["source_002"])

    def test_registry_failure_rolls_back_source_deletion(self):
        from ui.data_registry import remove_source
        self.bridge.execute("ingest", self.options)
        self.wait_for_worker()
        with patch("ui.data_registry.write_global_registries", side_effect=[OSError("registry locked"), None]):
            with self.assertRaises(OSError):
                remove_source(self.bridge._layout(), "speaker_001", "speaker_001", "source_001")
        self.bridge.refreshSources()
        self.assertEqual(len(self.bridge.sources), 1)
        self.assertTrue(self.bridge._layout().raw_source_path("speaker_001", "source_001", ".wav").is_file())

    def test_invalid_inputs_and_evidence_dependency(self):
        self.bridge.execute("full", dict(self.options, evidence=False))
        self.assertFalse(self.bridge.busy)
        self.assertIn("evidence", self.bridge.logs[-1]["text"])
        self.bridge.execute("full", dict(self.options, location="/missing/audio.wav"))
        self.assertFalse(self.bridge.busy)
        self.bridge.execute("full", dict(self.options, speaker_id="../bad"))
        self.assertFalse(self.bridge.busy)


if __name__ == "__main__":
    unittest.main()
