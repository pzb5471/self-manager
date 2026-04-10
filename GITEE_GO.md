# Gitee Go 流水线启用说明

仓库的流水线配置位于 `.workflow/` 目录，并统一升级为 Python `3.11`。

## 流水线文件

- `pr-pipeline.yml`
  - 用于 PR 合并到 `main` 前的质量门禁
- `branch-pipeline.yml`
  - 用于 `feature/*`、`bugfix/*`、`hotfix/*`、`release/*` 分支的推送检查模板
- `main-pipeline.yml`
  - 用于 `main` 主干推送后的最终质量门禁

三条流水线都会执行以下步骤：

- 安装 `requirements-dev.txt`
- 执行 `flake8 --config=.flake8`
- 执行 `black --check --config black.toml`
- 执行 `pytest tests -q`

## 仓库分支策略

- `main` 是唯一主分支
- 所有功能分支通过 PR 合并到 `main`
- 建议在 Gitee 仓库设置中将 `main` 配置为保护分支，并要求流水线成功后才能合并

## 在 Gitee 页面启用

1. 进入 `DevOps -> Gitee Go`
2. 选择从仓库 `.workflow/` 目录创建或刷新流水线
3. 分别启用 PR、分支模板、main 主干三条流水线
4. 进入 `仓库设置 -> 保护分支`，将 `main` 设置为唯一受保护主分支
