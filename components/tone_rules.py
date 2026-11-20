# -*- coding: utf-8 -*-
"""
祈使语气规则编辑组件（T02）
渲染投标称谓 / 祈使词 / 标志动词 / 例外词，支持浏览 / 增 / 删 / 改。

编辑区顺序（2026-11-18 用户定）：
  1. 投标人称谓替换   2. 祈使词替换（多字 + 单字合为一张表）
  3. 应+对分离结构标志动词   4. 例外词列表

采用 st.data_editor（映射表）+ st.text_area（列表）实现：
- 替换映射（原词 → 替换词）用可动态增删行的表格编辑。
- 祈使词表把多字 / 单字规则合成一张「原词/替换词」两列表；用户不必选类型，
  返回规则时按**原词字数**自动归位（1 字 → single_imperative，2 字及以上 →
  multi_imperative），转换逻辑不变。
- 例外词 / 标志动词用"每行一个词"的文本域编辑。

组件为纯渲染函数，返回用户当前编辑后的规则字典（工作副本），
持久化由 views/tone_config.py 负责。
"""
import logging

import streamlit as st


logger = logging.getLogger('WordStyle')

# 编辑器私有状态键前缀：
#   _INIT_ = 首次进入时固化的「输入数据源快照」，之后每轮都传同一份内容给控件；
#   _ROWS_ = 每轮控件当前输出，供「保存全部」直接读取（不依赖 fragment 是否重跑）。
# 有了 _INIT_，data_editor / text_area 自带的 widget 状态（key）不会被
# 「上一轮输出重建输入」冲掉，用户填了一半的行也不会丢失。
_INIT_PREFIX = "_tone_editor_init__"
_ROWS_PREFIX = "_tone_editor_rows__"


def _state_key(prefix, editor_key):
    return prefix + editor_key


def _clean_cell(value):
    """把表格单元格转成可保存的字符串。

    pandas 的空单元格是 NaN（float），而 ``NaN or ""`` 结果仍是 NaN（NaN 是真值），
    旧写法 ``str(x or "")`` 会把它变成字符串 'nan' 写进规则表 —— 这就是界面上
    出现 nan、以及空行被当成规则保存的原因。这里统一把 NaN / None / 空串 /
    字符串形式的 'nan'、'none'、'null' 都视为空。
    """
    import pandas as pd

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in ("nan", "none", "nat", "<na>", "null"):
        return ""
    return text


def _rows_to_mapping(rows):
    """表格行 → {原词: 替换词}；任一格为空的整行直接跳过。"""
    out = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        src = _clean_cell(row.get("原词"))
        tgt = _clean_cell(row.get("替换词"))
        if src and tgt:
            out[src] = tgt
    return out


def _rows_to_imperative(rows):
    """祈使词表行 → (multi_imperative, single_imperative)，按原词字数归类。"""
    multi, single = {}, {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        src = _clean_cell(row.get("原词"))
        tgt = _clean_cell(row.get("替换词"))
        if not src or not tgt:
            continue
        if len(src) == 1:
            single[src] = tgt
        else:
            multi[src] = tgt
    return multi, single


def _stable_editor_df(editor_key, rows, columns):
    """构造 data_editor 的输入：只认首次固化的快照，之后每轮内容恒定。"""
    import pandas as pd

    init_key = _state_key(_INIT_PREFIX, editor_key)
    if init_key not in st.session_state:
        st.session_state[init_key] = [dict(r) for r in rows]
    snapshot = st.session_state[init_key]
    return pd.DataFrame(snapshot, columns=columns) if snapshot else pd.DataFrame(columns=columns)


def _stable_text_value(editor_key, initial_text):
    """构造 text_area 的 value：只认首次固化的快照，之后每轮内容恒定。"""
    init_key = _state_key(_INIT_PREFIX, editor_key)
    if init_key not in st.session_state:
        st.session_state[init_key] = initial_text
    return st.session_state[init_key]


def _cache_editor_rows(editor_key, value):
    """缓存控件本轮输出（DataFrame/list[dict] 或文本），供保存时读取。"""
    if hasattr(value, "to_dict"):
        value = value.to_dict("records")
    st.session_state[_state_key(_ROWS_PREFIX, editor_key)] = value


def _cached_rows(editor_key):
    return st.session_state.get(_state_key(_ROWS_PREFIX, editor_key))


def _split_words(text):
    import re

    return [w.strip() for w in re.split(r"[\n,，、]+", text or "") if w.strip()]


def _render_mapping_editor(rules, category, editor_key, label):
    """渲染一个"原词 → 替换词"映射的 data_editor。

    返回更新后的 rules 字典（原地更新 category 键）。
    """
    mapping = rules.get(category, {}) or {}
    rows = [{"原词": k, "替换词": v} for k, v in mapping.items()]
    df = _stable_editor_df(editor_key, rows, ["原词", "替换词"])

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key,
        column_config={
            "原词": st.column_config.TextColumn("原词", help="要被替换的词"),
            "替换词": st.column_config.TextColumn("替换词", help="替换后的词"),
        },
    )

    _cache_editor_rows(editor_key, edited)
    rows_now = edited.to_dict("records") if hasattr(edited, "to_dict") else edited
    new_mapping = _rows_to_mapping(rows_now)
    rules[category] = new_mapping
    st.caption(f"当前 {label} 共 {len(new_mapping)} 条有效规则（空行将被忽略）")
    return rules


def _render_list_editor(rules, sub_key, editor_key, label, hint):
    """渲染一个"每行一个词"的文本域编辑器，用于例外词 / 标志动词列表。

    返回更新后的 rules 字典。
    """
    lst = rules.get(sub_key, []) or []
    value = _stable_text_value(editor_key, "\n".join(lst))

    edited_text = st.text_area(
        label,
        value=value,
        key=editor_key,
        height=120,
        help=hint,
    )

    _cache_editor_rows(editor_key, edited_text)
    items = _split_words(edited_text)
    rules[sub_key] = items
    st.caption(f"当前共 {len(items)} 个词")
    return rules


def _render_imperative_editor(rules, editor_key):
    """多字 / 单字祈使词合并成一张「原词 → 替换词」两列表编辑。

    「类型（多字/单字）」对用户无意义，且完全可由原词字数确定，故界面不再提供该列：
    用户只需填原词与替换词，返回规则时按**原词字数**自动归位——
    1 字 → `single_imperative`，2 字及以上 → `multi_imperative`。

    两个规则集在转换引擎里使用不同的正则与例外词机制，因此数据结构仍保留拆分，
    tone_rules_manager / doc_converter 零改动。空原词 / 空替换词的行忽略，值做 strip()。
    """
    multi = rules.get("multi_imperative", {}) or {}
    single = rules.get("single_imperative", {}) or {}

    rows = [{"原词": k, "替换词": v} for k, v in multi.items()]
    rows += [{"原词": k, "替换词": v} for k, v in single.items()]

    columns = ["原词", "替换词"]
    df = _stable_editor_df(editor_key, rows, columns)

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key,
        column_config={
            "原词": st.column_config.TextColumn("原词", help="要被替换的词"),
            "替换词": st.column_config.TextColumn("替换词", help="替换后的词"),
        },
    )

    _cache_editor_rows(editor_key, edited)
    rows_now = edited.to_dict("records") if hasattr(edited, "to_dict") else edited
    new_multi, new_single = _rows_to_imperative(rows_now)

    rules["multi_imperative"] = new_multi
    rules["single_imperative"] = new_single
    st.caption(f"当前共 {len(new_multi) + len(new_single)} 条有效规则（空行将被忽略）")
    return rules


@st.fragment
def render_tone_rules_editor(rules):
    """渲染语气规则编辑区（@st.fragment 局部刷新）。

    Args:
        rules: 当前工作副本规则字典（会被原地更新并返回）。

    Returns:
        dict: 更新后的规则字典。
    """
    if not isinstance(rules, dict):
        rules = {}

    # 1. 投标人称谓替换
    bidder_count = len(rules.get("bidder_terms", {}) or {})
    with st.expander(
        f"▸ 投标人称谓替换（{bidder_count} 条）",
        expanded=False,
        key="tone_expand_bidder",
    ):
        rules = _render_mapping_editor(rules, "bidder_terms", "tone_editor_bidder", "投标人称谓替换")

    # 2. 祈使词替换（多字 + 单字合为一张两列表，按原词字数自动归类）
    imperative_count = (
        len(rules.get("multi_imperative", {}) or {})
        + len(rules.get("single_imperative", {}) or {})
    )
    with st.expander(
        f"▸ 祈使词替换（{imperative_count} 条）",
        expanded=False,
        key="tone_expand_imperative",
    ):
        rules = _render_imperative_editor(rules, "tone_editor_imperative")

    # 3. "应+对"分离结构标志动词
    verbs_count = len(rules.get("ying_dui_verbs", []) or [])
    with st.expander(
        f"▸ 应+对分离结构标志动词（{verbs_count} 个）",
        expanded=False,
        key="tone_expand_verbs",
    ):
        _render_list_editor(rules, "ying_dui_verbs", "tone_editor_verbs",
                            "标志动词（每行一个词）",
                            "用于检测「应+对+动词」分离结构（如「应对…负责」），避免误替换")

    # 4. 例外词列表（3 组）
    exceptions = rules.setdefault("exceptions", {})
    if not isinstance(exceptions, dict):
        exceptions = {}
        rules["exceptions"] = exceptions
    exc_total = (
        len(exceptions.get("multi", []) or [])
        + len(exceptions.get("ying", []) or [])
        + len(exceptions.get("xu", []) or [])
    )
    with st.expander(
        f"▸ 例外词列表（{exc_total} 个）",
        expanded=False,
        key="tone_expand_exceptions",
    ):
        col_a, col_b = st.columns(2)
        with col_a:
            _render_list_editor(exceptions, "multi", "tone_editor_exc_multi",
                                "多字祈使词例外（每行一个词）",
                                "这些词中即使包含祈使词也不会被替换")
        with col_b:
            _render_list_editor(exceptions, "ying", "tone_editor_exc_ying",
                                "「应」字例外词（每行一个词）",
                                "这些词中的「应」字不会被替换")

        _render_list_editor(exceptions, "xu", "tone_editor_exc_xu",
                            "「须」字例外词（每行一个词）",
                            "这些词中的「须」字不会被替换")

    return rules


# 编辑区涉及的 widget key 集合（供"恢复默认"后清理 session_state）
TONE_EDITOR_KEYS = (
    "tone_editor_bidder",
    "tone_editor_imperative",
    "tone_editor_verbs",
    "tone_editor_exc_multi",
    "tone_editor_exc_ying",
    "tone_editor_exc_xu",
)


def collect_editor_rules(rules):
    """以「控件最近一次输出」为准重建规则字典，供「保存全部」/ 测试转换使用。

    编辑区是 @st.fragment：点击 fragment 外的按钮触发整页 rerun 时，fragment
    可能不重跑，页面拿到的是上一轮的工作副本。这里直接读各编辑器缓存的控件
    输出，保证保存时用的是用户实际看到/录入的内容，而不是旧副本。
    没有渲染过编辑器（缓存缺失）时，原样返回传入的 rules。
    """
    if not isinstance(rules, dict):
        return {}
    out = dict(rules)

    rows = _cached_rows("tone_editor_bidder")
    if rows is not None:
        out["bidder_terms"] = _rows_to_mapping(rows)

    rows = _cached_rows("tone_editor_imperative")
    if rows is not None:
        out["multi_imperative"], out["single_imperative"] = _rows_to_imperative(rows)

    for editor_key, sub_key, owner in (
        ("tone_editor_verbs", "ying_dui_verbs", None),
        ("tone_editor_exc_multi", "multi", "exceptions"),
        ("tone_editor_exc_ying", "ying", "exceptions"),
        ("tone_editor_exc_xu", "xu", "exceptions"),
    ):
        text = _cached_rows(editor_key)
        if text is None:
            continue
        items = _split_words(text)
        if owner is None:
            out[sub_key] = items
        else:
            exc = out.get(owner)
            if not isinstance(exc, dict):
                exc = {}
                out[owner] = exc
            exc[sub_key] = items
    return out


def clear_tone_editor_state():
    """清理语气编辑器在 session_state 中缓存的 widget 状态与输入快照。

    「恢复默认」「导入 JSON」后必须调用：清掉快照，下一轮才会用新规则重新
    初始化编辑器，否则界面会一直显示旧规则的固化快照。
    """
    for key in TONE_EDITOR_KEYS:
        if key in st.session_state:
            del st.session_state[key]
        for prefix in (_INIT_PREFIX, _ROWS_PREFIX):
            state_key = _state_key(prefix, key)
            if state_key in st.session_state:
                del st.session_state[state_key]


def editor_state_active() -> bool:
    """当前是否有编辑器 widget 处于活动状态（同一次页面会话内）。

    Streamlit 切换页面时会清理非当前页的 widget 状态：那时各编辑器 key 不在
    session_state 里，说明这是一次新的页面挂载，可以安全地用数据库最新规则
    校准。反之 widget 状态还在 = 用户正在本页编辑（可能含未保存输入），
    绝不能用库里的旧值覆盖其输入。
    """
    return any(key in st.session_state for key in TONE_EDITOR_KEYS)


def sync_editor_snapshots(rules):
    """把各编辑器的输入快照 / 输出缓存同步为给定规则（Bug #026）。

    只写 ``_INIT_`` / ``_ROWS_``，**不动 widget 状态**：
    - 当前页面仍显示用户刚编辑的内容（widget 状态优先）；
    - 跨页面重进、widget 状态被清理时，data_editor 会用这份最新快照重建表格，
      而不是显示首次进入页面时的旧规则。

    调用时机：①「保存全部」成功后（用刚保存的规则）；
    ② 配置页重新挂载时（用库里最新规则校准，见 views/tone_config.py）。
    """
    if not isinstance(rules, dict):
        return

    bidder = rules.get("bidder_terms") or {}
    multi = rules.get("multi_imperative") or {}
    single = rules.get("single_imperative") or {}
    exc = rules.get("exceptions") or {}
    if not isinstance(exc, dict):
        exc = {}

    mapping_rows = {
        "tone_editor_bidder": [
            {"原词": k, "替换词": v} for k, v in bidder.items()
        ],
        "tone_editor_imperative": (
            [{"原词": k, "替换词": v} for k, v in multi.items()]
            + [{"原词": k, "替换词": v} for k, v in single.items()]
        ),
    }
    text_values = {
        "tone_editor_verbs": "\n".join(str(x) for x in (rules.get("ying_dui_verbs") or [])),
        "tone_editor_exc_multi": "\n".join(str(x) for x in (exc.get("multi") or [])),
        "tone_editor_exc_ying": "\n".join(str(x) for x in (exc.get("ying") or [])),
        "tone_editor_exc_xu": "\n".join(str(x) for x in (exc.get("xu") or [])),
    }

    for key, rows in mapping_rows.items():
        st.session_state[_state_key(_INIT_PREFIX, key)] = [dict(r) for r in rows]
        st.session_state[_state_key(_ROWS_PREFIX, key)] = [dict(r) for r in rows]
    for key, text in text_values.items():
        st.session_state[_state_key(_INIT_PREFIX, key)] = text
        st.session_state[_state_key(_ROWS_PREFIX, key)] = text
