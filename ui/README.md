# PodSieve QML desktop UI

Native Qt Quick implementation of the processing workspace and Processed Data manager. The desktop interface uses local Python operations for processing, source management, and file actions.

## Start

From the repository root:

```bash
uv run --no-sync python ui/main.py
```

PySide6 is declared in `pyproject.toml`. The interface uses the existing project
environment and needs no HTTP server.

## First-run token setup

If the project root has no `.env`, a small startup dialog requests a Hugging Face
access token using a masked input. Save creates `.env` with `HF_TOKEN` and owner-only
permissions on POSIX systems, and makes the token available to the current process. Existing files
are never overwritten; `.env` remains Git-ignored. Later dismisses the dialog and
it returns on the next startup if the file is still missing. Token format is
checked locally; token validity/model access is checked by the processing backend.

## Responsive sizing

The window has a minimum size of 1180 × 720. Above the reference viewport,
`uiScale` grows with window dimensions (capped at 1.75); the logical canvas,
header, footer and dialogs scale together, including fonts and icons. Compact
layout decisions use logical dimensions. Small data labels have a larger baseline
font for readability; narrow tables retain horizontal scrolling.

## Connected behavior

- Two-column input/settings/control and status/log/output workspace, matching
  the reference colors, sizing, icons, cards, compact mode and animations.
- Native file chooser, editable local path, YouTube/Castbox URL input, and an
  optional destination directory directly below the input. An empty destination
  uses the existing default output.
- UI speaker IDs accept Unicode, spaces and arbitrary folder names (except path
  separators, empty names, dot paths and control characters). Source IDs still
  require `source_` plus 3–6 digits. Actual source statuses come from metadata.
- Processing opens with empty speaker/source IDs and unstarted stages, even
  when saved sources exist. Entering an existing ID pair loads its saved status.
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
- Clear in Pipeline Controls empties inputs, IDs, output destination, logs and
  stage status, and restores settings defaults. Stored sources/files remain intact.
  Clear is disabled while a worker runs.
- One worker at a time. Closing is deferred while a worker is running, to avoid
  destroying an active QThread. Cancellation is not implemented.

## Processed Data manager

The updated reference opens on Processed Data and adds header navigation back to
Process Audio. The processing form and its custom output/speaker-name support
remain intact.

- Counts, storage sizes, artifacts and stage timestamps are read from actual
  metadata and files; no sample source records or simulated failures are used.
- Search, speaker/status filters, sorting, six-row pagination and checkboxes.
  Selection uses internal speaker + source IDs, since source IDs repeat across
  different speakers. The inspector follows filtered selection and handles empty
  results without leaving stale details visible.
- Reference-sized table columns, proportional inspector, colored input/statistic
  icons, underline tabs, connected stage timeline and three inline footer actions.
  At narrow widths the table scrolls horizontally and the inspector stays usable.
- Inspector Overview, Processing Stages and Files tabs, actual artifact path
  copying/opening.
- Native Qt Multimedia preview selects vocals, working WAV or raw audio in that
  order, and supports play/pause, duration, seeking and decoder error reporting.
  It opens a file only when preview is requested. No synthetic waveform is shown.
- Deletion requires typing the exact source ID and is disabled while any job is
  running. Only that source's raw/working/generated files and owned external
  clips are moved to `.podsieve-trash/<id>` under the configured data root.
  Metadata and shared registries are updated; other sources and the speaker
  identity remain. On failure, moved files and metadata are restored.
- Trash includes a `restore.json` record with original paths and metadata.
  Restoring trash is currently manual; there is no restore button or automatic
  cleanup. The dialog clearly states that files move to local trash.
- Processing/failed states reflect this desktop session; existing metadata only
  persists pending/completed. The interface cannot detect a separate CLI process
  running concurrently against the same dataset.

## Structure

- `main.py`: application, bundled font loading and QML engine.
- `Main.qml`: navigation, processing workspace and advanced configuration dialog.
- `ProcessedData.qml`: source table, inspector, multimedia preview and deletion dialog.
- `data_registry.py`: real artifact inventory and source-isolated removal/rollback.
- `components/`: reusable styled fields, buttons, toggles, dropdowns and cards.
- `assets/`: SVG icons and JetBrains Mono with its OFL license. Inter is used
  when installed; otherwise Qt selects a fallback.
- `bridge.py`: QObject state, metadata reads, validation and worker orchestration.
- `storage_adapter.py`: UI-only alias allocation, preference persistence and
  publication to a user-selected directory. No CLI or shared pipeline changes.

Stage activity is indeterminate. The footer indicates completed stages out of
four, not an estimated percentage of audio processing. Detailed stdout/stderr
and model progress bars are not captured by the Python logging bridge.

Timeline editing, waveform rendering and a manual quality-review interface remain
outside these pages' scope.

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
protection, failure preservation, completed progress bars, duplicate source-ID
selection, data-page navigation/filters and source deletion/registry rollback. Separation and diarization
models are mocked in these tests; GPU inference and provider downloads require
separate operational validation. A smoke run ending with timeout status 124 is
expected because the GUI event loop remains open.
