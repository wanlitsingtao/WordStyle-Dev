# -*- coding: utf-8 -*-
"""
模板样式精简交互组件（T04 / 工具箱 Tab B）
样式清单 + 过滤 + 保留/删除切换 + 精简下载。
"""
import logging
import os

import streamlit as st

from style_cleaner import StyleCleaner

logger = logging.getLogger('WordStyle')


@st.fragment
def render_style_cleanup():
    """渲染样式精简交互区（@st.fragment 局部刷新）。"""
    st.markdown(
        "分析模板文档中所有段落样式，删除未被使用的样式，"
        "仅保留实际使用的样式，降低样式映射配置复杂度。"
    )

    user_id = st.session_state.get('user_id', 'default')

    uploaded = st.file_uploader(
        "上传模板文档（支持 .docx）",
        type=['docx'],
        key="style_cleanup_uploader",
    )

    if uploaded is None:
        st.info("📤 上传模板文档后自动分析样式使用情况。")
        return

    temp_path = f"temp_style_cleanup_{user_id}.docx"
    with open(temp_path, 'wb') as f:
        f.write(uploaded.getbuffer())

    try:
        analysis = StyleCleaner.analyze_styles(temp_path)
    except Exception as e:
        st.error(f"❌ 文档解析失败：{e}")
        return

    styles = analysis.get("styles", [])
    total = analysis.get("total", 0)
    used = analysis.get("used", 0)
    unused = analysis.get("unused", 0)

    # 统计指标
    col_t, col_u, col_un = st.columns(3)
    col_t.metric("总样式数", total)
    col_u.metric("已使用", used)
    col_un.metric("未使用", unused)

    st.markdown("---")

    # 过滤视图
    filter_mode = st.radio(
        "显示范围",
        options=["全部", "仅显示未使用"],
        horizontal=True,
        key="style_cleanup_filter",
    )

    # 初始化/同步删除选择状态（默认：未使用且未保护的样式 → 删除）
    detect_key = f"{uploaded.name}_{len(styles)}"
    st.session_state.setdefault('style_cleanup_detect_key', '')
    if st.session_state.get('style_cleanup_detect_key') != detect_key:
        st.session_state.style_cleanup_detect_key = detect_key
        st.session_state.style_cleanup_delete = {
            s["style_id"]: (s["usage_count"] == 0 and not s["protected"])
            for s in styles
        }

    delete_map = st.session_state.style_cleanup_delete

    # 构建显示清单
    if filter_mode == "仅显示未使用":
        display_styles = [s for s in styles if s["usage_count"] == 0]
    else:
        display_styles = styles

    if not display_styles:
        st.info("没有需要显示的样式。")
    else:
        # 表头
        h = st.columns([4, 1.2, 1.4, 1.4])
        h[0].markdown("**样式名称**")
        h[1].markdown("**类型**")
        h[2].markdown("**使用次数**")
        h[3].markdown("**操作**")

        for s in display_styles:
            sid = s["style_id"]
            c_name, c_type, c_count, c_action = st.columns([4, 1.2, 1.4, 1.4])
            with c_name:
                lock = "🔒" if s["protected"] else ""
                st.markdown(f"{lock} {s['name'] or sid}")
            with c_type:
                st.caption(s["type"])
            with c_count:
                st.caption(str(s["usage_count"]))
            with c_action:
                if s["protected"]:
                    st.caption("✅ 保留（内置）")
                else:
                    is_delete = delete_map.get(sid, False)
                    label = "❌ 删除" if is_delete else "✅ 保留"
                    if st.button(label, key=f"sc_toggle_{sid}", use_container_width=True):
                        delete_map[sid] = not is_delete

    st.markdown("---")

    col_sel, col_keep, col_re, col_go = st.columns([1, 1, 1, 2])
    with col_sel:
        if st.button("全选未使用", key="sc_select_unused", use_container_width=True):
            for s in styles:
                if not s["protected"] and s["usage_count"] == 0:
                    delete_map[s["style_id"]] = True
    with col_keep:
        if st.button("批量保留", key="sc_keep_all", use_container_width=True):
            for s in styles:
                delete_map[s["style_id"]] = False
    with col_re:
        re_analyze = st.button("🔄 重新分析", key="sc_reanalyze", use_container_width=True)
    with col_go:
        do_cleanup = st.button("🚀 精简并下载", key="sc_process", type="primary", use_container_width=True)

    if re_analyze:
        st.session_state.style_cleanup_detect_key = ''
        st.rerun()

    if do_cleanup:
        delete_ids = [sid for sid, flag in delete_map.items() if flag]
        if not delete_ids:
            st.warning("⚠️ 未选择任何要删除的样式。")
            return

        out_path = f"style_cleaned_{user_id}.docx"
        try:
            result = StyleCleaner.cleanup_styles(temp_path, out_path, delete_ids)
        except Exception as e:
            st.error(f"❌ 精简失败：{e}")
            return

        st.session_state.style_cleanup_result = {
            "path": out_path,
            "name": f"样式精简_{uploaded.name}",
            "deleted": result.get("deleted", 0),
            "skipped_protected": result.get("skipped_protected", 0),
            "skipped_dependency": result.get("skipped_dependency", 0),
            "message": result.get("message", ""),
        }

    result = st.session_state.get('style_cleanup_result')
    if result and os.path.exists(result["path"]):
        st.success(f"✅ 精简完成！{result['message']}")
        with open(result["path"], 'rb') as f:
            st.download_button(
                label=f"⬇️ 下载精简后的模板（{result['name']}）",
                data=f.read(),
                file_name=result["name"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="style_cleanup_download",
            )
        st.info("💡 建议将精简后的文档作为模板上传到「📄 文档转换」页。")
