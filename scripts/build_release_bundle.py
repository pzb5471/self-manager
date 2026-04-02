from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
TIMESTAMP = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
ARCHIVE_PATH = DIST_DIR / f"self-manager-{TIMESTAMP}.zip"

INCLUDE_PATHS = [
    ".githooks",
    ".pre-commit-config.yaml",
    ".flake8",
    "black.toml",
    "pyproject.toml",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
    "PRECOMMIT.md",
    "PROJECT.md",
    "README.md",
    "app.py",
    "logger_config.py",
    "main.py",
    "service.py",
    "frontend",
    "scripts",
]

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".oscanner",
    ".pre-commit-cache",
    ".pytest_cache",
    ".venv",
    "dist",
    "logs",
    "venv",
}

EXCLUDE_FILES = {
    "productivity_manager.db",
}


def iter_files(path: Path):
    if path.is_file():
        yield path
        return

    for child in path.rglob("*"):
        if child.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in child.parts):
            continue
        if child.name in EXCLUDE_FILES:
            continue
        yield child


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as archive:
        for relative in INCLUDE_PATHS:
            source = ROOT / relative
            if not source.exists():
                continue
            for file_path in iter_files(source):
                archive.write(file_path, file_path.relative_to(ROOT))

    print(f"Created build artifact: {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
