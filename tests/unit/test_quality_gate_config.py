from pathlib import Path
import tomllib

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_pre_commit_uses_python_311_and_quality_hooks():
    config = load_yaml(PROJECT_ROOT / ".pre-commit-config.yaml")

    assert config["default_install_hook_types"] == ["pre-commit", "pre-push"]
    assert config["default_language_version"]["python"] == "python3.11"

    repos = config["repos"]
    flake8_hook = next(
        hook
        for repo in repos
        if repo["repo"] == "https://github.com/pycqa/flake8"
        for hook in repo["hooks"]
        if hook["id"] == "flake8"
    )
    black_hook = next(
        hook
        for repo in repos
        if repo["repo"] == "https://github.com/psf/black"
        for hook in repo["hooks"]
        if hook["id"] == "black"
    )
    pytest_hook = next(hook for hook in repos if hook["repo"] == "local")["hooks"][0]

    assert flake8_hook["args"] == ["--config=.flake8"]
    assert black_hook["language_version"] == "python3.11"
    assert black_hook["args"] == ["--config", "black.toml"]
    assert pytest_hook["entry"] == "python -m pytest tests -q"
    assert pytest_hook["stages"] == ["pre-push"]
    assert pytest_hook["additional_dependencies"] == ["-r requirements-dev.txt"]


def test_flake8_focuses_on_indentation_and_whitespace_rules():
    content = (PROJECT_ROOT / ".flake8").read_text(encoding="utf-8")

    assert "select = E1, E2, E3, E4, E7, E9, F63, F7, F82, W291, W293" in content
    assert ".pre-commit-cache-run-1" in content
    assert "max-line-length = 100" in content


def test_black_targets_python_311():
    config = tomllib.loads((PROJECT_ROOT / "black.toml").read_text(encoding="utf-8"))

    assert config["tool"]["black"]["target-version"] == ["py311"]
    assert config["tool"]["black"]["line-length"] == 100


def test_requirements_dev_include_quality_dependencies():
    content = (PROJECT_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in content
    assert "pre-commit>=" in content
    assert "black>=" in content
    assert "flake8>=" in content
    assert "PyYAML>=" in content


def test_gitignore_covers_virtualenv_cache_and_local_db():
    content = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".venv/" in content
    assert "venv/" in content
    assert ".pre-commit-cache/" in content
    assert ".pre-commit-cache-run-1/" in content
    assert "*.db" in content


def test_quality_docs_describe_local_and_gitee_go_usage():
    precommit_doc = (PROJECT_ROOT / "PRECOMMIT.md").read_text(encoding="utf-8")
    gitee_doc = (PROJECT_ROOT / "GITEE_GO.md").read_text(encoding="utf-8")

    assert "pre-push" in precommit_doc
    assert "flake8" in precommit_doc
    assert "black" in precommit_doc
    assert "pytest tests -q" in precommit_doc

    assert ".workflow/" in gitee_doc
    assert "`main`" in gitee_doc
    assert "唯一主分支" in gitee_doc
    assert "Python `3.11`" in gitee_doc
