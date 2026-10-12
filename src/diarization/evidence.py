"""Version-checked capture and persistence of pyannote 4 speaker diarization evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


FORMAT_VERSION = 1
REQUIRED_ARRAYS = {
    "segmentation", "local_binary_activity", "speaker_count", "speaker_activity",
    "chunk_embeddings", "cluster_assignments", "effective_cluster_assignments",
    "cluster_scores", "cluster_centroids", "final_centroids", "mapped_activity",
    "segment_embeddings", "segment_embedding_clean_seconds", "segment_embedding_status",
    "speaker_prototypes", "speaker_prototype_reference_counts",
    "speaker_prototype_similarity", "independent_vad", "segment_rms",
    "segment_clipping_fraction",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class CapturedClustering:
    """Delegate once to the original clustering pipeline and retain its exact outputs.

    pyannote 4.0.1 has no clustering hook. This narrow instance wrapper is
    installed only for a single inference call, then restored in ``finally``.
    """

    def __init__(self, original: Any):
        self.original = original
        self.hard: np.ndarray | None = None
        self.soft: np.ndarray | None = None
        self.centroids: np.ndarray | None = None

    def __call__(self, *args: Any, **kwargs: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        hard, soft, centroids = self.original(*args, **kwargs)
        self.hard = np.array(hard, copy=True)
        self.soft = np.array(soft, copy=True)
        self.centroids = None if centroids is None else np.array(centroids, copy=True)
        return hard, soft, centroids


class PyannoteEvidenceCapture:
    def __init__(self, pipeline: Any):
        from pyannote.audio.pipelines.speaker_diarization import SpeakerDiarization

        installed = version("pyannote.audio")
        if installed != "4.0.1" or not isinstance(pipeline, SpeakerDiarization):
            raise RuntimeError(f"evidence adapter supports SpeakerDiarization in pyannote.audio 4.0.1; found {installed}, {type(pipeline).__name__}")
        self.pipeline = pipeline
        self.clustering = CapturedClustering(pipeline.clustering)
        self.artifacts: dict[str, Any] = {}

    def hook(self, step: str, artifact: Any, **kwargs: Any) -> None:
        if kwargs.get("completed") is not None or artifact is None:
            return
        if step == "speaker_counting":
            from pyannote.core import SlidingWindowFeature

            # apply() later overwrites count.data with its exclusive (<=1)
            # version. Preserve the original overlap-aware speaker count here.
            self.artifacts[step] = SlidingWindowFeature(np.array(artifact.data, copy=True), artifact.sliding_window)
        elif step in {"segmentation", "embeddings", "discrete_diarization"}:
            self.artifacts[step] = artifact

    def run(self, audio: dict[str, Any], num_speakers: int | None) -> Any:
        original = self.pipeline.clustering
        self.pipeline.clustering = self.clustering
        try:
            if num_speakers is None:
                return self.pipeline(audio, hook=self.hook)
            return self.pipeline(audio, num_speakers=num_speakers, hook=self.hook)
        finally:
            self.pipeline.clustering = original

    def arrays(self, result: Any) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        missing = {"segmentation", "speaker_counting", "embeddings", "discrete_diarization"} - self.artifacts.keys()
        if not result.speaker_diarization.labels() and missing == {"embeddings", "discrete_diarization"}:
            seg = self.artifacts["segmentation"]
            count = self.artifacts["speaker_counting"]
            dimension = int(self.pipeline._embedding.dimension)
            chunks, frames, channels = seg.data.shape
            arrays = {"segmentation": np.asarray(seg.data),
                      "local_binary_activity": np.zeros((chunks, frames, channels), dtype=np.uint8),
                      "speaker_count": np.asarray(count.data),
                      "speaker_activity": np.zeros((len(count.data), 0), dtype=np.uint8),
                      "chunk_embeddings": np.empty((chunks, channels, dimension), dtype=np.float32),
                      "cluster_assignments": np.full((chunks, channels), -2, dtype=np.int8),
                      "effective_cluster_assignments": np.full((chunks, channels), -2, dtype=np.int8),
                      "cluster_scores": np.empty((chunks, channels, 0), dtype=np.float32),
                      "cluster_centroids": np.empty((0, dimension), dtype=np.float32),
                      "final_centroids": np.empty((0, dimension), dtype=np.float32)}
            meta = {"windows": {"segmentation": window_dict(seg.sliding_window),
                                "segmentation_frames": window_dict(self.pipeline._segmentation.model.receptive_field),
                                "speaker_count": window_dict(count.sliding_window),
                                "speaker_activity": window_dict(count.sliding_window)},
                    "speaker_labels": [], "cluster_to_speaker": {},
                    "cluster_metric": getattr(self.pipeline.clustering, "metric", "unknown"),
                    "segmentation_powerset": bool(self.pipeline._segmentation.model.specifications.powerset),
                    "segmentation_output_kind": ("decoded_local_speaker_activity" if self.pipeline._segmentation.model.specifications.powerset
                                                 else "local_speaker_scores"),
                    "segmentation_classes": [str(c) for c in getattr(self.pipeline._segmentation.model.specifications, "classes", [])]}
            return arrays, meta
        if missing:
            raise ValueError(f"pyannote evidence hook omitted: {sorted(missing)}")
        if self.clustering.hard is None or self.clustering.soft is None or self.clustering.centroids is None:
            raise ValueError("pyannote clustering outputs unavailable")
        seg = self.artifacts["segmentation"]
        count = self.artifacts["speaker_counting"]
        discrete = self.artifacts["discrete_diarization"]
        embeddings = np.asarray(self.artifacts["embeddings"])
        hard = self.clustering.hard
        soft = self.clustering.soft
        centroids = self.clustering.centroids
        if seg.data.ndim != 3 or embeddings.shape[:2] != seg.data.shape[::2] or hard.shape != embeddings.shape[:2]:
            raise ValueError("segmentation, embeddings, and clustering axes disagree")
        if soft.shape[:2] != hard.shape or soft.shape[2] != centroids.shape[0]:
            raise ValueError("soft assignment and centroid axes disagree")
        labels = result.speaker_diarization.labels()
        ordered = np.asarray(result.speaker_embeddings)
        if ordered.ndim != 2 or ordered.shape[0] != len(labels):
            raise ValueError("final speaker centroid labels disagree")
        # Pipeline applies inactive=-2 after clustering; reproduce that exact
        # mutation from its binarized local segmentations.
        if self.pipeline._segmentation.model.specifications.powerset:
            binary = np.asarray(seg.data) > 0
        else:
            from pyannote.audio.utils.signal import binarize
            binary = binarize(seg, onset=self.pipeline.segmentation.threshold, initial_state=False).data > 0
        effective = hard.copy()
        effective[np.sum(binary, axis=1) == 0] = -2
        # The output labels and centroids are jointly ordered by pyannote.
        # Find the corresponding original centroid row, rejecting ambiguous ties.
        mapping: dict[int, str] = {}
        used: set[int] = set()
        for label, vector in zip(labels, ordered):
            matches = [i for i, centroid in enumerate(centroids) if i not in used and np.allclose(vector, centroid, rtol=1e-5, atol=1e-6)]
            if len(matches) != 1:
                raise ValueError(f"cannot uniquely map cluster centroid to final label {label}")
            mapping[matches[0]] = str(label)
            used.add(matches[0])
        arrays = {
            "segmentation": np.asarray(seg.data),
            "local_binary_activity": np.asarray(binary, dtype=np.uint8),
            "speaker_count": np.asarray(count.data),
            "speaker_activity": np.asarray(discrete.data),
            "chunk_embeddings": embeddings,
            "cluster_assignments": hard,
            "effective_cluster_assignments": effective,
            "cluster_scores": soft,
            "cluster_centroids": centroids,
            "final_centroids": ordered,
        }
        meta = {
            "windows": {"segmentation": window_dict(seg.sliding_window), "segmentation_frames": window_dict(self.pipeline._segmentation.model.receptive_field), "speaker_count": window_dict(count.sliding_window), "speaker_activity": window_dict(discrete.sliding_window)},
            "speaker_labels": [str(label) for label in labels],
            "cluster_to_speaker": {str(k): v for k, v in mapping.items()},
            "cluster_metric": getattr(self.pipeline.clustering, "metric", "unknown"),
            "segmentation_powerset": bool(self.pipeline._segmentation.model.specifications.powerset),
            "segmentation_output_kind": ("decoded_local_speaker_activity" if self.pipeline._segmentation.model.specifications.powerset
                                         else "local_speaker_scores"),
            "segmentation_classes": [str(c) for c in getattr(self.pipeline._segmentation.model.specifications, "classes", [])],
        }
        return arrays, meta


def mapped_activity(arrays: dict[str, np.ndarray], metadata: dict[str, Any], duration: float, resolution: float = 0.1) -> np.ndarray:
    """Aggregate local segmentation activity into global speaker bins.

    Each local channel is mapped through the exact cluster assignment from its
    own chunk. Multiple windows contribute by averaging, never by treating a
    local channel number as a persistent speaker identity.
    """
    labels = metadata["speaker_labels"]
    label_to_index = {label: i for i, label in enumerate(labels)}
    bins = int(np.ceil(duration / resolution))
    total = np.zeros((bins, len(labels)), dtype=np.float64)
    counts = np.zeros((bins, len(labels)), dtype=np.uint32)
    local = arrays["segmentation"]
    clusters = arrays["effective_cluster_assignments"]
    chunk_window = metadata["windows"]["segmentation"]
    frame_window = metadata["windows"]["segmentation_frames"]
    mapping = metadata["cluster_to_speaker"]
    for chunk in range(local.shape[0]):
        chunk_start = chunk_window["start"] + chunk * chunk_window["step"]
        for frame in range(local.shape[1]):
            center = chunk_start + frame_window["start"] + frame * frame_window["step"] + frame_window["duration"] / 2
            bucket = int(center / resolution)
            if bucket < 0 or bucket >= bins:
                continue
            for channel in range(local.shape[2]):
                label = mapping.get(str(int(clusters[chunk, channel])))
                if label is None:
                    continue
                activity = float(local[chunk, frame, channel])
                if np.isfinite(activity):
                    target = label_to_index[label]
                    total[bucket, target] += activity
                    counts[bucket, target] += 1
    return np.divide(total, counts, out=np.zeros_like(total), where=counts > 0).astype(np.float32)


def window_dict(window: Any) -> dict[str, float]:
    return {key: float(getattr(window, key)) for key in ("start", "duration", "step")}


def extract_segment_embeddings(pipeline: Any, audio: dict[str, Any], segments: list[dict[str, Any]], *, min_seconds: float = 0.8, max_seconds: float = 15.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Embed unpadded, non-overlapping segment interiors with the native model."""
    import torch

    waveform = audio["waveform"]
    sr = audio["sample_rate"]
    min_samples = max(int(min_seconds * sr), int(pipeline._embedding.min_num_samples))
    dimension = int(pipeline._embedding.dimension)
    vectors = np.full((len(segments), dimension), np.nan, dtype=np.float32)
    clean_seconds = np.zeros(len(segments), dtype=np.float32)
    status = np.zeros(len(segments), dtype=np.uint8)
    for i, segment in enumerate(segments):
        start, end = float(segment["start"]), float(segment["end"])
        # Any overlap contaminates the reference. Crop the longest clean run.
        cuts = [(start, end)]
        for other in segments:
            if other is segment or other["speaker"] == segment["speaker"]:
                continue
            left, right = max(start, float(other["start"])), min(end, float(other["end"]))
            if right <= left:
                continue
            cuts = [(a, b) for x, y in cuts for a, b in ((x, min(y, left)), (max(x, right), y)) if b > a]
        if not cuts:
            status[i] = 1
            continue
        a, b = max(cuts, key=lambda pair: pair[1] - pair[0])
        if (b - a) * sr < min_samples:
            status[i] = 2
            continue
        b = min(b, a + max_seconds)
        crop = waveform[:, round(a * sr):round(b * sr)]
        if crop.shape[-1] < min_samples:
            status[i] = 2
            continue
        with torch.inference_mode():
            vector = np.asarray(pipeline._embedding(crop.unsqueeze(0)))[0]
        if vector.shape != (dimension,) or not np.all(np.isfinite(vector)):
            status[i] = 3
            continue
        vectors[i] = vector
        clean_seconds[i] = crop.shape[-1] / sr
    return vectors, clean_seconds, status


def audio_features(audio: dict[str, Any], segments: list[dict[str, Any]], *, original_audio_path: Path | None = None) -> dict[str, np.ndarray]:
    waveform = audio["waveform"][0].numpy()
    sr = audio["sample_rate"]
    rms = np.zeros(len(segments), dtype=np.float32)
    clipping = np.zeros(len(segments), dtype=np.float32)
    for i, segment in enumerate(segments):
        crop = waveform[round(segment["start"] * sr):round(segment["end"] * sr)]
        if crop.size:
            rms[i] = np.sqrt(np.mean(crop.astype(np.float64) ** 2))
            clipping[i] = np.mean(np.abs(crop) >= 0.999)
    features = {"segment_rms": rms, "segment_clipping_fraction": clipping}
    if original_audio_path is not None and original_audio_path.is_file():
        original_rms = np.zeros(len(segments), dtype=np.float32)
        with sf.SoundFile(original_audio_path) as source:
            for i, segment in enumerate(segments):
                start = min(len(source), round(segment["start"] * source.samplerate))
                end = min(len(source), round(segment["end"] * source.samplerate))
                source.seek(start)
                samples = source.read(max(0, end - start), dtype="float32", always_2d=True)
                if samples.size:
                    original_rms[i] = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
        features["original_segment_rms"] = original_rms
        features["vocals_to_original_rms_ratio"] = np.divide(rms, original_rms,
            out=np.full_like(rms, np.nan), where=original_rms > 0)
    return features


def robust_prototypes(vectors: np.ndarray, segments: list[dict[str, Any]], clean_seconds: np.ndarray, labels: list[str], *, min_references: int = 2) -> tuple[np.ndarray, np.ndarray]:
    prototypes = np.full((len(labels), vectors.shape[1]), np.nan, dtype=np.float32)
    counts = np.zeros(len(labels), dtype=np.int32)
    for label_index, label in enumerate(labels):
        ids = [i for i, segment in enumerate(segments) if segment["speaker"] == label
               and clean_seconds[i] >= 0.8 and np.all(np.isfinite(vectors[i]))]
        if len(ids) < min_references:
            continue
        sample = vectors[ids].astype(np.float64)
        norm = np.linalg.norm(sample, axis=1)
        sample = sample[norm > 0] / norm[norm > 0, None]
        if len(sample) < min_references:
            continue
        centre = np.mean(sample, axis=0)
        centre /= np.linalg.norm(centre)
        similarities = sample @ centre
        keep = similarities >= np.quantile(similarities, 0.25) if len(sample) >= 4 else np.ones(len(sample), dtype=bool)
        prototype = np.mean(sample[keep], axis=0)
        prototype /= np.linalg.norm(prototype)
        prototypes[label_index] = prototype
        counts[label_index] = int(np.sum(keep))
    return prototypes, counts


def independent_vad(audio: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    from silero_vad import get_speech_timestamps, load_silero_vad

    model = load_silero_vad()
    waveform = audio["waveform"][0].cpu()
    sr = audio["sample_rate"]
    # Silero's timestamp helper streams internally; no additional full-wave copy.
    settings = {"threshold": 0.5, "min_speech_duration_ms": 250, "min_silence_duration_ms": 100, "speech_pad_ms": 30}
    spans = get_speech_timestamps(waveform, model, sampling_rate=sr, **settings)
    intervals = np.asarray([[s["start"] / sr, s["end"] / sr] for s in spans], dtype=np.float64).reshape(-1, 2)
    return intervals, {"model": "silero-vad", "version": version("silero-vad"), "settings": settings}


def save_evidence(path: Path, arrays: dict[str, np.ndarray], metadata: dict[str, Any], *, audio_path: Path, annotation_path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"evidence already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{path.name}-building-", dir=path.parent))
    try:
        files = {}
        for name, array in arrays.items():
            arr = np.asarray(array)
            if arr.dtype == object:
                raise ValueError(f"object array prohibited: {name}")
            target = staging / f"{name}.npy"
            np.save(target, arr, allow_pickle=False)
            digest = file_sha256(target)
            files[name] = {"file": target.name, "shape": list(arr.shape), "dtype": str(arr.dtype), "sha256": digest}
        info = sf.info(str(audio_path))
        annotation_digest = file_sha256(annotation_path)
        manifest = {"format_version": FORMAT_VERSION, "state": "complete", "files": files, "metadata": metadata,
                    "audio": {"path": str(audio_path.resolve()), "size": audio_path.stat().st_size, "mtime_ns": audio_path.stat().st_mtime_ns, "sample_rate": info.samplerate, "frames": info.frames},
                    "annotation": {"path": str(annotation_path.resolve()), "sha256": annotation_digest}}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_evidence(staging, audio_path=audio_path, annotation_path=annotation_path)
        if path.exists():
            shutil.rmtree(path)
        staging.rename(path)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def validate_evidence(path: Path, *, audio_path: Path, annotation_path: Path) -> dict[str, Any]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION or manifest.get("state") != "complete":
        raise ValueError("unsupported or incomplete evidence")
    missing = REQUIRED_ARRAYS - manifest["files"].keys()
    if missing:
        raise ValueError(f"incomplete evidence arrays: {sorted(missing)}")
    recorded_audio = manifest["audio"]
    if recorded_audio["size"] != audio_path.stat().st_size or recorded_audio["mtime_ns"] != audio_path.stat().st_mtime_ns:
        raise ValueError("evidence audio cache is stale")
    original = manifest["metadata"].get("original_audio")
    if original is not None:
        original_path = Path(original["path"])
        if not original_path.is_file() or original_path.stat().st_size != original["size"] or original_path.stat().st_mtime_ns != original["mtime_ns"]:
            raise ValueError("evidence original audio cache is stale")
    if manifest["annotation"]["sha256"] != file_sha256(annotation_path):
        raise ValueError("evidence annotation cache is stale")
    for name, spec in manifest["files"].items():
        target = path / spec["file"]
        if file_sha256(target) != spec["sha256"]:
            raise ValueError(f"corrupt evidence array: {name}")
        array = np.load(target, mmap_mode="r", allow_pickle=False)
        if list(array.shape) != spec["shape"] or str(array.dtype) != spec["dtype"]:
            raise ValueError(f"invalid evidence shape or dtype: {name}")
    shapes = {name: tuple(spec["shape"]) for name, spec in manifest["files"].items()}
    chunks, frames, channels = shapes["segmentation"]
    if shapes["local_binary_activity"] != (chunks, frames, channels):
        raise ValueError("local activity shape disagrees with segmentation")
    if shapes["chunk_embeddings"][:2] != (chunks, channels):
        raise ValueError("chunk embedding shape disagrees with segmentation")
    if shapes["cluster_assignments"] != (chunks, channels) or shapes["effective_cluster_assignments"] != (chunks, channels):
        raise ValueError("cluster assignment shape disagrees with segmentation")
    if shapes["cluster_scores"][:2] != (chunks, channels):
        raise ValueError("cluster score shape disagrees with segmentation")
    labels = manifest["metadata"]["speaker_labels"]
    if shapes["mapped_activity"][1:] != (len(labels),) or shapes["speaker_prototypes"][0] != len(labels):
        raise ValueError("global speaker axis disagrees with final labels")
    if shapes["segment_embeddings"][0] != shapes["segment_embedding_status"][0]:
        raise ValueError("segment embedding and status counts disagree")
    return manifest
