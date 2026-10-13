# Contributing to PodSieve

Thanks for helping improve PodSieve! Bug reports, documentation improvements, QML usability fixes, and reproducible audio-processing tests are welcome.

## Before you start

- Check [existing issues](https://github.com/rezasouri/podsieve/issues) before opening a duplicate.
- For larger features, open an issue to discuss the scope first.
- Do not share private recordings, API tokens, Hugging Face credentials, cookies, or identifying audio data in public issues.

## Local development

Install the [documented prerequisites](README.md#requirements) and use the project's locked environment:

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests -v
```

To launch the native UI:

```bash
uv run --locked python ui/main.py
```

For UI-only test coverage:

```bash
uv run --locked python -m unittest discover -s tests -p 'test_ui*.py' -v
```

Some audio pipelines require CUDA, checkpoints, gated models, FFmpeg, or network access. Do not claim a complete end-to-end GPU run unless you've executed it.

## Pull request guidelines

1. Work on a topic branch and keep changes focused.
2. Explain what changed and why, with links to the relevant issue where possible.
3. Add or update tests and documentation for behavioral changes.
4. For UI changes, include before/after screenshots when useful.
5. State your tested operating system, Python version, and test commands.
6. Never commit model weights, generated audio, datasets, secrets, or local `.env` files.

## Reporting issues

Use the repository issue templates where possible. Include the exact command or workflow, a minimal reproducible example, expected versus actual behavior, and a redacted traceback/log. Avoid publishing personal source media or tokens.

## Community expectations

Be respectful, constructive, and specific in reviews and discussions. Assume good intent and focus feedback on observable behavior and reproducible evidence.

## Licensing

A project-wide license has not yet been selected. Before contributing material intended for redistribution, check the current repository license status and third-party model/asset terms.
