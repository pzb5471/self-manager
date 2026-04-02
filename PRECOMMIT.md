# Pre-commit 使用说明

本仓库使用 `pre-commit` 作为本地质量门禁统一入口，Python 环境固定为 3.11。

## 已接入工具

- `flake8`
  - 代码风格检查
  - 严格检查乱缩进、多余空格等问题
- `black`
  - 自动格式化 Python 代码排版
- `pytest`
  - 在 `pre-push` 阶段执行自动化测试

## 安装与启用

```powershell
python -m pip install -r requirements-dev.txt
pre-commit install --hook-type pre-commit --hook-type pre-push
pre-commit run --all-files
```

## 触发时机

- `pre-commit`
  - 运行通用文件检查
  - 运行 `flake8`
  - 运行 `black`
- `pre-push`
  - 运行 `pytest tests -q`
