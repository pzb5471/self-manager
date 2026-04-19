# PROJECT

> 本文件用于每次对话的项目初始上下文。
> 手动生成：`python scripts/update_project_md.py`
> 自动更新：`.githooks/post-commit`

## 1. 项目概述

- 项目名称：`self-manager`
- 项目类型：个人效能/任务管理系统
- 核心目标：多用户登录鉴权、任务隔离、四象限优先级、习惯打卡、番茄钟、周报
- 当前形态：`FastAPI + H5 + SQLite` 单体应用

## 2. 技术栈

- 语言：Python 3.11+
- Web 框架：FastAPI + Uvicorn
- 前端：Vanilla JavaScript (H5)
- 数据存储：SQLite3
- 测试框架：pytest + httpx
- 日志：loguru
- 依赖文件：`requirements.txt`

## 3. 架构说明

```
路由层 (api/routes/)     → 请求解析、参数转换、响应格式化
    ↓
门面层 (service.py)      → TaskService 编排子服务、管理数据库连接
    ↓
子服务层 (services/)     → 各领域独立业务逻辑
    ↓
公共层 (services/common) → 纯函数：校验器、行映射器、日期/密码工具
    ↓
数据层 (services/schema) → SQLite 建表、迁移、索引管理
```

- 入口：`main.py` — FastAPI 应用创建与路由注册
- 门面：`service.py`（`TaskService`，约 620 行）— 编排所有子服务
- 子服务：
  - `services/auth_service.py` — 注册/登录/Token 校验
  - `services/category_service.py` — 分类 CRUD
  - `services/task_service.py` — 任务 CRUD、搜索、筛选、排序、统计、日历
  - `services/habit_service.py` — 工位打卡、手机克制、习惯仪表盘
  - `services/pomodoro_service.py` — 番茄钟记录与统计
  - `services/report_service.py` — 周报聚合
  - `services/stats_service.py` — 统计看板趋势数据
- 公共层：`services/common.py` — 校验器、行映射器、日期/密码工具函数
- 数据层：`services/schema.py` — 建表、列迁移、索引管理
- 数据库表：`users`、`auth_tokens`、`categories`、`tasks`、`workstation_checkins`、`phone_focus_records`、`pomodoro_sessions`

## 4. 已实现功能

- 用户与认证
  - 注册/登录/登出
  - PBKDF2-HMAC-SHA256 + 随机盐密码哈希
  - SHA-256 Token 哈希落库校验
- 任务管理
  - 新增/编辑/删除/完成状态切换
  - 四象限优先级、分类标签
  - 关键词搜索、分类/象限筛选、多维度排序
  - CSV 导入导出
  - 循环任务规则
  - 多用户数据隔离
- 分类管理
  - 默认四分类（工作/学习/生活/健康）
  - 自定义分类 CRUD
- 习惯打卡
  - 工位早/午/晚三次打卡
  - 手机克制记录
  - 连续满勤天数、成就徽章
- 番茄钟
  - 专注/短休/长休会话记录
  - 按日/按类型统计
- 统计看板
  - 任务趋势、分类分布
- 个人周报
  - 聚合任务/番茄/习惯数据与洞察文案
- 安全
  - SQL 参数化防注入
  - 输入校验与注入防护

## 5. 测试现状

- 测试目录：`tests/unit/` + `tests/integration/`
- 测试文件数：19
- 总测试用例：85
- 覆盖范围：
  - 数据库初始化、迁移与索引
  - 注册/登录/鉴权/登出流程
  - Token 哈希存储与过期处理
  - 任务 CRUD 与跨用户隔离
  - 分类 CRUD 与关联约束
  - 习惯打卡与手机克制
  - 番茄钟记录与统计
  - 周报聚合
  - 参数校验与安全防护

## 6. 运行方式

- 安装依赖：`pip install -r requirements.txt`
- 启动应用：`python -m uvicorn main:app --reload`
- 运行测试：`python -m pytest tests -q`
- API 文档：http://127.0.0.1:8000/docs
