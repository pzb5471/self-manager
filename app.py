import hashlib
from collections import Counter
from datetime import datetime, timedelta

import altair as alt
import streamlit as st

from service import TaskService


st.set_page_config(page_title="个人能效管理", page_icon="📵", layout="wide")


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


def quadrant_to_axes(quadrant: int) -> tuple[float, float]:
    mapping = {
        1: (8.0, 8.0),  # high importance, high urgency
        2: (8.0, 3.0),  # high importance, low urgency
        3: (3.0, 8.0),  # low importance, high urgency
        4: (3.0, 3.0),  # low importance, low urgency
    }
    return mapping.get(quadrant, (5.0, 5.0))


def jitter_from_task(task_id: int, axis: str) -> float:
    seed = f"{task_id}-{axis}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    return ((digest[0] / 255.0) - 0.5) * 1.2


def ensure_auth_state() -> None:
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "page" not in st.session_state:
        st.session_state.page = "首页统计"
    if "edit_id" not in st.session_state:
        st.session_state.edit_id = None


def do_logout(service: TaskService) -> None:
    token = st.session_state.auth_token
    if token:
        service.logout(token)
    st.session_state.auth_token = None
    st.session_state.current_user = None
    st.session_state.page = "首页统计"
    st.session_state.edit_id = None


def render_auth_page(service: TaskService) -> None:
    left, right = st.columns([1.1, 1], gap="large")

    with left:
        st.title("个人能效系统")
        st.markdown("### 聚焦重要事项，减少低价值忙碌")
        st.write("- 四象限可视化管理任务")
        st.write("- 图表化统计，快速掌握任务分布")
        st.write("- 支持多用户安全隔离")

    with right:
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


def get_filtered_sorted_tasks(
    service: TaskService,
    user_id: int,
    keyword: str,
    category_filter: str,
    quadrant_filter: str,
    sort_key: str,
) -> list[dict]:
    if keyword.strip():
        tasks = service.search_tasks(user_id=user_id, keyword=keyword)
    else:
        tasks = service.get_all_tasks(user_id=user_id)

    if category_filter != "全部":
        tasks = [task for task in tasks if task["category"] == category_filter]
    if quadrant_filter != "全部":
        tasks = [task for task in tasks if task["quadrant"] == int(quadrant_filter)]

    if not keyword.strip() and category_filter == "全部" and quadrant_filter == "全部":
        return service.get_sorted_tasks(user_id=user_id, sort_by=sort_key)

    sort_field = "created_at" if "created" in sort_key else "updated_at"
    reverse = "desc" in sort_key
    return sorted(tasks, key=lambda t: (t[sort_field], t["id"]), reverse=reverse)


def build_trend_data(tasks: list[dict], days: int = 14) -> list[dict]:
    today = datetime.utcnow().date()
    start = today - timedelta(days=days - 1)

    counter = Counter()
    for task in tasks:
        try:
            d = datetime.strptime(task["created_at"], "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            continue
        if d >= start:
            counter[d.isoformat()] += 1

    series = []
    for i in range(days):
        current = start + timedelta(days=i)
        iso = current.isoformat()
        series.append({"date": iso, "count": counter.get(iso, 0)})
    return series


def render_dashboard_page(service: TaskService, user_id: int) -> None:
    st.title("任务统计首页")

    stats = service.get_statistics(user_id)
    tasks = service.get_all_tasks(user_id)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("总任务", stats["total"])
    metric_col2.metric("Q1任务", stats["by_quadrant"][1])
    metric_col3.metric("Q2任务", stats["by_quadrant"][2])
    metric_col4.metric("近14天新增", sum(point["count"] for point in build_trend_data(tasks, days=14)))

    category_values = [
        {"category": category, "count": count}
        for category, count in stats["by_category"].items()
    ]
    quadrant_values = [
        {"quadrant": f"Q{quadrant}", "count": count}
        for quadrant, count in stats["by_quadrant"].items()
    ]
    trend_values = build_trend_data(tasks, days=14)

    top_left, top_right = st.columns(2)
    with top_left:
        st.subheader("分类分布")
        pie = (
            alt.Chart(alt.Data(values=category_values))
            .mark_arc(innerRadius=55)
            .encode(theta=alt.Theta("count:Q"), color=alt.Color("category:N"), tooltip=["category:N", "count:Q"])
            .properties(height=320)
        )
        st.altair_chart(pie, use_container_width=True)

    with top_right:
        st.subheader("四象限任务量")
        bar = (
            alt.Chart(alt.Data(values=quadrant_values))
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("quadrant:N", title="象限"),
                y=alt.Y("count:Q", title="任务数"),
                color=alt.Color("quadrant:N", legend=None),
                tooltip=["quadrant:N", "count:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(bar, use_container_width=True)

    st.subheader("近14天任务新增趋势")
    trend = (
        alt.Chart(alt.Data(values=trend_values))
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="日期"),
            y=alt.Y("count:Q", title="新增任务数"),
            tooltip=["date:T", "count:Q"],
        )
        .properties(height=320)
    )
    st.altair_chart(trend, use_container_width=True)


def render_quadrant_page(service: TaskService, user_id: int) -> None:
    st.title("四象限任务")

    f1, f2, f3, f4 = st.columns([2, 1.3, 1.3, 1.4])
    with f1:
        keyword = st.text_input("搜索任务", placeholder="标题或描述")
    with f2:
        category = st.selectbox("分类", ["全部"] + service.get_categories())
    with f3:
        quadrant = st.selectbox("象限", ["全部", "1", "2", "3", "4"])
    with f4:
        sort_option = st.selectbox(
            "排序",
            [
                ("最新创建", "created_desc"),
                ("最早创建", "created_asc"),
                ("最新更新", "updated_desc"),
                ("最早更新", "updated_asc"),
            ],
            format_func=lambda item: item[0],
        )

    tasks = get_filtered_sorted_tasks(
        service=service,
        user_id=user_id,
        keyword=keyword,
        category_filter=category,
        quadrant_filter=quadrant,
        sort_key=sort_option[1],
    )

    if not tasks:
        st.info("暂无任务，去“添加任务”页面创建第一条任务。")
        return

    scatter_values = []
    for task in tasks:
        x, y = quadrant_to_axes(task["quadrant"])
        scatter_values.append(
            {
                "id": task["id"],
                "title": task["title"],
                "category": task["category"],
                "quadrant": f"Q{task['quadrant']}",
                "importance": max(0, min(10, x + jitter_from_task(task["id"], "x"))),
                "urgency": max(0, min(10, y + jitter_from_task(task["id"], "y"))),
                "created_at": task["created_at"],
            }
        )

    points = (
        alt.Chart(alt.Data(values=scatter_values))
        .mark_circle(size=180, opacity=0.8)
        .encode(
            x=alt.X("importance:Q", scale=alt.Scale(domain=[0, 10]), title="重要程度"),
            y=alt.Y("urgency:Q", scale=alt.Scale(domain=[0, 10]), title="紧急程度"),
            color=alt.Color("quadrant:N", title="象限"),
            tooltip=["title:N", "category:N", "quadrant:N", "created_at:N"],
        )
    )

    vline = alt.Chart(alt.Data(values=[{"x": 5}])).mark_rule(strokeDash=[8, 6], color="#888").encode(x="x:Q")
    hline = alt.Chart(alt.Data(values=[{"y": 5}])).mark_rule(strokeDash=[8, 6], color="#888").encode(y="y:Q")

    chart = (points + vline + hline).properties(height=520)
    st.altair_chart(chart, use_container_width=True)

    st.caption("横轴=重要程度，纵轴=紧急程度；中线用于区分四象限。")

    st.subheader(f"任务明细（{len(tasks)}）")
    for task in tasks:
        card = st.container(border=True)
        with card:
            info_col, action_col = st.columns([4, 1])
            with info_col:
                st.markdown(f"**{task['title']}**")
                st.caption(f"{task['category']} | {quadrant_label(task['quadrant'])}")
                if task["description"]:
                    st.write(task["description"])
                st.caption(f"创建: {task['created_at']}  更新: {task['updated_at']}")
            with action_col:
                if st.button("编辑", key=f"edit_{task['id']}", use_container_width=True):
                    st.session_state.edit_id = task["id"]
                    st.session_state.page = "添加任务"
                    st.rerun()
                if st.button("删除", key=f"del_{task['id']}", use_container_width=True):
                    service.delete_task(task["id"], user_id)
                    st.success("任务已删除")
                    st.rerun()


def render_task_editor_page(service: TaskService, user_id: int) -> None:
    is_edit = st.session_state.edit_id is not None
    st.title("编辑任务" if is_edit else "添加任务")

    edit_task = service.get_task_by_id(st.session_state.edit_id, user_id) if is_edit else None
    if is_edit and edit_task is None:
        st.warning("任务不存在，已返回四象限任务页面。")
        st.session_state.edit_id = None
        st.session_state.page = "四象限任务"
        st.rerun()

    categories = service.get_categories()
    quadrant_options = [1, 2, 3, 4]

    with st.form("task_form"):
        title = st.text_input("任务标题", value=edit_task["title"] if edit_task else "")
        description = st.text_area("任务描述", value=edit_task["description"] if edit_task else "")

        c1, c2 = st.columns(2)
        with c1:
            default_category = edit_task["category"] if edit_task else categories[0]
            category = st.selectbox("分类", categories, index=categories.index(default_category))
        with c2:
            default_quadrant = edit_task["quadrant"] if edit_task else 1
            quadrant = st.selectbox("四象限", quadrant_options, index=quadrant_options.index(default_quadrant))
            st.caption(quadrant_label(quadrant))

        b1, b2 = st.columns(2)
        with b1:
            submit_save = st.form_submit_button("保存任务", use_container_width=True)
        with b2:
            submit_cancel = st.form_submit_button("取消", use_container_width=True)

    if submit_save:
        try:
            title_trimmed = title.strip()
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
            st.session_state.page = "四象限任务"
            st.rerun()
        except ValueError as error:
            st.error(str(error))

    if submit_cancel:
        st.session_state.edit_id = None
        st.session_state.page = "四象限任务"
        st.rerun()


ensure_auth_state()
service = get_task_service()

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

selected_page = st.sidebar.radio("导航", ["首页统计", "四象限任务", "添加任务"])
if st.session_state.page != selected_page:
    st.session_state.page = selected_page

if st.session_state.page == "首页统计":
    render_dashboard_page(service, user_id)
elif st.session_state.page == "四象限任务":
    render_quadrant_page(service, user_id)
else:
    render_task_editor_page(service, user_id)
