# PodSieve QML desktop UI

This Qt Quick / PySide6 desktop interface uses **direct Python calls** to the
existing processing code. No FastAPI server, REST API, subprocess CLI shell, or
separate virtual environment is required.

## Start (from repository root)

PySide6 is already installed in your existing project `.venv`:

```bash
uv run --no-sync python ui/main.py
```

If that installation is lost, install into the **same** environment:

```bash
uv pip install --python .venv/bin/python 'PySide6>=6.7,<7'
```

`--no-sync` is important as PySide6 is not yet pinned in the audio project's
`pyproject.toml` / `uv.lock`. This avoids silently removing the manual installation.

## Architecture

- `main.py`: Qt engine, exposes the bridge to QML.
- `bridge.py`: `PipelineBridge(QObject)` exposes sources and methods.
- `PipelineWorker(QThread)`: runs the existing functions off the UI thread and
  reports completion or failure through Qt signals.
- `Main.qml`: desktop presentation and user actions.
- The existing `run.py` functions and `src/` remain unchanged.
- `configs/default.yaml` controls pipeline execution.

### Connected now

- Reads registered speakers and sources from each `metadata.json`.
- Runs real `run_ingest` for URLs/local paths (Add Source).
- Runs real `run_convert`, `run_separation`, `run_diarization`.
- Invokes existing quality `analyze_source`.
- Reports running/completed/failed and refreshes sources after completion.
- Only one pipeline task is allowed at once to avoid conflicting writes.

### Still UI-only

- Waveform, playback position, speaker timeline, review queue and inspector use
  **sample visualization data**. They do not yet parse real diarization JSON,
  quality reports, or play an actual WAV.
- Pipeline option fields outside the specific mapped arguments are visual
  previews. Advanced ingest download settings are **not** applied by the UI.
  The existing YAML defaults take precedence.
- Overview counts are example figures.
- Settings fields are non-persistent and do not change YAML.
- No persistent queue, cancellation, auto-chaining or progress percentage.
- No individual manual review edits or publishing/final regeneration.

## Important safety and operational notes

The stages **write files** to the configured `storage.data_root`.
Default `overwrite` is false. To avoid accidental changes, confirm the selected
speaker/source and inspect the real output directory before clicking Run.
A previous stage run does not automatically rerun downstream stages.

The default YouTube cookie behavior is read from `configs/default.yaml`,
not from the visual-only Advanced fields.

This integration has not yet been run against a Linux display and model weights
in this session; validate it locally before relying on it for expensive model runs.

## Next integration work

Real audio playback, waveform peak generation, RTTM/JSON speaker timeline,
quality report models and per-segment review controls should be implemented as
small, independently testable Python/QML modules rather than extending a single
large QML file.
