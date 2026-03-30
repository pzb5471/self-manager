# 个人效能管理系统（Self Manager）

基于 `FastAPI + SQLite + H5` 的个人任务管理系统，支持多用户登录、任务优先级管理、日历与列表视图、CSV 数据备份恢复，以及完整的单元测试与集成测试。

## 1. 功能概览

### 1.1 用户与认证

- 用户注册、登录、退出登录
- Bearer Token 鉴权
- Token 服务端哈希存储
- 支持“记住我”
- 多用户数据隔离

### 1.2 任务管理

- 新增、查询、编辑、删除任务
- 支持任务标题、描述、分类、四象限优先级
- 支持截止日期时间
- 支持重复日程：`none / daily / weekly / monthly`
- 支持完成 / 未完成切换
- 支持剩余时间与逾期提醒

### 1.3 视图与交互

- 登录后默认进入“首页”工作台
- 首页支持三种视图切换：
  - 列表视图
  - 四象限视图
  - 日历视图
- 列表视图包含：
  - 今日任务
  - 本周任务
  - 全部任务
- 日历视图支持点击日期直接新增任务
- 新增 / 编辑任务使用弹窗表单
- 删除任务带二次确认

### 1.4 分类管理

- 创建分类
- 编辑分类
- 删除分类
- 分类颜色管理
- 分类与任务关联，分类改名后会同步到关联任务

### 1.5 统计与概览

- 任务统计页
- 总任务数、未完成数、已完成数
- 分类分布
- 优先级分布
- 近 14 天任务新增趋势

### 1.6 数据导入导出

- 导出全部任务为 CSV 文件
- CSV 可直接用 Excel 打开
- 支持使用导出的 CSV 重新导入系统
- 可作为任务数据备份与恢复方案

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
├─ main.py                             # FastAPI 入口与接口定义
├─ service.py                          # 业务逻辑、数据库访问、兼容迁移
├─ logger_config.py                    # 日志配置
├─ frontend/
│  ├─ index.html                       # 前端页面结构
│  ├─ styles.css                       # 前端样式
│  └─ app.js                           # 前端交互逻辑
├─ tests/
│  ├─ unit/                            # 单元测试
│  │  ├─ test_app_pytest.py
│  │  ├─ test_app_unittest.py
│  │  ├─ test_fastapi_pytest.py
│  │  └─ test_regression_baseline.py
│  └─ integration/                     # 集成测试
│     ├─ test_task_integration.py
│     └─ test_regression_workflow.py
├─ features/
│  ├─ 4.2.md                           # 测试用例库与回归测试记录
│  ├─ 4.2-quick-regression.txt         # 快速回归日志
│  └─ 4.2-full-regression.txt          # 完整回归日志
├─ pytest.ini                          # pytest 标记配置
├─ requirements.txt                    # 依赖清单
├─ README.md
└─ app.py                              # 历史 Streamlit 入口
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

## 5. 环境配置

支持通过环境变量指定数据库路径：

- `SELF_MANAGER_DB_PATH`：数据库文件路径，默认 `productivity_manager.db`

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
- `POST /api/tasks`：新增任务
- `PUT /api/tasks/{task_id}`：编辑任务
- `DELETE /api/tasks/{task_id}`：删除任务
- `PATCH /api/tasks/{task_id}/status`：切换完成状态
- `GET /api/tasks/export`：导出任务 CSV
- `POST /api/tasks/import`：导入任务 CSV

支持参数：

- `keyword`
- `category`
- `quadrant`
- `status`
- `sort`

### 6.4 日程接口

- `GET /api/schedule/overview`：获取今日 / 本周任务概览
- `GET /api/schedule/calendar`：获取日历视图数据

### 6.5 统计接口

- `GET /api/stats/dashboard`：获取任务统计数据

## 7. 测试说明

### 7.1 pytest 标记

`pytest.ini` 已定义：

- `unit`
- `integration`

### 7.2 单元测试

单元测试位于 `tests/unit/`，覆盖：

- 任务 CRUD
- 参数校验
- 截止时间与重复日程
- 统计、筛选、搜索、排序
- CSV 导入导出
- 鉴权与 token 处理

运行命令：

```bash
pytest tests/unit/ -v
```

### 7.3 集成测试

集成测试位于 `tests/integration/`，覆盖：

- 完整任务生命周期
- 分类与象限筛选流程
- 日程概览与日历流程
- CSV 备份导出与导入恢复
- 回归基线工作流

运行命令：

```bash
pytest tests/integration/ -v
```

### 7.4 完整回归测试

```bash
pytest tests/ -v
```

### 7.5 回归测试记录

本项目已建立测试用例库与回归执行记录，见：

- [4.2.md](/d:/test/self-manager/features/4.2.md)
- [4.2-quick-regression.txt](/d:/test/self-manager/features/4.2-quick-regression.txt)
- [4.2-full-regression.txt](/d:/test/self-manager/features/4.2-full-regression.txt)

## 8. 运行结果参考

当前回归基线：

- 快速回归：`45 passed`
- 完整回归：`54 passed`

说明：

- 测试运行中可能出现 `.pytest_cache` 权限 warning
- 该 warning 不影响测试通过，可忽略

## 9. 常见问题

- `uvicorn` 命令不可用
  - 使用 `python -m uvicorn main:app --reload`
- Excel 打开 CSV 中文乱码
  - 当前导出文件已带 UTF-8 BOM，通常可直接正常打开
- 导入 CSV 失败
  - 请确认 CSV 至少包含这些列：
    - `title`
    - `description`
    - `category`
    - `quadrant`
    - `completed`
    - `due_at`
    - `recurrence_rule`
- 分类删除失败
  - 如果分类下仍有关联任务，系统会阻止删除

## 10. 开发说明

- 核心业务逻辑集中在 `service.py`
- Web API 在 `main.py`
- 当前主前端为 `frontend/` 下的 H5 页面
- `app.py` 为历史 Streamlit 入口，已做基础同步，但主开发路径建议以 FastAPI + H5 为准

新增功能建议遵循以下流程：

1. 先补数据库字段或迁移逻辑
2. 再补 service 层与 API
3. 再补前端交互
4. 最后补单元测试与集成测试
5. 执行快速回归与完整回归
