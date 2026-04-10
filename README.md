# Self Manager

基于 `FastAPI + SQLite + H5` 的个人效能管理系统，支持多用户登录、任务四象限管理、日历视图、统计面板，以及 CSV 数据导入导出。

项目当前已接入统一开发质量门禁：

- `pre-commit`
- `flake8`
- `black`
- `pytest`
- Gitee Go `.workflow/` 流水线

## 功能概览

### 用户与认证

- 用户注册、登录、退出登录
- Bearer Token 鉴权
- 服务端保存 Token 哈希
- 支持 `remember_me`
- 多用户数据隔离

### 任务管理

- 新增、查询、编辑、删除任务
- 支持标题、描述、分类、四象限优先级
- 支持截止时间 `due_at`
- 支持重复规则 `none / daily / weekly / monthly`
- 支持完成状态切换
- 支持按关键字、分类、象限、状态、排序查询

### 分类管理

- 创建分类
- 编辑分类
- 删除分类
- 支持分类颜色配置
- 分类改名后自动同步到关联任务

### 日程与统计

- 今日任务与本周任务总览
- 日历视图
- 任务总数、完成数、未完成数统计
- 分类分布与象限分布统计
- 最近 14 天任务趋势

### 数据导入导出

- 导出全部任务为 CSV
- 支持将 CSV 再导回系统
- 导出文件可直接用于备份与迁移

## 技术栈

- Python 3.11
- FastAPI
- SQLite
- Vanilla JavaScript
- HTML5 / CSS3
- loguru
- pytest

## 项目结构

```text
self-manager/
|-- main.py                         # FastAPI 应用入口与 API 定义
|-- service.py                      # 核心业务逻辑与数据库访问
|-- logger_config.py                # 日志配置
|-- frontend/
|   |-- index.html                  # 前端页面
|   |-- styles.css                  # 前端样式
|   `-- app.js                      # 前端交互逻辑
|-- .workflow/
|   |-- pr-pipeline.yml             # PR 质量门禁
|   |-- branch-pipeline.yml         # 分支模板质量门禁
|   `-- main-pipeline.yml           # main 主干质量门禁
|-- tests/
|   |-- unit/                       # 单元测试
|   `-- integration/                # 集成测试
|-- PRECOMMIT.md                    # 本地质量门禁说明
|-- GITEE_GO.md                     # Gitee Go 启用说明
|-- .pre-commit-config.yaml         # pre-commit 配置
|-- .flake8                         # flake8 配置
|-- black.toml                      # black 配置
|-- pytest.ini                      # pytest 标记配置
|-- requirements.txt                # 运行时依赖
|-- requirements-dev.txt            # 开发与质量依赖
`-- app.py                          # 历史 Streamlit 入口
```

## 快速开始

### 1. 安装依赖

运行环境：

- 推荐 Python `3.11`
- Windows 下可直接使用本机 `py311` 环境

安装运行依赖：

```powershell
python -m pip install -r requirements.txt
```

如果要进行开发或执行质量检查，再安装开发依赖：

```powershell
python -m pip install -r requirements-dev.txt
```

### 2. 启动服务

```powershell
uvicorn main:app --reload
```

如果 `uvicorn` 不在 PATH 中：

```powershell
python -m uvicorn main:app --reload
```

### 3. 访问地址

- 首页: `http://127.0.0.1:8000/`
- OpenAPI 文档: `http://127.0.0.1:8000/docs`

## 环境变量

可通过环境变量指定数据库文件路径：

- `SELF_MANAGER_DB_PATH`

示例：

```powershell
$env:SELF_MANAGER_DB_PATH = ".\\data\\dev.db"
python -m uvicorn main:app --reload
```

默认数据库文件为：

```text
productivity_manager.db
```

## API 概览

### 认证接口

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### 分类接口

- `GET /api/meta/categories`
- `GET /api/categories`
- `POST /api/categories`
- `PUT /api/categories/{category_id}`
- `DELETE /api/categories/{category_id}`

### 任务接口

- `GET /api/tasks`
- `POST /api/tasks`
- `PUT /api/tasks/{task_id}`
- `DELETE /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}/status`
- `GET /api/tasks/export`
- `POST /api/tasks/import`

支持的查询参数：

- `keyword`
- `category`
- `quadrant`
- `status`
- `sort`

### 日程接口

- `GET /api/schedule/overview`
- `GET /api/schedule/calendar`

### 统计接口

- `GET /api/stats/dashboard`

## 测试

`pytest.ini` 已定义两个测试标记：

- `unit`
- `integration`

### 运行单元测试

```powershell
python -m pytest tests/unit -v
```

### 运行集成测试

```powershell
python -m pytest tests/integration -v
```

### 运行全量回归

```powershell
python -m pytest tests -q
```

当前已验证通过的测试基线：

- `77 passed`

### 新增功能测试清单

本轮新增功能已补齐对应测试，重点包括：

- 工位打卡与克制玩手机
  - [test_habit_service.py](d:/test/self-manager/tests/unit/test_habit_service.py)
  - [test_habit_api.py](d:/test/self-manager/tests/unit/test_habit_api.py)
  - [test_habit_integration.py](d:/test/self-manager/tests/integration/test_habit_integration.py)
- 番茄钟工作法
  - [test_pomodoro_service.py](d:/test/self-manager/tests/unit/test_pomodoro_service.py)
  - [test_pomodoro_api.py](d:/test/self-manager/tests/unit/test_pomodoro_api.py)
  - [test_pomodoro_regression.py](d:/test/self-manager/tests/unit/test_pomodoro_regression.py)
  - [test_pomodoro_integration.py](d:/test/self-manager/tests/integration/test_pomodoro_integration.py)
- 工程质量配置
  - [test_quality_gate_config.py](d:/test/self-manager/tests/unit/test_quality_gate_config.py)
  - [test_workflow_pipeline_config.py](d:/test/self-manager/tests/integration/test_workflow_pipeline_config.py)

## 本地质量门禁

仓库已集成以下本地质量检查：

- `flake8`：重点检查乱缩进、多余空格、行尾空白、基础语法错误
- `black`：统一 Python 代码格式
- `pytest`：在 `pre-push` 阶段执行自动化测试

安装并启用：

```powershell
python -m pip install -r requirements-dev.txt
pre-commit install --hook-type pre-commit --hook-type pre-push
pre-commit run --all-files
```

详细说明见 [PRECOMMIT.md](d:/test/self-manager/PRECOMMIT.md)。

## Gitee Go 流水线

仓库 `.workflow/` 目录下已提供：

- PR 质量门禁
- 分支模板质量门禁
- `main` 主干质量门禁

统一使用 Python `3.11`，并执行：

- `flake8`
- `black --check`
- `pytest tests -q`

详细启用方式见 [GITEE_GO.md](d:/test/self-manager/GITEE_GO.md)。

## 常见问题

### 1. `pytest` 或 `uvicorn` 命令不可用

优先使用：

```powershell
python -m pytest tests -q
python -m uvicorn main:app --reload
```

### 2. CSV 中文乱码

导出 CSV 时已带 UTF-8 BOM，通常可直接使用 Excel 打开。

### 3. 删除分类失败

如果分类下仍有关联任务，系统会阻止删除，需要先删除或迁移相关任务。

### 4. 本地出现 `.pytest_cache` 权限 warning

这类 warning 通常不影响测试通过，可忽略；如需避免，可在可写目录或虚拟环境下执行测试。

## 开发说明

- 核心业务逻辑集中在 `service.py`
- Web API 定义位于 `main.py`
- 前端页面位于 `frontend/`
- `app.py` 是历史 Streamlit 入口，当前主开发路径以 FastAPI + H5 为准

建议新增功能时遵循以下顺序：

1. 先补数据结构或数据库逻辑
2. 再补 service 层
3. 再补 API 层
4. 再补前端交互
5. 最后补齐单元测试、集成测试和质量配置测试
