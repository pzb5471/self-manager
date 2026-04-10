# pre-commit 本地质量门禁说明

本仓库统一使用 `pre-commit` 作为本地质量门禁入口，默认 Python 版本为 `3.11`。

## 已启用的检查

- `check-yaml`、`check-merge-conflict`、`end-of-file-fixer`、`trailing-whitespace`
- `flake8`
  - 重点检查乱缩进、语法错误、多余空格、行尾空白等基础代码风格问题
- `black`
  - 自动统一 Python 代码排版
- `pytest`
  - 在 `pre-push` 阶段执行 `pytest tests -q`，阻止未通过测试的代码被推送

## 本地安装

```powershell
python -m pip install -r requirements-dev.txt
pre-commit install --hook-type pre-commit --hook-type pre-push
```

## 常用命令

```powershell
pre-commit run --all-files
pre-commit run flake8 --all-files
pre-commit run black --all-files
pre-commit run pytest-quality-gate --hook-stage pre-push
```

## 触发时机

- `pre-commit`
  - 执行通用文件检查
  - 执行 `flake8`
  - 执行 `black`
- `pre-push`
  - 执行 `pytest tests -q`
