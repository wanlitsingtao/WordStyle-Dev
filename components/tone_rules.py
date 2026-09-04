# -*- coding: utf-8 -*-
"""
祈使语气规则编辑组件（T02）
渲染 4 类规则 + 例外词 + ying_dui_verbs，支持浏览 / 增 / 删 / 改。

采用 st.data_editor（映射表）+ st.text_area（列表）实现：
- 替换映射（原词 → 替换词）用可动态增删行的表格编辑。
- 例外词 / 标志动词用"每行一个词"的文本域编辑。

组件为纯渲染函数，返回用户当前编辑后的规则字典（工作副本），
持久化由 pages/tone_config.py 负责。
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
    st.markdown(f"**{label}（{len(mapping)} 条）**")

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

    # 1. 多字祈使词替换
    st.markdown("### ▸ 多字祈使词替换")
    rules = _render_mapping_editor(rules, "multi_imperative", "tone_editor_multi", "多字祈使词替换")

    st.markdown("---")

    # 2. 单字祈使词替换
    st.markdown("### ▸ 单字祈使词替换")
    rules = _render_mapping_editor(rules, "single_imperative", "tone_editor_single", "单字祈使词替换")

    st.markdown("---")

    # 3. 投标人称谓替换
    st.markdown("### ▸ 投标人称谓替换")
    rules = _render_mapping_editor(rules, "bidder_terms", "tone_editor_bidder", "投标人称谓替换")

    st.markdown("---")

    # 4. 例外词列表（3 组）
    st.markdown("### ▸ 例外词列表")
    exceptions = rules.setdefault("exceptions", {})
    if not isinstance(exceptions, dict):
        exceptions = {}
        rules["exceptions"] = exceptions

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

    st.markdown("---")

    # 5. "应+对"分离结构标志动词
    st.markdown("### ▸ 应+对分离结构标志动词")
    _render_list_editor(rules, "ying_dui_verbs", "tone_editor_verbs",
                        "标志动词（每行一个词）",
                        "用于检测「应+对+动词」分离结构（如「应对…负责」），避免误替换")

    return rules


# 编辑区涉及的 widget key 集合（供"恢复默认"后清理 session_state）
TONE_EDITOR_KEYS = (
    "tone_editor_multi",
    "tone_editor_single",
    "tone_editor_bidder",
    "tone_editor_exc_multi",
    "tone_editor_exc_ying",
    "tone_editor_exc_xu",
    "tone_editor_verbs",
)


def clear_tone_editor_state():
    """清理语气编辑器在 session_state 中缓存的 widget 状态。"""
    for key in TONE_EDITOR_KEYS:
        if key in st.session_state:
            del st.session_state[key]
