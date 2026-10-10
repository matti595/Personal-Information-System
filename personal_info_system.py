"""个人成长信息管理系统

运行方式：
    streamlit run personal_info_system.py

本程序使用 CSV 文件保存数据，不依赖外部数据库，适合课程作业演示。
它把个人信息分为荣誉/证书、学习记录、项目经历和社团/实践四类，
实现信息录入、条件筛选、统计展示、删除和 CSV 下载。
"""

from pathlib import Path
import shutil
from typing import Optional

import pandas as pd
import streamlit as st


# -------------------- 基础配置与数据层 --------------------
st.set_page_config(
    page_title="个人成长信息管理系统",
    page_icon="📚",
    layout="wide",
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "records.csv"
LEGACY_CSV_PATH = DATA_DIR / "personal_records.csv"

# 不同类型的信息都统一保存为一条记录，方便后续查询和统计。
COLUMNS = [
    "id",
    "record_type",
    "title",
    "record_date",
    "status",
    "priority",
    "tags",
    "content",
    "link",
    "is_favorite",
    "created_at",
]

RECORD_TYPES = ["荣誉/证书", "学习记录", "项目经历", "社团/实践"]
STATUS_OPTIONS = ["未开始", "进行中", "已完成", "暂缓"]
PRIORITY_OPTIONS = ["低", "中", "高"]


def empty_dataframe() -> pd.DataFrame:
    """返回一个带有完整列名的空表。"""
    return pd.DataFrame(columns=COLUMNS)


def existing_data_path() -> Optional[Path]:
    """优先使用课件约定的文件名，同时兼容上一版程序的数据文件。"""
    if CSV_PATH.exists():
        return CSV_PATH
    if LEGACY_CSV_PATH.exists():
        return LEGACY_CSV_PATH
    return None


def load_data() -> pd.DataFrame:
    """从 CSV 读取数据，处理不存在、为空和损坏三种情况。"""
    data_path = existing_data_path()
    if data_path is None:
        return empty_dataframe()

    try:
        df = pd.read_csv(data_path, encoding="utf-8-sig")
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        ValueError,
    ):
        # 保留问题现场，避免用户下次运行时再次遇到同一个损坏文件。
        backup_path = DATA_DIR / (
            f"{data_path.stem}.corrupt."
            f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
        )
        backup_succeeded = False
        try:
            shutil.move(str(data_path), str(backup_path))
            backup_succeeded = True
            st.warning(
                "原数据文件无法读取，系统已将其备份为 "
                f"{backup_path.name}，并重新建立空数据表。"
            )
        except OSError:
            st.warning("原数据文件无法读取，系统将以空数据表继续运行。")
        fresh_df = empty_dataframe()
        if backup_succeeded:
            save_data(fresh_df)
        return fresh_df

    # 兼容文件缺少某些列的情况，并保证列顺序固定。
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[COLUMNS]


def save_data(df: pd.DataFrame) -> bool:
    """把当前 DataFrame 保存为 CSV，且只写入 data/ 目录。"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df = df.copy()
        for column in COLUMNS:
            if column not in df.columns:
                df[column] = ""
        df[COLUMNS].to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        return True
    except OSError:
        st.error("数据保存失败，请检查 data 文件夹是否具有写入权限。")
        return False


def next_id(df: pd.DataFrame) -> int:
    """生成下一条记录的整数 ID。"""
    if df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    return 1 if ids.empty else int(ids.max()) + 1


def clean_text(value: str) -> str:
    """清理文本首尾空格，避免保存大量无意义空白。"""
    return value.strip()


def generate_local_insight(df: pd.DataFrame) -> str:
    """根据本地数据生成简单洞察。

    这是独立的分析层函数，不修改数据读取和保存逻辑。
    当前用本地规则完成，未来可以在保持函数输入输出不变的情况下替换成大模型 API。
    """
    if df.empty:
        return "目前还没有记录。先新增几条信息，系统就可以生成成长概况。"

    type_counts = df["record_type"].value_counts()
    status_counts = df["status"].value_counts()
    main_type = type_counts.index[0]
    completed = int((df["status"] == "已完成").sum())
    in_progress = int((df["status"] == "进行中").sum())
    high_priority = int((df["priority"] == "高").sum())

    insight = (
        f"当前共有 {len(df)} 条记录，数量最多的是“{main_type}”，"
        f"共 {int(type_counts.iloc[0])} 条。"
    )
    suggestions = []
    if in_progress > completed:
        suggestions.append("进行中的事项多于已完成事项，可以优先收尾一项。")
    if high_priority:
        suggestions.append(f"目前有 {high_priority} 条高优先级记录，建议及时安排后续行动。")
    if "荣誉/证书" not in type_counts.index:
        suggestions.append("可以补充荣誉或证书记录，形成更完整的个人成长档案。")
    if not suggestions:
        suggestions.append("各类记录比较均衡，可以继续保持定期整理的习惯。")

    status_summary = "、".join(
        f"{status}{int(count)}条" for status, count in status_counts.items()
    )
    return insight + f" 当前状态分布为：{status_summary}。\n\n建议：" + " ".join(suggestions)


def show_insight(df: pd.DataFrame) -> None:
    """展示独立的本地规则洞察模块。"""
    st.subheader("智能洞察（本地规则版）")
    st.caption("当前使用本地统计规则，后续可替换为大模型 API。")
    st.info(generate_local_insight(df))


# -------------------- 输入功能 --------------------
def input_form(df: pd.DataFrame) -> pd.DataFrame:
    """收集一条个人信息，并在点击保存后写入 CSV。"""
    st.subheader("新增一条信息")

    with st.form("add_record_form", clear_on_submit=True):
        first_row = st.columns([1.2, 2.2, 1.2])
        with first_row[0]:
            record_type = st.selectbox("信息类型 *", RECORD_TYPES)
        with first_row[1]:
            title = st.text_input("标题 *", placeholder="例如：数据库课程 Lecture 3")
        with first_row[2]:
            record_date = st.date_input("日期 *")

        second_row = st.columns([1.2, 1.2, 2.4])
        with second_row[0]:
            status = st.selectbox("状态", STATUS_OPTIONS, index=1)
        with second_row[1]:
            priority = st.select_slider("优先级", options=PRIORITY_OPTIONS, value="中")
        with second_row[2]:
            tags = st.text_input("标签", placeholder="多个标签用逗号分隔，例如：数据库,作业")

        content = st.text_area(
            "详细内容",
            placeholder="记录这条信息的具体内容、心得、下一步行动等……",
            height=110,
        )
        link = st.text_input("相关链接（可选）", placeholder="https://...")
        is_favorite = st.checkbox("加入重点记录")

        submitted = st.form_submit_button(
            "保存信息",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        title = clean_text(title)
        content = clean_text(content)
        tags = clean_text(tags)
        link = clean_text(link)

        if not title:
            st.error("请先填写标题。")
            return df

        new_record = {
            "id": next_id(df),
            "record_type": record_type,
            "title": title,
            "record_date": record_date.strftime("%Y-%m-%d"),
            "status": status,
            "priority": priority,
            "tags": tags,
            "content": content,
            "link": link,
            "is_favorite": "是" if is_favorite else "否",
            "created_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        if save_data(df):
            st.success("信息保存成功。")

    return df


# -------------------- 查询、统计与删除功能 --------------------
def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    """根据侧边栏条件筛选记录。"""
    st.sidebar.header("查询条件")
    keyword = st.sidebar.text_input("关键词", placeholder="搜索标题、标签或详细内容")
    selected_type = st.sidebar.selectbox("信息类型", ["全部"] + RECORD_TYPES)
    selected_status = st.sidebar.selectbox("状态", ["全部"] + STATUS_OPTIONS)
    only_favorite = st.sidebar.checkbox("只看重点记录")

    result = df.copy()
    if keyword:
        searchable = result[["title", "tags", "content"]].fillna("").astype(str).agg(" ".join, axis=1)
        result = result[searchable.str.contains(keyword, case=False, na=False)]
    if selected_type != "全部":
        result = result[result["record_type"] == selected_type]
    if selected_status != "全部":
        result = result[result["status"] == selected_status]
    if only_favorite:
        result = result[result["is_favorite"].astype(str) == "是"]
    return result


def show_statistics(df: pd.DataFrame) -> None:
    """展示记录总数、完成数、进行中数量和重点记录数。"""
    total = len(df)
    completed = int((df["status"] == "已完成").sum()) if not df.empty else 0
    in_progress = int((df["status"] == "进行中").sum()) if not df.empty else 0
    favorites = int((df["is_favorite"].astype(str) == "是").sum()) if not df.empty else 0

    cards = st.columns(4)
    cards[0].metric("记录总数", total)
    cards[1].metric("已完成", completed)
    cards[2].metric("进行中", in_progress)
    cards[3].metric("重点记录", favorites)


def delete_record(df: pd.DataFrame) -> pd.DataFrame:
    """按 ID 删除一条记录。"""
    if df.empty:
        return df

    st.subheader("删除记录")
    ids = pd.to_numeric(df["id"], errors="coerce").dropna().astype(int).tolist()
    selected_id = st.selectbox("选择要删除的记录 ID", ids)
    if st.button("删除所选记录", type="secondary"):
        df = df[pd.to_numeric(df["id"], errors="coerce") != selected_id].copy()
        if save_data(df):
            st.rerun()
    return df


def show_records(df: pd.DataFrame, filtered_df: pd.DataFrame) -> None:
    """展示筛选结果，并提供 CSV 下载。"""
    st.subheader("信息列表")
    st.caption(f"当前显示 {len(filtered_df)} 条，共保存 {len(df)} 条。")

    display_columns = {
        "id": "编号",
        "record_type": "类型",
        "title": "标题",
        "record_date": "日期",
        "status": "状态",
        "priority": "优先级",
        "tags": "标签",
        "content": "详细内容",
        "link": "链接",
        "is_favorite": "重点",
    }
    display_df = filtered_df[list(display_columns)].rename(columns=display_columns)
    st.dataframe(display_df, hide_index=True, use_container_width=True)

    csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "下载当前筛选结果 CSV",
        data=csv_data,
        file_name="records.csv",
        mime="text/csv",
        use_container_width=True,
    )


# -------------------- 页面主体 --------------------
st.title("📚 个人成长信息管理系统")
st.caption("记录学习、项目与实践经历，让个人信息可持续积累、查询和整理。")

df = load_data()
df = input_form(df)

show_statistics(df)
show_insight(df)

st.divider()
filtered_df = filter_data(df)
show_records(df, filtered_df)

if not df.empty:
    st.divider()
    df = delete_record(df)
