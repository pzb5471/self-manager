from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = PROJECT_ROOT / ".workflow"


def load_pipeline(name: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))


def step_commands(pipeline: dict) -> list[str]:
    return pipeline["stages"][0]["stage"]["steps"][0]["commands"]


def test_workflow_directory_contains_expected_quality_gate_pipelines():
    expected = {"pr-pipeline.yml", "branch-pipeline.yml", "main-pipeline.yml"}
    actual = {path.name for path in WORKFLOW_DIR.glob("*.yml")}
    assert expected.issubset(actual)


def test_pr_pipeline_targets_main_pull_requests():
    pipeline = load_pipeline("pr-pipeline.yml")

    assert pipeline["name"] == "pr-quality-gate"
    assert pipeline["triggers"]["pr"]["branches"]["include"] == ["main"]
    assert pipeline["stages"][0]["stage"]["steps"][0]["pythonVersion"] == "3.11"
    assert step_commands(pipeline) == [
        "python3 -m pip install --upgrade pip",
        "pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple",
        "pip3 install -r requirements-dev.txt",
        "python3 -m flake8 --config=.flake8 .",
        "python3 -m black --check . --config black.toml",
        "python3 -m pytest tests -q",
    ]


def test_branch_pipeline_is_template_for_non_main_branches():
    pipeline = load_pipeline("branch-pipeline.yml")
    branches = pipeline["triggers"]["push"]["branches"]

    assert pipeline["name"] == "branch-quality-template"
    assert branches["exclude"] == ["main"]
    assert branches["include"] == ["feature/*", "bugfix/*", "hotfix/*", "release/*"]
    assert pipeline["stages"][0]["stage"]["steps"][0]["pythonVersion"] == "3.11"


def test_main_pipeline_is_the_only_mainline_quality_gate():
    pipeline = load_pipeline("main-pipeline.yml")

    assert pipeline["name"] == "main-quality-gate"
    assert pipeline["triggers"]["push"]["branches"]["include"] == ["main"]
    assert pipeline["stages"][0]["stage"]["steps"][0]["pythonVersion"] == "3.11"
    assert "main主干质量门禁" in pipeline["displayName"]
