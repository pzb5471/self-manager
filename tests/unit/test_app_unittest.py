"""
个人能效管理系统 - 单元测试

本模块包含 TaskService 类的完整单元测试用例，
覆盖正常情况、边界情况和异常情况。
"""

import unittest
from datetime import datetime
from service import TaskService


class TestTaskService(unittest.TestCase):
    """TaskService 类的单元测试"""

    def setUp(self):
        """
        每个测试方法执行前的初始化操作

        创建一个新的 TaskService 实例，确保各测试之间互不影响
        """
        self.service = TaskService()

    def test_service_initialization(self):
        """测试服务初始化"""
        # 验证新实例属性
        self.assertEqual(self.service.tasks, [])
        self.assertEqual(self.service.next_id, 1)

    # ==================== 添加任务测试 ====================
    def test_add_task_success(self):
        """测试成功添加任务"""
        # 添加一个正常任务
        task = self.service.add_task("完成项目报告", "工作", "高")

        # 验证任务属性
        self.assertEqual(task['id'], 1)
        self.assertEqual(task['title'], "完成项目报告")
        self.assertEqual(task['category'], "工作")
        self.assertEqual(task['priority'], "高")
        self.assertEqual(task['completed'], False)
        self.assertIsNotNone(task['created_at'])

        # 验证任务已添加到列表
        self.assertEqual(len(self.service.tasks), 1)

    def test_add_task_with_default_category(self):
        """测试添加任务时使用默认分类"""
        # 不提供分类参数，应使用默认值"未分类"
        task = self.service.add_task("学习Python")

        self.assertEqual(task['category'], "未分类")

    def test_add_task_with_empty_category(self):
        """测试添加任务时分类为空字符串"""
        # 传递空字符串，应使用默认值"未分类"
        task = self.service.add_task("测试任务", "", "高")

        self.assertEqual(task['category'], "未分类")

    def test_add_task_id_increment(self):
        """测试任务ID自动递增"""
        # 添加多个任务
        task1 = self.service.add_task("任务1")
        task2 = self.service.add_task("任务2")
        task3 = self.service.add_task("任务3")

        # 验证ID递增
        self.assertEqual(task1['id'], 1)
        self.assertEqual(task2['id'], 2)
        self.assertEqual(task3['id'], 3)

    def test_add_task_with_whitespace_title(self):
        """测试带首尾空格的任务标题会被去除"""
        # 标题带有首尾空格
        task = self.service.add_task("  测试任务  ")

        # 验证空格被去除
        self.assertEqual(task['title'], "测试任务")

    # ==================== 添加任务 - 异常情况测试 ====================
    def test_add_task_empty_title(self):
        """测试添加空标题任务应抛出异常"""
        with self.assertRaises(ValueError) as context:
            self.service.add_task("")

        self.assertEqual(str(context.exception), "任务标题不能为空！")

    def test_add_task_only_whitespace_title(self):
        """测试只有空格的标题应抛出异常"""
        with self.assertRaises(ValueError) as context:
            self.service.add_task("   ")

        self.assertEqual(str(context.exception), "任务标题不能为空！")

    def test_add_task_title_too_short(self):
        """测试标题太短（少于2个字符）应抛出异常"""
        with self.assertRaises(ValueError) as context:
            self.service.add_task("测")

        self.assertEqual(str(context.exception), "任务标题太短（至少2个字符）")

    def test_add_task_borderline_min_length(self):
        """测试标题边界情况：正好2个字符应该成功"""
        # 只有两个字符的标题应该正常添加
        task = self.service.add_task("测试")

        self.assertEqual(task['title'], "测试")

    # ==================== 更新任务测试 ====================
    def test_update_task_success(self):
        """测试成功更新任务"""
        # 先添加一个任务
        self.service.add_task("原标题", "工作", "高")

        # 更新任务
        result = self.service.update_task(1, title="新标题", category="学习", priority="低")

        # 验证返回值
        self.assertTrue(result)

        # 验证任务被更新
        task = self.service.get_task_by_id(1)
        self.assertEqual(task['title'], "新标题")
        self.assertEqual(task['category'], "学习")
        self.assertEqual(task['priority'], "低")

    def test_update_task_not_exist(self):
        """测试更新不存在的任务应返回False"""
        result = self.service.update_task(999, title="测试")
        self.assertFalse(result)

    def test_update_task_partial(self):
        """测试部分更新任务（只更新部分字段）"""
        # 添加任务
        self.service.add_task("原标题", "工作", "高")

        # 只更新标题
        self.service.update_task(1, title="新标题")

        # 验证只有标题被更新
        task = self.service.get_task_by_id(1)
        self.assertEqual(task['title'], "新标题")
        self.assertEqual(task['category'], "工作")  # 分类未变
        self.assertEqual(task['priority'], "高")     # 优先级未变

    def test_update_task_title_with_validation(self):
        """测试更新标题时也会进行验证"""
        # 添加任务
        self.service.add_task("原任务")

        # 尝试用无效标题更新
        with self.assertRaises(ValueError):
            self.service.update_task(1, title="")

    # ==================== 删除任务测试 ====================
    def test_delete_task_success(self):
        """测试成功删除任务"""
        # 添加任务
        self.service.add_task("任务1")
        self.service.add_task("任务2")
        self.service.add_task("任务3")

        # 删除第二个任务
        result = self.service.delete_task(2)

        # 验证删除结果
        self.assertTrue(result)
        self.assertEqual(len(self.service.tasks), 2)

        # 验证删除了正确的任务
        tasks = self.service.get_all_tasks()
        task_ids = [t['id'] for t in tasks]
        self.assertNotIn(2, task_ids)
        self.assertIn(1, task_ids)
        self.assertIn(3, task_ids)

    def test_delete_task_not_exist(self):
        """测试删除不存在的任务应返回False"""
        result = self.service.delete_task(999)
        self.assertFalse(result)

    def test_delete_task_from_empty_list(self):
        """测试从空列表删除任务应返回False"""
        result = self.service.delete_task(1)
        self.assertFalse(result)

    # ==================== 切换完成状态测试 ====================
    def test_toggle_task_completion(self):
        """测试切换任务完成状态"""
        # 添加任务
        self.service.add_task("测试任务")

        # 默认状态应该是未完成
        task = self.service.get_task_by_id(1)
        self.assertFalse(task['completed'])

        # 切换状态
        self.service.toggle_task_completion(1)

        # 验证状态已切换
        task = self.service.get_task_by_id(1)
        self.assertTrue(task['completed'])

    def test_toggle_task_completion_set_true(self):
        """测试设置任务为完成状态"""
        self.service.add_task("测试任务")

        # 设置为完成
        self.service.toggle_task_completion(1, completed=True)

        task = self.service.get_task_by_id(1)
        self.assertTrue(task['completed'])

    def test_toggle_task_completion_set_false(self):
        """测试设置任务为未完成状态"""
        self.service.add_task("测试任务")

        # 先设置为完成
        self.service.toggle_task_completion(1, completed=True)

        # 设置回未完成
        self.service.toggle_task_completion(1, completed=False)

        task = self.service.get_task_by_id(1)
        self.assertFalse(task['completed'])

    def test_toggle_task_not_exist(self):
        """测试切换不存在任务的状态应返回False"""
        result = self.service.toggle_task_completion(999)
        self.assertFalse(result)

    # ==================== 查找任务测试 ====================
    def test_find_task_by_id(self):
        """测试根据ID查找任务"""
        self.service.add_task("任务1")
        self.service.add_task("任务2")

        # 查找存在的任务
        task = self.service.get_task_by_id(1)
        self.assertEqual(task['title'], "任务1")

        task = self.service.get_task_by_id(2)
        self.assertEqual(task['title'], "任务2")

    def test_find_task_by_id_not_exist(self):
        """测试查找不存在的任务应返回None"""
        task = self.service.get_task_by_id(999)
        self.assertIsNone(task)

    # ==================== 获取所有任务测试 ====================
    def test_get_all_tasks_empty(self):
        """测试获取空任务列表"""
        tasks = self.service.get_all_tasks()
        self.assertEqual(tasks, [])

    def test_get_all_tasks_returns_copy(self):
        """测试 get_all_tasks 返回的是副本，修改不影响原列表"""
        # 添加任务
        self.service.add_task("任务1")

        # 获取任务列表
        tasks = self.service.get_all_tasks()

        # 修改返回的列表
        tasks[0]['title'] = "修改后的标题"

        # 验证原列表未受影响
        original_task = self.service.get_task_by_id(1)
        self.assertEqual(original_task['title'], "任务1")

    # ==================== 筛选任务测试 ====================
    def test_filter_tasks_by_category(self):
        """测试按分类筛选"""
        self.service.add_task("任务1", "工作")
        self.service.add_task("任务2", "学习")
        self.service.add_task("任务3", "工作")

        # 筛选工作类任务
        filtered = self.service.filter_tasks(category="工作")
        self.assertEqual(len(filtered), 2)
        for task in filtered:
            self.assertEqual(task['category'], "工作")

    def test_filter_tasks_by_priority(self):
        """测试按优先级筛选"""
        self.service.add_task("任务1", "工作", "高")
        self.service.add_task("任务2", "学习", "中")
        self.service.add_task("任务3", "工作", "高")

        # 筛选高优先级任务
        filtered = self.service.filter_tasks(priority="高")
        self.assertEqual(len(filtered), 2)
        for task in filtered:
            self.assertEqual(task['priority'], "高")

    def test_filter_tasks_by_both(self):
        """测试同时按分类和优先级筛选"""
        self.service.add_task("任务1", "工作", "高")
        self.service.add_task("任务2", "学习", "高")
        self.service.add_task("任务3", "工作", "中")

        # 筛选工作类且高优先级的任务
        filtered = self.service.filter_tasks(category="工作", priority="高")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['title'], "任务1")

    def test_filter_tasks_no_match(self):
        """测试筛选无匹配结果"""
        self.service.add_task("任务1", "工作")

        # 筛选不存在的分类
        filtered = self.service.filter_tasks(category="不存在的分类")
        self.assertEqual(len(filtered), 0)

    def test_filter_tasks_all(self):
        """测试筛选全部任务（无筛选条件）"""
        self.service.add_task("任务1")
        self.service.add_task("任务2")

        # 不提供筛选条件
        filtered = self.service.filter_tasks()
        self.assertEqual(len(filtered), 2)

    def test_filter_tasks_category_all(self):
        """测试分类参数为"全部"时返回所有任务"""
        self.service.add_task("任务1", "工作")
        self.service.add_task("任务2", "学习")

        filtered = self.service.filter_tasks(category="全部")
        self.assertEqual(len(filtered), 2)

    # ==================== 排序任务测试 ====================
    def test_sort_tasks_by_priority(self):
        """测试按优先级排序任务"""
        # 添加不同优先级的任务
        self.service.add_task("低优先级", "工作", "低")
        self.service.add_task("高优先级", "工作", "高")
        self.service.add_task("中优先级", "工作", "中")

        # 排序
        sorted_tasks = self.service.sort_tasks_by_priority()

        # 验证顺序：高 -> 中 -> 低
        self.assertEqual(sorted_tasks[0]['priority'], "高")
        self.assertEqual(sorted_tasks[1]['priority'], "中")
        self.assertEqual(sorted_tasks[2]['priority'], "低")

    def test_sort_tasks_empty_list(self):
        """测试空列表排序"""
        sorted_tasks = self.service.sort_tasks_by_priority()
        self.assertEqual(sorted_tasks, [])

    def test_sort_tasks_with_custom_list(self):
        """测试对自定义列表排序"""
        # 创建自定义任务列表（不添加到service中）
        custom_tasks = [
            {'id': 1, 'priority': '低'},
            {'id': 2, 'priority': '高'},
            {'id': 3, 'priority': '中'},
        ]

        # 排序自定义列表
        sorted_tasks = self.service.sort_tasks_by_priority(custom_tasks)

        # 验证顺序
        self.assertEqual(sorted_tasks[0]['priority'], "高")
        self.assertEqual(sorted_tasks[1]['priority'], "中")
        self.assertEqual(sorted_tasks[2]['priority'], "低")

    def test_sort_tasks_preserve_original(self):
        """测试排序不修改原列表"""
        # 添加任务
        self.service.add_task("任务1", "工作", "低")
        self.service.add_task("任务2", "工作", "高")

        # 记录原始顺序
        original_ids = [t['id'] for t in self.service.tasks]

        # 排序
        sorted_tasks = self.service.sort_tasks_by_priority()

        # 验证原列表未改变
        current_ids = [t['id'] for t in self.service.tasks]
        self.assertEqual(original_ids, current_ids)

    def test_sort_tasks_unknown_priority(self):
        """测试未知优先级的任务排在中间位置"""
        # 添加任务（带未知优先级）
        self.service.add_task("任务1", "工作", "高")
        self.service.add_task("任务2", "工作", "未知")
        self.service.add_task("任务3", "工作", "低")

        # 排序
        sorted_tasks = self.service.sort_tasks_by_priority()

        # 未知优先级应排在中间位置（默认值1，等于"中"）
        self.assertEqual(sorted_tasks[0]['priority'], "高")
        self.assertEqual(sorted_tasks[1]['priority'], "未知")
        self.assertEqual(sorted_tasks[2]['priority'], "低")

    # ==================== 统计测试 ====================
    def test_statistics_empty(self):
        """测试空任务列表的统计"""
        stats = self.service.get_statistics()

        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['completed'], 0)
        self.assertEqual(stats['pending'], 0)

    def test_statistics_basic(self):
        """测试基本统计功能"""
        self.service.add_task("任务1", "工作", "高")
        self.service.add_task("任务2", "学习", "中")

        stats = self.service.get_statistics()

        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['work'], 1)
        self.assertEqual(stats['study'], 1)
        self.assertEqual(stats['high_priority'], 1)
        self.assertEqual(stats['medium_priority'], 1)

    def test_statistics_completion_status(self):
        """测试完成状态统计"""
        self.service.add_task("任务1")
        self.service.add_task("任务2")

        # 标记第一个任务为完成
        self.service.toggle_task_completion(1, completed=True)

        stats = self.service.get_statistics()

        self.assertEqual(stats['completed'], 1)
        self.assertEqual(stats['pending'], 1)

    def test_statistics_all_categories(self):
        """测试所有分类统计"""
        self.service.add_task("任务1", "工作")
        self.service.add_task("任务2", "学习")
        self.service.add_task("任务3", "生活")
        self.service.add_task("任务4", "健康")

        stats = self.service.get_statistics()

        self.assertEqual(stats['work'], 1)
        self.assertEqual(stats['study'], 1)
        self.assertEqual(stats['life'], 1)
        self.assertEqual(stats['health'], 1)

    def test_statistics_all_priorities(self):
        """测试所有优先级统计"""
        self.service.add_task("任务1", "工作", "高")
        self.service.add_task("任务2", "工作", "中")
        self.service.add_task("任务3", "工作", "低")

        stats = self.service.get_statistics()

        self.assertEqual(stats['high_priority'], 1)
        self.assertEqual(stats['medium_priority'], 1)
        self.assertEqual(stats['low_priority'], 1)

    def test_statistics_undefined_category(self):
        """测试未定义分类的任务不计入分类统计"""
        self.service.add_task("任务1", "其他分类")
        self.service.add_task("任务2", "工作")

        stats = self.service.get_statistics()

        # 只统计已知分类
        self.assertEqual(stats['work'], 1)
        self.assertEqual(stats['study'], 0)
        self.assertEqual(stats['life'], 0)
        self.assertEqual(stats['health'], 0)
        # 但总数应该是2
        self.assertEqual(stats['total'], 2)

    # ==================== 获取分类测试 ====================
    def test_get_categories_empty(self):
        """测试获取空任务的分类列表"""
        categories = self.service.get_categories()
        self.assertEqual(categories, [])

    def test_get_categories(self):
        """测试获取任务分类"""
        self.service.add_task("任务1", "工作")
        self.service.add_task("任务2", "学习")
        self.service.add_task("任务3", "生活")
        self.service.add_task("任务4", "学习")  # 重复分类

        categories = self.service.get_categories()

        # 验证去重和有序
        self.assertEqual(categories, ['学习', '工作', '生活'])  # 按字母序

    def test_get_categories_duplicates(self):
        """测试获取分类时去除重复"""
        self.service.add_task("任务1", "工作")
        self.service.add_task("任务2", "工作")
        self.service.add_task("任务3", "工作")

        categories = self.service.get_categories()

        # 应该只有一个"工作"
        self.assertEqual(len(categories), 1)
        self.assertEqual(categories[0], '工作')

    # ==================== 清空任务测试 ====================
    def test_clear_all_tasks(self):
        """测试清空所有任务"""
        # 添加多个任务
        self.service.add_task("任务1")
        self.service.add_task("任务2")
        self.service.add_task("任务3")

        # 清空任务
        self.service.clear_all_tasks()

        # 验证任务列表为空
        self.assertEqual(len(self.service.tasks), 0)
        self.assertEqual(self.service.next_id, 1)  # ID计数器也重置

    def test_clear_all_tasks_after_operations(self):
        """测试在多次操作后清空任务"""
        # 添加、更新、删除任务
        self.service.add_task("任务1")
        self.service.add_task("任务2")
        self.service.delete_task(1)
        self.service.add_task("任务3")

        # 清空任务
        self.service.clear_all_tasks()

        # 验证完全清空
        self.assertEqual(self.service.tasks, [])
        self.assertEqual(self.service.next_id, 1)

    # ==================== 集成测试 ====================
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        # 1. 添加任务
        task1 = self.service.add_task("完成项目", "工作", "高")
        task2 = self.service.add_task("学习Python", "学习", "中")

        self.assertEqual(len(self.service.tasks), 2)

        # 2. 完成一个任务
        self.service.toggle_task_completion(1, completed=True)
        self.assertTrue(self.service.get_task_by_id(1)['completed'])

        # 3. 更新另一个任务
        self.service.update_task(2, priority="高")
        self.assertEqual(self.service.get_task_by_id(2)['priority'], "高")

        # 4. 按优先级筛选
        high_priority = self.service.filter_tasks(priority="高")
        self.assertEqual(len(high_priority), 2)

        # 5. 删除一个任务
        self.service.delete_task(1)
        self.assertEqual(len(self.service.tasks), 1)

        # 6. 检查统计
        stats = self.service.get_statistics()
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['high_priority'], 1)


if __name__ == '__main__':
    # 运行测试时显示详细信息
    unittest.main(verbosity=2)
