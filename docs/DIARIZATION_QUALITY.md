# Diarization quality analysis

`diarize` now saves the intermediate model outputs and runs quality analysis.
`analyze-diarization` reads that evidence to rerank regions without running
pyannote or Silero again. It does not change speaker labels.
Scores are **review priorities**, not calibrated error probabilities.

## Run

```bash
uv run python run.py diarize \
  --speaker-id speaker_001 --source-id source_001 --num-speakers 2

uv run python run.py analyze-diarization \
  --speaker-id speaker_001 --source-id source_001 --overwrite
```

Optional arguments include `--top-k 30`, `--min-score 0.5`,
`--export-review-clips`, `--no-export-review-clips`, `--overwrite`,
`--features-file /path/to/features.json`, and
`--reference-rttm /path/to/reference.rttm`. Evaluation also accepts
`--collar 0.25` and `--skip-overlap`.

Historical results have no intermediate evidence. Run
`upgrade-diarization-evidence --speaker-id ... --source-id ... --overwrite`
to rerun diarization on the saved vocals and generate it. This replaces the
old annotation, which may differ slightly. For a basic run, use both
`--no-save-evidence --no-quality-analysis`.

## Architecture and feature availability

The quality package separates input schemas, overlap sweeps, temporal rules,
speaker embedding comparison, optional activity analysis, scoring, export,
and reference evaluation. The analyzer consumes normalized segments and
timestamped evidence; model execution is outside the analyzer. Python callers
can inject an `EvidenceAdapter` with `segment_embeddings`, `activity_frames`,
and `independent_vad` methods instead of using a JSON feature file.

| Analysis | Available from existing output? | Evidence |
| --- | --- | --- |
| Confirmed output overlap | Yes | Concurrent distinct speaker labels in RTTM/JSON |
| Short turns, A-B-A switches, short gaps | Yes | Diarization timestamps |
| Speaker confusion | New runs with sufficient clean references | Native model segment embeddings |
| Potentially missed or spurious overlap | New runs | Local segmentation mapped through chunk cluster IDs |
| Boundary activity ambiguity | New runs | Mapped per-speaker activity |
| Missed/false speech candidates | New runs | Silero VAD intervals |
| Cluster ambiguity | New runs | Native clustering scores and assignments |

The adapter supports exactly `pyannote.audio 4.0.1`'s
`SpeakerDiarization` implementation with the configured
`pyannote/speaker-diarization-3.1` model. Its public hook yields segmentation,
speaker count, chunk embeddings and discrete activity. There is no clustering
hook in this version, so a scoped delegating wrapper captures the exact
hard assignments, soft scores and centroids during the same inference call;
the original clustering object is restored afterward. The adapter refuses
other installed pyannote versions until checked. A new backend can implement
the same saved manifest and `EvidenceAdapter` methods.

The local segmentation's channel number is never treated as a global speaker.
Each chunk channel is mapped through its effective cluster assignment. The
original centroid rows are matched to pyannote's ordered final centroids to
recover final speaker labels. The powerset segmentation model's hook output in
this pipeline is already decoded to binary local speaker activity by pyannote;
the original powerset class logits are not exposed by this hook. Its powerset flag
and class names are saved in the manifest. Frame and chunk sliding windows,
including their starts, durations and steps, are also recorded.

Each `.npy` file preserves its source dtype and shape; `manifest.json`
records a SHA-256 digest. The loader validates all digests, the vocals file
size and modification time, and the annotation hash before analysis. This
catches corruption and stale evidence. Files include `segmentation`,
`local_binary_activity`, `speaker_count`, `speaker_activity`,
`chunk_embeddings`, `cluster_assignments`, `effective_cluster_assignments`,
`cluster_scores`, `cluster_centroids`, `final_centroids`, `mapped_activity`,
`segment_embeddings`, `speaker_prototypes`, `independent_vad` and segment
audio features. Arrays are written individually, so they can be opened with
NumPy memory mapping. Long vocals are still loaded into memory by the current
diarization pipeline; sufficient RAM is required.

An external adapter may produce the following JSON. Frame times are **global
seconds** from the beginning of `vocals.wav`; values must be finite in `[0,1]`
and are activity evidence, not validated probabilities. Embedding keys are the
segment `index` values in `diarization.json` (or zero-based RTTM row order).
The `vad_source` marker must be `independent` to prevent same-pipeline activity
from masquerading as independent verification.

```json
{
  "embedding_source": "adapter-name-and-model-version",
  "segment_embeddings": {"0": [0.1, 0.2], "1": [0.2, 0.1]},
  "timebase": "global_seconds",
  "speaker_label_space": "final_diarization",
  "activity_source": "adapter-name-and-model-version",
  "activity_frames": [
    {"start": 1.0, "end": 1.02, "activities": {"SPEAKER_00": 0.8, "SPEAKER_01": 0.6}}
  ],
  "vad_source": "independent",
  "independent_vad": [{"start": 1.0, "end": 2.0}]
}
```

Embeddings are normalized before cosine comparison. Clean references exclude
annotated overlap, use multiple segments, trim low-similarity outliers, and
leave the target segment out of its assigned speaker's prototype. Very short
segments and speakers with insufficient clean references are skipped. A
negative similarity margin means an alternative prototype fits better; it
does not prove that the speaker label is wrong.

Segment embeddings are extracted from the unpadded vocals waveform using the
same embedding model pyannote used for clustering. The longest clean part of
each turn is selected; turns with less than 0.8 seconds of clean speech are
marked insufficient. Short turns are not combined with neighboring turns:
shared audio between a target embedding and its reference would invalidate
leave-one-out comparison. Robust per-speaker prototypes, reference counts and
pairwise similarities are saved. Candidate comparison leaves the target out
of its assigned reference. The native clustering metric and scores are kept
separately from cosine prototype comparisons. Segment RMS and clipping rates,
plus aligned original-to-vocals RMS when the original WAV exists, are saved as
diagnostic context, not as calibrated speech quality labels.

Confirmed overlap uses unique active speakers, so duplicate tracks for one
speaker do not create artificial overlap. Potential overlap and boundary
activity checks use mapped model frames when available. Timing rules flag
review candidates and do not assert a boundary error. VAD disagreements are
also candidates; the independent detector can itself be wrong.

## Scoring and configuration

`configs/default.yaml` contains `diarization_quality` thresholds and weights.
Each candidate records raw features, normalized component scores, the available
evidence, and a weighted sum review score scaled by the largest configured
weight. Missing components contribute nothing. Candidates with model or activity evidence are ranked
separately ahead of timing-only candidates; within each group the order is
score descending, then start/end time and label. `quality_summary.json` stores
the effective configuration and ranking method for reproducibility.

`expected_num_speakers` is optional. If set, a mismatch adds a warning; it
does not change the diarization. The default maximum exported candidates is
30. Use `--top-k` and `--min-score` to control the review set.

## Output

Diagnostics are written under
`data/speakers/<speaker_id>/diarization/<source_id>/diagnostics/quality/`:

- `suspicious_segments.json`: full structured candidate records
- `suspicious_segments.csv`: review-friendly rows with JSON-encoded feature columns
- `quality_summary.json`: counts, feature availability, configuration, warnings,
  `feature_status` with explicit unavailable reasons, ranking method, and
  optional reference evaluation
- `overlap_candidates.csv` and `.json`: all detected, missed and uncertain
  overlap candidates. Generic top-k and score cutoffs do not filter this report.
- `review_groups.json`: nearby findings merged into listening intervals, with
  the ranks of every underlying individual finding
- `review_clips/suspicious/`: deterministic excerpts for ranked findings
- `review_clips/groups/`: excerpts for nearby findings reviewed together
- `review_clips/overlap/`: overlap excerpts with one second of source context

The final, unflagged WAV segments are published separately under
`data/speakers/<speaker_id>/diarization/<source_id>/final/segments/<speaker>/`.
`manifest.csv` and `manifest.json` list the published segments and record which
review windows were excluded. “Unflagged” means no generated review window
intersected the segment; it is not a claim that the audio was human-verified.

`analyze-diarization` leaves annotation and audio unchanged. `--overwrite`
replaces quality outputs and prior review clips.

## Optional reference evaluation

With `--reference-rttm`, `pyannote.metrics` computes DER and JER with speaker
label mapping, collar and overlap policy. Additional ranking diagnostics
report precision/recall at the exported set and the fraction of reference
error duration covered by reviewed intervals. These interval-hit diagnostics
are approximate around collars; DER/JER are the authoritative error metrics.
Reference evaluation is independent of unsupervised candidate generation.

## Validation and limits

Unit tests use synthetic timestamps, embeddings, activity, audio and RTTM.
They do not download model weights:

```bash
uv run python -m unittest discover -s tests -v
```

An optional cached-model smoke test is included but skipped by default. It
must be opted into explicitly with `PODSIEVE_PYANNOTE_INTEGRATION=1` and a
complete offline model cache.

The model-based overlap and clustering signals share pyannote's segmentation
and embedding models, so they are correlated evidence. Silero is independent
but can still disagree with correct diarization. Current ranking weights are
review priorities, not measured error probabilities. No ground truth is
available for the ordinary inference run; use reference RTTM to measure DER,
JER and candidate coverage when available.

Assess practical usefulness on reviewed Persian podcast excerpts by measuring
DER/JER against reference RTTM and ranking precision/coverage at the review
budget you can afford. Scores and thresholds should be tuned on held-out
recordings; none are calibrated error probabilities.
