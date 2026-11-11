# -*- coding: utf-8 -*-
"""
源文档标题整理交互组件（T04 / 工具箱）

2026-11-10 合并：原「源文档标题查漏」只读检查 + 原「源文档标题预处理」批量转标题。
两者共用同一套识别引擎、重叠太大，合并为一个入口：

    一次扫描 → 全部候选分类（漏检 / 正常标题 / 误套 / 疑似条款 / 正文条款）
             → 用户逐条决定（转标题 / 保持 / 降为正文）

设计原则（用户 2026-11-10 明确）：
    1) 尽量多识别、不遗漏 —— 引擎不丢候选，只分类；
    2) 区分「正常标题 / 异常标题 / 应降为正文的标题」；
    3) 处理权交给用户 —— 引擎只给建议，勾选与动作都由用户定。
"""
import hashlib
import html
import logging
import os
import threading
import time

import streamlit as st

from title_preprocessor import (
    ACTION_DEMOTE, ACTION_HEADING, ACTION_KEEP,
    CATEGORY_BODY, CATEGORY_MISUSE, CATEGORY_MISSING, CATEGORY_NORMAL,
    CATEGORY_ORDER, CATEGORY_SUSPECT, TitlePreprocessor,
)

logger = logging.getLogger('WordStyle')

# 识别引擎版本：参与结果缓存签名。识别规则一变就改这里，旧缓存自动失效，
# 避免界面还显示上一版规则的结果（2026-11-05 起沿用这个约定）。
_ENGINE_VER = '2026-11-11-organize-v3'

# 标题文字长度过滤的默认阈值（用户 2026-11-06 指定：默认 20 字符）。
DEFAULT_MAX_TITLE_CHARS = 20

# 每页渲染条数可选项。每条要渲染 3 个控件（勾选/编号/动作），一页 100 条约 300 个
# 控件；而 Streamlit 的任何控件交互都会重跑所在 fragment，行数越多单次响应越慢。
# 2026-11-10 用户反馈"每操作一下整个页面都会刷新"，改为可调、默认 50（更快），
# 需要一次看更多时自己切到 100/200。
# 同日用户追加要求"要具有一页显示所有记录的能力"：PAGE_ALL = 0 即"一页显示全部"，
# 实际每页条数取当前筛选后的总行数（行数很多时每次交互都会明显变慢，属预期）。
PAGE_SIZE_OPTIONS = [20, 50, 100, 200, 0]
PAGE_ALL = 0
DEFAULT_PAGE_SIZE = 50


def _page_size_label(n: int) -> str:
    """「每页条数」下拉项的显示文案。0 是"一页显示全部"的哨兵值。"""
    return '一页显示全部' if n == PAGE_ALL else f'每页 {n} 条'


def _effective_page_size(raw: int, total_rows: int) -> int:
    """把下拉里的原始值（可能为 PAGE_ALL 哨兵）换算成实际每页条数。"""
    return total_rows if raw == PAGE_ALL else int(raw)

# 列表列宽（表头与数据行共用同一组比例，否则列会错位）
_COL_WIDTHS = [0.42, 1.0, 3.1, 0.85, 1.55, 1.25, 1.45]
_HEAD_LABELS = ['选', '类别', '原文（含编号）', '新编号', '现样式', '建议', '处理方式']

# 类别徽章配色（背景, 文字）
_CATEGORY_COLORS = {
    CATEGORY_MISSING: ('#fff7ed', '#c2410c'),
    CATEGORY_NORMAL: ('#ecfdf5', '#047857'),
    CATEGORY_MISUSE: ('#fef2f2', '#b91c1c'),
    CATEGORY_SUSPECT: ('#fefce8', '#a16207'),
    CATEGORY_BODY: ('#f1f5f9', '#475569'),
}

# 五张计数卡的数字样式（用户 2026-11-11：字体黑色、加粗）。
# - st.metric 没有颜色/字重参数，只能走 CSS；
# - 用 st.container(key='tp_summary') 生成的 .st-key-* 限定作用域，
#   避免把侧边栏「剩余额度」等其它 st.metric 一起改掉；
# - 主题默认把 metric 数值染成强调色（深蓝），这里显式改回纯黑并加粗。
_SUMMARY_CSS = (
    "<style>\n"
    '    .st-key-tp_summary [data-testid="stMetricValue"] {\n'
    "        color: #000000 !important;\n"
    "        font-weight: 800 !important;\n"
    "    }\n"
    '    .st-key-tp_summary [data-testid="stMetricValue"] * {\n'
    "        color: inherit !important;\n"
    "        font-weight: inherit !important;\n"
    "    }\n"
    "</style>"
)

# 处理方式下拉项：顺序固定，索引稳定（会话里存的是字符串本身，不是索引）
_ACTION_OPTIONS = ['保持不动'] + [f'转为 H{i}' for i in range(1, 10)] + ['降为正文']


def _default_action(item) -> str:
    """按引擎建议给出默认处理方式。

    漏检 → 转标题（用户要求"尽量多识别"）；误套 → 降为正文；
    正常标题 / 疑似条款 / 正文条款 → 保持不动（不动就是最安全的）。
    """
    if item['category'] == CATEGORY_MISSING:
        return f"转为 H{item['detected_level']}"
    if item['category'] == CATEGORY_MISUSE:
        return '降为正文'
    return '保持不动'


def _default_selected(item) -> bool:
    """默认是否勾选：勾"引擎认为要动"的条目 —— 漏检与误套。

    误套默认勾选（用户 2026-11-11：默认按建议处理，漏检转标题、误套降为正文）；
    之前误套默认不勾（2026-11-10 的保守做法），需要用「快速选择」手动放开。
    疑似条款（带标题编号、说不准是标题还是正文）与正文条款仍从不默认勾选。
    """
    return item['category'] in (CATEGORY_MISSING, CATEGORY_MISUSE)


def _action_of(label: str) -> str:
    if label == '降为正文':
        return ACTION_DEMOTE
    if label == '保持不动':
        return ACTION_KEEP
    return ACTION_HEADING


def _level_of(label: str) -> int:
    if not label.startswith('转为 H'):
        return 0
    try:
        return int(label[len('转为 H'):])
    except ValueError:
        return 0


def _short(text: str, limit: int) -> str:
    text = text or ''
    return text if len(text) <= limit else text[:limit] + '…'


def _title_text(item) -> str:
    """「标题文字」——不含编号与分隔符，作为长度过滤的计量口径。

    不能直接数 text：那样 `7.4.17` 这 6 个字符会被算进长度里。
    """
    content = item.get('content')
    if isinstance(content, str) and content.strip():
        return content.strip()
    text = str(item.get('text') or '')
    number = str(item.get('number') or '')
    if number and text.startswith(number):
        text = text[len(number):]
    return text.lstrip(' \t\u3000.、．').strip()


def _widget_value(key: str, fallback):
    """优先取控件在 session_state 里的**本轮最新值**，取不到才用 fallback。

    为什么不能只读自己维护的 dict：「处理并下载」按钮渲染在列表**上方**，
    它执行时本轮列表还没渲染，dict 还停留在上一轮。用户「改完编号立刻点按钮」
    时，新值已经写进 session_state[key]，dict 却还没更新 → 新值被静默丢弃。
    """
    val = st.session_state.get(key)
    return fallback if val is None else val


class _TitleTask:
    """标题处理后台任务状态（线程安全，带代次防止旧线程覆盖新任务）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._gen = 0
        self.running = False
        self.done = 0
        self.total = 0
        self.finished = False
        self.error = None
        self.result = None

    def reset(self):
        with self._lock:
            self._gen += 1
            self.running = False
            self.done = 0
            self.total = 0
            self.finished = False
            self.error = None
            self.result = None

    def start(self, total):
        with self._lock:
            self._gen += 1
            self.running = True
            self.done = 0
            self.total = total
            self.finished = False
            self.error = None
            self.result = None
            return self._gen

    def update(self, gen, done, total):
        with self._lock:
            if gen != self._gen:
                return
            self.done = done
            self.total = total

    def finish(self, gen, error=None, result=None):
        with self._lock:
            if gen != self._gen:
                return
            self.running = False
            self.finished = True
            self.error = error
            self.result = result

    def snapshot(self):
        with self._lock:
            return (self.running, self.done, self.total,
                    self.finished, self.error, self.result)


_title_task = _TitleTask()


def _render_task_result(result):
    """渲染处理完成后的下载按钮与变更摘要（两处共用）。"""
    summary = result.get("summary") or {}
    st.success(
        f"✅ 处理完成：转标题 {summary.get(ACTION_HEADING, 0)} 条，"
        f"降为正文 {summary.get(ACTION_DEMOTE, 0)} 条。"
    )
    data = result.get("data")
    if data is None:
        with open(result["path"], 'rb') as f:
            data = f.read()
        result["data"] = data
    st.download_button(
        label=f"⬇️ 下载整理后的文档（{result['name']}）",
        data=data,
        file_name=result["name"],
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        key="title_organize_download",
    )
    demoted = result.get("demoted") or []
    if demoted:
        with st.expander(f"📉 已降为正文的 {len(demoted)} 条（点开核对）"):
            for row in demoted:
                st.markdown(f"- `{row['style']}` → 正文：{row['text']}")
    st.info("💡 建议将整理后的文档作为源文档上传到「📄 文档转换」页。")


@st.fragment(run_every="0.5s")
def _poll_task_progress():
    """有后台任务时才挂载的轮询片段：每 0.5s 刷新进度条。

    2026-11-10 调整：原来 `_render_task_progress` 本身带 run_every，空闲时也每
    0.5s 重跑一次，日志里刷出大量 "fragment does not exist anymore"，
    并且与列表翻页 / 勾选的重跑互相打断（实测翻页要 6 秒）。改成只在 running 时
    才挂载这个片段 —— 空闲期零轮询。
    """
    running, done, total, finished, error, result = _title_task.snapshot()
    if running:
        st.progress(done / total if total else 1.0)
        st.caption(f"⏳ 正在处理… {done}/{total}")
        return
    if not finished:
        return
    # 任务刚结束：整页重跑一次，把结果交给父级静态渲染。
    # 为什么不在轮询片段里直接画结果：轮询每 0.5s 都会重画一次下载按钮（携带整份
    # 文档字节），同时父级也在更新列表 —— 两个写入方叠在一起，实测会短暂留下
    # 错位的幽灵分页节点（截图可见）。这里只跳一次，父级随后走 _render_task_result。
    st.rerun()


def _render_task_progress():
    """任务进行中才挂载轮询片段；空闲时只在有新结果时内联渲染一次。"""
    running, done, total, finished, error, result = _title_task.snapshot()
    if running:
        _poll_task_progress()
        return
    if not finished:
        return
    if error:
        st.error(f"❌ 处理失败：{error}")
        return
    if result and os.path.exists(result["path"]):
        _render_task_result(result)


def _category_badge(item) -> str:
    bg, fg = _CATEGORY_COLORS.get(item['category'], ('#f1f5f9', '#475569'))
    label = item['category_label']
    if item['category'] == CATEGORY_MISUSE and item['confidence'] == 'high':
        label += '·高'
    return (f"<span style='display:inline-block;padding:1px 7px;border-radius:9px;"
            f"background:{bg};color:{fg};font-size:0.76rem;font-weight:700;"
            f"white-space:nowrap;'>{html.escape(label)}</span>")


def _suggestion_text(item) -> str:
    if item['suggestion'] == ACTION_HEADING:
        return f"转 H{item['detected_level']}"
    if item['suggestion'] == ACTION_DEMOTE:
        return '降为正文'
    return '保持'


def _load_items(user_id, uploaded, progress_callback):
    """解析上传文档并分类。返回 (items, temp_path)。

    临时文件只在缓存失效（换文件）时写一次，供后续 apply_changes 使用；
    每次交互都重写会让 3 秒的识别变成每次点击都付一次。
    """
    from config import TEMP_DIR
    temp_path = str(TEMP_DIR / f"temp_title_organize_{user_id}.docx")
    with open(temp_path, 'wb') as f:
        f.write(uploaded.getbuffer())
    items = TitlePreprocessor.classify_headings(
        temp_path, progress_callback=progress_callback)
    return items, temp_path


@st.fragment
def render_title_preprocess():
    """渲染「源文档标题整理」交互区。

    整个交互区包在 @st.fragment 里（2026-11-10 用户反馈"每操作一下整个页面都会刷新"）：
    勾选/改编号/切页/筛选只重跑本区块，不再重跑侧边栏、页面标题、JS 注入和另外两个
    标签页的组件。上传控件也放在 fragment 内 —— 换文档只影响本工具。
    """
    st.markdown(
        "一次扫描把文档里的标题候选**全部分类**，再由你决定怎么处理："
        "「漏检」是应为标题却没有标题格式的短条目；「正常标题」是已经带 Heading / "
        "大纲级别的条目；「误套」是套了标题样式但语义是正文的段落；"
        "「疑似条款」是**带标题编号**（多级，如 5.1.11.2.2）、却没有标题样式也没有"
        "大纲级别、读起来又像条文的条目——编号形态像标题，所以不能埋进正文条款，"
        "可单独筛选出来逐条确认（同父级编号连续、上一条已是疑似条款时，紧跟的短条目"
        "也归这一类，按同组条款处理）；"
        "「正文条款」是**不带标题编号**（单级枚举 1)、无编号）的正文长句。"
        "两者的区别就是**有没有标题编号**；建议都是**保持不动**。"
        "\n\n**处理方式**：转标题（套 Heading + 关掉 Word 自动编号 + 编号写进正文）、"
        "降为正文（换回正文样式 + 删大纲级别，保留原编号）、保持不动。"
    )

    user_id = st.session_state.get('user_id', 'default')

    uploaded = st.file_uploader(
        "上传源文档（支持 .docx）",
        type=['docx'],
        key="title_organize_uploader",
    )

    if uploaded is None:
        for _k in ("_to_sig", "_to_items", "_to_path"):
            st.session_state.pop(_k, None)
        st.info("📤 上传源文档后自动识别并分类标题。")
        return

    sig = (uploaded.name, uploaded.size, _ENGINE_VER)
    need_parse = (st.session_state.get("_to_sig") != sig
                  or "_to_items" not in st.session_state)

    if need_parse:
        bar = st.progress(0)
        status = st.empty()
        last_ts = [0.0]

        def _on_progress(done, total):
            frac = done / total if total else 0.0
            now = time.time()
            if frac >= 1.0 or now - last_ts[0] >= 0.1:
                last_ts[0] = now
                bar.progress(min(frac, 1.0))
                status.caption(f"🔍 正在识别并分类… {done}%")

        try:
            items, temp_path = _load_items(user_id, uploaded, _on_progress)
        except Exception as e:
            logger.exception("标题整理解析失败")
            st.error(f"❌ 文档解析失败：{e}")
            return

        bar.progress(1.0)
        status.caption("✅ 识别完成")

        st.session_state["_to_sig"] = sig
        st.session_state["_to_items"] = items
        st.session_state["_to_path"] = temp_path

        # 换文档：勾选/动作/编号全部按新文档重建，筛选回到默认值。
        # 必须写在对应控件渲染之前 —— 控件已实例化时写 session_state 会被忽略。
        st.session_state["title_organize_selected"] = {
            it['index']: _default_selected(it) for it in items}
        st.session_state["title_organize_actions"] = {
            it['index']: _default_action(it) for it in items}
        st.session_state["title_organize_numbers"] = {
            it['index']: it['number'] for it in items}
        st.session_state["to_only_abnormal"] = False
        st.session_state["to_hide_long"] = False
        st.session_state["to_max_chars"] = DEFAULT_MAX_TITLE_CHARS
        st.session_state["to_show_body"] = False
        st.session_state["to_hide_suspect"] = False
        st.session_state["to_quick"] = True   # 误套默认勾选，开关同步为"已勾"
        st.session_state["to_page"] = 0
        st.session_state["to_page_size"] = DEFAULT_PAGE_SIZE
        st.session_state["to_sel_epoch"] = 0
        for _pos in ("a", "b"):
            st.session_state[f"to_jump_{_pos}"] = 1
        _title_task.reset()

    items = st.session_state["_to_items"]
    temp_path = st.session_state.get("_to_path")

    if not items:
        st.warning("未识别到任何标题候选（文档里没有编号段落，也没有标题样式段落）。")
        return

    # 级别筛选的可选项：本文档实际出现的级别
    level_options = ["H%d" % n
                     for n in sorted({int(it['detected_level']) for it in items})]
    prev_levels = st.session_state.get("to_levels")
    if not isinstance(prev_levels, list) or any(v not in level_options for v in prev_levels):
        # 换文档后选项集合会变，先把残留的旧取值收敛掉（含首轮 None）
        st.session_state["to_levels"] = list(level_options)

    _render_summary(items)
    sel = _render_filters(items, level_options)
    selected_levels, only_abnormal, hide_long, max_chars = sel[:4]
    show_body, hide_suspect = sel[4], sel[5]

    # 计算当前筛选结果（分页前）
    rows = _filter_items(items, selected_levels, only_abnormal, hide_long,
                         max_chars, show_body, hide_suspect)
    total_rows = len(rows)

    st.markdown("---")
    _render_toolbar(items, rows, sig, temp_path)
    # 后台任务进度 / 结果展示（每 0.5s 轮询，不阻塞主界面）
    _render_task_progress()

    if not rows:
        if hide_suspect:
            st.info("当前筛选条件下没有条目。可调整上方筛选，或取消勾选过滤项。")
        else:
            st.info("当前筛选条件下没有条目。可调整上方筛选，或勾选「显示正文条款」。")
        return

    # PAGE_ALL（0）= 一页显示全部：实际条数取当前筛选后的总行数。
    # 必须在 rows 算出来之后换算（用户 2026-11-10 要求"一页显示所有记录"）。
    # 注意不能用 `or DEFAULT_PAGE_SIZE`：0 是合法取值（= 全部），会被 or 当假值吃掉。
    _raw_size = st.session_state.get("to_page_size")
    _raw_size = DEFAULT_PAGE_SIZE if _raw_size is None else int(_raw_size)
    page_size = _effective_page_size(_raw_size, total_rows)
    page = int(st.session_state.get("to_page") or 0)
    max_page = max((total_rows - 1) // page_size, 0)
    page = max(0, min(page, max_page))
    st.session_state["to_page"] = page
    page_rows = rows[page * page_size:(page + 1) * page_size]

    # 分页条在列表顶端和底端各一条（用户 2026-11-10 要求），
    # 「每页条数」只在顶端出现（它是设置项，不是导航）。
    _render_pager('a', total_rows, page, max_page, page_size, with_page_size=True)
    if _raw_size == PAGE_ALL:
        # 「一页显示全部」用 data_editor 单元素渲染：逐行控件在几百行时会超线性劣化
        # （实测 358 行 >400s），详见 _render_all_table 的说明。
        _render_all_table(rows, sig)
    else:
        _render_table(items, page_rows, sig)
    _render_pager('b', total_rows, page, max_page, page_size, with_page_size=False)


def _render_summary(items):
    """五张计数卡：漏检 / 正常 / 误套 / 疑似条款 / 正文条款。"""
    counts = {c: 0 for c in CATEGORY_ORDER}
    for it in items:
        counts[it['category']] = counts.get(it['category'], 0) + 1

    specs = [
        (CATEGORY_MISSING, '漏检（应为标题）'),
        (CATEGORY_NORMAL, '正常标题'),
        (CATEGORY_MISUSE, '误套（建议降为正文）'),
        (CATEGORY_SUSPECT, '疑似条款（带标题编号）'),
        (CATEGORY_BODY, '正文条款（不转标题）'),
    ]
    st.markdown(_SUMMARY_CSS, unsafe_allow_html=True)
    with st.container(key='tp_summary'):
        cols = st.columns(5)
        for col, (cat, label) in zip(cols, specs):
            with col:
                st.metric(label, counts.get(cat, 0))


def _render_filters(items, level_options):
    """筛选：格式异常 / 标题级别 / 长度上限 / 显示正文条款 / 不显示疑似条款。"""
    col_abn, col_level = st.columns([1.1, 2.9], vertical_alignment="center")
    with col_abn:
        only_abnormal = st.checkbox(
            "只看格式异常的条目", key="to_only_abnormal",
            help="格式异常 = 除「正常标题」以外的全部条目："
                 "「漏检」（该是标题却没有标题格式）、"
                 "「误套」（有标题格式但内容是正文）、"
                 "「疑似条款」「正文条款」（都没有标题格式）。")
    with col_level:
        col_lab, col_ms = st.columns([1.2, 2.8], vertical_alignment="top")
        with col_lab:
            st.markdown(
                "<div style='height:2.5rem;display:flex;align-items:center;"
                "text-align:left;font-size:1rem;white-space:nowrap;'>"
                "显示标题级别（可多选）</div>",
                unsafe_allow_html=True,
            )
        with col_ms:
            picked = st.multiselect(
                "显示标题级别（可多选）",
                options=level_options,
                # 不传 default：默认值已写进 st.session_state["to_levels"]，
                # 两处同时给会触发 Streamlit 的 "default value but also set via
                # Session State API" 告警。
                key="to_levels",
                label_visibility="collapsed",
                placeholder="默认全部显示；取消勾选即隐藏该级别",
            )

    col_hide, col_len = st.columns([1.1, 2.9], vertical_alignment="center")
    with col_hide:
        hide_long = st.checkbox(
            "不显示过长的标题", key="to_hide_long",
            help="勾选后隐藏标题文字超过右侧字符数的条目；不统计编号。",
        )
    with col_len:
        col_lab2, col_num, _ = st.columns([1.2, 0.85, 1.95], vertical_alignment="top")
        with col_lab2:
            st.markdown(
                "<div style='height:2.5rem;display:flex;align-items:center;"
                "text-align:left;font-size:1rem;white-space:nowrap;'>"
                "字符数上限（不含编号）</div>",
                unsafe_allow_html=True,
            )
        with col_num:
            if "to_max_chars" not in st.session_state:
                st.session_state["to_max_chars"] = DEFAULT_MAX_TITLE_CHARS
            max_chars = st.number_input(
                "字符数上限（不含编号）",
                min_value=1, max_value=300, step=1,
                key="to_max_chars",
                label_visibility="collapsed",
                help="默认 20。只数标题文字本身，标题编号（如 7.4.17）不计入。",
            )

    body_count = sum(1 for it in items if it['category'] == CATEGORY_BODY)
    suspect_count = sum(1 for it in items if it['category'] == CATEGORY_SUSPECT)
    # 两个开关**同一行**（用户 2026-11-11 要求）：它们是一对互斥视角的入口，
    # 分开两行会让人以为要分别设置。条数为 0 时也渲染（禁用），保持布局稳定、
    # 用户始终能看到功能入口。
    col_body, col_suspect = st.columns(2, vertical_alignment="center")
    with col_body:
        show_body = st.checkbox(
            f"显示「正文条款」条目（{body_count} 条，默认折叠）",
            key="to_show_body",
            disabled=body_count == 0,
            help="正文条款 = **不带标题编号**的正文长句（单级枚举 1)、"
                 "或无编号的整句），有明确正文特征（冒号/句末标点/整句/超 300 字）。"
                 "识别它们是为了不漏，但转成标题会把整段正文抬进目录，默认不显示。",
        )
    with col_suspect:
        hide_suspect = st.checkbox(
            f"不显示疑似条款（{suspect_count} 条）",
            key="to_hide_suspect",
            help="疑似条款 = **带标题编号**（多级，如 5.1.11.2.2）、"
                 "但没有标题样式也没有大纲级别、读起来像条文的条目——"
                 "编号形态像标题，说不准是标题还是正文。"
                 "同一父级编号连续、上一条为疑似条款时，紧跟的短条目也算这一类。"
                 "**默认显示**（先让你看到全貌）；勾上后从列表里过滤掉这一类，"
                 "取消勾选即恢复显示。",
        )

    return (set(picked or []), only_abnormal, hide_long, int(max_chars),
            show_body, hide_suspect)


def _filter_items(items, selected_levels, only_abnormal, hide_long, max_chars,
                  show_body, hide_suspect):
    """按筛选条件过滤，返回保持文档顺序的列表。

    类别是**并集**关系（用户 2026-11-11 明确）：
      · 默认五类全部显示，先给用户全貌；
      · 「显示正文条款」不勾 → 过滤掉正文条款；
      · 「不显示疑似条款」勾上 → 过滤掉疑似条款；
      · 两个开关互不排斥，也与其它类别无关，不存在「只看某一类」。
    级别、长度是**交集**过滤，作用在类别结果之上。

    「只看格式异常」= 保留 `category != CATEGORY_NORMAL` 的全部条目，
    因此**包含误套**（用户 2026-11-11 明确）；旧实现按 `is_heading` 判断，
    把误套一起滤掉了。
    """
    rows = []
    for it in items:
        if hide_suspect and it['category'] == CATEGORY_SUSPECT:
            continue
        if not show_body and it['category'] == CATEGORY_BODY:
            continue
        if only_abnormal and it['category'] == CATEGORY_NORMAL:
            # 「格式异常」= 除正常标题外的全部（用户 2026-11-11：**必须包含误套**）。
            # 旧实现按 `is_heading` 一刀切，把「有标题格式但内容是正文」的误套
            # 当成"格式没问题"过滤掉了 —— 恰好漏掉最该修的那一类。
            continue
        if ("H%d" % it['detected_level']) not in selected_levels:
            continue
        if hide_long and len(_title_text(it)) > max_chars:
            continue
        rows.append(it)
    return rows


def _set_row_state(idx, suffix, checked=None, action=None):
    """同时更新「控件状态」与「自维护 dict」。

    checkbox / selectbox 一旦有 key，之后每轮都以控件自身状态为准，
    `value` 参数会被忽略 —— 只改 dict 不写 session_state[key] 就是"点了没反应"。
    """
    selected = st.session_state["title_organize_selected"]
    actions = st.session_state["title_organize_actions"]
    if checked is not None:
        selected[idx] = checked
        st.session_state[f"to_check_{suffix}_{idx}"] = checked
    if action is not None:
        actions[idx] = action
        st.session_state[f"to_action_{suffix}_{idx}"] = action


def _preset_checked(item, include_misuse: bool) -> bool:
    """「恢复默认勾选」/「快速选择」的勾选判据（纯函数，便于离线单测）。

    漏检一定勾；误套由 `include_misuse` 决定；正常标题 / 疑似条款 / 正文条款从不自动勾。
    不再按 confidence 二次过滤 —— 用户 2026-11-10 反馈"勾了快速选择，误套还是没勾"。
    """
    if item['category'] == CATEGORY_MISSING:
        return True
    return bool(include_misuse and item['category'] == CATEGORY_MISUSE)


def _bump_epoch():
    """批量操作代次 +1：让「一页显示全部」的 data_editor 强制重挂。

    data_editor 会保留前端的编辑增量；批量操作改了 dict 后如果不重挂，
    下一轮表内旧值会把批量结果覆盖回去（实测风险，2026-11-10）。
    """
    st.session_state["to_sel_epoch"] = int(st.session_state.get("to_sel_epoch", 0)) + 1


def _apply_preset(items, suffix, include_misuse: bool):
    """按引擎建议重置**全部**条目的勾选与动作（「恢复默认勾选」按钮用）。

    漏检=勾选+转标题；误套=勾选+降为正文（`include_misuse=False` 时不勾）；
    正常标题/疑似条款/正文条款=不勾+保持。
    """
    _bump_epoch()
    for it in items:
        _set_row_state(it['index'], suffix,
                       checked=_preset_checked(it, include_misuse),
                       action=_default_action(it))


def _apply_misuse_toggle(items, suffix, on: bool):
    """「快速选择“误套”」开关：**只**改误套条目，其他类别一条都不碰。

    为什么单独一个函数（用户 2026-11-11 明确）：这个复选框只控制误套的选择，
    不能顺带把漏检/正常标题的勾选或处理方式重置掉 —— 用户可能已经逐条改过
    漏检的目标级别，被一次误套开关打回默认值是绝对不能接受的。

    勾上 → 误套全部勾选，处理方式置为「降为正文」；
    取消 → 误套全部取消勾选（处理方式保留，重新勾上仍是降为正文）。
    """
    _bump_epoch()
    for it in items:
        if it['category'] != CATEGORY_MISUSE:
            continue
        _set_row_state(it['index'], suffix, checked=on,
                       action='降为正文' if on else None)


def _render_toolbar(items, rows, sig, temp_path):
    """批量操作 + 快速选择 + 处理按钮。"""
    suffix = hashlib.md5(str(sig).encode('utf-8')).hexdigest()[:8]

    col_re, col_go = st.columns([1, 2])
    with col_re:
        if st.button("🔄 重新识别", key="to_redetect", use_container_width=True):
            for k in ("_to_sig", "_to_items", "_to_path"):
                st.session_state.pop(k, None)
            _title_task.reset()
            # 本函数已是 @st.fragment，这里只重跑工具区，不重跑整页。
            st.rerun(scope="fragment")
    with col_go:
        do_process = st.button(
            "🚀 按当前设置处理并下载", key="to_process",
            type="primary", use_container_width=True)

    col_all, col_inv, col_rest = st.columns(3)
    with col_all:
        if st.button("全选当前筛选", key="to_select_all", use_container_width=True):
            _bump_epoch()
            for it in rows:
                _set_row_state(it['index'], suffix, checked=True)
    with col_inv:
        if st.button("反选当前筛选", key="to_invert", use_container_width=True):
            _bump_epoch()
            selected = st.session_state["title_organize_selected"]
            for it in rows:
                idx = it['index']
                cur = st.session_state.get(f"to_check_{suffix}_{idx}",
                                           selected.get(idx, True))
                _set_row_state(idx, suffix, checked=not cur)
    with col_rest:
        if st.button("恢复默认勾选", key="to_reset_sel", use_container_width=True):
            # 默认已含误套（2026-11-11），开关同步置勾选状态，避免"显示未勾、实际已勾"。
            st.session_state["to_quick"] = True
            _apply_preset(items, suffix, True)
            st.rerun(scope="fragment")

    # 「快速选择“误套”」复选框：**只**控制误套条目的勾选（用户 2026-11-11 明确），
    # 不动漏检、正常标题、疑似条款、正文条款的勾选与处理方式。
    def _on_quick_change():
        _apply_misuse_toggle(items, suffix, bool(st.session_state.get("to_quick")))

    st.checkbox(
        "⚡ 快速选择“误套”（勾选并降为正文）",
        key="to_quick",
        on_change=_on_quick_change,
        help="只控制「误套」这一类：勾上 = 全部误套勾选、处理方式设为「降为正文」"
             "（默认就勾上，与列表里误套默认选中一致）；"
             "取消 = 取消全部误套的勾选，便于逐条确认。"
             "漏检的勾选与目标级别、正常标题 / 疑似条款 / 正文条款一概不受影响；"
             "也不改变上方筛选条件。",
    )

    if not do_process:
        return

    if _title_task.running:
        st.info("⏳ 正在处理中，请稍候…")
        return

    selected = st.session_state["title_organize_selected"]
    actions = st.session_state["title_organize_actions"]
    numbers = st.session_state["title_organize_numbers"]

    changes = []
    demoted_preview = []
    for it in items:
        idx = it['index']
        # 勾选与处理方式以 dict 为准（唯一事实源）：分页视图由 on_change 回调、
        # 「一页显示全部」由 data_editor 每轮同步，两条路都会即时写回 dict。
        # 不能读 to_check_* 控件 key——ALL 模式下这些 key 不更新，会读回旧值。
        if not selected.get(idx, _default_selected(it)):
            continue
        label = actions.get(idx, _default_action(it))
        action = _action_of(label)
        if action == ACTION_KEEP:
            continue
        if action == ACTION_HEADING:
            level = _level_of(label)
            if level < 1:
                continue
            changes.append({
                "index": idx,
                "action": ACTION_HEADING,
                "target_level": level,
                # 编号仍读控件值：用户可能在文本框里改了还没失焦就点处理，
                # session_state 里是尚未提交的新值，dict 还是旧的。
                "new_number": str(_widget_value(
                    f"to_num_{suffix}_{idx}", numbers.get(idx, it['number'])) or "").strip(),
            })
        else:
            changes.append({
                "index": idx,
                "action": ACTION_DEMOTE,
                "body_style": it.get('body_style_hint') or 'Normal',
            })
            demoted_preview.append({
                "style": it.get('style_name') or '',
                "text": _short(it['text'], 80),
            })

    if not changes:
        st.error("❌ 没有需要处理的条目：请至少勾选一条，并把处理方式设为"
                 "「转为 H*」或「降为正文」。")
        return

    from config import TEMP_DIR
    out_path = str(TEMP_DIR / f"title_organized_{st.session_state.get('user_id', 'default')}.docx")
    # 文件名要在主线程取出：后台线程里读 st.session_state 拿不到会话上下文。
    source_name = getattr(st.session_state.get("title_organize_uploader"), "name", "source.docx")
    gen = _title_task.start(len(changes))

    def _work():
        try:
            def _on_progress(done, total):
                _title_task.update(gen, done, total)

            summary = TitlePreprocessor.apply_changes(
                temp_path, out_path, changes, progress_callback=_on_progress)
            _title_task.finish(gen, result={
                "path": out_path,
                "name": f"标题整理_{source_name}",
                "summary": summary,
                "demoted": demoted_preview,
            })
        except Exception as e:
            logger.exception("标题整理处理失败")
            _title_task.finish(gen, error=str(e))

    threading.Thread(target=_work, daemon=True).start()


def _sync_jump_inputs(target):
    """把两个分页条的「跳转到」输入框同步到目标页（target 为 0-based）。

    只能写 `st.session_state[key]`：这类函数只作为按钮 / 控件的 on_click、on_change
    回调使用，回调发生在脚本重跑之前，此时控件尚未实例化，写入才合法
    （重跑后控件已实例化再写会抛 StreamlitAPIException）。
    """
    st.session_state["to_page"] = int(target)
    for pos in ("a", "b"):
        st.session_state[f"to_jump_{pos}"] = int(target) + 1


def _on_jump(pos):
    """「跳转到 __ 页」输入框变化：收敛到合法页码后切页。"""
    try:
        target = int(st.session_state.get(f"to_jump_{pos}") or 1) - 1
    except (TypeError, ValueError):
        target = 0
    _sync_jump_inputs(max(0, target))


def _on_page_size_change():
    """改每页条数后回到第一页，避免停在越界页码上。"""
    _sync_jump_inputs(0)


def _render_pager(pos, total_rows, page, max_page, page_size, with_page_size):
    """分页条：首页 / 上一页 / 下一页 / 末页 / 跳转 __ 页（可选每页条数）。

    用户 2026-11-10 要求列表顶端与底端各有一条，翻长列表不用滚回顶部。
    """
    if with_page_size:
        widths = [0.8, 0.9, 2.0, 0.9, 0.8, 1.35, 1.5]
    else:
        widths = [0.8, 0.9, 2.0, 0.9, 0.8, 1.35, 1.5]
    cols = st.columns(widths, vertical_alignment="center")

    def _nav(container, label, key, target, disabled=False):
        with container:
            st.button(label, key=key, use_container_width=True, disabled=disabled,
                      on_click=_sync_jump_inputs, args=(target,))

    _nav(cols[0], "⏮ 首页", f"to_first_{pos}", 0, disabled=page <= 0)
    _nav(cols[1], "← 上一页", f"to_prev_{pos}", page - 1, disabled=page <= 0)
    with cols[2]:
        st.markdown(
            f"<div style='text-align:center;color:#64748b;font-size:0.9rem;"
            f"line-height:2.4rem;'>共 {total_rows} 条 · 第 {page + 1}/{max_page + 1} 页</div>",
            unsafe_allow_html=True,
        )
    _nav(cols[3], "下一页 →", f"to_next_{pos}", page + 1, disabled=page >= max_page)
    _nav(cols[4], "末页 ⏭", f"to_last_{pos}", max_page, disabled=page >= max_page)

    with cols[5]:
        key = f"to_jump_{pos}"
        # 先收敛再渲染：筛选条件变化会让总页数变小，残留的旧页码可能已经越界，
        # number_input 拿到越界值会直接报错。这里在控件实例化之前写，是合法时机。
        cur = st.session_state.get(key)
        if not isinstance(cur, int) or cur < 1 or cur > max_page + 1:
            st.session_state[key] = page + 1
        st.number_input(
            "跳转到第几页", min_value=1, max_value=max_page + 1, step=1,
            key=key, label_visibility="collapsed",
            on_change=_on_jump, args=(pos,),
            help="输入页码后按回车跳转",
        )

    with cols[6]:
        if with_page_size:
            # session_state 里存的必须是下拉选项本身（20/50/100/200/0），
            # 不能存换算后的总行数——否则 selectbox 会因值不在 options 里报错。
            if "to_page_size" not in st.session_state:
                st.session_state["to_page_size"] = DEFAULT_PAGE_SIZE
            st.selectbox(
                "每页条数", options=PAGE_SIZE_OPTIONS, key="to_page_size",
                label_visibility="collapsed", on_change=_on_page_size_change,
                format_func=_page_size_label,
                help="行数越多，勾选/翻页等每次操作的响应越慢；"
                     "「一页显示全部」适合最后一轮总核对。",
            )


def _category_plain(item) -> str:
    """data_editor 里的类别纯文本（不支持 HTML 徽章）。"""
    label = item['category_label']
    if item['category'] == CATEGORY_MISUSE and item['confidence'] == 'high':
        label += '·高'
    return label


def _all_editor_key(rows, sig) -> str:
    """「一页显示全部」编辑器的控件 key。

    必须随「行集合 + 批量操作代次」变化：
      - 行集合变（筛选变化）→ 重新挂载，避免旧编辑增量错位到新行上；
      - 批量操作（全选/反选/快速选择/恢复默认）→ 代次 +1 强制重挂，
        否则编辑器会保留前端的旧编辑值，把批量结果又覆盖回去。
    """
    h = hashlib.md5(str(sig).encode('utf-8'))
    h.update(str(st.session_state.get("to_sel_epoch", 0)).encode())
    for it in rows:
        h.update(str(it['index']).encode())
    return f"to_all_{h.hexdigest()[:10]}"


def _render_all_table(rows, sig):
    """「一页显示全部」：用 st.data_editor 单元素渲染全部记录。

    为什么不用逐行控件：实测（2026-11-10）逐行 7 列 + 3 控件的布局在 100 行时
    端到端 8.3s，358 行时要 400s 以上仍未渲染完——元素数量上千后超线性劣化。
    data_editor 是单个虚拟化表格元素：358 行端到端 6.5s、1000 行 3.5s。

    编辑结果每轮同步回三个 dict（唯一事实源），与分页视图完全等价。
    """
    import pandas as pd

    selected = st.session_state["title_organize_selected"]
    actions = st.session_state["title_organize_actions"]
    numbers = st.session_state["title_organize_numbers"]

    st.caption(
        "📋 一页显示全部记录（表内滚动查看）。勾选、新编号、处理方式可直接在表内修改，"
        "改动即时同步；切回「每页 50 条」后编辑仍保留。"
    )

    data = []
    for it in rows:
        idx = it['index']
        act = actions.get(idx, _default_action(it))
        if act not in _ACTION_OPTIONS:
            act = '保持不动'
        data.append({
            # 隐藏的序号列：同步时按它对齐，而不是按行位置。
            # data_editor 允许点表头排序，排序后 edited 的行序会变，
            # 按位置同步会把编辑写到错误的行上（2026-11-10 加固）。
            '序号': int(idx),
            '选': bool(selected.get(idx, _default_selected(it))),
            '类别': _category_plain(it),
            '原文（含编号）': it['text'],
            '新编号': str(numbers.get(idx, it['number']) or ''),
            '现样式': it['style_description'],
            '建议': _suggestion_text(it),
            '处理方式': act,
        })

    edited = st.data_editor(
        pd.DataFrame(data),
        key=_all_editor_key(rows, sig),
        hide_index=True,
        use_container_width=True,
        height=760,
        num_rows='fixed',
        disabled=['类别', '原文（含编号）', '现样式', '建议'],
        column_config={
            # None = 在表格里隐藏该列（数据仍随 edited 返回，用于行对齐）
            '序号': None,
            '选': st.column_config.CheckboxColumn(width='small'),
            '类别': st.column_config.TextColumn(width='small'),
            '原文（含编号）': st.column_config.TextColumn(width='large'),
            '新编号': st.column_config.TextColumn(width='small'),
            '现样式': st.column_config.TextColumn(width='medium'),
            '建议': st.column_config.TextColumn(width='small'),
            '处理方式': st.column_config.SelectboxColumn(
                options=_ACTION_OPTIONS, width='medium'),
        },
    )

    # 把表内编辑结果同步回 dict：按隐藏序号列对齐（排序也安全）。
    suffix = hashlib.md5(str(sig).encode('utf-8')).hexdigest()[:8]
    for _, row in edited.iterrows():
        try:
            idx = int(row['序号'])
        except (KeyError, TypeError, ValueError):
            continue
        selected[idx] = bool(row['选'])
        numbers[idx] = str(row['新编号'] or '').strip()
        label = str(row['处理方式'] or '保持不动')
        actions[idx] = label if label in _ACTION_OPTIONS else '保持不动'
        # 同步「新编号」控件 key：处理步骤读编号时先看 session_state（为了拿到
        # 用户输入但未失焦的值）。ALL 模式下这些 key 不会随表内编辑更新，
        # 不写这里会读回上一次分页视图的旧编号。
        st.session_state[f"to_num_{suffix}_{idx}"] = numbers[idx]


def _render_table(items, page_rows, sig):
    """渲染当前页的表格（表头 + 行）。

    ⚠️ 跨页勾选持久化的关键机制（2026-11-10 实测定案）：

    Streamlit 只会把「本轮脚本运行内、控件实例化之前」写入 session_state 的值
    推送给前端控件；**上一轮写入的值（按钮体/回调/批量预设）对从未挂载过的控件
    不生效**——前端按控件默认值渲染，随后又把默认值上报回来，把服务端状态一起
    污染掉。这就是"翻页丢勾选、全选只对当前页生效"的根因（AppTest 测不出来，
    它绕过了前端协议；必须用真实浏览器验证）。

    修复模式（最小应用 mini_app2.py 验证通过）：
      1) 每轮渲染每行时，**先把 dict 值写进控件 key 再实例化**——本轮写入
         一定会推送到前端，无论控件是否挂载过；
      2) 控件加 on_change 回调，把用户交互后的值同步回 dict——保证预写用的
         dict 值就是用户最新选择（用户刚点的勾不会被预写回滚）。
    两个动作合起来：dict 是唯一事实源，控件只是它的投影。
    """
    suffix = hashlib.md5(str(sig).encode('utf-8')).hexdigest()[:8]

    head_cols = st.columns(_COL_WIDTHS, vertical_alignment="center")
    for col, label in zip(head_cols, _HEAD_LABELS):
        with col:
            st.markdown(
                "<div style='font-size:0.82rem;font-weight:700;color:#64748b;"
                f"line-height:1.6;'>{label}</div>",
                unsafe_allow_html=True,
            )
    st.markdown(
        "<div style='height:1px;background:#e2e8f0;margin:0 0 0.4rem 0;'></div>",
        unsafe_allow_html=True,
    )

    selected = st.session_state["title_organize_selected"]
    actions = st.session_state["title_organize_actions"]
    numbers = st.session_state["title_organize_numbers"]

    # on_change 回调：把控件交互后的最新值同步回 dict。
    # 回调发生在重跑之前（此时 session_state 里已是控件新值），
    # 这样下一轮预写用的 dict 值就是用户刚交互的值，不会被回滚。
    def _sync_check(idx):
        selected[idx] = bool(st.session_state[f"to_check_{suffix}_{idx}"])

    def _sync_action(idx):
        actions[idx] = st.session_state[f"to_action_{suffix}_{idx}"]

    def _sync_number(idx):
        numbers[idx] = str(st.session_state.get(f"to_num_{suffix}_{idx}") or '').strip()

    for it in page_rows:
        idx = it['index']
        col_check, col_cat, col_text, col_num, col_style, col_hint, col_action = st.columns(
            _COL_WIDTHS, vertical_alignment="center")

        with col_check:
            _k = f"to_check_{suffix}_{idx}"
            # 预写（本轮写入）：见函数 docstring。注意不能同时传 value=，
            # 否则触发 "default value but also set via Session State API" 告警。
            st.session_state[_k] = bool(
                selected.get(idx, _default_selected(it)))
            selected[idx] = st.checkbox(
                "选", key=_k, label_visibility="collapsed",
                on_change=_sync_check, args=(idx,))

        with col_cat:
            st.markdown(_category_badge(it), unsafe_allow_html=True)

        with col_text:
            # 整段原文放进 title 属性：列里截断，鼠标悬停看全文
            st.markdown(
                f"<div title=\"{html.escape(it['text'])}\" "
                "style='font-size:0.86rem;line-height:1.5;color:#0f172a;'>"
                f"{html.escape(_short(it['text'], 58))}</div>",
                unsafe_allow_html=True,
            )

        with col_num:
            _k = f"to_num_{suffix}_{idx}"
            _v = str(numbers.get(idx, it['number']) or '')
            st.session_state[_k] = _v
            numbers[idx] = st.text_input(
                "新编号", key=_k, label_visibility="collapsed",
                on_change=_sync_number, args=(idx,))

        with col_style:
            st.markdown(
                f"<div title=\"{html.escape(it['style_description'])}\" "
                "style='font-size:0.8rem;color:#64748b;line-height:1.4;'>"
                f"{html.escape(_short(it['style_description'], 18))}</div>",
                unsafe_allow_html=True,
            )

        with col_hint:
            # 判定依据放进 tooltip：一行放不下，但用户复核时需要它
            st.markdown(
                f"<div title=\"{html.escape(it.get('reason_text') or '')}\" "
                "style='font-size:0.82rem;color:#475569;line-height:1.4;'>"
                f"{html.escape(_suggestion_text(it))}</div>",
                unsafe_allow_html=True,
            )

        with col_action:
            _k = f"to_action_{suffix}_{idx}"
            _v = actions.get(idx, _default_action(it))
            if _v not in _ACTION_OPTIONS:
                _v = '保持不动'
            st.session_state[_k] = _v
            actions[idx] = st.selectbox(
                "处理方式", options=_ACTION_OPTIONS, key=_k,
                label_visibility="collapsed",
                on_change=_sync_action, args=(idx,))
