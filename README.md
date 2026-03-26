# 个人效能管理系统（Self Manager）

基于 `FastAPI + SQLite + H5` 的个人任务管理系统，支持多用户登录、四象限任务管理、分类管理、任务完成状态筛选、统计分析、日志记录，以及完整的单元测试与集成测试。

## 1. 功能概览

### 1.1 用户与认证

- 用户注册、登录、退出登录
- Bearer Token 鉴权
- Token 服务端哈希存储
- `记住我` 登录：
  - 勾选时有效期 7 天
  - 不勾选时有效期 24 小时
- 多用户数据隔离

### 1.2 任务管理

- 任务新增、查询、编辑、删除
- 四象限管理：`Q1 ~ Q4`
- 任务支持关联分类
- 任务支持完成 / 未完成状态切换
- 已完成任务前端使用删除线样式显示
- 默认仅显示未完成任务

### 1.3 分类管理

- 支持创建分类
- 支持编辑分类
- 支持删除分类
- 每个分类包含：
  - 名称
  - 颜色
- 分类与任务关联，分类名修改后会同步更新关联任务

### 1.4 筛选与统计

- 按关键字搜索任务
- 按分类筛选任务
- 按象限筛选任务
- 按状态筛选任务：`全部 / 未完成 / 已完成`
- 支持组合筛选
- 支持按创建时间 / 更新时间排序
- 统计首页展示：
  - 总任务数
  - 未完成任务数
  - 已完成任务数
  - 分类分布
  - 四象限分布
  - 最近 14 天新增趋势

### 1.5 日志系统

- 使用 `loguru` 配置统一日志
- 日志同时输出到控制台和文件
- 日志文件使用 UTF-8 编码
- 日志格式包含：
  - 时间
  - 日志级别
  - 文件名
  - 行号
  - 日志消息
- 为数据库连接、初始化、增删改查、认证流程添加了日志记录

## 2. 技术栈

- Python 3.11+
- FastAPI
- SQLite
- Vanilla JavaScript
- HTML5 / CSS3
- loguru
- pytest

## 3. 项目结构

```text
self-manager/
├─ main.py                         # FastAPI 入口与接口定义
├─ service.py                      # 业务层、数据库访问、兼容迁移
├─ logger_config.py                # 日志配置
├─ frontend/
│  ├─ index.html                   # 前端页面结构
│  ├─ styles.css                   # 前端样式
│  └─ app.js                       # 前端交互逻辑
├─ tests/
│  ├─ unit/                        # 单元测试（内存数据库）
│  │  ├─ test_app_pytest.py
│  │  ├─ test_app_unittest.py
│  │  └─ test_fastapi_pytest.py
│  └─ integration/                 # 集成测试（文件数据库）
│     └─ test_task_integration.py
├─ pytest.ini                      # pytest 标记配置
├─ requirements.txt                # 依赖清单
├─ README.md
└─ app.py                          # 历史 Streamlit 入口
```

## 4. 快速开始

### 4.1 安装依赖

```bash
pip install -r requirements.txt
```

### 4.2 启动服务

```bash
uvicorn main:app --reload
```

### 4.3 访问地址

- 首页：`http://127.0.0.1:8000/`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`

## 5. 配置说明

支持通过环境变量指定数据库文件：

- `SELF_MANAGER_DB_PATH`：数据库路径，默认 `productivity_manager.db`

示例：

```powershell
$env:SELF_MANAGER_DB_PATH = "./data/dev.db"
uvicorn main:app --reload
```

## 6. API 概览

### 6.1 认证接口

- `POST /api/auth/register`：注册
- `POST /api/auth/login`：登录
- `POST /api/auth/logout`：退出登录
- `GET /api/auth/me`：获取当前用户

### 6.2 分类接口

- `GET /api/meta/categories`：获取分类元数据
- `GET /api/categories`：查询分类列表
- `POST /api/categories`：创建分类
- `PUT /api/categories/{category_id}`：编辑分类
- `DELETE /api/categories/{category_id}`：删除分类

### 6.3 任务接口

- `GET /api/tasks`：查询任务
  - 支持参数：`keyword`、`category`、`quadrant`、`status`、`sort`
- `POST /api/tasks`：新增任务
- `PUT /api/tasks/{task_id}`：编辑任务
- `DELETE /api/tasks/{task_id}`：删除任务
- `PATCH /api/tasks/{task_id}/status`：切换任务完成状态

### 6.4 统计接口

- `GET /api/stats/dashboard`：统计首页数据

## 7. 测试说明

### 7.1 单元测试

- 所有单元测试统一放置在 `tests/unit/`
- 使用内存数据库
- 覆盖 service 层与 FastAPI 层的核心增删改查与业务逻辑

运行全部单元测试：

```bash
pytest -m unit
```

### 7.2 集成测试

- 所有集成测试统一放置在 `tests/integration/`
- 使用测试数据库文件
- 当前已覆盖场景：
  - 完整任务生命周期
  - 分类筛选 / 象限筛选
  - 并发添加多个任务
  - 同一任务多种查询方式的数据一致性
  - 分类 + 象限组合筛选

运行全部集成测试：

```bash
pytest -m integration
```

### 7.3 运行全部测试

```bash
pytest
```

## 8. 日志文件

- 默认日志文件：`logs/self-manager.log`
- 日志会在应用启动时自动创建目录并写入

## 9. 常见问题

- `uvicorn` 命令不可用
  - 使用 `python -m uvicorn main:app --reload`
- 出现 `.pytest_cache` 权限 warning
  - 不影响测试通过，可忽略
- 创建分类后任务下拉未更新
  - 重新进入任务页或刷新页面即可重新拉取分类

## 10. 开发说明

- 任务、分类、认证逻辑统一放在 `service.py`
- 新增字段时建议先补数据库迁移，再补接口、前端和测试
- 提交前建议至少运行：

```bash
pytest -m unit
pytest -m integration
```
