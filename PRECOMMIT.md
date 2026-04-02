# Pre-commit Quality Gate

This repository now includes a Python 3.11 quality gate for local Git hooks and CI.

## Scope

- `pre-commit`
  - `black` format
  - `ruff` lint
- `pre-push`
  - `pytest tests -q`

## Recommended Setup

Create and activate a Python 3.11 virtual environment first, then run:

```powershell
python -m pip install -r requirements-dev.txt
git config core.hooksPath .githooks
```

## Notes

- The repository keeps `.pre-commit-config.yaml` as the shared quality-gate definition for CI and optional manual runs.
- Git hooks are executed from `.githooks/` instead of `.git/hooks/`.
- The local `pre-commit` hook formats staged Python files with `black` and applies `ruff --fix`.
- The local `pre-push` hook runs `pytest tests -q`.
