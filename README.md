# Self Manager

基于 `FastAPI + SQLite + H5` 的个人效能管理系统，支持多用户登录、任务管理、工位打卡、番茄钟、统计看板，以及个人统计周报。

## 功能概览

- **认证** — 用户注册、登录、登出，Bearer Token 鉴权，PBKDF2 密码哈希 + SHA-256 Token 哈希落库
- **任务管理** — 四象限优先级、分类标签、搜索筛选排序、CSV 导入导出、循环任务
- **日程视图** — 日程总览与未来日历
- **习惯打卡** — 工位早/午/晚三次打卡、手机克制记录、连续满勤天数、成就徽章
- **番茄钟** — 专注/短休/长休会话记录、按日/按类型统计
- **统计看板** — 任务趋势、分类分布、仪表盘概览
- **周报** — 聚合任务、番茄、习惯数据与洞察文案，接口契约见 [features/weekly-report-api.md](features/weekly-report-api.md)

## 技术栈

- Python 3.11
- FastAPI + Uvicorn
- SQLite3
- Vanilla JavaScript (H5)
- pytest + httpx
- loguru

## 项目结构

```
self-manager/
├── main.py                  # FastAPI 入口，路由注册
├── service.py               # 服务层门面（TaskService），编排子服务
├── logger_config.py         # loguru 日志配置
├── api/
│   ├── deps.py              # 鉴权依赖注入
│   ├── schemas.py           # 请求/响应 Pydantic 模型
│   └── routes/
│       ├── auth.py          # 认证路由
│       ├── categories.py    # 分类路由
│       ├── tasks.py         # 任务路由
│       ├── habits.py        # 习惯打卡路由
│       ├── pomodoro.py      # 番茄钟路由
│       ├── schedule.py      # 日程路由
│       ├── stats.py         # 统计路由
│       └── reports.py       # 周报路由
├── services/
│   ├── common.py            # 共享纯函数（校验器、行映射器、日期工具）
│   ├── schema.py            # 数据库建表、迁移、索引
│   ├── auth_service.py      # 认证服务
│   ├── category_service.py  # 分类服务
│   ├── task_service.py      # 任务服务
│   ├── habit_service.py     # 习惯打卡服务
│   ├── pomodoro_service.py  # 番茄钟服务
│   ├── report_service.py    # 周报服务
│   └── stats_service.py     # 统计看板服务
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
│   ├── unit/                # 14 个单元测试文件
│   └── integration/         # 5 个集成测试文件
├── agents/                  # 多智能体角色定义
├── skills/                  # 可复用技能模板
├── features/                # 功能需求与接口契约
├── scripts/                 # 工具脚本
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── PROJECT.md
```

### 架构分层

```
路由层 (api/routes/)     → 请求解析、参数转换、响应格式化
    ↓
门面层 (service.py)      → TaskService 编排所有子服务、管理数据库连接
    ↓
子服务层 (services/)     → 各领域独立业务逻辑
    ↓
公共层 (services/common) → 纯函数：校验器、行映射器、日期/密码工具
    ↓
数据层 (services/schema) → SQLite 建表、迁移、索引管理
```

## 快速开始

### 1. 安装依赖

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt   # 可选，开发/测试用
```

### 2. 启动服务

```powershell
cd D:\test\self-manager
python -m uvicorn main:app --reload
```

- 首页：http://127.0.0.1:8000/
- API 文档：http://127.0.0.1:8000/docs

### 3. 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SELF_MANAGER_DB_PATH` | SQLite 数据库路径 | `productivity_manager.db` |

```powershell
$env:SELF_MANAGER_DB_PATH = ".\data\dev.db"
python -m uvicorn main:app --reload
```

## API 接口

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前用户 |

### 分类

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/categories` | 分类列表 |
| POST | `/api/categories` | 创建分类 |
| PUT | `/api/categories/{id}` | 更新分类 |
| DELETE | `/api/categories/{id}` | 删除分类 |

### 任务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tasks` | 任务列表（支持搜索/筛选/排序） |
| POST | `/api/tasks` | 创建任务 |
| PUT | `/api/tasks/{id}` | 更新任务 |
| DELETE | `/api/tasks/{id}` | 删除任务 |
| PATCH | `/api/tasks/{id}/status` | 切换完成状态 |
| GET | `/api/tasks/export` | 导出 CSV |
| POST | `/api/tasks/import` | 导入 CSV |

### 习惯与专注

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/habits/dashboard` | 习惯仪表盘 |
| GET | `/api/habits/checkins` | 打卡记录 |
| POST | `/api/habits/checkins` | 工位打卡 |
| GET | `/api/habits/phone-focus` | 手机克制记录 |
| POST | `/api/habits/phone-focus` | 记录克制 |
| GET | `/api/pomodoro/sessions` | 番茄钟记录 |
| POST | `/api/pomodoro/sessions` | 记录番茄钟 |
| GET | `/api/pomodoro/stats` | 番茄钟统计 |

### 统计与周报

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats/dashboard` | 统计看板 |
| GET | `/api/schedule/overview` | 日程总览 |
| GET | `/api/schedule/calendar` | 日历视图 |
| GET | `/api/reports/weekly` | 个人周报 |

## 测试

```powershell
# 全量测试
python -m pytest tests -q

# 仅单元测试
python -m pytest tests/unit -v

# 仅集成测试
python -m pytest tests/integration -v
```

## 质量门禁

```powershell
# 代码检查
pre-commit run --all-files

# 测试
python -m pytest tests -q
```

仓库已配置：`pre-commit` + `flake8` + `black` + `pytest`，CI 流水线见 `.workflow/`。

## 多智能体协作

- `agents/` — 角色定义（frontend-architect、backend-architect）
- `skills/` — 可复用技能模板（code-review-expert、unit-test-generator、feature-delivery）

协作流程采用"接口先行"模式：先定义 API 契约，再交给前后端角色并行开发，最后统一集成验证。
