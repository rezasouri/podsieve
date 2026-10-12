from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from .analyzer import read_diarization
from .overlap import interval_overlap, union_intervals
from .schemas import Candidate, Interval, Segment


def _annotation(segments: Sequence[Segment]):
    from pyannote.core import Annotation, Segment as PySegment

    annotation = Annotation(uri="evaluation")
    for index, item in enumerate(segments):
        annotation[PySegment(item.start, item.end), index] = item.speaker
    return annotation


def _error_intervals(
    reference: Sequence[Segment], hypothesis: Sequence[Segment], collar: float, skip_overlap: bool
) -> list[Interval]:
    reference_labels = sorted({item.speaker for item in reference})
    hypothesis_labels = sorted({item.speaker for item in hypothesis})
    times = sorted({point for item in [*reference, *hypothesis] for point in (item.start, item.end)})
    if len(times) < 2:
        return []
    confusion = np.zeros((len(hypothesis_labels), len(reference_labels)), dtype=float)
    spans: list[tuple[float, float, set[str], set[str]]] = []
    for start, end in zip(times, times[1:]):
        if end <= start:
            continue
        ref = {item.speaker for item in reference if item.start < end and item.end > start}
        hyp = {item.speaker for item in hypothesis if item.start < end and item.end > start}
        if skip_overlap and len(ref) > 1:
            continue
        spans.append((start, end, ref, hyp))
        for h in hyp:
            for r in ref:
                confusion[hypothesis_labels.index(h), reference_labels.index(r)] += end - start
    mapping: dict[str, str] = {}
    if confusion.size:
        rows, columns = linear_sum_assignment(-confusion)
        mapping = {hypothesis_labels[int(row)]: reference_labels[int(column)]
                   for row, column in zip(rows, columns)}
    ref_boundaries = [point for item in reference for point in (item.start, item.end)]
    result: list[Interval] = []
    for start, end, ref, hyp in spans:
        middle = (start + end) / 2
        if collar > 0 and any(abs(middle - point) < collar / 2 for point in ref_boundaries):
            continue
        mapped = {mapping.get(name, f"unmapped:{name}") for name in hyp}
        if mapped != ref:
            result.append(Interval(start, end))
    return union_intervals(result)


def evaluate_reference(
    reference_path: Path, hypothesis: Sequence[Segment], candidates: Sequence[Candidate],
    *, collar: float = 0.0, skip_overlap: bool = False,
) -> dict[str, object]:
    if collar < 0:
        raise ValueError("evaluation collar must be non-negative")
    reference = read_diarization(reference_path)
    from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

    ref_annotation = _annotation(reference)
    hyp_annotation = _annotation(hypothesis)
    der_metric = DiarizationErrorRate(collar=collar, skip_overlap=skip_overlap)
    jer_metric = JaccardErrorRate(collar=collar, skip_overlap=skip_overlap)
    components = der_metric(ref_annotation, hyp_annotation, detailed=True)
    der = float(components["diarization error rate"])
    jer = float(jer_metric(ref_annotation, hyp_annotation))
    errors = _error_intervals(reference, hypothesis, collar, skip_overlap)
    selected = [Interval(item.start, item.end) for item in candidates]
    reviewed = union_intervals(selected)
    hits = sum(any(interval_overlap(item, error) > 0 for error in errors) for item in selected)
    error_hits = sum(any(interval_overlap(error, item) > 0 for item in reviewed) for error in errors)
    error_duration = sum(item.end - item.start for item in errors)
    covered = sum(interval_overlap(item, error) for item in reviewed for error in errors)
    return {
        "der": der, "jer": jer, "collar_seconds": collar, "skip_overlap": skip_overlap,
        "speaker_confusion_seconds": float(components["confusion"]),
        "missed_speech_seconds": float(components["missed detection"]),
        "false_alarm_seconds": float(components["false alarm"]),
        "error_interval_count": len(errors),
        "precision_at_k": hits / len(selected) if selected else None,
        "recall_at_k": error_hits / len(errors) if errors else None,
        "error_duration_coverage": min(1.0, covered / error_duration) if error_duration else None,
        "reviewed_audio_seconds": sum(item.end - item.start for item in reviewed),
        "ranking_evaluation_note": "Interval-hit diagnostics use optimal label mapping and are approximate around evaluation collars; DER/JER are computed by pyannote.metrics.",
    }
