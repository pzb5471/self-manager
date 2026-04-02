# Pre-commit Quality Gate

This repository now includes a `pre-commit` quality gate designed for a Python 3.11 environment.

## Scope

- `pre-commit`
  - YAML/TOML validation
  - merge-conflict detection
  - trailing whitespace cleanup
  - end-of-file normalization
  - line-ending normalization
  - large file checks
  - `black` format
  - `ruff` lint
- `pre-push`
  - `pytest tests -q`

## Recommended Setup

Create and activate a Python 3.11 virtual environment first, then run:

```powershell
python -m pip install -r requirements-dev.txt
git config core.hooksPath .githooks
pre-commit run --all-files
```

## Notes

- The hook runtime is pinned to `python3.11` in `.pre-commit-config.yaml`.
- Git hooks are executed from `.githooks/` instead of `.git/hooks/`.
- Frontend assets, logs, caches, database files, and binary test artifacts are excluded from hygiene hooks.
- The `pre-push` hook builds its own isolated Python environment and installs the test dependencies declared in the hook.
