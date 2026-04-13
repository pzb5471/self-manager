# Self Manager

基于 `FastAPI + SQLite + H5` 的个人效能管理系统，支持多用户登录、任务管理、工位打卡、番茄钟、统计看板，以及个人统计周报。

## 功能概览

- 用户注册、登录、登出、Bearer Token 鉴权
- 任务新增、编辑、删除、完成状态切换
- 四象限任务管理、分类管理、搜索筛选与排序
- 日程总览与未来日历视图
- 工位打卡与克制玩手机记录
- 番茄钟记录与专注统计
- 任务 CSV 导入导出
- 个人统计周报
  - 统一接口：`GET /api/reports/weekly`
  - 聚合任务、番茄、习惯与洞察文案
  - 前后端按接口契约并行开发

## 技术栈

- Python `3.11`
- FastAPI
- SQLite
- Vanilla JavaScript
- HTML5 / CSS3
- pytest
- loguru

## 项目结构

```text
self-manager/
|-- main.py
|-- service.py
|-- app.py
|-- logger_config.py
|-- frontend/
|   |-- index.html
|   |-- app.js
|   `-- styles.css
|-- tests/
|   |-- unit/
|   `-- integration/
|-- features/
|   |-- weekly-report-api.md
|   `-- weekly-report-agent-context.md
|-- agents/
|   |-- README.md
|   |-- frontend-architect/
|   `-- backend-architect/
|-- skills/
|   `-- code-review-expert/
|-- scripts/
|-- requirements.txt
|-- requirements-dev.txt
|-- pytest.ini
|-- PROJECT.md
`-- README.md
```

## 快速开始

### 1. 安装依赖

推荐使用 Python `3.11`。

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

如果本机已有 Conda `py311` 环境，也可以直接使用对应解释器。

### 2. 启动服务

```powershell
python -m uvicorn main:app --reload
```

访问地址：

- 首页：`http://127.0.0.1:8000/`
- OpenAPI：`http://127.0.0.1:8000/docs`

### 3. 可选环境变量

- `SELF_MANAGER_DB_PATH`

示例：

```powershell
$env:SELF_MANAGER_DB_PATH = ".\\data\\dev.db"
python -m uvicorn main:app --reload
```

## 主要接口

### 认证

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### 分类

- `GET /api/meta/categories`
- `GET /api/categories`
- `POST /api/categories`
- `PUT /api/categories/{category_id}`
- `DELETE /api/categories/{category_id}`

### 任务

- `GET /api/tasks`
- `POST /api/tasks`
- `PUT /api/tasks/{task_id}`
- `DELETE /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}/status`
- `GET /api/tasks/export`
- `POST /api/tasks/import`

### 习惯与专注

- `GET /api/habits/dashboard`
- `GET /api/habits/checkins`
- `POST /api/habits/checkins`
- `GET /api/habits/phone-focus`
- `POST /api/habits/phone-focus`
- `GET /api/pomodoro/sessions`
- `POST /api/pomodoro/sessions`
- `GET /api/pomodoro/stats`

### 统计与周报

- `GET /api/stats/dashboard`
- `GET /api/reports/weekly`

周报接口契约文档见 [features/weekly-report-api.md](/d:/test/self-manager/features/weekly-report-api.md)。

## 测试

运行单元测试：

```powershell
python -m pytest tests/unit -v
```

运行集成测试：

```powershell
python -m pytest tests/integration -v
```

运行全量测试：

```powershell
python -m pytest tests -q
```

本轮周报功能验证过的命令：

```powershell
D:\panzubin\download\Conda\envs\py311\python.exe -m pytest tests\unit\test_weekly_report.py tests\unit\test_fastapi_pytest.py tests\unit\test_habit_api.py tests\unit\test_habit_service.py tests\unit\test_pomodoro_api.py tests\unit\test_pomodoro_service.py
node --check frontend\app.js
```

## 质量门禁

仓库已接入以下质量检查：

- `pre-commit`
- `flake8`
- `black`
- `pytest`
- Gitee Go `.workflow/`

可本地执行：

```powershell
pre-commit run --all-files
python -m pytest tests -q
```

## 多智能体协作

仓库内置了可复用的角色定义与技能说明：

- `agents/`
  - 面向“谁来负责什么”
  - 当前包含 `frontend-architect`、`backend-architect`
- `skills/`
  - 面向“如何完成某类任务”
  - 当前包含 `code-review-expert` 等能力模板

本次“个人统计周报”功能采用了“接口先行”的协作模式：

1. 先定义统一 API 契约
2. 再将契约交给前后端角色并行开发
3. 最后统一集成、补测、验证

协作记录见 [features/weekly-report-agent-context.md](/d:/test/self-manager/features/weekly-report-agent-context.md)。

## 说明

- `main.py` 是当前 FastAPI 主入口
- `service.py` 是核心业务与数据访问层
- `frontend/` 是当前主前端实现
- `app.py` 为历史 Streamlit 入口，当前主开发链路以 FastAPI + H5 为准
