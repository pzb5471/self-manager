# 个人效能管理系统（Self Manager）

基于 `Streamlit + SQLite` 的任务管理应用，现已支持用户注册、登录与鉴权，并按用户隔离任务数据。

## 功能概览

- 用户系统：注册、登录、退出登录、Token 鉴权
- 任务 CRUD：新增、编辑、删除、查看
- 多用户隔离：任务查询/修改按 `user_id` 严格隔离
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
- pytest

## 项目结构

```text
self-manager/
├─ app.py                          # Streamlit 页面入口（含登录注册）
├─ service.py                      # 业务层与 SQLite 访问（含鉴权）
├─ .mcp.json                       # sqlite MCP 配置
├─ mcp/
│  ├─ README.md                    # MCP 使用说明
│  └─ sql/auth_schema.sql          # MCP 初始化/迁移脚本
├─ requirements.txt                # 依赖
├─ productivity_manager.db         # 默认数据库文件（运行后生成）
├─ skills/
│  ├─ code-review-expert/          # 代码审查专家 Skill
│  └─ unit-test-generator/         # 单元测试生成 Skill
└─ tests/
   └─ unit/
      ├─ test_app_unittest.py      # unittest 测试
      └─ test_app_pytest.py        # pytest 测试
```

## 数据库设计

### 表：`users`

- `id`：INTEGER PRIMARY KEY AUTOINCREMENT
- `username`：TEXT UNIQUE NOT NULL
- `password_hash`：TEXT NOT NULL
- `password_salt`：TEXT NOT NULL
- `created_at`：TEXT

### 表：`auth_tokens`

- `id`：INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id`：INTEGER NOT NULL
- `token`：TEXT（兼容字段，不参与鉴权匹配）
- `token_hash`：TEXT UNIQUE（实际鉴权使用，存储 token 的 SHA-256 哈希）
- `expires_at`：TEXT NOT NULL
- `created_at`：TEXT

### 表：`tasks`

- `id`：INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id`：INTEGER
- `title`：TEXT NOT NULL
- `description`：TEXT
- `category`：TEXT NOT NULL
- `quadrant`：INTEGER NOT NULL，限制为 `1~4`
- `created_at`：TEXT
- `updated_at`：TEXT

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

## 运行测试（py311）

1. `unittest`

```bash
python -m unittest discover -s tests/unit -p "test_app_unittest.py" -v
```

2. `pytest`

```bash
pip install pytest
pytest tests/unit/test_app_pytest.py
```

## sqlite MCP 配置

项目根目录已提供 `.mcp.json`，默认指向：

- `./productivity_manager.db`
- MCP 初始化脚本：`mcp/sql/auth_schema.sql`

可按你的 MCP 客户端要求加载该配置。

## 核心业务规则

- 标题不能为空，且至少 2 个字符
- 分类必须属于：`工作 / 学习 / 生活 / 健康`
- 象限必须为 `1~4`
- 密码采用 `PBKDF2-HMAC-SHA256 + 随机盐` 存储
- 会话 token 仅以 `SHA-256` 哈希形式参与存储与校验，不保存可直接复用的明文 token
- 历史 `user_id IS NULL` 任务不会在登录时自动归属给任意用户，需通过显式迁移处理
- 所有 SQL 使用参数化查询，避免注入

## 已知限制

- 当前 token 保存在本地数据库，适用于单机/学习场景
- 搜索基于 SQLite `LIKE`，不支持复杂全文检索
- `.pytest_cache` 在当前环境可能因目录权限产生 warning（不影响测试通过）

## License

遵循仓库中的 `LICENSE`。
