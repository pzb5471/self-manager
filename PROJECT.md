# PROJECT

> 本文件用于每次对话的项目初始上下文。  
> 手动生成：`D:\\panzubin\\download\\Conda\\envs\\py311\\python.exe scripts/update_project_md.py`  
> 自动更新：`.githooks/post-commit`

## 1. 项目概述

- 项目名称：`self-manager`
- 项目类型：个人效能/任务管理系统
- 核心目标：支持多用户登录鉴权、任务隔离管理和四象限优先级管理
- 当前形态：`Streamlit` 单体应用 + `SQLite` 本地持久化

## 2. 技术栈

- 语言：`Python 3.11+`
- 前端/UI：`Streamlit`
- 数据存储：`SQLite3`
- 测试框架：`unittest`、`pytest`
- 依赖文件：`requirements.txt`

## 3. 架构说明

- 表现层：`app.py`
  - 登录/注册页面
  - 任务列表、添加、编辑页面
  - 搜索、筛选、排序、统计、分组视图
- 业务层：`service.py`（`TaskService`）
  - 认证流程（注册/登录/校验/登出）
  - 任务 CRUD，按 `user_id` 隔离
  - 输入校验、搜索、筛选、排序、统计聚合
  - SQLite 初始化与兼容迁移
- 数据层：`productivity_manager.db`
  - 表：`users`、`auth_tokens`、`tasks`

## 4. 已实现功能

- 用户与认证
  - 用户注册与登录
  - token 签发、校验、登出失效
  - 密码采用 `PBKDF2-HMAC-SHA256 + 随机盐`
  - token 以 `SHA-256` 哈希形式落库校验
- 任务管理
  - 新增/编辑/删除/查询任务
  - 清空当前用户任务
  - 多用户任务数据隔离
- 效能管理能力
  - 分类：工作/学习/生活/健康
  - 四象限：Q1-Q4
  - 关键词搜索（标题/描述）
  - 分类/象限筛选
  - 创建时间/更新时间排序（升降序）
  - 总数/分类/象限统计
  - 按象限、按分类分组展示
- 安全与稳定性
  - SQL 参数化防注入
  - 历史 `user_id IS NULL` 任务不会被自动认领

## 5. 测试现状

- 测试目录：`tests/unit`
- 测试文件数：`16`
- 覆盖范围：
  - 数据库初始化与索引
  - 注册/登录/鉴权/登出流程
  - token 哈希存储与过期处理
  - 任务 CRUD 与跨用户隔离
  - 参数校验与注入防护
  - 搜索/筛选/排序/统计/分组/清空

## 6. 运行方式

- 安装依赖：`pip install -r requirements.txt`
- 启动应用：`streamlit run app.py`
- 运行测试：
  - `python -m unittest discover -s tests/unit -p "test_app_unittest.py" -v`
  - `pytest tests/unit/test_app_pytest.py`

## 7. 仓库快照

- 生成时间（UTC）：`2026-04-19 10:59:11 UTC`
- Git 跟踪文件数：`97`
- 最近提交短哈希：`cd04a62`
- 最近提交时间：`2026-04-19 18:59:05 +0800`
- 最近提交摘要：`refactor: 服务层解耦与分层架构重构`
- 最近提交完整哈希：`cd04a6213fceecedc54104b51889a26e873bd58c`

## 8. Commit 后自动更新

- 生成脚本：`scripts/update_project_md.py`
- Hook：`.githooks/post-commit`
- 机制说明：
  - 每次 `git commit` 完成后，hook 自动刷新 `PROJECT.md`
  - 因为是 `post-commit`，刷新发生在提交之后，通常会形成新的工作区改动
  - 若要将最新 `PROJECT.md` 纳入版本库，请在下一次提交中包含该文件
