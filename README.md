# PodSieve

PodSieve is a command-line pipeline for preparing audio for speaker diarization.
It takes a local audio file or a supported URL through four stages:

```text
ingest → convert to WAV → separate vocals → diarize speakers
```

The project keeps source files, intermediate audio, diarization results, and
metadata under one configurable data directory. It currently includes the
ingestion, conversion, vocal separation, and diarization stages.

## Features

- Ingest local audio files or supported YouTube and Castbox URLs.
- Convert audio to WAV with FFmpeg.
- Separate vocals and instrumental audio with `audio-separator`.
- Run speaker diarization with a pyannote.audio pipeline.
- Save diarization as RTTM and JSON, with optional per-segment WAV files.
- Track source and stage status in per-speaker metadata and CSV registries.

## Requirements

- Linux with Python 3.10.
- [`uv`](https://docs.astral.sh/uv/) for Python and dependency management.
- NVIDIA GPU and a compatible NVIDIA driver for the configured CUDA 12.8
  PyTorch wheels. CPU execution may be possible, but has not been documented
  or tuned here.
- FFmpeg for audio conversion and separation.
- Node.js when downloading URLs with the default `yt-dlp` configuration.
- A Hugging Face access token with permission to use the configured pyannote
  model.

## Installation

From the project directory:

```bash
uv python install 3.10
uv sync
```

This creates a project-local `.venv` and installs the locked dependencies from
`uv.lock`. To verify the PyTorch CUDA installation:

```bash
uv run python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'unavailable')"
```

FFmpeg must be available on `PATH`:

```bash
ffmpeg -version
```

For URL ingestion, confirm Node.js is available too:

```bash
node --version
```

## Configuration

The main configuration file is [`configs/default.yaml`](configs/default.yaml).
It controls the data root, audio sample rates, URL download options, separation
model, and diarization model and output settings.

The default download configuration currently points to a machine-specific
cookies file. Set `download.cookies_file` to a valid Netscape-format cookies
file on your machine, or set it to `null` if cookies are not needed. You can
also configure `cookies_from_browser` where supported by `yt-dlp`.

The separation checkpoint is expected at:

```text
checkpoints/model_bs_roformer_ep_317_sdr_12.9755.ckpt
```

The separation checkpoint is kept locally at this path and is ignored by Git.
The pyannote model and its dependent model weights are downloaded from
Hugging Face on first use. To keep that cache under `checkpoints/`, set
`HF_HOME` to `checkpoints/huggingface` when running diarization. The cache is
also ignored by Git.

Set your Hugging Face token in the environment before running diarization. The model files will be cached under `checkpoints/huggingface/`:

```bash
export HF_TOKEN="your-hugging-face-token"
```

The config uses `HF_TOKEN` by default. The model configured by default is
`pyannote/speaker-diarization-3.1`; make sure your Hugging Face account has
accepted its access conditions.

## Run the pipeline

Use the same `speaker-id` and `source-id` for every stage. IDs must use the
formats `speaker_001` and `source_001` (three to six digits).

### 1. Ingest audio

From a local file:

```bash
uv run python run.py ingest \
  --speaker-id speaker_001 \
  --source-id source_001 \
  --input-file /path/to/audio.mp3
```

Or from a supported URL:

```bash
uv run python run.py ingest \
  --speaker-id speaker_001 \
  --source-id source_001 \
  --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

`--input-file` and `--url` are mutually exclusive. Ingestion stores the raw
source and records its metadata. Optional speaker metadata can be set with
`--name`, `--gender`, and `--language`.

### 2. Convert to WAV

```bash
uv run python run.py convert \
  --speaker-id speaker_001 \
  --source-id source_001
```

### 3. Separate vocals

```bash
uv run python run.py separate \
  --speaker-id speaker_001 \
  --source-id source_001
```

This produces `vocals.wav` and `instrumental.wav`. Pass `--keep-work-dir` to
retain temporary separation chunks for inspection.

### 4. Run diarization

```bash
HF_HOME="$PWD/checkpoints/huggingface" uv run python run.py diarize \
  --speaker-id speaker_001 \
  --source-id source_001
```

The diarization stage runs on the separated vocals. Depending on the
configuration, it writes RTTM and JSON results and one WAV file per detected
segment.

Each stage accepts `--overwrite` to replace its existing output. Use it only
when you intend to regenerate that stage's result.

## Outputs

By default, outputs are written under `data/`:

```text
data/
├── manifests/
│   ├── speakers.csv
│   └── sources.csv
└── speakers/
    └── speaker_001/
        ├── metadata.json
        ├── raw/
        ├── wav/
        ├── separated/
        │   └── source_001/
        │       ├── vocals.wav
        │       └── instrumental.wav
        └── diarization/
            └── source_001/
                ├── diarization.rttm
                ├── diarization.json
                └── segments/
```

Set another storage directory in the config, or override it for one invocation:

```bash
uv run python run.py --data-root /path/to/audio-data ingest \
  --speaker-id speaker_001 \
  --source-id source_001 \
  --input-file /path/to/audio.mp3
```

## Command help

```bash
uv run python run.py --help
uv run python run.py ingest --help
uv run python run.py convert --help
uv run python run.py separate --help
uv run python run.py diarize --help
```

## Troubleshooting

- **CUDA is unavailable:** check the NVIDIA driver and the output of
  `uv run python -c "import torch; print(torch.cuda.is_available())"`.
- **FFmpeg is missing:** install FFmpeg using your Linux distribution's package
  manager and confirm it is on `PATH`.
- **URL download fails:** check Node.js, `yt-dlp`, network access, and whether
  the source requires cookies. Configure the cookie path in
  `configs/default.yaml` when needed.
- **pyannote cannot load the model:** confirm `HF_TOKEN` is set in the same
  shell and that your Hugging Face account has access to the configured model.
- **A stage says output already exists:** rerun that command with `--overwrite`
  only if replacing the existing result is intended.

## License and model terms

No project license is specified yet. Audio models and checkpoints may have
terms separate from this code; review the upstream model licenses and access
conditions before redistribution or commercial use.

## Git history

Initialize a repository in this directory and create the first commit:

```bash
git init
git branch -M main
git add .gitignore README.md pyproject.toml uv.lock configs src run.py
git commit -m "chore: initialize PodSieve pipeline"
```

Then make focused commits as you work. For example, stage and commit each part
of the pipeline separately:

```bash
git add src/ingestion
git commit -m "feat: add audio ingestion and conversion"

git add src/separation checkpoints/*.yaml
git commit -m "feat: add vocal separation stage"

git add src/diarization
git commit -m "feat: add speaker diarization stage"

git add run.py src/core configs/default.yaml
git commit -m "feat: connect audio processing stages"
```

Review the staged changes before each commit with `git status` and
`git diff --staged`. The `.gitignore` excludes local data, virtual environments,
logs, secrets, and checkpoint files. The separation checkpoint is about 610 MB;
if you decide to version it, install Git LFS, track `checkpoints/*.ckpt` with
`git lfs track`, then add and commit the generated `.gitattributes` file along
with the checkpoint. Keep tokens and cookies out of Git history.
