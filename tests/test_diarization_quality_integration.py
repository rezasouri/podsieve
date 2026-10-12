"""Opt-in real-model smoke test. Requires previously cached model weights."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf


@unittest.skipUnless(os.environ.get("PODSIEVE_PYANNOTE_INTEGRATION") == "1", "opt-in model integration")
class CachedPyannoteIntegrationTest(unittest.TestCase):
    def test_cached_pipeline_on_short_audio(self) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[1] / "checkpoints/huggingface"))
        from pyannote.audio import Pipeline
        from src.diarization.audio import load_audio_for_pyannote
        from src.diarization.pyannote_io import extract_annotation

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "silence.wav"
            sf.write(path, np.zeros(16000, dtype=np.float32), 16000)
            pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
            if pipeline is None:
                self.skipTest("model weights are not cached")
            audio = load_audio_for_pyannote(path)
            audio["uri"] = "integration"
            result = pipeline(audio)
            self.assertTrue(hasattr(extract_annotation(result), "itertracks"))
