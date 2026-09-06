# -*- coding: utf-8 -*-
"""
源文档标题预处理交互组件（T04 / 工具箱 Tab A）
检测表格 + 级别编辑 + 处理下载。
"""
import logging
import os

import streamlit as st

from title_preprocessor import TitlePreprocessor

logger = logging.getLogger('WordStyle')

# 目标级别选项：H1-H9 + "不转换"
LEVEL_OPTIONS = [f"H{i}" for i in range(1, 10)] + ["不转换"]


def _level_to_int(level_label):
    if level_label == "不转换":
        return 0
    return int(level_label[1:])


def _detect(user_id, uploaded_file):
    """保存上传文件并检测标题。返回 (headings, temp_path)。"""
    temp_path = f"temp_title_preprocess_{user_id}.docx"
    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    headings = TitlePreprocessor.detect_headings(temp_path)
    return headings, temp_path


@st.fragment
def render_title_preprocess():
    """渲染标题预处理交互区（@st.fragment 局部刷新）。"""
    st.markdown(
        "提取以正文格式出现的编号标题（数字编号 + 制表符 + 标题文本，如 `1.1\t线路`），"
        "赋予对应大纲级别（Heading 1-9），生成可被样式映射识别的新文档。"
    )

    user_id = st.session_state.get('user_id', 'default')

    uploaded = st.file_uploader(
        "上传源文档（支持 .docx）",
        type=['docx'],
        key="title_preprocess_uploader",
    )

    if uploaded is None:
        st.info("📤 上传源文档后自动检测编号标题。")
        return

    # 检测（每次上传/重跑都基于当前上传文件重新分析；数据量小，无需缓存）
    try:
        headings, temp_path = _detect(user_id, uploaded)
    except Exception as e:
        st.error(f"❌ 文档解析失败：{e}")
        return

    if not headings:
        st.warning("未检测到编号标题（数字编号 + 制表符 + 标题文本 格式）。")
        return

    st.markdown(f"**检测到 {len(headings)} 个疑似标题段落：**")

    # 初始化/同步勾选状态与目标级别到 session_state
    detect_key = f"title_detect_{uploaded.name}_{len(headings)}"
    st.session_state.setdefault('title_preprocess_detect_key', '')
    if st.session_state.get('title_preprocess_detect_key') != detect_key:
        st.session_state.title_preprocess_detect_key = detect_key
        st.session_state.title_preprocess_selected = {h["index"]: True for h in headings}
        st.session_state.title_preprocess_levels = {
            h["index"]: f"H{h['detected_level']}" for h in headings
        }

    selected = st.session_state.title_preprocess_selected
    levels = st.session_state.title_preprocess_levels

    # 处理操作区（重新检测 / 处理并下载 + 结果展示），放在"全选/反选"之上
    col_re, col_go = st.columns([1, 2])
    with col_re:
        re_detect = st.button("🔄 重新检测", key="tp_redetect", use_container_width=True)
    with col_go:
        do_process = st.button("🚀 处理并下载", key="tp_process", type="primary", use_container_width=True)

    if re_detect:
        st.session_state.title_preprocess_detect_key = ''
        st.rerun()

    if do_process:
        selections = []
        for h in headings:
            idx = h["index"]
            if selected.get(idx, True):
                target_level = _level_to_int(levels.get(idx, f"H{h['detected_level']}"))
                if target_level >= 1:
                    selections.append({"index": idx, "target_level": target_level})

        if not selections:
            st.error("❌ 请至少选择一个要转换的标题段落。")
        else:
            out_path = f"title_preprocessed_{user_id}.docx"
            progress_bar = st.progress(0)
            status_text = st.empty()

            def _on_progress(done, total):
                progress_bar.progress(done / total if total else 1.0)
                status_text.text(f"⏳ 正在处理... {done}/{total}")

            try:
                TitlePreprocessor.apply_headings(
                    temp_path, out_path, selections, progress_callback=_on_progress
                )
            except Exception as e:
                st.error(f"❌ 处理失败：{e}")
            else:
                progress_bar.progress(1.0)
                status_text.text("✅ 处理完成")
                st.session_state.title_preprocess_result = {
                    "path": out_path,
                    "name": f"标题预处理_{uploaded.name}",
                    "count": len(selections),
                }

    # 显示处理结果
    result = st.session_state.get('title_preprocess_result')
    if result and os.path.exists(result["path"]):
        st.success(f"✅ 处理完成！已为 {result['count']} 个段落设置标题级别。")
        with open(result["path"], 'rb') as f:
            st.download_button(
                label=f"⬇️ 下载处理后的文档（{result['name']}）",
                data=f.read(),
                file_name=result["name"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="title_preprocess_download",
            )
        st.info("💡 建议将处理后的文档作为源文档上传到「📄 文档转换」页。")

    st.markdown("---")

    # 批量操作（全选 / 反选）
    col_sel, col_inv, col_only = st.columns(3)
    with col_sel:
        if st.button("全选", key="tp_select_all", use_container_width=True):
            for h in headings:
                selected[h["index"]] = True
    with col_inv:
        if st.button("反选", key="tp_invert", use_container_width=True):
            for h in headings:
                selected[h["index"]] = not selected.get(h["index"], True)

    # 渲染检测表格
    for i, h in enumerate(headings):
        idx = h["index"]
        col_check, col_text, col_detected, col_target = st.columns([0.6, 5, 1.4, 1.6])
        with col_check:
            selected[idx] = st.checkbox(
                "选",
                value=selected.get(idx, True),
                key=f"tp_check_{idx}",
                label_visibility="collapsed",
            )
        with col_text:
            st.markdown(f"`{h['number']}` {h['text'][:80]}")
        with col_detected:
            st.caption(f"H{h['detected_level']}")
        with col_target:
            current_label = levels.get(idx, f"H{h['detected_level']}")
            try:
                current_index = LEVEL_OPTIONS.index(current_label)
            except ValueError:
                current_index = h['detected_level'] - 1
            levels[idx] = st.selectbox(
                "目标级别",
                options=LEVEL_OPTIONS,
                index=current_index,
                key=f"tp_level_{idx}",
                label_visibility="collapsed",
            )
