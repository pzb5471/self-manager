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

    # 筛选任务
    filtered_tasks = st.session_state.tasks
    if selected_category != "全部":
        filtered_tasks = [t for t in filtered_tasks if t.get('category', '未分类') == selected_category]
    if selected_priority != "全部":
        filtered_tasks = [t for t in filtered_tasks if t.get('priority', '中') == selected_priority]

    # 显示任务统计
    st.subheader(f"共 {len(filtered_tasks)} 个任务")

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
                if not title.strip():
                    st.error("任务标题不能为空")
                else:
                    if edit_id:
                        # 更新现有任务
                        for task in st.session_state.tasks:
                            if task['id'] == edit_id:
                                task['title'] = title
                                task['category'] = category if category else '未分类'
                                task['priority'] = priority
                                break
                        st.success("任务更新成功！")
                    else:
                        # 添加新任务
                        new_task = {
                            'id': len(st.session_state.tasks) + 1,
                            'title': title,
                            'category': category if category else '未分类',
                            'priority': priority,
                            'completed': False,
                            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        st.session_state.tasks.append(new_task)
                        st.success("任务添加成功！")

                    st.session_state.page = "任务列表"
                    st.session_state.edit_id = None
                    st.rerun()

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
