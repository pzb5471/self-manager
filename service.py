"""个人能效管理系统 - SQLite 业务逻辑层。

本模块将任务数据统一持久化到 SQLite，
用于替代原先的内存态 session_state 数据管理。
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional


class TaskService:
    """任务服务类：封装 SQLite 的建库、增删改查与统计能力。"""

    # 默认分类（初始化时即提供给界面与业务层使用）
    DEFAULT_CATEGORIES = ["工作", "学习", "生活", "健康"]

    def __init__(self, db_path: str = "productivity_manager.db"):
        """初始化任务服务并确保数据库结构就绪。"""
        self.db_path = str(Path(db_path))
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """创建数据库连接并启用按列名访问。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """初始化数据库：创建任务表与索引。"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 任务主表：严格按迁移要求定义字段
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                quadrant INTEGER NOT NULL CHECK(quadrant BETWEEN 1 AND 4),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 常用查询字段索引：分类、象限、创建时间
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_quadrant ON tasks(quadrant)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)")

        # 显式提交，确保建表与建索引立即持久化
        conn.commit()
        conn.close()

    def add_task(
        self,
        title: str,
        description: Optional[str] = "",
        category: str = "工作",
        quadrant: int = 1,
    ) -> Dict:
        """新增任务并返回完整任务对象。"""
        title_trimmed = self._validate_title(title)
        category_checked = self._validate_category(category)
        quadrant_checked = self._validate_quadrant(quadrant)

        conn = self._get_connection()
        cursor = conn.cursor()

        # 使用 ? 占位符防止 SQL 注入
        cursor.execute(
            """
            INSERT INTO tasks (title, description, category, quadrant)
            VALUES (?, ?, ?, ?)
            """,
            (title_trimmed, (description or "").strip(), category_checked, quadrant_checked),
        )

        # 显式提交，保证写入落盘
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()

        task = self.get_task_by_id(task_id)
        if task is None:
            raise RuntimeError("任务写入后读取失败")
        return task

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
    ) -> bool:
        """更新任务字段，成功返回 True，不存在返回 False。"""
        if self.get_task_by_id(task_id) is None:
            return False

        updates: List[str] = []
        params: List = []

        if title is not None:
            updates.append("title = ?")
            params.append(self._validate_title(title))
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if category is not None:
            updates.append("category = ?")
            params.append(self._validate_category(category))
        if quadrant is not None:
            updates.append("quadrant = ?")
            params.append(self._validate_quadrant(quadrant))

        # 无业务字段更新时，仍更新 updated_at，保证时间语义一致
        updates.append("updated_at = CURRENT_TIMESTAMP")

        conn = self._get_connection()
        cursor = conn.cursor()
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        params.append(task_id)
        cursor.execute(sql, params)

        # 显式提交，保证更新落盘
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def delete_task(self, task_id: int) -> bool:
        """删除任务，成功返回 True，不存在返回 False。"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

        # 显式提交，保证删除落盘
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """根据任务 ID 获取任务详情。"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_task(row) if row else None

    def get_all_tasks(self) -> List[Dict]:
        """获取全部任务，按创建时间倒序显示。"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            ORDER BY created_at DESC, id DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def filter_tasks(
        self,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
    ) -> List[Dict]:
        """按分类与象限筛选任务。"""
        conditions: List[str] = []
        params: List = []

        if category and category != "全部":
            conditions.append("category = ?")
            params.append(self._validate_category(category))

        if quadrant and str(quadrant) != "全部":
            conditions.append("quadrant = ?")
            params.append(self._validate_quadrant(int(quadrant)))

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            {where_sql}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def get_statistics(self) -> Dict:
        """获取统计信息：总数、分类统计、象限统计。"""
        all_tasks = self.get_all_tasks()

        category_stats = {category: 0 for category in self.DEFAULT_CATEGORIES}
        quadrant_stats = {1: 0, 2: 0, 3: 0, 4: 0}

        for task in all_tasks:
            category_stats[task["category"]] += 1
            quadrant_stats[task["quadrant"]] += 1

        return {
            "total": len(all_tasks),
            "by_category": category_stats,
            "by_quadrant": quadrant_stats,
        }

    def get_categories(self) -> List[str]:
        """返回默认分类列表（初始化时提供：工作/学习/生活/健康）。"""
        return self.DEFAULT_CATEGORIES.copy()

    def get_tasks_grouped_by_quadrant(self) -> Dict[int, List[Dict]]:
        """返回按象限分组的任务字典。"""
        grouped = {1: [], 2: [], 3: [], 4: []}
        for task in self.get_all_tasks():
            grouped[task["quadrant"]].append(task)
        return grouped

    def get_tasks_grouped_by_category(self) -> Dict[str, List[Dict]]:
        """返回按分类分组的任务字典。"""
        grouped = {category: [] for category in self.DEFAULT_CATEGORIES}
        for task in self.get_all_tasks():
            grouped[task["category"]].append(task)
        return grouped

    def search_tasks(self, keyword: str) -> List[Dict]:
        """按标题或描述模糊搜索任务，使用 LIKE 和占位符防注入。"""
        if not keyword or not keyword.strip():
            return self.get_all_tasks()

        search_term = f"%{keyword.strip()}%"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            WHERE title LIKE ? OR description LIKE ?
            ORDER BY created_at DESC, id DESC
            """,
            (search_term, search_term),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def get_sorted_tasks(self, sort_by: str = "created_desc") -> List[Dict]:
        """按指定字段排序任务。
        
        sort_by 可选值:
        - created_desc: 按创建时间倒序（最新在前）
        - created_asc: 按创建时间正序（最旧在前）
        - updated_desc: 按更新时间倒序（最新更新在前）
        - updated_asc: 按更新时间正序（最旧更新在前）
        """
        # 映射排序字段与 SQL 语句
        sort_mapping = {
            "created_desc": "created_at DESC, id DESC",
            "created_asc": "created_at ASC, id ASC",
            "updated_desc": "updated_at DESC, id DESC",
            "updated_asc": "updated_at ASC, id ASC",
        }

        order_clause = sort_mapping.get(sort_by, sort_mapping["created_desc"])

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            ORDER BY {order_clause}
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def clear_all_tasks(self) -> None:
        """清空全部任务（测试场景使用）。"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        conn.commit()
        conn.close()

    def _validate_title(self, title: str) -> str:
        """校验任务标题：不能为空、至少 2 个字符。"""
        title_trimmed = title.strip()
        if not title_trimmed:
            raise ValueError("任务标题不能为空！")
        if len(title_trimmed) < 2:
            raise ValueError("任务标题太短（至少2个字符）")
        return title_trimmed

    def _validate_category(self, category: str) -> str:
        """校验分类必须属于默认分类集合。"""
        if category not in self.DEFAULT_CATEGORIES:
            raise ValueError("分类必须是 工作/学习/生活/健康 之一")
        return category

    def _validate_quadrant(self, quadrant: int) -> int:
        """校验象限值必须在 1-4。"""
        if quadrant not in (1, 2, 3, 4):
            raise ValueError("象限必须是 1-4 的整数")
        return quadrant

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Dict:
        """将 sqlite3.Row 转换为标准任务字典。"""
        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"] or "",
            "category": row["category"],
            "quadrant": row["quadrant"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
