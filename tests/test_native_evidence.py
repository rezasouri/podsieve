from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from src.diarization.evidence import audio_features, mapped_activity, robust_prototypes, save_evidence, validate_evidence
from src.diarization.quality.saved_evidence import SavedEvidenceAdapter
from src.diarization.quality.scoring import rank_candidates
from src.diarization.quality.schemas import ActivityFrame, Candidate, QualityConfig, Segment
from src.diarization.quality.segmentation import activity_candidates
from src.diarization.quality.overlap_review import export_overlap_review


class EvidenceTests(unittest.TestCase):
    def test_local_channel_mapping_changes_per_chunk(self) -> None:
        arrays = {
            "segmentation": np.array([[[.9, .1]], [[.1, .9]]], dtype=np.float32),
            "effective_cluster_assignments": np.array([[0, 1], [1, 0]]),
        }
        meta = {"speaker_labels": ["A", "B"], "cluster_to_speaker": {"0": "A", "1": "B"},
                "windows": {"segmentation": {"start": 0., "duration": 1., "step": 1.},
                            "segmentation_frames": {"start": 0., "duration": 1., "step": 1.}}}
        activity = mapped_activity(arrays, meta, 2., resolution=1.)
        self.assertAlmostEqual(float(activity[0, 0]), .9)
        self.assertAlmostEqual(float(activity[1, 0]), .9)

    def test_prototype_excludes_insufficient_speaker(self) -> None:
        vectors = np.array([[1., 0.], [.9, .1], [0., 1.]], dtype=np.float32)
        segments = [{"speaker": "A"}, {"speaker": "A"}, {"speaker": "B"}]
        prototypes, counts = robust_prototypes(vectors, segments, np.ones(3), ["A", "B"])
        self.assertEqual(counts.tolist(), [2, 0])
        self.assertTrue(np.isnan(prototypes[1]).all())

    def test_configured_weights_affect_single_evidence_ranking(self) -> None:
        strong = Candidate(0, 1, "A", "B", ["speaker_confusion_candidate"],
                           feature_scores={"speaker_margin": .7}, evidence_available=["speaker_embeddings"])
        weak = Candidate(1, 2, "A", None, ["short_turn"],
                         feature_scores={"short_turn": .7}, evidence_available=["diarization_timing"])
        ranked = rank_candidates([weak, strong], QualityConfig())
        self.assertGreater(strong.review_score, weak.review_score)
        self.assertEqual(ranked[0], strong)

    def test_spurious_overlap_uses_mapped_activity(self) -> None:
        segments = [Segment(0, 1, "A", 0), Segment(.2, .8, "B", 1)]
        frames = [ActivityFrame(.3, .6, {"A": .9, "B": .1})]
        candidates = activity_candidates(segments, frames, QualityConfig(), include_boundaries=False)
        self.assertIn("spurious_overlap_candidate", candidates[0].issue_types)

    def test_original_vocals_energy_comparison_is_timestamp_aligned(self) -> None:
        import torch

        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.wav"
            sf.write(original, np.ones(16000, dtype=np.float32) * .5, 16000)
            vocals = {"waveform": torch.full((1, 16000), .25), "sample_rate": 16000}
            features = audio_features(vocals, [{"start": 0., "end": 1.}], original_audio_path=original)
            self.assertAlmostEqual(float(features["vocals_to_original_rms_ratio"][0]), .5, places=3)

    def test_overlap_review_exports_low_score_candidates_and_clips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "vocals.wav"
            sf.write(audio, np.zeros(2 * 16000, dtype=np.float32), 16000)
            candidates = [
                Candidate(.2, .5, None, None, ["confirmed_output_overlap"],
                          features={"speakers": ["A", "B"]}, review_score=.1,
                          evidence_available=["diarization_annotation"]),
                Candidate(1., 1.4, "A", "B", ["missed_overlap_candidate"],
                          features={"active_speakers": ["A", "B"]}, review_score=.05,
                          evidence_available=["frame_activity"]),
            ]
            summary = export_overlap_review(audio, root / "overlap_review", candidates,
                                            QualityConfig(), audio_duration=2.)
            rows = json.loads((root / "overlap_review/overlap_candidates.json").read_text())
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(list((root / "overlap_review/clips").glob("*.wav"))), 2)
            self.assertFalse(summary["thresholds"]["score_minimum_applied"])

    def test_manifest_integrity_and_audio_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "audio.wav"
            annotation = root / "diarization.json"
            sf.write(audio, np.zeros(1600), 16000)
            annotation.write_text("{}")
            evidence = root / "evidence"
            arrays = {"segmentation": np.zeros((1, 1, 1)), "local_binary_activity": np.zeros((1, 1, 1)),
                      "speaker_count": np.zeros((1, 1)), "speaker_activity": np.zeros((1, 1)),
                      "chunk_embeddings": np.zeros((1, 1, 2)), "cluster_assignments": np.zeros((1, 1)),
                      "effective_cluster_assignments": np.zeros((1, 1)), "cluster_scores": np.zeros((1, 1, 1)),
                      "cluster_centroids": np.zeros((1, 2)), "final_centroids": np.zeros((1, 2)),
                      "mapped_activity": np.zeros((1, 1)), "segment_embeddings": np.zeros((1, 2)),
                      "segment_embedding_clean_seconds": np.zeros(1), "segment_embedding_status": np.zeros(1),
                      "speaker_prototypes": np.zeros((1, 2)), "speaker_prototype_reference_counts": np.zeros(1),
                      "speaker_prototype_similarity": np.zeros((1, 1)), "independent_vad": np.empty((0, 2)),
                      "segment_rms": np.zeros(1), "segment_clipping_fraction": np.zeros(1)}
            save_evidence(evidence, arrays, {"speaker_labels": ["A"]},
                          audio_path=audio, annotation_path=annotation, overwrite=False)
            self.assertEqual(validate_evidence(evidence, audio_path=audio, annotation_path=annotation)["state"], "complete")
            with (evidence / "segmentation.npy").open("ab") as stream:
                stream.write(b"damage")
            with self.assertRaisesRegex(ValueError, "corrupt evidence"):
                validate_evidence(evidence, audio_path=audio, annotation_path=annotation)
            save_evidence(evidence, arrays, {"speaker_labels": ["A"]},
                          audio_path=audio, annotation_path=annotation, overwrite=True)
            sf.write(audio, np.ones(1600), 16000)
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_evidence(evidence, audio_path=audio, annotation_path=annotation)

    def test_saved_evidence_real_integration_if_present(self) -> None:
        root = Path("/tmp/podsieve-integration-two-speaker")
        audio = Path("/tmp/podsieve-integration-two-speaker.wav")
        if not (root / "evidence/manifest.json").is_file():
            self.skipTest("real model integration output is absent")
        adapter = SavedEvidenceAdapter(root / "evidence", audio_path=audio,
                                       annotation_path=root / "diarization.json")
        self.assertGreater(len(adapter.segment_embeddings()), 0)
        self.assertEqual(len(adapter.activity_frames()), 700)
        self.assertGreater(len(adapter.independent_vad()), 0)


@unittest.skipUnless(os.environ.get("PODSIEVE_NATIVE_EVIDENCE_INTEGRATION") == "1", "opt-in native model integration")
class NativeModelIntegration(unittest.TestCase):
    def test_real_source_excerpt_end_to_end(self) -> None:
        from dotenv import load_dotenv
        from src.diarization.runner import diarize_audio

        load_dotenv(".env")
        source = Path("data/speakers/speaker_001/separated/source_001/vocals.wav")
        if not source.is_file():
            self.skipTest("source_001 vocals are absent")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "vocals.wav"
            with sf.SoundFile(source) as stream:
                stream.seek(round(200 * stream.samplerate))
                samples = stream.read(round(30 * stream.samplerate), dtype="float32", always_2d=True)
                rate = stream.samplerate
            sf.write(audio, samples, rate)
            result = diarize_audio(audio, root / "diarization.rttm", root / "diarization.json",
                                   root / "segments", source_id="source_001_excerpt", num_speakers=2,
                                   save_segments=False, cache_dir=Path("checkpoints/huggingface").resolve())
            adapter = SavedEvidenceAdapter(result["evidence_dir"], audio_path=audio,
                                           annotation_path=root / "diarization.json")
            self.assertGreater(len(adapter.segment_embeddings()), 0)
            self.assertTrue((result["quality_dir"] / "quality_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
