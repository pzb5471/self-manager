# 个人效能管理系统（Self Manager）

基于 `Streamlit + SQLite` 的任务管理应用，支持四象限管理法、搜索、排序、筛选，以及基础统计分析。

## 功能概览

- 任务 CRUD：新增、编辑、删除、查看
- SQLite 持久化：任务数据落库，刷新页面不丢失
- 四象限管理：按 `quadrant=1~4` 管理任务优先级
- 分类管理：内置分类 `工作 / 学习 / 生活 / 健康`
- 搜索：按标题和描述模糊匹配
- 排序：支持创建时间/更新时间的升序与降序
- 筛选：按分类、象限组合筛选
- 统计：总任务数、按分类统计、按象限统计

## 技术栈

- Python 3.11+
- Streamlit
- SQLite3
- unittest

## 项目结构

```text
self-manager/
├─ app.py                          # Streamlit 页面入口
├─ service.py                      # 业务层与 SQLite 访问
├─ requirements.txt                # 依赖
├─ productivity_manager.db         # 默认数据库文件（运行后生成）
└─ tests/
   └─ unit/
      └─ test_app_unittest.py      # 单元测试
```

## 数据库设计

### 表：`tasks`

- `id`：INTEGER PRIMARY KEY AUTOINCREMENT
- `title`：TEXT NOT NULL
- `description`：TEXT
- `category`：TEXT NOT NULL
- `quadrant`：INTEGER NOT NULL，限制为 `1~4`
- `created_at`：TIMESTAMP，默认 `CURRENT_TIMESTAMP`
- `updated_at`：TIMESTAMP，默认 `CURRENT_TIMESTAMP`

### 索引

- `idx_tasks_category`
- `idx_tasks_quadrant`
- `idx_tasks_created_at`

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 启动应用

```bash
streamlit run app.py
```

启动后访问：`http://localhost:8501`

## 运行测试

推荐在你当前 `py311` 环境执行：

```bash
python -m unittest discover -s tests/unit -p "test_*.py" -v
```

当前测试覆盖：

- 数据库初始化（建表、索引）
- 任务增删改查
- 输入校验与异常分支
- 搜索与 SQL 注入防护
- 排序逻辑
- 分组统计与清空数据

## 核心业务规则

- 标题不能为空，且至少 2 个字符
- 分类必须属于：`工作 / 学习 / 生活 / 健康`
- 象限必须为 `1~4`
- 所有 SQL 使用参数化查询，避免注入

## 已知限制

- 当前为单用户本地应用
- 搜索基于 SQLite `LIKE`，不支持复杂全文检索

## License

遵循仓库中的 `LICENSE`。
