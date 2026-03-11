import streamlit as st
from datetime import datetime

# 初始化内存数据
if 'tasks' not in st.session_state:
    st.session_state.tasks = []

if 'show_form' not in st.session_state:
    st.session_state.show_form = False

# 设置页面配置
st.set_page_config(page_title="个人能效管理", page_icon="📋")

# 侧边栏
st.sidebar.title("📋 个人能效管理")
page = st.sidebar.radio("选择页面", ["任务列表", "添加任务"])

# 任务列表页面
if page == "任务列表":
    st.header("任务列表")

    # ===== 任务统计功能 =====
    st.subheader("📊 任务统计")

    # 使用 st.columns() 创建三列布局
    stat_col1, stat_col2, stat_col3 = st.columns(3)

    # ===== 第一列：总任务数 =====
    # 使用 len() 函数获取列表长度，统计任务总数
    total_tasks = len(st.session_state.tasks)

    with stat_col1:
        st.metric("总任务数", total_tasks)

    # ===== 第二列：按分类统计 =====
    # 使用字典存储分类统计结果（Python内置数据类型 - 字典）
    category_stats = {'工作': 0, '学习': 0, '生活': 0, '健康': 0}

    # 使用 for 循环遍历任务列表，统计各分类数量
    for task in st.session_state.tasks:  # 遍历列表（Python内置数据类型 - 列表）
        category = task.get('category', '未分类')  # 使用 dict.get() 方法获取字典值
        if category in category_stats:  # 使用 if 判断条件）
            category_stats[category] += 1  # 字典值自增操作

    with stat_col2:
        st.write("**按分类统计**")
        # 使用 for 循环遍历字典，显示统计结果
        for category, count in category_stats.items():  # 使用 dict.items() 遍历字典键值对
            if count > 0:  # 只显示数量大于0的分类
                st.write(f"- {category}: {count} 个")

    # ===== 第三列：按优先级统计 =====
    # 使用字典存储优先级统计结果（字典初始化）
    priority_stats = {'高': 0, '中': 0, '低': 0}

    # 使用 for 循环遍历任务列表
    for task in st.session_state.tasks:
        priority = task.get('priority', '中')  # 获取优先级，默认为'中'
        if priority in priority_stats:
            priority_stats[priority] += 1

    with stat_col3:
        st.write("**按优先级统计**")
        st.write(f"🔴 高: {priority_stats['高']} 个")
        st.write(f"🟡 中: {priority_stats['中']} 个")
        st.write(f"🟢 低: {priority_stats['低']} 个")

    st.markdown("---")
    # ===== 任务统计功能结束 =====

    # 筛选功能
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_category = st.selectbox("分类", ["全部"] + list(set(t.get('category', '未分类') for t in st.session_state.tasks)))
    with col2:
        selected_priority = st.selectbox("优先级", ["全部", "高", "中", "低"])
    with col3:
        st.write("")
        if st.button("刷新"):
            st.rerun()

    # 筛选任务 - 使用列表推导式（Python高级特性 - 列表推导式）
    filtered_tasks = st.session_state.tasks
    if selected_category != "全部":
        filtered_tasks = [t for t in filtered_tasks if t.get('category', '未分类') == selected_category]
    if selected_priority != "全部":
        filtered_tasks = [t for t in filtered_tasks if t.get('priority', '中') == selected_priority]

    # 删除原来的简单统计显示
    # st.subheader(f"共 {len(filtered_tasks)} 个任务")

    # 按优先级排序显示
    priority_order = {'高': 0, '中': 1, '低': 2}
    filtered_tasks.sort(key=lambda x: priority_order.get(x.get('priority', '中'), 1))

    # 显示任务
    if not filtered_tasks:
        st.info("暂无任务")
    else:
        for idx, task in enumerate(filtered_tasks):
            task_id = task['id']
            priority = task.get('priority', '中')
            category = task.get('category', '未分类')
            completed = task.get('completed', False)
            created_at = task.get('created_at', '')

            # 优先级颜色
            priority_color = {
                '高': '🔴',
                '中': '🟡',
                '低': '🟢'
            }.get(priority, '⚪')

            # 任务卡片
            with st.container():
                col1, col2, col3, col4 = st.columns([0.5, 4, 2, 1])

                with col1:
                    st.checkbox("", value=completed, key=f"check_{task_id}")

                with col2:
                    title_style = "~~{}~~" if completed else "{}"
                    st.markdown(title_style.format(task['title']))

                with col3:
                    st.markdown(f"{priority_color} {priority} | {category}")

                with col4:
                    if st.button("编辑", key=f"edit_{task_id}"):
                        st.session_state.edit_id = task_id
                        st.rerun()
                    if st.button("删除", key=f"del_{task_id}"):
                        st.session_state.tasks = [t for t in st.session_state.tasks if t['id'] != task_id]
                        st.rerun()

                st.caption(f"创建时间: {created_at}")
                st.markdown("---")

    # 添加任务按钮
    if st.button("➕ 添加任务", use_container_width=True):
        st.session_state.page = "添加任务"
        st.session_state.edit_id = None
        st.rerun()

# 添加/编辑任务页面
elif page == "添加任务" or st.session_state.get('page') == "添加任务":
    st.header("添加任务" if st.session_state.get('edit_id') is None else "编辑任务")

    # 检查是否是编辑模式
    edit_id = st.session_state.get('edit_id')
    edit_task = None
    if edit_id:
        for task in st.session_state.tasks:
            if task['id'] == edit_id:
                edit_task = task
                break

    # 任务表单
    with st.form("task_form"):
        title = st.text_input("任务标题", value=edit_task['title'] if edit_task else "")

        col1, col2 = st.columns(2)
        with col1:
            category = st.text_input("分类", value=edit_task.get('category', '') if edit_task else "",
                                    placeholder="例如: 工作、学习、生活")
        with col2:
            priority = st.selectbox("优先级", ["高", "中", "低"],
                                   index=["高", "中", "低"].index(edit_task.get('priority', '中')) if edit_task else 1)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.form_submit_button("保存", use_container_width=True):
                # ===== 任务标题验证功能 =====
                # 使用 str.strip() 去除首尾空格（Python字符串方法）
                title_trimmed = title.strip()
                title_length = len(title_trimmed)  # 使用 len() 获取字符串长度

                # ===== 使用 if/elif/else 条件判断进行验证 =====
                if not title_trimmed:
                    # 使用 st.error() 显示错误信息（Streamlit组件）
                    st.error("❌ 错误：任务标题不能为空！")
                elif title_length < 2:
                    # 使用 st.warning() 显示警告信息（Streamlit组件）
                    st.warning("⚠️ 警告：任务标题太短（至少2个字符）")
                elif title_length > 50:
                    st.warning("⚠️ 警告：任务标题过长（建议不超过50个字符）")
                else:
                    # 验证通过，保存任务
                    if edit_id:
                        # 更新现有任务 - 使用 for 循环查找并更新任务
                        for task in st.session_state.tasks:  # 遍历列表
                            if task['id'] == edit_id:  # 条件判断
                                task['title'] = title_trimmed
                                task['category'] = category if category else '未分类'
                                task['priority'] = priority
                                break  # 跳出循环
                        st.success("✅ 任务更新成功！")
                    else:
                        # 添加新任务 - 使用字典创建任务对象
                        new_task = {  # Python字典字面量
                            'id': len(st.session_state.tasks) + 1,
                            'title': title_trimmed,
                            'category': category if category else '未分类',
                            'priority': priority,
                            'completed': False,
                            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        # 使用 list.append() 方法添加元素到列表
                        st.session_state.tasks.append(new_task)
                        st.success("✅ 任务添加成功！")

                    # 重置页面状态
                    st.session_state.page = "任务列表"
                    st.session_state.edit_id = None
                    st.rerun()
                # ===== 任务标题验证功能结束 =====

        with col2:
            if st.form_submit_button("取消", use_container_width=True):
                st.session_state.page = "任务列表"
                st.session_state.edit_id = None
                st.rerun()

    # 处理完成任务
    completed_ids = [k.replace('check_', '') for k, v in st.session_state.items()
                    if k.startswith('check_') and isinstance(v, bool) and v]
    for task in st.session_state.tasks:
        task_id_str = str(task['id'])
        if task_id_str in completed_ids:
            task['completed'] = True
        elif f'check_{task_id_str}' in st.session_state:
            task['completed'] = st.session_state[f'check_{task_id_str}']
