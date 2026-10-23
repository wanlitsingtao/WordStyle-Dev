# -*- coding: utf-8 -*-
"""
补全标题编号交互组件（T04 / 工具箱标签：补全标题编号）

与「源文档标题预处理」互补：
    源文档标题预处理：编号标题 → 补标题样式/大纲级别
    补全标题编号（本组件）：标题样式/大纲级别 → 补编号文字

交互顺序：
    上传 → 自动检测 → 预览编辑（统计数字 + 编号设置 + 勾选/级别/编号）→ 生成并下载
"""
import hashlib
import os
import time

import streamlit as st

from title_numberer import TitleNumberer

# 分隔符选项：键为界面文案，值为实际写入的字符
SEPARATOR_OPTIONS = {
    '空格': ' ',
    '制表符': '\t',
    '全角空格': '\u3000',
}
_DEFAULT_SEP_LABEL = '空格'

# 统计数字样式（值加粗放大）。
# - st.metric 没有字号/字重参数，只能走 CSS；
# - 用 st.container(key='title_numbering_stats') 生成的 .st-key-* 限定作用域，
#   避免把侧边栏「剩余额度」等其它 st.metric 一起放大；
# - 字号引用 ui_theme 的 --ws-font-stat-*，缺失时回落到字面值，
#   保证脱离 app.py 单独渲染（测试环境）也不失效。
_STATS_CSS = (
    "<style>\n"
    '    .st-key-title_numbering_stats [data-testid="stMetricValue"] {\n'
    "        font-size: var(--ws-font-stat-value, 2rem) !important;\n"
    "        font-weight: 800 !important;\n"
    "        line-height: 1.15 !important;\n"
    "    }\n"
    '    .st-key-title_numbering_stats [data-testid="stMetricValue"] * {\n'
    "        font-size: inherit !important;\n"
    "        font-weight: inherit !important;\n"
    "    }\n"
    '    .st-key-title_numbering_stats [data-testid="stMetricLabel"] {\n'
    "        font-size: var(--ws-font-stat-label, 1rem) !important;\n"
    "        font-weight: 700 !important;\n"
    "    }\n"
    '    .st-key-title_numbering_stats [data-testid="stMetricLabel"] * {\n'
    "        font-size: inherit !important;\n"
    "        font-weight: inherit !important;\n"
    "    }\n"
    "</style>"
)


def _read_numbering_options():
    """读上一轮保存的编号设置（前缀、分隔符），供控件渲染**之前**的编号计算使用。

    为什么需要它：
        「编号设置」控件现在显示在统计数字下方（用户要求），而统计里的编号
        必须先知道前缀才能算。Streamlit 的控件在渲染那一刻才产生返回值，
        没法「先算后画」，因此这里读 session_state（上一轮由控件写入）。
        首次运行没有状态，回落到与控件默认值完全一致的 (空前缀, 空格)，
        不会出现「按空前缀算、控件却显示 C」的错位。
    """
    prefix = str(st.session_state.get('title_numbering_prefix_input', '') or '').strip()
    label = st.session_state.get('title_numbering_separator', _DEFAULT_SEP_LABEL)
    if label not in SEPARATOR_OPTIONS:
        label = _DEFAULT_SEP_LABEL
    return prefix, SEPARATOR_OPTIONS[label]


def _render_numbering_options():
    """渲染「编号设置」控件（前缀 + 分隔符），返回 (前缀, 分隔符字符)。"""
    col_prefix, col_sep = st.columns([2, 1])
    with col_prefix:
        prefix = st.text_input(
            "增加前缀",
            key="title_numbering_prefix_input",
            placeholder="留空则不加前缀；填 C 得到 C1、C1.1、C1.1.1",
            help="前缀同时作用于自动生成的编号与原文已有编号；中文编号（第一章）不加前缀。",
        ).strip()
    with col_sep:
        sep_label = st.selectbox(
            "编号与标题之间",
            options=list(SEPARATOR_OPTIONS.keys()),
            index=0,
            key="title_numbering_separator",
            help="写入编号后紧跟的分隔符，与标题正文隔开。",
        )
    if prefix:
        st.caption(f"预览效果：`{prefix}1`、`{prefix}1.1`、`{prefix}1.1.1` …")
    return prefix, SEPARATOR_OPTIONS[sep_label]


def _detect_cached(user_id: str, uploaded_file) -> dict:
    """按文件内容 md5 缓存检测结果。

    为什么必须缓存：
        Streamlit 每次交互（改前缀、改级别、勾选）都会重跑本函数，而检测要把整份
        docx 解析成 Document 对象再逐段扫描。不缓存的话，每敲一个字符就把文档重新
        解析一遍，157 个标题的样本还能忍，上万段的标书会明显卡顿。
    缓存键用**内容 md5**而不是文件名：
        同一份文件反复上传、或用户改了文件名但内容没变，都应命中缓存；
        反过来，同名但内容变了必须重新检测，否则会拿到过期的段落索引。
    """
    from config import TEMP_DIR

    raw = uploaded_file.getbuffer().tobytes()
    file_key = hashlib.md5(raw).hexdigest()[:16]

    cache = st.session_state.get('_title_numbering_cache')
    if cache and cache.get('key') == file_key:
        return cache

    temp_path = str(TEMP_DIR / f"temp_title_numbering_{user_id}.docx")
    with open(temp_path, 'wb') as f:
        f.write(raw)

    started = time.time()
    items = TitleNumberer.detect(temp_path)
    cache = {
        'key': file_key,
        'path': temp_path,
        'items': items,
        'elapsed': time.time() - started,
    }
    st.session_state._title_numbering_cache = cache
    # 换了文件 → 之前那份文档的编辑状态、生成结果全部作废。
    # 不清会造成两个后果：① 旧 edits 的段落索引套到新文档上，级别/勾选错位；
    # ② 页面底部还挂着上一份文档的下载按钮，用户可能下错文件。
    # data_editor 的编辑增量现在是按 key 存在 session_state 里的（键名带文件 md5），
    # 换文件后旧键不会再被读取，这里顺手清掉，避免长会话里越积越多。
    for _stale in [k for k in st.session_state.keys()
                   if k.startswith('title_numbering_editor_')]:
        try:
            st.session_state.pop(_stale, None)
        except Exception:
            # data_editor 的 widget 状态不允许直接 pop。留着也无害：key 里带文件 md5，
            # 新文件的 key 与之不同，旧状态永远不会再被读到。
            pass
    st.session_state.pop('title_numbering_edits', None)
    st.session_state.pop('title_numbering_result', None)
    return cache


def _action_label(p):
    """把内部动作翻译成给人看的说明。

    keep 且结构编号与原文编号不一致时要点出来：这类段落多半是人工编号与标题层级
    对不上（或层级识别错了），保留原文是正确的默认行为，但用户需要看到这个差异
    才知道该去改级别还是该接受现状。
    """
    if p['action'] == 'insert':
        return '写入'
    if p['action'] == 'replace':
        # 用户改了编号 → 原文的旧编号会被替换掉，这里要说清楚是"改写"不是"跳过"
        return '改写编号'
    if p['action'] == 'keep':
        if p.get('number_mismatch'):
            return f"保留原文（结构应为 {p.get('generated_number')}）"
        return '保留原文'
    return '跳过'


def _row_notes(it) -> str:
    """每行的附加说明（级别来源、冲突、已有编号、疑似编号）。"""
    note = []
    if it['level_source'] == 'outline':
        note.append('级别来自大纲')
    if it['level_conflict']:
        note.append(f"⚠ 样式H{it['style_level']}/大纲H{it['outline_level']}")
    if it['existing_number']:
        sign = it['existing_sign'] or ''
        # 不写"（保留）"：编号列可改，改成别的值时就变成 replace 了，
        # 这里只陈述原文事实，处理结果由「处理」列表达。
        note.append(f"原文编号 {sign}{it['existing_number']}")
    elif it.get('existing_cjk_number'):
        # 中文编号的原文已写进「处理」列（"保留中文编号 第一章"），这里不再重复。
        note.append('中文编号体系，未换算')
    elif it.get('suspected_number'):
        note.append("⚠ 疑似已有编号但缺分隔符，请核对")
    return '；'.join(note)


def _build_editor_df(plan) -> "object":
    """构建编辑表：应用 / 级别 / 编号 三列可编辑，其余只读。

    关于「编号」列为空：空串 = 这一行不编号（也不占号），界面上用 placeholder
    画成 "—"。不用 "—" 当实际值，是为了让用户清空单元格时语义无歧义。
    """
    import pandas as pd

    rows = []
    for p in plan:
        rows.append({
            '应用': bool(p.get('apply', True)),
            '级别': int(p['level']),
            '编号': p['display_number'] or '',
            '写入后标题': p['new_text'],
            '处理': _action_label(p),
            '说明': _row_notes(p),
        })
    return pd.DataFrame(rows, columns=['应用', '级别', '编号', '写入后标题', '处理', '说明'])


def _apply_edits(items, edits):
    """把 session_state 里保存的用户编辑（应用/级别）合并回检测结果。

    编号不在这里合并：它走 `overrides` 参数，因为编号会参与计数回填，
    必须在 compute_numbers 内部按行序处理，不能简单覆盖。
    """
    out = []
    for pos, it in enumerate(items):
        item = dict(it)
        e = edits.get(pos) or {}
        if 'apply' in e:
            item['apply'] = bool(e['apply'])
        if 'level' in e:
            item['level'] = int(e['level'])
        out.append(item)
    return out


def _overrides_from(edits):
    """{行位置: 用户输入的编号}，只取用户显式改过编号的行。"""
    return {pos: str(e['number'])
            for pos, e in edits.items() if 'number' in e}


def _pending_edits(editor_key):
    """读 data_editor 的**待处理编辑**（st.session_state[key] → DataEditorState）。

    为什么能在控件渲染**之前**读到：
        key 化的控件，前端编辑状态在每次 rerun 开始时就已写进 session_state
        （与 text_input 的读取时机完全一样）。先读它 → 算出编号 → 再渲染，
        编号就能在**同一轮**更新，不必额外 rerun 一次重画整张表。
        这是官方支持的读法：DataEditorState = {edited_rows, added_rows, deleted_rows}，
        edited_rows 的键是**行位置**（对应 items 下标，与我们的 edits 键一致）。

    读不到时返回 {}（首轮、或控件状态被清），调用方会自动退回"渲染后 diff + rerun"。
    """
    state = st.session_state.get(editor_key)
    if state is None:
        return {}
    try:
        rows = state['edited_rows'] or {}
    except Exception:
        # 不同版本/序列化路径下可能是别的容器类型；读不到就走兜底路径，不影响功能
        return {}

    out = {}
    for pos, cells in rows.items():
        if not isinstance(cells, dict):
            continue
        e = {}
        if '应用' in cells:
            e['apply'] = bool(cells['应用'])
        if '级别' in cells:
            try:
                e['level'] = int(cells['级别'])
            except (TypeError, ValueError):
                pass
        if '编号' in cells:
            v = cells['编号']
            e['number'] = '' if v is None else str(v).strip()
        if e:
            try:
                out[int(pos)] = e
            except (TypeError, ValueError):
                continue
    return out


def _merge_edits(stored, pending, items):
    """合并"已保存的编辑"与"本轮待处理编辑"，并做归一化。

    pending 优先级更高：它始终反映前端的当前状态，用户改回原值后
    pending 就是原值，覆盖掉 stored 里的旧记录，正好实现"改回去=解锁"。
    """
    merged = {pos: dict(e) for pos, e in stored.items()}
    for pos, e in pending.items():
        merged.setdefault(pos, {}).update(e)

    for pos in list(merged):
        e = merged[pos]
        # 归一化：改回默认值 = 没改，避免 edits 越堆越多、
        # 也避免把某行永久钉死（后面改级别时这一行不再重算）。
        if e.get('apply') is True:
            e.pop('apply', None)
        if 'level' in e and pos < len(items) and int(e['level']) == int(items[pos]['level']):
            e.pop('level', None)
        if not e:
            merged.pop(pos)
    return merged


def _collect_edits(df, edited, items, old_edits):
    """比较"传进去的表"和"控件返回的表"，把用户改动收进 edits。

    这是**兜底路径**：正常流程里 `_pending_edits` 已经在渲染前拿到改动，
    编号当轮就画对了，这里 diff 不到任何变化。只有预读失效（控件状态被清、
    或未来 Streamlit 改了行为）时才会 diff 出差异，此时仍需再跑一轮把编号刷出来。

    为什么必须 diff 而不是直接取返回值：
        `edited` 是**整张表**（含未改动行），若把所有行都记成"用户指定"，
        编号会被永久锁死，改级别也不会再重算。只有和传入 df 不同的单元格
        才是用户真正动过的。

    为什么要在旧 edits 基础上增量合并：
        df 本身已经是"应用旧 edits 之后"的结果。用户没再动某格时，
        `edited` 与 `df` 相等，这一格的编辑记录必须原样保留 —— 这正是
        早先"取消勾选又自动勾上"的根因（每轮从零重算，记录就丢了）。
    """
    import pandas as pd

    new_edits = {pos: dict(e) for pos, e in old_edits.items()}

    for pos in range(len(df)):
        e = new_edits.get(pos) or {}

        a_old = bool(df.iloc[pos]['应用'])
        a_new = bool(edited.iloc[pos]['应用'])
        l_old = int(df.iloc[pos]['级别'])
        l_new = int(edited.iloc[pos]['级别'])
        n_old = '' if pd.isna(df.iloc[pos]['编号']) else str(df.iloc[pos]['编号']).strip()
        n_new = '' if pd.isna(edited.iloc[pos]['编号']) else str(edited.iloc[pos]['编号']).strip()

        if a_new != a_old:
            e['apply'] = a_new
        if l_new != l_old:
            e['level'] = l_new
        if n_new != n_old:
            e['number'] = n_new

        # 归一化：改回默认值的项删掉，避免 edits 里堆一堆无意义记录
        if e.get('apply') is True:
            e.pop('apply', None)
        if 'level' in e and e['level'] == int(items[pos]['level']):
            e.pop('level', None)

        if e:
            new_edits[pos] = e
        else:
            new_edits.pop(pos, None)

    return new_edits


@st.fragment
def render_title_numbering():
    """渲染补全标题编号交互区（@st.fragment 局部刷新）。"""
    st.markdown(
        "为**已具有标题样式（Heading N）或大纲级别**、但正文里没有编号文字的标题，"
        "按全文层级结构自动补上 `1` / `1.1` / `1.1.1` 形式的编号。"
        "若文档里有的标题已经带编号（如 `★1.2 工程范围`），默认原样保留、只占号不覆盖。"
    )

    user_id = st.session_state.get('user_id', 'default')

    uploaded = st.file_uploader(
        "上传源文档（支持 .docx）",
        type=['docx'],
        key="title_numbering_uploader",
    )

    if uploaded is None:
        st.info("📤 上传源文档后自动分析标题结构。")
        return

    # ---------------- 检测 ----------------
    try:
        with st.spinner("🔍 正在分析标题结构…"):
            cache = _detect_cached(user_id, uploaded)
    except Exception as e:
        st.error(f"❌ 文档解析失败：{e}")
        return

    items = cache['items']
    if not items:
        st.warning(
            "未检测到标题段落。本工具只处理**已设置标题样式（Heading 1-9）或大纲级别**的段落；"
            "若标题只是普通正文格式，请先到「📑 源文档标题预处理」为它们设置标题样式。"
        )
        return

    st.caption(
        f"✅ 共检测到 **{len(items)}** 个标题段落"
        f"（用时 {cache['elapsed']:.1f}s）；未设标题样式/大纲级别的正文段落不会被改动。"
    )

    # ---------------- 预览编辑（含编号，一个表） ----------------
    st.markdown("---")
    st.markdown("##### 👀 预览编辑")
    st.caption(
        "「应用」取消勾选 → 该标题不编号、也不占号（后续同级标题编号保持连续）；"
        "「级别」可逐条修正；**「编号」可直接改**（清空=不编号）。"
        "三者任一改动，编号与写入后标题都会立即重算。"
    )

    # key 里带"代次"：点重置时代次 +1 → 控件被重建 → 前端累积的编辑状态清空。
    # 只清 session_state 是无效的：data_editor 的编辑状态存在**控件自己**里
    # （且官方说明"数据值变化时编辑会被保留"），下一轮又会被重新套用到新表上，
    # 表现为"点了重置，勾选还在"。换 key 是官方推荐的重建手段。
    editor_key = (f"title_numbering_editor_{cache['key']}_"
                  f"{st.session_state.get('title_numbering_gen', 0)}")
    # 关键：渲染前先读控件的待处理编辑（详见 _pending_edits 的说明）。
    # 这样"勾选 → 编号重算 → 重画"在**同一轮**完成，不再需要额外的第二轮子跑。
    edits = _merge_edits(
        st.session_state.get('title_numbering_edits', {}),
        _pending_edits(editor_key),
        items,
    )
    stored_edits = st.session_state.get('title_numbering_edits', {})

    # 「编号设置」的两个控件渲染在统计数字**下方**（用户 2026-10-23 要求），
    # 但统计里的编号必须先知道前缀才能算出来。控件没渲染时拿不到返回值，
    # 所以先读上一轮存在 session_state 里的值；首次运行没有状态，回落到
    # 与控件默认值完全一致的 (空前缀, 空格) —— 不会出现「按空前缀算、控件显示 C」。
    prefix, separator = _read_numbering_options()

    # 渲染前先按"已保存的编辑"算一遍，这样表里画出来的编号就是最新的。
    items_eff = _apply_edits(items, edits)
    overrides = _overrides_from(edits)
    if overrides:
        # 用户把编号改成了"本来就该是这个值" → 视为没改，解除锁定，
        # 否则该行编号会被永久钉死，后面改级别也不动。
        base = TitleNumberer.compute_numbers(items_eff, prefix=prefix, separator=separator)
        for _pos in list(overrides):
            if _pos < len(base) and overrides[_pos] == base[_pos]['display_number']:
                overrides.pop(_pos)
    plan = TitleNumberer.compute_numbers(
        items_eff, prefix=prefix, separator=separator, overrides=overrides
    )

    def _counts(p):
        return (sum(1 for x in p if x['action'] == 'insert'),
                sum(1 for x in p if x['action'] == 'keep'),
                sum(1 for x in p if x['action'] == 'replace'),
                sum(1 for x in p if x['action'] == 'skip'))

    n_insert, n_keep, n_replace, n_skip = _counts(plan)

    st.markdown(_STATS_CSS, unsafe_allow_html=True)
    with st.container(key='title_numbering_stats'):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("新写入编号", f"{n_insert} 个")
        m2.metric("改写原有编号", f"{n_replace} 个")
        m3.metric("保持不变", f"{n_keep} 个")
        m4.metric("不处理", f"{n_skip} 个")

    # ---------------- 编号设置（放在统计数字之下） ----------------
    st.markdown("##### ⚙️ 编号设置")
    # 这里的返回值必然与上面 _read_numbering_options() 读到的相同（同一个 key），
    # 赋值只是为了让后续 new_text / 写入用控件真值，语义上更直白。
    prefix, separator = _render_numbering_options()

    if edits:
        _c1, _c2 = st.columns([1, 3])
        if _c1.button("🔄 重置全部编辑", key="title_numbering_reset",
                      use_container_width=True):
            st.session_state.pop('title_numbering_edits', None)
            st.session_state.title_numbering_gen = (
                st.session_state.get('title_numbering_gen', 0) + 1
            )
            st.rerun(scope="fragment")

    if not n_insert and not n_replace and n_keep:
        # 所有编号都保持原样时的兜底说明。不说清楚的话，用户点了生成、
        # 下载回来发现"一字未改"，会以为工具坏了。
        st.info(
            "ℹ️ 所有标题的编号都与原文一致，本次**不会修改任何文字**。"
            "若要把中文编号（第一章 / 一、）改成 1 / 1.1 体系，直接在「编号」列里改。"
        )

    edited = st.data_editor(
        _build_editor_df(plan),
        use_container_width=True,
        hide_index=True,
        height=520,
        # key 带上文件指纹：换文件时天然换一套编辑状态，不会把上一份文档的
        # 行级编辑（勾选/级别/编号）串到新文档上。
        key=editor_key,
        disabled=['写入后标题', '处理', '说明'],
        column_config={
            '应用': st.column_config.CheckboxColumn(
                '应用', width='small', help='取消勾选则不写入编号'
            ),
            '级别': st.column_config.SelectboxColumn(
                '级别', width='small',
                options=list(range(1, TitleNumberer.MAX_LEVEL + 1)),
                help='标题层级；改这里会重算全文编号',
            ),
            '编号': st.column_config.TextColumn(
                '编号', width='small',
                help='可直接修改；清空表示这一行不编号。改后后续标题会接着续号。',
            ),
            '写入后标题': st.column_config.TextColumn('写入后标题', width='large'),
            '处理': st.column_config.TextColumn('处理', width='small'),
            '说明': st.column_config.TextColumn('说明', width='medium'),
        },
    )

    # 收尾：把编辑落库。
    #   - 正常路径（预读生效）：df_now 与 edited 一致 → final == edits，只落库、不重跑。
    #     表格里刚画出来的编号已经是对的，不需要第二轮。
    #   - 兜底路径（预读失效）：diff 出差异 → 落库 + 再跑一轮把编号刷出来。
    df_now = _build_editor_df(plan)
    final = _collect_edits(df_now, edited, items, edits)
    if final != edits:
        st.session_state.title_numbering_edits = final
        st.rerun(scope="fragment")
    if final != stored_edits:
        st.session_state.title_numbering_edits = final

    # 下载用的 plan 就是上面渲染表格用的那份（同源），不再按返回值重算第二遍：
    # 两者本应完全一致，多算一次反而给了它们分叉的机会。
    n_insert, n_keep, n_replace, n_skip = _counts(plan)
    has_work = n_insert or n_replace or n_keep

    # ---------------- 生成并下载 ----------------
    st.markdown("---")
    if st.button("🚀 生成编号并下载", type="primary", use_container_width=True,
                 key="title_numbering_apply"):
        if not has_work:
            st.error("❌ 没有任何标题会被处理，请至少勾选一个标题。")
        else:
            from config import TEMP_DIR
            out_path = str(TEMP_DIR / f"title_numbered_{user_id}.docx")
            try:
                with st.spinner("正在写入编号…"):
                    stats = TitleNumberer.apply(
                        cache['path'], out_path, plan, separator=separator
                    )
                st.session_state.title_numbering_result = {
                    'path': out_path,
                    'name': f"已补编号_{uploaded.name}",
                    'stats': stats,
                    'file_key': cache['key'],
                }
            except Exception as e:
                st.session_state.pop('title_numbering_result', None)
                st.error(f"❌ 写入失败：{e}")

    result = st.session_state.get('title_numbering_result')
    # 只展示与当前上传文件匹配的结果，避免换文件后还显示上一次的下载按钮
    if result and result.get('file_key') == cache['key'] and os.path.exists(result['path']):
        stats = result['stats']
        st.success(
            f"✅ 处理完成！新写入编号 {stats['inserted']} 个，"
            f"改写原有编号 {stats.get('replaced', 0)} 个，"
            f"保持不变 {stats['kept']} 个，跳过 {stats['skipped']} 个"
            + (f"，**{stats['failed']} 个段落因找不到可写入位置被跳过**"
               if stats['failed'] else '') + "。"
        )
        with open(result['path'], 'rb') as f:
            st.download_button(
                label=f"⬇️ 下载处理后的文档（{result['name']}）",
                data=f.read(),
                file_name=result['name'],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="title_numbering_download",
            )
        st.info("💡 建议将处理后的文档作为源文档上传到「📄 文档转换」页。")
