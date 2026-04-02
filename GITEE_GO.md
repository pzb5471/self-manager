# Gitee Go 配置说明

当前仓库仅使用 `main` 分支，Gitee Go 已按以下规则配置：

- `pr-pipeline.yml`
  - 触发条件：PR 合并到 `main`
  - 执行内容：安装依赖、`flake8`、`black --check`、`pytest`
- `branch-pipeline.yml`
  - 保留为分支模板
  - 当前仓库只有 `main`，因此默认不会触发
- `main-pipeline.yml`
  - 触发条件：推送到 `main`
  - 执行内容：安装依赖、`flake8`、`black --check`、`pytest`

## Gitee 页面还需开启

1. `DevOps -> Gitee Go`
   从 `.workflow/` 创建或刷新流水线
2. `仓库设置 -> Pull Request / 代码评审`
   开启 PR 审核
3. `仓库设置 -> 保护分支`
   将 `main` 设为保护分支，并要求流水线成功后才允许合并
