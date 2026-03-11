"""
个人能效管理系统 - 业务逻辑层

本模块包含任务管理的核心业务逻辑函数，
从 Streamlit UI 层分离出来，便于单元测试。
"""

from datetime import datetime
from typing import List, Dict, Optional


class TaskService:
    """任务服务类，封装任务管理的所有业务逻辑"""

    def __init__(self):
        """初始化任务服务"""
        self.tasks: List[Dict] = []
        self.next_id: int = 1

    def add_task(self, title: str, category: str = "未分类",
                 priority: str = "中") -> Dict:
        """
        添加新任务

        参数:
            title: 任务标题
            category: 任务分类（默认"未分类"）
            priority: 任务优先级（默认"中"）

        返回:
            新创建的任务字典

        异常:
            ValueError: 当标题无效时抛出
        """
        # 验证任务标题
        title_trimmed = self._validate_title(title)

        # 创建新任务
        new_task = {
            'id': self.next_id,
            'title': title_trimmed,
            'category': category if category else '未分类',
            'priority': priority,
            'completed': False,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        # 自增ID
        self.next_id += 1

        # 添加到任务列表
        self.tasks.append(new_task)

        return new_task

    def update_task(self, task_id: int, title: Optional[str] = None,
                    category: Optional[str] = None,
                    priority: Optional[str] = None) -> bool:
        """
        更新现有任务

        参数:
            task_id: 任务ID
            title: 新标题（可选）
            category: 新分类（可选）
            priority: 新优先级（可选）

        返回:
            bool: 更新成功返回True，任务不存在返回False

        异常:
            ValueError: 当标题无效时抛出
        """
        task = self._find_task_by_id(task_id)
        if not task:
            return False

        # 更新标题（如果提供了新标题）
        if title is not None:
            task['title'] = self._validate_title(title)

        # 更新分类（如果提供了新分类）
        if category is not None:
            task['category'] = category if category else '未分类'

        # 更新优先级（如果提供了新优先级）
        if priority is not None:
            task['priority'] = priority

        return True

    def delete_task(self, task_id: int) -> bool:
        """
        删除任务

        参数:
            task_id: 要删除的任务ID

        返回:
            bool: 删除成功返回True，任务不存在返回False
        """
        original_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if t['id'] != task_id]
        return len(self.tasks) < original_count

    def toggle_task_completion(self, task_id: int, completed: Optional[bool] = None) -> bool:
        """
        切换任务完成状态

        参数:
            task_id: 任务ID
            completed: 完成状态，None表示切换当前状态

        返回:
            bool: 操作成功返回True，任务不存在返回False
        """
        task = self._find_task_by_id(task_id)
        if not task:
            return False

        if completed is None:
            # 切换状态
            task['completed'] = not task['completed']
        else:
            # 设置指定状态
            task['completed'] = completed

        return True

    def _find_task_by_id(self, task_id: int) -> Optional[Dict]:
        """
        根据ID查找任务

        参数:
            task_id: 任务ID

        返回:
            任务字典，不存在则返回None
        """
        for task in self.tasks:
            if task['id'] == task_id:
                return task
        return None

    def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """
        根据ID获取任务（公共方法）

        参数:
            task_id: 任务ID

        返回:
            任务字典，不存在则返回None
        """
        return self._find_task_by_id(task_id)

    def get_all_tasks(self) -> List[Dict]:
        """
        获取所有任务

        返回:
            任务列表（深拷贝，修改不影响原列表）
        """
        # 使用 deepcopy 确保返回的是完全独立的副本
        import copy
        return copy.deepcopy(self.tasks)

    def filter_tasks(self, category: Optional[str] = None,
                     priority: Optional[str] = None) -> List[Dict]:
        """
        筛选任务

        参数:
            category: 分类筛选，None表示不筛选
            priority: 优先级筛选，None表示不筛选

        返回:
            筛选后的任务列表
        """
        filtered = self.tasks

        # 按分类筛选
        if category and category != "全部":
            filtered = [t for t in filtered
                       if t.get('category', '未分类') == category]

        # 按优先级筛选
        if priority and priority != "全部":
            filtered = [t for t in filtered
                       if t.get('priority', '中') == priority]

        return filtered

    def sort_tasks_by_priority(self, tasks: Optional[List[Dict]] = None) -> List[Dict]:
        """
        按优先级排序任务

        优先级顺序：高 > 中 > 低

        参数:
            tasks: 要排序的任务列表，None表示排序所有任务

        返回:
            排序后的任务列表（新列表，不修改原列表）
        """
        if tasks is None:
            tasks = self.tasks

        priority_order = {'高': 0, '中': 1, '低': 2}
        # 创建副本并排序
        return sorted(tasks.copy(),
                     key=lambda x: priority_order.get(x.get('priority', '中'), 1))

    def get_statistics(self) -> Dict[str, int]:
        """
        获取任务统计信息

        返回:
            包含统计数据的字典：
            - total: 总任务数
            - completed: 已完成任务数
            - pending: 未完成任务数
            - work: 工作任务数
            - study: 学习任务数
            - life: 生活任务数
            - health: 健康任务数
            - high_priority: 高优先级任务数
            - medium_priority: 中优先级任务数
            - low_priority: 低优先级任务数
        """
        stats = {
            'total': len(self.tasks),
            'completed': 0,
            'pending': 0,
            'work': 0,
            'study': 0,
            'life': 0,
            'health': 0,
            'high_priority': 0,
            'medium_priority': 0,
            'low_priority': 0
        }

        # 分类统计映射
        category_map = {
            '工作': 'work',
            '学习': 'study',
            '生活': 'life',
            '健康': 'health'
        }

        # 优先级统计映射
        priority_map = {
            '高': 'high_priority',
            '中': 'medium_priority',
            '低': 'low_priority'
        }

        for task in self.tasks:
            # 统计完成状态
            if task.get('completed', False):
                stats['completed'] += 1
            else:
                stats['pending'] += 1

            # 统计分类
            category = task.get('category', '未分类')
            if category in category_map:
                stats[category_map[category]] += 1

            # 统计优先级
            priority = task.get('priority', '中')
            if priority in priority_map:
                stats[priority_map[priority]] += 1

        return stats

    def get_categories(self) -> List[str]:
        """
        获取所有任务分类

        返回:
            分类列表
        """
        categories = set()
        for task in self.tasks:
            category = task.get('category', '未分类')
            categories.add(category)
        return sorted(list(categories))

    def _validate_title(self, title: str) -> str:
        """
        验证任务标题

        参数:
            title: 原始标题

        返回:
            去除首尾空格后的标题

        异常:
            ValueError: 标题为空或太短时抛出
        """
        title_trimmed = title.strip()

        if not title_trimmed:
            raise ValueError("任务标题不能为空！")
        if len(title_trimmed) < 2:
            raise ValueError("任务标题太短（至少2个字符）")

        return title_trimmed

    def clear_all_tasks(self) -> None:
        """清空所有任务"""
        self.tasks.clear()
        self.next_id = 1
