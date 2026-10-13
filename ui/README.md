# PodSieve — QML interface prototype

A dark desktop-first prototype, inspired by the PodSieve Figma workspace.
**UI only**: does not import the CLI, read project metadata, invoke processing,
download files, or connect to any backend. Everything shown is mock data.

## Run with the project's existing uv environment

You have already installed PySide6 into the existing `.venv`.

```bash
uv run --no-sync python ui/main.py
```

If PySide6 is missing from this same environment:

```bash
uv pip install --python .venv/bin/python 'PySide6>=6.7,<7'
uv run --no-sync python ui/main.py
```

`--no-sync` is deliberate: it avoids altering your manually installed PySide6
while leaving the project's CUDA/audio dependency lock untouched.

## Screens

- Dataset: searchable mock source records and selectable sources
- Processing: stage controls and a simulated processing state
- Review: waveform visualization, speaker tracks, suspect review queue, inspector
- Settings: configuration-preview controls
- Ingest: local path or URL form, advanced settings entry points

The audio waveform, job state, counters, and review findings are simulated.
This is an editable QML implementation, not a backend-enabled production app.

## Scope boundary

No changes were made to `run.py`, `src/`, `configs/`, or `uv.lock`.
Keep persistence, file access, real audio playback, and job execution for the
future backend/service integration stage.
