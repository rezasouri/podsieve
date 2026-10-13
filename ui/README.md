# PodSieve QML desktop UI

Native Qt Quick implementation of the workspace in `REACT/src/App.tsx` and
`REACT/src/index.css`. The React source is the visual reference; its simulated
jobs, sample initial statuses and browser-only actions are replaced by local
Python operations.

## Start

From the repository root:

```bash
uv run --no-sync python ui/main.py
```

PySide6 is declared in `pyproject.toml`. The interface uses the existing project
environment and needs no HTTP server.

## Connected behavior

- Two-column input/settings/control and status/log/output workspace, matching
  the reference colors, sizing, icons, cards, compact mode and animations.
- Native file chooser, editable local path, YouTube/Castbox URL input, and an
  optional destination directory directly below the input. An empty destination
  uses the existing default output.
- UI speaker IDs accept Unicode, spaces and arbitrary folder names (except path
  separators, empty names, dot paths and control characters). Source IDs still
  require `source_` plus 3–6 digits. Actual source statuses come from metadata.
- Individual Ingest, Convert, Separate and Diarize operations, plus sequential
  full-pipeline execution. A failure stops the remaining stages.
- Overwrite defaults to off. Completed stages require explicit overwrite.
  An individual stage does not automatically rerun subsequent stages.
- Language, speaker name, free-text gender, optional positive speaker count,
  evidence and quality settings are passed to the processing functions.
  Enabling quality also enables evidence; disabling evidence disables quality.
- Advanced model dialog applies sample rate, processing chunk duration, model
  names, token environment name, download formats and YouTube cookie method to
  the next run. These overrides do not modify the YAML file.
- Timestamped logging from Python logging, clear logs, native clipboard copy
  and native output-folder opening. Folder availability also checks disk.
- One worker at a time. Closing is deferred while a worker is running, to avoid
  destroying an active QThread. Cancellation is not implemented.

## Structure

- `main.py`: application, bundled font loading and QML engine.
- `Main.qml`: workspace and advanced configuration dialog.
- `components/`: reusable styled fields, buttons, toggles, dropdowns and cards.
- `assets/`: SVG paths ported from the React icons, and JetBrains Mono with its
  OFL license. Inter is used when installed, otherwise Qt selects a fallback.
- `bridge.py`: QObject state, metadata reads, validation and worker orchestration.
- `storage_adapter.py`: UI-only alias allocation, preference persistence and
  publication to a user-selected directory. No CLI or shared pipeline changes.

Stage activity is indeterminate. The footer indicates completed stages out of
four, not an estimated percentage of audio processing. Detailed stdout/stderr
and model progress bars are not captured by the Python logging bridge.

This workspace follows the React reference; waveform playback, timeline editing
and a manual quality-review interface are outside this page's scope.

## Custom output and CLI isolation

For speaker `hamid`, source `source_001` and destination `/home/nobka/Desktop`:

```text
/home/nobka/Desktop/hamid/
  SPEAKER_00/source_001_SPEAKER_00_0001.wav
  SPEAKER_01/source_001_SPEAKER_01_0002.wav
  .podsieve/source_001/manifest.csv
  .podsieve/source_001/manifest.json
  .podsieve-export.json
```

Model speaker labels remain separate subfolders. Source-prefixed filenames avoid
collisions between different inputs for the same speaker. CSV clip paths are
relative to the displayed speaker output folder. Source-specific manifests and
export ownership information are kept alongside the final audio.

Raw input, conversion, separated audio, annotation and diagnostics keep their
existing project workspace paths. Only final audio publication is redirected:
it uses temporary staging on the destination disk and publishes to the speaker
folder. No final WAV copies are retained in the default `final/segments` folder
for that run. Existing exports from earlier default runs are not removed.

Output replacement is staged and restores the old output if publication fails.
Overwriting one source preserves other sources' files. A nonempty unrelated
folder is rejected even with overwrite enabled.

UI preferences are stored under the configured data root in `.podsieve-ui.json`.
Free speaker names map to allocated, valid internal `speaker_NNNNNN` IDs; the
original names remain visible in the UI and output folders. Existing valid
`speaker_NNN` names continue to address their original datasets. The CLI still
rejects `hamid` as an ID and keeps its original layout and command options.
No monkey-patching or changes to `run.py`, `src/` or YAML are involved.

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_ui*.py' -v
QT_QPA_PLATFORM=offscreen timeout 3 .venv/bin/python ui/main.py
```

The UI tests use temporary storage. They exercise real local ingest and
FFmpeg conversion, completed-stage overwrite protection, full-pipeline chaining,
failure stopping, diarization option forwarding, speaker alias persistence,
external final publication, multi-source overwrite isolation, foreign-directory
protection, failure preservation and completed progress bars. Separation and diarization
models are mocked in these tests; GPU inference and provider downloads require
separate operational validation. A smoke run ending with timeout status 124 is
expected because the GUI event loop remains open.
