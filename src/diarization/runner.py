from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .audio import load_audio_for_pyannote
from .evidence import PyannoteEvidenceCapture, audio_features, extract_segment_embeddings, independent_vad, mapped_activity, robust_prototypes, save_evidence
from .finalize import publish_clean_segments
from .pyannote_io import extract_annotation, segments_from_annotation
from .quality import QualityConfig, analyze_source
from .quality.saved_evidence import SavedEvidenceAdapter
from .writers import (
    DEFAULT_MIN_SEGMENT_DURATION_SEC,
    DEFAULT_SEGMENT_FADE_SEC,
    DEFAULT_SEGMENT_PADDING_SEC,
    write_json,
    write_rttm,
    write_segment_wavs,
)
from ..core.errors import StageError
from ..core.files import ensure_outputs_available


LOGGER = logging.getLogger(__name__)


def diarize_audio(
    input_file: Path,
    rttm_output: Path,
    json_output: Path,
    segments_dir: Path,
    *,
    source_id: str,
    model: str = "pyannote/speaker-diarization-3.1",
    token_env: str = "HF_TOKEN",
    target_sample_rate: int = 16000,
    device: str | None = None,
    save_json: bool = True,
    save_segments: bool = True,
    segment_padding_sec: float = DEFAULT_SEGMENT_PADDING_SEC,
    segment_fade_sec: float = DEFAULT_SEGMENT_FADE_SEC,
    segment_min_duration_sec: float = DEFAULT_MIN_SEGMENT_DURATION_SEC,
    cache_dir: Path | None = None,
    num_speakers: int | None = None,
    overwrite: bool = False,
    save_native_evidence: bool = True,
    quality_analysis: bool = True,
    quality_config: QualityConfig | None = None,
    original_audio_path: Path | None = None,
) -> dict[str, Any]:
    """Run pyannote diarization and save RTTM, JSON, and speaker-turn WAVs."""
    stage = "diarization"
    if quality_analysis and not save_native_evidence:
        raise StageError(stage, "quality analysis requires saved evidence; also pass --no-quality-analysis")

    if not input_file.is_file():
        raise StageError(stage, f"input vocals audio does not exist: {input_file}")

    expected = [rttm_output]
    if save_json:
        expected.append(json_output)
    ensure_outputs_available(expected, overwrite, stage)

    existing_segments = list(segments_dir.rglob("*.wav")) if segments_dir.exists() else []
    if save_segments and existing_segments and not overwrite:
        raise StageError(
            stage,
            f"final segment outputs already exist in {segments_dir}. Pass --overwrite to replace them.",
        )

    # Set the Hugging Face cache before importing pyannote/huggingface_hub.
    # Respect an explicit HF_HOME from the caller; otherwise keep model files
    # inside this project's checkpoints directory by default.
    default_cache_dir = cache_dir or Path("checkpoints/huggingface")
    os.environ.setdefault("HF_HOME", str(default_cache_dir.expanduser().resolve()))

    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise StageError(stage, f"missing diarization dependency: {exc.name}") from exc

    selected_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    if selected_device == "cuda" and not torch.cuda.is_available():
        raise StageError(stage, "CUDA was requested but torch.cuda.is_available() is false")
    if selected_device not in {"cuda", "cpu"}:
        raise StageError(stage, f"unsupported device: {selected_device}")

    LOGGER.info("stage=%s model=%s device=%s", stage, model, selected_device)

    token = os.environ.get(token_env) or os.environ.get("HUGGINGFACE_TOKEN")
    load_args: dict[str, Any] = {}
    if token:
        load_args["token"] = token

    try:
        pipeline = Pipeline.from_pretrained(model, **load_args)
    except Exception as exc:
        raise StageError(
            stage,
            f"could not load pyannote model '{model}': check your token first",
        ) from exc
    if pipeline is None:
        raise StageError(stage, f"pyannote returned no pipeline for model '{model}'")
    pipeline.to(torch.device(selected_device))

    try:
        audio = load_audio_for_pyannote(input_file, target_sr=target_sample_rate)
    except Exception as exc:
        if isinstance(exc, StageError):
            raise
        raise StageError(stage, f"could not load audio {input_file}: {exc}") from exc

    audio["uri"] = source_id
    duration = audio["waveform"].shape[-1] / audio["sample_rate"]
    LOGGER.info(
        "stage=%s loaded_audio=%s duration=%.2f sample_rate=%s",
        stage,
        input_file,
        duration,
        audio["sample_rate"],
    )

    capture = PyannoteEvidenceCapture(pipeline) if save_native_evidence else None
    try:
        result = capture.run(audio, num_speakers) if capture is not None else (
            pipeline(audio, num_speakers=num_speakers) if num_speakers is not None else pipeline(audio)
        )
    except Exception as exc:
        raise StageError(stage, f"pyannote failed for {input_file}: {exc}") from exc

    annotation = extract_annotation(result)
    annotation.uri = source_id
    segment_data = segments_from_annotation(annotation)

    rttm_output.parent.mkdir(parents=True, exist_ok=True)
    write_rttm(annotation, rttm_output)

    if save_json:
        write_json(
            segment_data,
            json_output,
            source_id=source_id,
            input_file=input_file,
        )

    source_dir = rttm_output.parent.parent
    evidence_dir = source_dir / "diagnostics" / "evidence"
    quality_dir = source_dir / "diagnostics" / "quality"
    if capture is not None:
        try:
            from importlib.metadata import version

            arrays, metadata = capture.arrays(result)
            vectors, clean_seconds, extraction_status = extract_segment_embeddings(pipeline, audio, segment_data)
            arrays["segment_embeddings"] = vectors
            arrays["segment_embedding_clean_seconds"] = clean_seconds
            arrays["segment_embedding_status"] = extraction_status
            prototypes, prototype_counts = robust_prototypes(vectors, segment_data, clean_seconds, metadata["speaker_labels"])
            arrays["speaker_prototypes"] = prototypes
            arrays["speaker_prototype_reference_counts"] = prototype_counts
            prototype_similarity = np.full((len(prototypes), len(prototypes)), np.nan, dtype=np.float32)
            for i, left in enumerate(prototypes):
                for j, right in enumerate(prototypes):
                    if np.all(np.isfinite(left)) and np.all(np.isfinite(right)):
                        prototype_similarity[i, j] = float(left @ right)
            arrays["speaker_prototype_similarity"] = prototype_similarity
            arrays.update(audio_features(audio, segment_data, original_audio_path=original_audio_path))
            vad, vad_metadata = independent_vad(audio)
            arrays["independent_vad"] = vad
            arrays["mapped_activity"] = mapped_activity(arrays, metadata, duration)
            metadata.update({
                "model": model,
                "pyannote_audio_version": version("pyannote.audio"),
                "audio_duration_seconds": duration,
                "inference_sample_rate": audio["sample_rate"],
                "num_speakers_requested": num_speakers,
                "pipeline_parameters": pipeline.parameters(instantiated=True),
                "mapped_activity_resolution": 0.1,
                "segment_embedding_model": str(getattr(pipeline, "embedding", "pipeline embedding")),
                "segment_embedding_min_seconds": 0.8,
                "segment_embedding_status_codes": {"0": "extracted", "1": "fully overlapped", "2": "insufficient clean duration", "3": "invalid embedding"},
                "independent_vad": vad_metadata,
                "original_audio": ({"path": str(original_audio_path.resolve()),
                                    "size": original_audio_path.stat().st_size,
                                    "mtime_ns": original_audio_path.stat().st_mtime_ns}
                                   if original_audio_path is not None and original_audio_path.is_file() else None),
            })
            if cache_dir is not None and model.count("/") == 1:
                model_ref = cache_dir / "hub" / ("models--" + model.replace("/", "--")) / "refs" / "main"
                if model_ref.is_file():
                    metadata["model_revision"] = model_ref.read_text(encoding="utf-8").strip()
                config_path = cache_dir / "hub" / ("models--" + model.replace("/", "--")) / "snapshots" / metadata.get("model_revision", "") / "config.yaml"
                if config_path.is_file():
                    import yaml

                    model_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                    components = {}
                    for key in ("segmentation", "embedding"):
                        identifier = model_config.get("pipeline", {}).get("params", {}).get(key)
                        if isinstance(identifier, str):
                            ref = cache_dir / "hub" / ("models--" + identifier.replace("/", "--")) / "refs" / "main"
                            components[key] = {"model": identifier,
                                               "revision": ref.read_text(encoding="utf-8").strip() if ref.is_file() else None}
                    metadata["model_components"] = components
            save_evidence(evidence_dir, arrays, metadata, audio_path=input_file,
                          annotation_path=json_output if save_json else rttm_output, overwrite=overwrite)
        except Exception as exc:
            raise StageError(stage, f"evidence extraction failed: {exc}") from exc
    del audio

    segment_files: list[Path] = []
    if save_segments or quality_analysis:
        with tempfile.TemporaryDirectory(
            prefix=".diarization-segments-building-", dir=rttm_output.parent
        ) as temporary_dir:
            temporary_segments_dir = Path(temporary_dir) / "segments"
            if save_segments:
                segment_files = write_segment_wavs(
                    input_file,
                    annotation,
                    temporary_segments_dir,
                    padding_sec=segment_padding_sec,
                    fade_sec=segment_fade_sec,
                    min_duration_sec=segment_min_duration_sec,
                )

            if quality_analysis:
                if capture is None:
                    raise StageError(stage, "quality analysis requires native evidence")
                try:
                    annotation_path = json_output if save_json else rttm_output
                    adapter = SavedEvidenceAdapter(evidence_dir, audio_path=input_file, annotation_path=annotation_path)
                    analyze_source(source_id=source_id, audio_path=input_file,
                                   diarization_path=annotation_path, output_dir=quality_dir,
                                   config=quality_config or QualityConfig(), evidence_adapter=adapter,
                                   overwrite=overwrite, configured_backend=model)
                except Exception as exc:
                    raise StageError(stage, f"automatic quality analysis failed: {exc}") from exc

            if save_segments:
                try:
                    manifest = publish_clean_segments(
                        source_id=source_id,
                        temporary_segments_dir=temporary_segments_dir,
                        segments=segment_data,
                        quality_dir=quality_dir,
                        final_dir=segments_dir.parent,
                        padding_seconds=segment_padding_sec,
                        overwrite=overwrite,
                        quality_analysis=quality_analysis,
                    )
                    LOGGER.info(
                        "stage=%s final_segments=%d excluded=%d",
                        stage,
                        manifest["published_segment_count"],
                        manifest["excluded_by_quality_review_count"],
                    )
                    segment_files = list(segments_dir.rglob("*.wav"))
                except Exception as exc:
                    raise StageError(stage, f"could not publish final segments: {exc}") from exc

    return {
        "rttm": rttm_output.resolve(),
        "json": json_output.resolve() if save_json else None,
        "segments_dir": segments_dir.resolve() if save_segments else None,
        "segment_count": len(segment_files) if save_segments else len(segment_data),
        "speaker_count": len(annotation.labels()),
        "evidence_dir": evidence_dir.resolve() if capture is not None else None,
        "quality_dir": quality_dir.resolve() if quality_analysis else None,
    }
