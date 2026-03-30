# PROJECT

> 本文件用于快速建立当前项目上下文，偏向开发者视角的项目快照。  
> 当前主开发路径：`FastAPI + SQLite + H5`。  
> 历史入口 `app.py` 仍保留，但不再是主交互入口。

## 1. 项目概述

- 项目名称：`self-manager`
- 项目类型：个人效能与任务管理系统
- 核心目标：
  - 支持多用户认证与数据隔离
  - 支持任务全生命周期管理
  - 支持四象限优先级与日程视图
  - 支持 CSV 数据备份与恢复
  - 建立可复用的测试用例库与回归测试流程

## 2. 当前主架构

### 后端

- 入口：[main.py](/d:/test/self-manager/main.py)
- 框架：FastAPI
- 主要职责：
  - 用户认证
  - 分类管理
  - 任务 CRUD
  - 任务状态切换
  - 日程概览 / 日历数据
  - CSV 导入导出
  - 统计接口

### 业务层

- 核心文件：[service.py](/d:/test/self-manager/service.py)
- 核心类：`TaskService`
- 主要职责：
  - SQLite 初始化与兼容迁移
  - 用户、Token、分类、任务的业务逻辑
  - 截止时间与重复日程规则
  - 日历 / 概览展开逻辑
  - CSV 导出与导入恢复

### 前端

- 入口页面：[frontend/index.html](/d:/test/self-manager/frontend/index.html)
- 交互逻辑：[frontend/app.js](/d:/test/self-manager/frontend/app.js)
- 样式文件：[frontend/styles.css](/d:/test/self-manager/frontend/styles.css)
- 当前主页面结构：
  - 首页：任务工作台
  - 分类管理
  - 任务统计

### 历史入口

- [app.py](/d:/test/self-manager/app.py)
- 说明：历史 Streamlit 入口，已做基础功能同步，但主开发不建议继续以它为中心扩展

## 3. 数据模型

### users

- 用户基本信息

### auth_tokens

- Bearer Token 持久化
- 服务端使用哈希值校验

### categories

- 用户自定义分类
- 字段包含：名称、颜色

### tasks

- 任务核心字段：
  - `title`
  - `description`
  - `category`
  - `quadrant`
  - `completed`
  - `due_at`
  - `recurrence_rule`
  - `created_at`
  - `updated_at`

## 4. 当前已实现能力

### 用户与安全

- 注册 / 登录 / 退出
- Bearer Token 鉴权
- Token 哈希存储
- 多用户数据隔离

### 任务能力

- 新增、编辑、删除、查询任务
- 完成状态切换
- 截止时间
- 剩余时间 / 逾期提醒
- 重复日程：
  - `none`
  - `daily`
  - `weekly`
  - `monthly`

### 页面与交互

- 首页整合三视图：
  - 列表视图
  - 四象限视图
  - 日历视图
- 统一状态筛选：
  - 未完成
  - 全部
  - 已完成
- 统一搜索、分类、排序
- 弹窗新增 / 编辑任务
- 删除任务二次确认
- 日历点击日期直接新增任务

### 日程能力

- 今日任务
- 本周任务
- 日历展开重复任务
- 空截止时间安全处理

### 统计能力

- 总任务数
- 未完成数
- 已完成数
- 分类分布
- 四象限分布
- 近 14 天新增趋势

### 数据备份能力

- 导出全部任务为 CSV
- CSV 可直接被 Excel 打开
- 支持 CSV 导入恢复

## 5. API 速览

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

### 日程

- `GET /api/schedule/overview`
- `GET /api/schedule/calendar`

### 统计

- `GET /api/stats/dashboard`

## 6. 测试现状

### 测试目录

- 单元测试：[tests/unit](/d:/test/self-manager/tests/unit)
- 集成测试：[tests/integration](/d:/test/self-manager/tests/integration)

### 基线测试

- 单元测试：
  - [test_regression_baseline.py](/d:/test/self-manager/tests/unit/test_regression_baseline.py)
  - 包含：`test_add_task`、`test_update_task`、`test_delete_task`
- 集成测试：
  - [test_regression_workflow.py](/d:/test/self-manager/tests/integration/test_regression_workflow.py)
  - 包含：`test_complete_task_workflow`、`test_task_filtering`

### 已覆盖新增功能

- 截止时间与重复日程
- 日程概览与日历接口
- CSV 导入导出
- 工作流集成验证

### pytest 标记

- `unit`
- `integration`

配置文件：

- [pytest.ini](/d:/test/self-manager/pytest.ini)

## 7. 回归测试流程

### 快速回归

```powershell
python -m pytest tests/unit/ -v
```

### 完整回归

```powershell
python -m pytest tests/ -v
```

### 当前记录

- 说明文档：[4.2.md](/d:/test/self-manager/features/4.2.md)
- 快速回归日志：[4.2-quick-regression.txt](/d:/test/self-manager/features/4.2-quick-regression.txt)
- 完整回归日志：[4.2-full-regression.txt](/d:/test/self-manager/features/4.2-full-regression.txt)

最近一次回归基线：

- 快速回归：`45 passed`
- 完整回归：`54 passed`

## 8. 运行方式

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动主服务

```bash
uvicorn main:app --reload
```

### 启动历史 Streamlit

```bash
streamlit run app.py
```

## 9. 开发约定

- 新功能开发建议顺序：
  1. 数据字段 / 迁移
  2. service 层
  3. API
  4. 前端
  5. 单元测试
  6. 集成测试
  7. 快速回归
  8. 完整回归

- 重要原则：
  - 先保证接口与数据结构稳定，再做页面联动
  - 新功能必须考虑空值、旧数据兼容和回归影响
  - 页面交互尽量复用现有弹窗、列表和状态流

## 10. 文档关系

- [README.md](/d:/test/self-manager/README.md)
  - 面向使用者与提交说明
- [PROJECT.md](/d:/test/self-manager/PROJECT.md)
  - 面向开发者的上下文快照
- [4.2.md](/d:/test/self-manager/features/4.2.md)
  - 面向课程要求的测试与回归记录
