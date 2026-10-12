from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
import heapq

from .overlap import interval_overlap, subtract_intervals, union_intervals
from .schemas import ActivityFrame, Candidate, Interval, QualityConfig, Segment


def activity_candidates(
    segments: Sequence[Segment], frames: Sequence[ActivityFrame], config: QualityConfig,
    *, include_overlap: bool = True, include_boundaries: bool = True,
) -> list[Candidate]:
    """Only explicit global-time, per-speaker activity frames are accepted."""
    result: list[Candidate] = []
    ordered_segments = sorted(segments, key=lambda item: item.start)
    ordered_frames = sorted(frames, key=lambda item: (item.start, item.end))
    active_segments: list[tuple[float, int, Segment]] = []
    next_segment = 0
    for frame in ordered_frames:
        if frame.end <= frame.start:
            continue
        while next_segment < len(ordered_segments) and ordered_segments[next_segment].start < frame.end:
            item = ordered_segments[next_segment]
            heapq.heappush(active_segments, (item.end, item.index, item))
            next_segment += 1
        while active_segments and active_segments[0][0] <= frame.start:
            heapq.heappop(active_segments)
        active_labels = [name for name, value in frame.activities.items() if value >= config.activity_threshold]
        if include_overlap:
            shown = [s for _, _, s in active_segments if s.start < frame.end and s.end > frame.start]
            shown_speakers = {s.speaker for s in shown}
        if include_overlap and len(active_labels) >= 2:
            if len(shown_speakers) < 2:
                result.append(Candidate(
                    frame.start, frame.end, next(iter(shown_speakers), None), None,
                    ["missed_overlap_candidate"],
                    features={"active_speakers": sorted(active_labels)},
                    feature_scores={"missed_overlap": min(1.0, min(frame.activities[n] for n in active_labels))},
                    evidence_available=["frame_activity"],
                ))
        elif include_overlap and len(active_labels) < 2:
            ranked_activity = sorted(frame.activities.items(), key=lambda row: (-row[1], row[0]))
            if len(ranked_activity) >= 2:
                first_name, first_value = ranked_activity[0]
                second_name, second_value = ranked_activity[1]
                lower = max(0.0, config.activity_threshold - config.activity_margin_threshold)
                if first_value >= config.activity_threshold and lower <= second_value < config.activity_threshold:
                    shown = [s for _, _, s in active_segments if s.start < frame.end and s.end > frame.start]
                    if len({s.speaker for s in shown}) < 2:
                        result.append(Candidate(
                            frame.start, frame.end, next(iter({s.speaker for s in shown}), None), second_name,
                            ["uncertain_overlap_candidate"],
                            features={"overlap_speakers": [first_name, second_name],
                                      "stronger_activity": round(first_value, 6),
                                      "weaker_activity": round(second_value, 6),
                                      "activity_threshold": config.activity_threshold},
                            feature_scores={"uncertain_overlap": second_value},
                            evidence_available=["frame_activity"],
                        ))
        if include_overlap and len(active_labels) < 2 and len(shown_speakers) >= 2:
            strengths = sorted(frame.activities.values(), reverse=True)
            second = strengths[1] if len(strengths) > 1 else 0.0
            result.append(Candidate(
                frame.start, frame.end, None, None, ["spurious_overlap_candidate"],
                features={"diarized_speakers": sorted(shown_speakers),
                          "second_speaker_activity": round(second, 6)},
                feature_scores={"spurious_overlap": max(0.0, 1.0 - second)},
                evidence_available=["frame_activity"],
            ))
    # Boundary uncertainty is about activity ambiguity, not a proven timing error.
    frame_starts = [item.start for item in ordered_frames]
    maximum_frame_duration = max((item.end - item.start for item in ordered_frames), default=0.0)
    for segment in segments if include_boundaries else ():
        for boundary in (segment.start, segment.end):
            window = Interval(max(0.0, boundary - config.boundary_window_seconds),
                              boundary + config.boundary_window_seconds)
            first = bisect_left(frame_starts, window.start - maximum_frame_duration)
            nearby = []
            for frame_index in range(first, len(ordered_frames)):
                frame = ordered_frames[frame_index]
                if frame.start >= window.end:
                    break
                if frame.end > window.start:
                    nearby.append(frame)
            if not nearby:
                continue
            ambiguities = []
            for frame in nearby:
                values = sorted(frame.activities.values(), reverse=True)
                if len(values) >= 2 and values[0] >= config.activity_threshold:
                    ambiguities.append(1 - min(1.0, values[0] - values[1]))
            if ambiguities and max(ambiguities) >= 1 - config.activity_margin_threshold:
                result.append(Candidate(
                    window.start, window.end, segment.speaker, None,
                    ["boundary_uncertainty_candidate"],
                    features={"activity_ambiguity": round(max(ambiguities), 6)},
                    feature_scores={"boundary_uncertainty": max(ambiguities)},
                    evidence_available=["frame_activity"],
                ))
    merged: list[Candidate] = []
    for item in sorted(result, key=lambda row: (row.start, row.end, row.issue_types)):
        if (merged and item.issue_types in (["missed_overlap_candidate"], ["spurious_overlap_candidate"], ["uncertain_overlap_candidate"])
                and merged[-1].issue_types == item.issue_types
                and merged[-1].assigned_speaker == item.assigned_speaker
                and merged[-1].end >= item.start
                and merged[-1].features.get("active_speakers") == item.features.get("active_speakers")
                and merged[-1].features.get("diarized_speakers") == item.features.get("diarized_speakers")
                and merged[-1].features.get("overlap_speakers") == item.features.get("overlap_speakers")):
            merged[-1].end = max(merged[-1].end, item.end)
            key = ({"missed_overlap_candidate": "missed_overlap",
                    "spurious_overlap_candidate": "spurious_overlap",
                    "uncertain_overlap_candidate": "uncertain_overlap"}[item.issue_types[0]])
            merged[-1].feature_scores[key] = max(
                merged[-1].feature_scores[key], item.feature_scores[key]
            )
        else:
            merged.append(item)
    overlap_issues = {"missed_overlap_candidate", "spurious_overlap_candidate", "uncertain_overlap_candidate"}
    return [item for item in merged
            if item.issue_types[0] not in overlap_issues
            or item.end - item.start + 1e-6 >= config.minimum_activity_interval]


def vad_disagreement_candidates(
    segments: Sequence[Segment], vad: Sequence[Interval], config: QualityConfig
) -> list[Candidate]:
    diarized = union_intervals([Interval(s.start, s.end) for s in segments])
    result: list[Candidate] = []
    for item in subtract_intervals(vad, diarized):
        if item.end - item.start >= config.minimum_activity_interval:
            result.append(Candidate(item.start, item.end, None, None,
                ["missed_speech_candidate"],
                features={"disagreement_seconds": round(item.end - item.start, 6)},
                feature_scores={"activity_disagreement": 0.7},
                evidence_available=["independent_vad"]))
    for item in subtract_intervals(diarized, vad):
        if item.end - item.start >= config.minimum_activity_interval:
            result.append(Candidate(item.start, item.end, None, None,
                ["false_speech_candidate"],
                features={"disagreement_seconds": round(item.end - item.start, 6)},
                feature_scores={"activity_disagreement": 0.5},
                evidence_available=["independent_vad"]))
    return result
