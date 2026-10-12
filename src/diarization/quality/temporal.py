from __future__ import annotations

from collections.abc import Sequence

from .schemas import Candidate, QualityConfig, Segment


def temporal_candidates(segments: Sequence[Segment], config: QualityConfig) -> list[Candidate]:
    ordered = sorted(segments, key=lambda item: (item.start, item.end, item.speaker, item.index))
    result: list[Candidate] = []
    for position, segment in enumerate(ordered):
        if segment.duration <= config.short_turn_seconds:
            result.append(Candidate(
                segment.start, segment.end, segment.speaker, None, ["short_turn"],
                features={"duration_seconds": round(segment.duration, 6)},
                feature_scores={"short_turn": min(1.0, 1 - segment.duration / max(config.short_turn_seconds, 1e-9))},
                evidence_available=["diarization_timing"],
            ))
        if position == 0:
            continue
        previous = ordered[position - 1]
        gap = segment.start - previous.end
        if previous.speaker != segment.speaker and 0 <= gap <= config.short_gap_seconds:
            result.append(Candidate(
                max(previous.end - config.boundary_window_seconds, previous.start),
                min(segment.start + config.boundary_window_seconds, segment.end),
                segment.speaker, previous.speaker, ["short_gap_at_change", "boundary_timing_candidate"],
                features={"gap_seconds": round(gap, 6)},
                feature_scores={"short_gap": 1 - gap / max(config.short_gap_seconds, 1e-9)},
                evidence_available=["diarization_timing"],
            ))
        if position >= 2:
            before = ordered[position - 2]
            if (before.speaker == segment.speaker != previous.speaker
                    and previous.duration <= config.rapid_switch_seconds
                    and 0 <= previous.start - before.end <= config.rapid_switch_seconds
                    and 0 <= segment.start - previous.end <= config.rapid_switch_seconds):
                result.append(Candidate(
                    previous.start, previous.end, previous.speaker, before.speaker,
                    ["rapid_a_b_a_switch", "isolated_speaker_label"],
                    features={"middle_turn_seconds": round(previous.duration, 6)},
                    feature_scores={"rapid_switch": 1 - previous.duration / max(config.rapid_switch_seconds, 1e-9)},
                    evidence_available=["diarization_timing"],
                ))
    return result
