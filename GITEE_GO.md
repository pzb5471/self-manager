# Gitee Go Setup

This repository is prepared for Gitee Go with:

- PR quality gate in `.workflow/pr-pipeline.yml`
- branch package build in `.workflow/branch-pipeline.yml`
- main release package build in `.workflow/main-pipeline.yml`

## What Runs

- PR to `main`
  - install dependencies
  - `black --check`
  - `ruff check`
  - `pytest tests -q`
- push to non-`main` branch
  - run the same checks
  - create a zip package in `dist/`
  - upload the package as a cloud artifact
- push to `main`
  - run the same checks
  - create a zip package in `dist/`
  - upload the package as a cloud artifact
  - publish the uploaded package as a release artifact

## Gitee UI Steps Required

Repository YAML alone is not enough to block merges. In Gitee, also enable:

1. `DevOps -> Gitee Go`
   Create or refresh the three pipelines from `.workflow/`.
2. `Repository Settings -> Pull Request / Code Review`
   Require PR review before merge.
3. `Repository Settings -> Protected Branches`
   Protect `main` and require pipeline success before merge if your edition exposes this option.

## Sources

- Gitee Go quick start: https://gitee.com/help/articles/4293
- Gitee Go YAML format: https://gitee.com/help/articles/4292
- Gitee pipeline triggers: https://gitee.com/help/articles/4358
