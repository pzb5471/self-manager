import streamlit as st

from service import TaskService


st.set_page_config(page_title="个人能效管理", page_icon="📵")


@st.cache_resource
def get_task_service() -> TaskService:
    return TaskService(db_path="productivity_manager.db")


def quadrant_label(quadrant: int) -> str:
    labels = {
        1: "第一象限（重要且紧急）",
        2: "第二象限（重要不紧急）",
        3: "第三象限（紧急不重要）",
        4: "第四象限（不紧急不重要）",
    }
    return labels.get(quadrant, f"第{quadrant}象限")


def ensure_auth_state() -> None:
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "page" not in st.session_state:
        st.session_state.page = "任务列表"
    if "edit_id" not in st.session_state:
        st.session_state.edit_id = None


def do_logout(service: TaskService) -> None:
    token = st.session_state.auth_token
    if token:
        service.logout(token)
    st.session_state.auth_token = None
    st.session_state.current_user = None
    st.session_state.page = "任务列表"
    st.session_state.edit_id = None


def render_auth_page(service: TaskService) -> None:
    st.title("个人能效系统")
    st.subheader("请先登录")

    login_tab, register_tab = st.tabs(["登录", "注册"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("用户名")
            password = st.text_input("密码", type="password")
            submit_login = st.form_submit_button("登录", use_container_width=True)

        if submit_login:
            result = service.login_user(username, password)
            if not result:
                st.error("用户名或密码错误")
            else:
                st.session_state.auth_token = result["token"]
                st.session_state.current_user = result["user"]
                st.success("登录成功")
                st.rerun()

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("注册用户名")
            password = st.text_input("注册密码", type="password")
            confirm_password = st.text_input("确认密码", type="password")
            submit_register = st.form_submit_button("注册", use_container_width=True)

        if submit_register:
            if password != confirm_password:
                st.error("两次输入的密码不一致")
            else:
                try:
                    service.register_user(username, password)
                    st.success("注册成功，请在登录页登录")
                except ValueError as error:
                    st.error(f"注册失败：{error}")



def render_task_item(service: TaskService, user_id: int, task: dict) -> None:
    task_id = task["id"]
    with st.container():
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.markdown(f"**{task['title']}**")
            if task["description"]:
                st.caption(task["description"])
        with col2:
            st.markdown(f"{task['category']} | {quadrant_label(task['quadrant'])}")
            st.caption(f"创建: {task['created_at']}")
            st.caption(f"更新: {task['updated_at']}")
        with col3:
            if st.button("编辑", key=f"edit_{task_id}"):
                st.session_state.edit_id = task_id
                st.session_state.page = "添加任务"
                st.rerun()
            if st.button("删除", key=f"del_{task_id}"):
                service.delete_task(task_id, user_id)
                st.success("任务删除成功")
                st.rerun()
        st.markdown("---")


ensure_auth_state()
service = get_task_service()

# Validate token every run.
current_user = None
if st.session_state.auth_token:
    current_user = service.verify_token(st.session_state.auth_token)
    if current_user is None:
        do_logout(service)

if current_user is None:
    render_auth_page(service)
    st.stop()

user_id = current_user["id"]
st.session_state.current_user = {
    "id": current_user["id"],
    "username": current_user["username"],
    "created_at": current_user["created_at"],
}

st.sidebar.title("📵 个人能效管理")
st.sidebar.caption(f"当前用户：{current_user['username']}")
if st.sidebar.button("退出登录", use_container_width=True):
    do_logout(service)
    st.rerun()

sidebar_page = st.sidebar.radio("选择页面", ["任务列表", "添加任务"])
page = st.session_state.page if st.session_state.page != "任务列表" else sidebar_page

if page == "任务列表":
    st.header("任务列表")

    st.subheader("任务统计")
    stats = service.get_statistics(user_id)
    stat_col1, stat_col2, stat_col3 = st.columns(3)

    with stat_col1:
        st.metric("总任务数", stats["total"])

    with stat_col2:
        st.write("**按分类统计**")
        for category, count in stats["by_category"].items():
            st.write(f"- {category}: {count} 个")

    with stat_col3:
        st.write("**按象限统计**")
        for quadrant, count in stats["by_quadrant"].items():
            st.write(f"- Q{quadrant}: {count} 个")

    st.markdown("---")

    st.subheader("搜索与排序")
    search_col, sort_col = st.columns([2, 2])
    with search_col:
        search_keyword = st.text_input("搜索任务（按标题或描述）", placeholder="输入关键词...")
    with sort_col:
        sort_option = st.selectbox(
            "排序方式",
            [
                ("最新创建优先", "created_desc"),
                ("最早创建优先", "created_asc"),
                ("最新更新优先", "updated_desc"),
                ("最早更新优先", "updated_asc"),
            ],
            format_func=lambda x: x[0],
        )

    st.markdown("---")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_category = st.selectbox("分类", ["全部"] + service.get_categories())
    with col2:
        selected_quadrant = st.selectbox("象限", ["全部", 1, 2, 3, 4])
    with col3:
        st.write("")
        if st.button("刷新"):
            st.rerun()

    if search_keyword:
        tasks_to_process = service.search_tasks(user_id=user_id, keyword=search_keyword)
    else:
        tasks_to_process = service.get_all_tasks(user_id=user_id)

    category_filter = None if selected_category == "全部" else selected_category
    quadrant_filter = None if selected_quadrant == "全部" else int(selected_quadrant)

    if category_filter or quadrant_filter:
        filtered_tasks = []
        for task in tasks_to_process:
            if category_filter and task["category"] != category_filter:
                continue
            if quadrant_filter and task["quadrant"] != quadrant_filter:
                continue
            filtered_tasks.append(task)
    else:
        filtered_tasks = tasks_to_process

    sort_key = sort_option[1]
    if not search_keyword and not category_filter and not quadrant_filter:
        sorted_tasks = service.get_sorted_tasks(user_id=user_id, sort_by=sort_key)
    else:
        sorted_tasks = sorted(
            filtered_tasks,
            key=lambda t: (t["created_at"] if "created" in sort_key else t["updated_at"], t["id"]),
            reverse="desc" in sort_key,
        )

    st.subheader(f"当前结果：{len(sorted_tasks)} 个任务")
    if not sorted_tasks:
        st.info("暂无任务")
    else:
        for task in sorted_tasks:
            render_task_item(service, user_id, task)

    st.subheader("视图面板")
    tab_quadrant, tab_category = st.tabs(["四象限视图", "分类视图"])

    with tab_quadrant:
        quadrant_groups = {1: [], 2: [], 3: [], 4: []}
        for task in sorted_tasks:
            quadrant_groups[task["quadrant"]].append(task)

        q_col1, q_col2 = st.columns(2)
        with q_col1:
            st.markdown("### Q1")
            st.caption(quadrant_label(1))
            for task in quadrant_groups[1]:
                st.write(f"- {task['title']}（{task['category']}）")
            st.markdown("### Q3")
            st.caption(quadrant_label(3))
            for task in quadrant_groups[3]:
                st.write(f"- {task['title']}（{task['category']}）")
        with q_col2:
            st.markdown("### Q2")
            st.caption(quadrant_label(2))
            for task in quadrant_groups[2]:
                st.write(f"- {task['title']}（{task['category']}）")
            st.markdown("### Q4")
            st.caption(quadrant_label(4))
            for task in quadrant_groups[4]:
                st.write(f"- {task['title']}（{task['category']}）")

    with tab_category:
        categories = service.get_categories()
        category_groups = {category: [] for category in categories}
        for task in sorted_tasks:
            category_groups[task["category"]].append(task)

        for category in categories:
            with st.expander(f"{category}（{len(category_groups[category])}）", expanded=True):
                if not category_groups[category]:
                    st.write("- 暂无任务")
                else:
                    for task in category_groups[category]:
                        st.write(f"- {task['title']}（Q{task['quadrant']}）")

    if st.button("+ 添加任务", use_container_width=True):
        st.session_state.page = "添加任务"
        st.session_state.edit_id = None
        st.rerun()

elif page == "添加任务":
    is_edit = st.session_state.edit_id is not None
    st.header("编辑任务" if is_edit else "添加任务")

    edit_task = service.get_task_by_id(st.session_state.edit_id, user_id) if is_edit else None
    if is_edit and edit_task is None:
        st.warning("任务不存在，已返回任务列表。")
        st.session_state.edit_id = None
        st.session_state.page = "任务列表"
        st.rerun()

    categories = service.get_categories()
    quadrant_options = [1, 2, 3, 4]

    with st.form("task_form"):
        title = st.text_input("任务标题", value=edit_task["title"] if edit_task else "")
        description = st.text_area("任务描述", value=edit_task["description"] if edit_task else "")

        col1, col2 = st.columns(2)
        with col1:
            default_category = edit_task["category"] if edit_task else categories[0]
            category = st.selectbox("分类", categories, index=categories.index(default_category))
        with col2:
            default_quadrant = edit_task["quadrant"] if edit_task else 1
            quadrant = st.selectbox("象限", quadrant_options, index=quadrant_options.index(default_quadrant))

        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            submit_save = st.form_submit_button("保存", use_container_width=True)
        with action_col2:
            submit_cancel = st.form_submit_button("取消", use_container_width=True)

    if submit_save:
        title_trimmed = title.strip()
        if not title_trimmed:
            st.error("错误：任务标题不能为空")
        elif len(title_trimmed) < 2:
            st.warning("警告：任务标题太短（至少2个字符）")
        elif len(title_trimmed) > 50:
            st.warning("警告：任务标题过长（建议不超过50个字符）")
        else:
            try:
                if is_edit:
                    service.update_task(
                        task_id=st.session_state.edit_id,
                        user_id=user_id,
                        title=title_trimmed,
                        description=description,
                        category=category,
                        quadrant=quadrant,
                    )
                    st.success("任务更新成功")
                else:
                    service.add_task(
                        user_id=user_id,
                        title=title_trimmed,
                        description=description,
                        category=category,
                        quadrant=quadrant,
                    )
                    st.success("任务添加成功")

                st.session_state.edit_id = None
                st.session_state.page = "任务列表"
                st.rerun()
            except ValueError as error:
                st.error(f"{error}")

    if submit_cancel:
        st.session_state.edit_id = None
        st.session_state.page = "任务列表"
        st.rerun()
