from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from src.diarization.quality.analyzer import analyze_source, read_diarization
from src.diarization.quality.embeddings import speaker_confusion
from src.diarization.quality.overlap import confirmed_overlap
from src.diarization.quality.schemas import ActivityFrame, Interval, QualityConfig, Segment
from src.diarization.quality.temporal import temporal_candidates
from run import build_parser, main


def segment(index: int, start: float, end: float, speaker: str) -> Segment:
    return Segment(start, end, speaker, index)


class EmbeddingAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = QualityConfig(minimum_reference_segments=2)

    def test_correct_two_speaker_assignments(self) -> None:
        rows = [segment(i, i * 2, i * 2 + 1, "A" if i < 3 else "B") for i in range(6)]
        vectors = {i: ([1, 0] if i < 3 else [0, 1]) for i in range(6)}
        self.assertEqual(speaker_confusion(rows, vectors, self.config)[0], [])

    def test_swapped_assignment_and_ambiguous_embedding(self) -> None:
        rows = [segment(i, i * 2, i * 2 + 1, "A" if i < 4 else "B") for i in range(7)]
        vectors = {i: ([1, 0] if i < 4 else [0, 1]) for i in range(7)}
        vectors[3] = [0, 1]
        candidates, _ = speaker_confusion(rows, vectors, self.config)
        self.assertTrue(any(c.assigned_speaker == "A" and c.candidate_speaker == "B" for c in candidates))
        self.assertTrue(any(c.features["speaker_margin"] < 0 for c in candidates))
        vectors[3] = [1, 1]
        candidates, _ = speaker_confusion(rows, vectors, self.config)
        self.assertTrue(any(abs(c.features["speaker_margin"]) < 0.11 for c in candidates))

    def test_short_or_insufficient_reference_segments(self) -> None:
        rows = [segment(0, 0, .2, "A"), segment(1, 1, 2, "A"), segment(2, 3, 4, "B")]
        candidates, warnings = speaker_confusion(rows, {0: [0, 1], 1: [1, 0], 2: [0, 1]}, self.config)
        self.assertFalse(candidates)
        self.assertTrue(warnings)

    def test_three_speakers(self) -> None:
        rows = [segment(i, i * 2, i * 2 + 1, "ABC"[i // 3]) for i in range(9)]
        vectors = {i: [[1, 0, 0], [0, 1, 0], [0, 0, 1]][i // 3] for i in range(9)}
        vectors[2] = [0, 0, 1]
        candidates, _ = speaker_confusion(rows, vectors, self.config)
        self.assertTrue(any(c.candidate_speaker == "C" for c in candidates))


class OverlapAndTemporalTests(unittest.TestCase):
    def test_no_overlap_and_adjacent_turns(self) -> None:
        rows = [segment(0, 0, 1, "A"), segment(1, 1, 2, "B")]
        self.assertEqual(confirmed_overlap(rows), [])

    def test_overlap_and_duplicate_same_speaker_tracks(self) -> None:
        rows = [segment(0, 0, 3, "A"), segment(1, 1, 2, "A"), segment(2, 1.5, 2.5, "B")]
        result = confirmed_overlap(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0][0].start, result[0][0].end, result[0][1]), (1.5, 2.5, ("A", "B")))

    def test_three_speaker_overlap_and_adjacent_boundaries(self) -> None:
        rows = [segment(0, 0, 2, "A"), segment(1, 1, 2, "B"),
                segment(2, 1.5, 2.5, "C"), segment(3, 2.5, 3, "B")]
        result = confirmed_overlap(rows)
        self.assertEqual(result[1][1], ("A", "B", "C"))
        self.assertEqual((result[1][0].start, result[1][0].end), (1.5, 2.0))

    def test_rapid_a_b_a_switch(self) -> None:
        rows = [segment(0, 0, 2, "A"), segment(1, 2, 2.3, "B"), segment(2, 2.3, 4, "A")]
        issues = [kind for c in temporal_candidates(rows, QualityConfig()) for kind in c.issue_types]
        self.assertIn("rapid_a_b_a_switch", issues)


class AnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audio = self.root / "vocals.wav"
        sf.write(self.audio, np.zeros(16000 * 5, dtype=np.float32), 16000)
        self.diarization = self.root / "diarization.json"
        self.output = self.root / "quality"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_segments(self, rows: list[dict]) -> None:
        self.diarization.write_text(json.dumps({"segments": rows}), encoding="utf-8")

    def analyze(self, **kwargs):
        return analyze_source(source_id="source_001", audio_path=self.audio,
            diarization_path=self.diarization, output_dir=self.output,
            config=QualityConfig(), **kwargs)

    def test_empty_diarization_and_unavailable_features(self) -> None:
        self.write_segments([])
        summary = self.analyze(export_clips=False)
        self.assertEqual(summary["candidate_count"], 0)
        self.assertFalse(summary["feature_availability"]["speaker_embeddings"])
        self.assertFalse(summary["feature_availability"]["segmentation_uncertainty"])
        self.assertTrue((self.output / "suspicious_segments.csv").is_file())

    def test_single_speaker_and_serialization(self) -> None:
        self.write_segments([{"start": 0, "end": .2, "speaker": "A"}])
        summary = self.analyze(export_clips=False)
        self.assertEqual(summary["speaker_count"], 1)
        rows = json.loads((self.output / "suspicious_segments.json").read_text())
        self.assertEqual(rows[0]["issue_types"], ["short_turn"])
        with (self.output / "suspicious_segments.csv").open(newline="") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 1)

    def test_rttm_input_and_review_clip_sample_mapping(self) -> None:
        rttm = self.root / "diarization.rttm"
        rttm.write_text("SPEAKER source_001 1 1.000 0.200 <NA> <NA> A <NA> <NA>\n")
        summary = analyze_source(source_id="source_001", audio_path=self.audio,
            diarization_path=rttm, output_dir=self.output, config=QualityConfig(), top_k=1)
        self.assertEqual(summary["candidate_count"], 1)
        clips = list((self.output / "review_clips").glob("*.wav"))
        self.assertEqual(len(clips), 1)
        self.assertEqual(sf.info(clips[0]).frames, 19200)  # 0.5 s padding on both sides

    def test_frame_activity_and_independent_vad(self) -> None:
        self.write_segments([{"start": 1, "end": 2, "speaker": "A"}])
        features = self.root / "features.json"
        features.write_text(json.dumps({"activity_source": "external-adapter", "timebase": "global_seconds",
            "speaker_label_space": "final_diarization", "vad_source": "independent",
            "activity_frames": [{"start": 1.2, "end": 1.4, "activities": {"A": .8, "B": .7}}],
            "independent_vad": [{"start": 0, "end": 2.5}]}))
        summary = self.analyze(features_path=features, export_clips=False)
        self.assertTrue(summary["feature_availability"]["missed_overlap_evidence"])
        issues = {issue for row in json.loads((self.output / "suspicious_segments.json").read_text())
                  for issue in row["issue_types"]}
        self.assertIn("missed_overlap_candidate", issues)
        self.assertIn("missed_speech_candidate", issues)

    def test_false_speech_candidate_from_independent_vad(self) -> None:
        self.write_segments([{"start": 1, "end": 2, "speaker": "A"}])
        features = self.root / "features.json"
        features.write_text(json.dumps({"vad_source": "independent", "independent_vad": [
            {"start": 1, "end": 1.3}]}))
        self.analyze(features_path=features, export_clips=False)
        issues = {issue for row in json.loads((self.output / "suspicious_segments.json").read_text())
                  for issue in row["issue_types"]}
        self.assertIn("false_speech_candidate", issues)

    def test_missing_evidence_does_not_fabricate_candidates(self) -> None:
        self.write_segments([{"start": 1, "end": 2, "speaker": "A"}])
        summary = self.analyze(export_clips=False)
        self.assertFalse(summary["feature_availability"]["missed_overlap_evidence"])
        self.assertFalse(summary["feature_availability"]["independent_speech_activity"])

    def test_replaceable_evidence_adapter(self) -> None:
        self.write_segments([{"start": 1, "end": 2, "speaker": "A"}])

        class MockEvidence:
            def segment_embeddings(self):
                return {}

            def activity_frames(self):
                return [ActivityFrame(1.1, 1.3, {"A": .9, "B": .8})]

            def independent_vad(self):
                return [Interval(0, 2)]

        summary = self.analyze(evidence_adapter=MockEvidence(), export_clips=False)
        self.assertTrue(summary["feature_availability"]["missed_overlap_evidence"])
        self.assertTrue(summary["feature_availability"]["independent_speech_activity"])

    def test_overwrite_and_existing_output(self) -> None:
        self.write_segments([{"start": 1, "end": 1.2, "speaker": "A"}])
        self.analyze()
        with self.assertRaises(FileExistsError):
            self.analyze()
        self.write_segments([])
        self.analyze(overwrite=True)
        self.assertFalse(list((self.output / "review_clips").glob("*.wav")))

    def test_reference_metrics(self) -> None:
        self.write_segments([{"start": 0, "end": 1, "speaker": "A"}])
        rttm = self.root / "reference.rttm"
        rttm.write_text("SPEAKER source_001 1 0.000 1.000 <NA> <NA> X <NA> <NA>\n")
        result = self.analyze(reference_rttm=rttm, export_clips=False)
        self.assertAlmostEqual(result["ground_truth_evaluation"]["der"], 0.0)

    def test_cli_analysis_keeps_existing_diarization(self) -> None:
        data_root = self.root / "data"
        target = data_root / "speakers/speaker_001/diarization/source_001"
        target.mkdir(parents=True)
        vocals = data_root / "speakers/speaker_001/separated/source_001/vocals.wav"
        vocals.parent.mkdir(parents=True)
        vocals.write_bytes(self.audio.read_bytes())
        target.joinpath("diarization.json").write_text(json.dumps({"segments": [
            {"start": 0, "end": .2, "speaker": "A"}]}))
        before = target.joinpath("diarization.json").read_bytes()
        result = main(["--data-root", str(data_root), "analyze-diarization",
                       "--speaker-id", "speaker_001", "--source-id", "source_001", "--top-k", "1"])
        self.assertEqual(result, 0)
        self.assertEqual(target.joinpath("diarization.json").read_bytes(), before)
        self.assertTrue(target.joinpath("quality/quality_summary.json").is_file())

    def test_existing_cli_commands_still_parse(self) -> None:
        parser = build_parser()
        for command in ("convert", "separate", "diarize"):
            args = parser.parse_args([command, "--speaker-id", "speaker_001",
                                      "--source-id", "source_001"])
            self.assertEqual(args.command, command)
        diarize = parser.parse_args(["diarize", "--speaker-id", "speaker_001",
                                     "--source-id", "source_001"])
        self.assertIsNone(diarize.num_speakers)


if __name__ == "__main__":
    unittest.main()
