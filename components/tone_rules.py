# -*- coding: utf-8 -*-
"""
祈使语气规则编辑组件（T02）
渲染投标称谓 / 祈使词 / 标志动词 / 例外词，支持浏览 / 增 / 删 / 改。

编辑区顺序（2026-11-18 用户定）：
  1. 投标人称谓替换   2. 祈使词替换（多字 + 单字合为一张表）
  3. 应+对分离结构标志动词   4. 例外词列表

采用 st.data_editor（映射表）+ st.text_area（列表）实现：
- 替换映射（原词 → 替换词）用可动态增删行的表格编辑。
- 祈使词表额外带「类型」列（多字/单字下拉）；返回规则时仍拆回
  multi_imperative / single_imperative 两个键，转换逻辑不变。
- 例外词 / 标志动词用"每行一个词"的文本域编辑。

组件为纯渲染函数，返回用户当前编辑后的规则字典（工作副本），
持久化由 views/tone_config.py 负责。
"""
import logging

import streamlit as st


logger = logging.getLogger('WordStyle')


def _render_mapping_editor(rules, category, editor_key, label):
    """渲染一个"原词 → 替换词"映射的 data_editor。

    返回更新后的 rules 字典（原地更新 category 键）。
    """
    import pandas as pd

    mapping = rules.get(category, {}) or {}

    if mapping:
        df = pd.DataFrame(
            [{"原词": k, "替换词": v} for k, v in mapping.items()],
            columns=["原词", "替换词"],
        )
    else:
        df = pd.DataFrame(columns=["原词", "替换词"])

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

    # 过滤空行并转换为字典（去除首尾空白；空原词/空替换词的行忽略）
    new_mapping = {}
    for _, row in edited.iterrows():
        src = str(row.get("原词", "") or "").strip()
        tgt = str(row.get("替换词", "") or "").strip()
        if src and tgt:
            new_mapping[src] = tgt
    rules[category] = new_mapping
    st.caption(f"当前 {label} 共 {len(new_mapping)} 条有效规则（空行将被忽略）")
    return rules


def _render_list_editor(rules, sub_key, editor_key, label, hint):
    """渲染一个"每行一个词"的文本域编辑器，用于例外词 / 标志动词列表。

    返回更新后的 rules 字典。
    """
    import re

    lst = rules.get(sub_key, []) or []
    initial_text = "\n".join(lst)

    edited_text = st.text_area(
        label,
        value=initial_text,
        key=editor_key,
        height=120,
        help=hint,
    )

    items = [w.strip() for w in re.split(r"[\n,，、]+", edited_text) if w.strip()]
    rules[sub_key] = items
    st.caption(f"当前共 {len(items)} 个词")
    return rules


def _render_imperative_editor(rules, editor_key):
    """多字 / 单字祈使词合并成一张表编辑（含「类型」列）。

    界面上只有一张表，但保存/测试仍按原有两个规则集取值：
    返回时按「类型」拆回 multi_imperative / single_imperative，
    因此 tone_rules_manager / doc_converter 的数据结构与转换逻辑零改动。

    新增行若未选类型（留空），按「多字」处理，避免默认空类型导致规则被丢弃。
    """
    import pandas as pd

    multi = rules.get("multi_imperative", {}) or {}
    single = rules.get("single_imperative", {}) or {}

    rows = []
    for k, v in multi.items():
        rows.append({"类型": "多字", "原词": k, "替换词": v})
    for k, v in single.items():
        rows.append({"类型": "单字", "原词": k, "替换词": v})

    if rows:
        df = pd.DataFrame(rows, columns=["类型", "原词", "替换词"])
    else:
        df = pd.DataFrame(columns=["类型", "原词", "替换词"])

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key,
        column_config={
            "类型": st.column_config.SelectboxColumn(
                "类型",
                options=["多字", "单字"],
                help="多字祈使词（如「必须」）或单字祈使词（如「应」）",
            ),
            "原词": st.column_config.TextColumn("原词", help="要被替换的词"),
            "替换词": st.column_config.TextColumn("替换词", help="替换后的词"),
        },
    )

    new_multi = {}
    new_single = {}
    for _, row in edited.iterrows():
        src = str(row.get("原词", "") or "").strip()
        tgt = str(row.get("替换词", "") or "").strip()
        if not src or not tgt:
            continue
        kind = str(row.get("类型", "") or "").strip()
        if kind == "单字":
            new_single[src] = tgt
        else:
            # 类型为空 / 其它值一律按「多字」，保证新增行不会静默丢失
            new_multi[src] = tgt

    rules["multi_imperative"] = new_multi
    rules["single_imperative"] = new_single
    st.caption(
        f"当前共 {len(new_multi)} 条多字 + {len(new_single)} 条单字规则"
        "（空行将被忽略；类型留空按「多字」处理）"
    )
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

    # 2. 祈使词替换（多字 + 单字合为一张表）
    multi_count = len(rules.get("multi_imperative", {}) or {})
    single_count = len(rules.get("single_imperative", {}) or {})
    with st.expander(
        f"▸ 祈使词替换（多字 {multi_count} + 单字 {single_count} 条）",
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


def clear_tone_editor_state():
    """清理语气编辑器在 session_state 中缓存的 widget 状态。"""
    for key in TONE_EDITOR_KEYS:
        if key in st.session_state:
            del st.session_state[key]
