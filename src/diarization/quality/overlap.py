from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from .schemas import Interval, Segment


def confirmed_overlap(segments: Sequence[Segment]) -> list[tuple[Interval, tuple[str, ...]]]:
    """Sweep event times, counting unique active speakers rather than tracks."""
    events: dict[float, list[tuple[str, int]]] = defaultdict(list)
    for segment in segments:
        if segment.end <= segment.start:
            continue
        events[segment.start].append((segment.speaker, 1))
        events[segment.end].append((segment.speaker, -1))
    counts: dict[str, int] = defaultdict(int)
    result: list[tuple[Interval, tuple[str, ...]]] = []
    previous: float | None = None
    for time in sorted(events):
        speakers = tuple(sorted(name for name, count in counts.items() if count > 0))
        if previous is not None and time > previous and len(speakers) >= 2:
            if result and result[-1][0].end == previous and result[-1][1] == speakers:
                result[-1] = (Interval(result[-1][0].start, time), speakers)
            else:
                result.append((Interval(previous, time), speakers))
        for name, change in events[time]:
            counts[name] += change
        previous = time
    return result


def union_intervals(intervals: Sequence[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for item in sorted(intervals, key=lambda x: (x.start, x.end)):
        if item.end <= item.start:
            continue
        if merged and item.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, item.end))
        else:
            merged.append(item)
    return merged


def interval_overlap(a: Interval, b: Interval) -> float:
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def subtract_intervals(base: Sequence[Interval], removed: Sequence[Interval]) -> list[Interval]:
    result: list[Interval] = []
    cuts = union_intervals(removed)
    for item in union_intervals(base):
        cursor = item.start
        for cut in cuts:
            if cut.end <= cursor:
                continue
            if cut.start >= item.end:
                break
            if cut.start > cursor:
                result.append(Interval(cursor, min(item.end, cut.start)))
            cursor = max(cursor, cut.end)
            if cursor >= item.end:
                break
        if cursor < item.end:
            result.append(Interval(cursor, item.end))
    return result
