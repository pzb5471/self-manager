# 个人效能管理系统（Self Manager）

基于 `FastAPI + SQLite + H5` 的任务管理应用，支持用户注册登录、四象限任务管理、图表化统计与多用户数据隔离。

## 1. 项目亮点

- 认证与安全
  - 用户注册、登录、退出
  - Token 鉴权（服务端哈希存储）
  - `记住我` 支持：
    - 勾选：Token 有效期 7 天
    - 不勾选：Token 有效期 24 小时
- 任务管理
  - 新增、编辑、删除、查询
  - 按 `user_id` 严格隔离数据
  - 分类：`工作 / 学习 / 生活 / 健康`
  - 四象限：`Q1~Q4`
- 可视化与交互
  - 统计首页（总量、分类分布、象限分布、14 天趋势）
  - 点击统计项可跳转到任务页并自动筛选
  - 四象限坐标展示（横轴：重要，纵轴：紧急）
- 测试保障
  - `pytest` 覆盖 service 层与 FastAPI 接口

## 2. 技术栈

- Python 3.11+
- FastAPI
- SQLite3
- H5 + Vanilla JavaScript + CSS
- pytest

## 3. 项目结构

```text
self-manager/
├─ main.py                         # FastAPI 入口（API + H5 静态页面）
├─ service.py                      # 业务层与 SQLite 访问（含鉴权）
├─ frontend/
│  ├─ index.html                   # 前端页面结构
│  ├─ styles.css                   # UI 样式
│  └─ app.js                       # 前端状态与交互逻辑
├─ requirements.txt                # 依赖清单
├─ productivity_manager.db         # 默认数据库（运行后生成）
├─ tests/
│  └─ unit/
│     ├─ test_app_pytest.py        # service 层 pytest
│     ├─ test_fastapi_pytest.py    # API 层 pytest
│     └─ test_app_unittest.py      # 历史 unittest
└─ app.py                          # 历史 Streamlit 版本入口（已非主入口）
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

- H5 页面：`http://127.0.0.1:8000/`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`

## 5. 配置说明

支持通过环境变量指定数据库文件：

- `SELF_MANAGER_DB_PATH`：数据库路径（默认 `productivity_manager.db`）

示例：

```bash
# Windows PowerShell
$env:SELF_MANAGER_DB_PATH = "./data/dev.db"
uvicorn main:app --reload
```

## 6. API 概览

### 6.1 认证

- `POST /api/auth/register` 注册
- `POST /api/auth/login` 登录（支持 `remember_me`）
- `POST /api/auth/logout` 退出登录
- `GET /api/auth/me` 当前用户

### 6.2 元数据

- `GET /api/meta/categories` 获取分类

### 6.3 任务

- `GET /api/tasks` 查询任务（支持 `keyword/category/quadrant/sort`）
- `POST /api/tasks` 新增任务
- `PUT /api/tasks/{task_id}` 更新任务
- `DELETE /api/tasks/{task_id}` 删除任务

### 6.4 统计

- `GET /api/stats/dashboard` 统计首页数据

## 7. 测试

### 7.1 运行全部 pytest（推荐）

```bash
pytest tests/unit/test_app_pytest.py tests/unit/test_fastapi_pytest.py
```

### 7.2 单独运行

```bash
pytest tests/unit/test_app_pytest.py
pytest tests/unit/test_fastapi_pytest.py
```

## 8. 常见问题

- 启动后无法访问页面
  - 检查是否使用 `uvicorn main:app --reload`
  - 检查端口 `8000` 是否被占用
- pytest 出现 `.pytest_cache` 权限 warning
  - 不影响测试通过，可忽略
- `uvicorn` 命令不可用
  - 使用 `python -m uvicorn main:app --reload`

## 9. 开发建议

- 若新增字段（如独立“重要/紧急分值”），优先在 `service.py` 增加校验与迁移，再补 API 和前端。
- 每次改动建议同步补充 `tests/unit/` 对应用例，确保回归稳定。
