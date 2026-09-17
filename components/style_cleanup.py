# -*- coding: utf-8 -*-
"""
模板样式精简交互组件（T04 / 工具箱标签：模板样式精简）
上传分析（总样式/已使用/未使用）+ 精简方式选择 + 样式清单保留/删除单选 + 精简下载。
分析、精简均带进度条（按真实处理进度节流推进，对齐文档转换页，不静止、不阻塞）。
"""
import logging
import os
import time

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

    from config import TEMP_DIR
    temp_path = str(TEMP_DIR / f"temp_style_cleanup_{user_id}.docx")
    with open(temp_path, 'wb') as f:
        f.write(uploaded.getbuffer())

    # ===== 分析阶段（带进度条）=====
    analyze_bar = st.progress(0)
    analyze_status = st.empty()
    _analyze_ts = [0.0]

    def _on_analyze_progress(done, total):
        frac = done / total if total else 0.0
        _now = time.time()
        if frac >= 1.0 or _now - _analyze_ts[0] >= 0.1:
            _analyze_ts[0] = _now
            analyze_bar.progress(min(frac, 1.0))
            analyze_status.caption(f"🔍 正在分析样式… {done}/{total} 段")

    try:
        analysis = StyleCleaner.analyze_styles(temp_path, progress_callback=_on_analyze_progress)
    except Exception as e:
        st.error(f"❌ 文档解析失败：{e}")
        return

    analyze_bar.progress(1.0)
    analyze_status.caption("✅ 分析完成")

    styles = analysis.get("styles", [])
    total = analysis.get("total", 0)
    builtin_count = analysis.get("builtin_count", 0)
    custom_count = analysis.get("custom_count", 0)
    used = analysis.get("used", 0)
    unused = analysis.get("unused", 0)
    cleanable = analysis.get("cleanable", 0)

    # 统计指标（自定义卡片，字号比原生 st.metric 大一倍，避免全局 CSS 影响其它页面）
    st.markdown(
        """
<style>
.sc-metric-card {
    background: #ffffff;
    border: 1px solid #e0e3e8;
    border-radius: 8px;
    padding: 16px 8px;
    text-align: center;
}
.sc-metric-label {
    font-size: 1.1rem;
    color: #555555;
    margin-bottom: 8px;
}
.sc-metric-value {
    font-size: 2.4rem;
    font-weight: 700;
    color: #1f2937;
    line-height: 1.2;
}
</style>
""",
        unsafe_allow_html=True,
    )
    metric_cols = st.columns(6)
    metric_items = [
        ("总样式", total),
        ("自定义样式", custom_count),
        ("内置样式", builtin_count),
        ("使用样式", used),
        ("未使用样式", unused),
        ("可清理样式", cleanable),
    ]
    for col, (label, value) in zip(metric_cols, metric_items):
        with col:
            st.markdown(
                f'<div class="sc-metric-card">'
                f'<div class="sc-metric-label">{label}</div>'
                f'<div class="sc-metric-value">{value}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # 精简方式选择（单选）+ 精简下载按钮
    mode_row = st.columns([3, 1.5])
    with mode_row[0]:
        mode = st.radio(
            "精简方式",
            options=["删除全部未使用", "自定义配置"],
            horizontal=True,
            key="style_cleanup_mode",
        )
    with mode_row[1]:
        do_cleanup = st.button(
            "⬇️ 精简下载",
            key="sc_process",
            type="primary",
            use_container_width=True,
        )

    # 初始化/同步删除选择状态（默认：已使用或内置 → 保留，未使用 → 删除）
    # 用 file_id 唯一标识一次上传，避免重新上传同一文件时沿用旧的下载结果。
    detect_key = f"{getattr(uploaded, 'file_id', '')}_{uploaded.name}_{uploaded.size}_{len(styles)}"
    st.session_state.setdefault('style_cleanup_detect_key', '')
    if st.session_state.get('style_cleanup_detect_key') != detect_key:
        st.session_state.style_cleanup_detect_key = detect_key
        st.session_state.style_cleanup_delete = {
            s["style_id"]: (s["usage_count"] == 0 and not s["protected"])
            for s in styles
        }
        # 清除旧的逐行单选状态，确保新文档按默认规则重新渲染
        for s in styles:
            st.session_state.pop(f"sc_action_{s['style_id']}", None)
        st.session_state.pop('style_cleanup_result', None)

    delete_map = st.session_state.style_cleanup_delete

    # 精简执行 + 下载结果：紧跟"精简下载"按钮下方展示，避免用户误以为没有反应
    if do_cleanup:
        if mode == "删除全部未使用":
            delete_ids = [
                s["style_id"]
                for s in styles
                if s["usage_count"] == 0 and not s["protected"]
            ]
        else:
            delete_ids = [sid for sid, flag in delete_map.items() if flag]

        if not delete_ids:
            st.warning("⚠️ 未选择任何要删除的样式。")
        else:
            out_path = str(TEMP_DIR / f"style_cleaned_{user_id}.docx")

            # ===== 精简阶段（带进度条，按阶段推进）=====
            cleanup_bar = st.progress(0)
            cleanup_status = st.empty()
            _cleanup_ts = [0.0]

            def _on_cleanup_progress(done, total):
                frac = done / total if total else 0.0
                _now = time.time()
                if frac >= 1.0 or _now - _cleanup_ts[0] >= 0.1:
                    _cleanup_ts[0] = _now
                    cleanup_bar.progress(min(frac, 1.0))
                    cleanup_status.caption(f"🧹 正在精简样式… {int(frac * 100)}%")

            try:
                result = StyleCleaner.cleanup_styles(
                    temp_path, out_path, delete_ids,
                    progress_callback=_on_cleanup_progress,
                )
            except Exception as e:
                st.error(f"❌ 精简失败：{e}")
            else:
                cleanup_bar.progress(1.0)
                cleanup_status.caption("✅ 精简完成")
                st.session_state.style_cleanup_result = {
                    "path": out_path,
                    "name": f"样式精简_{uploaded.name}",
                    "deleted": result.get("deleted", 0),
                    "skipped_protected": result.get("skipped_protected", 0),
                    "repointed": result.get("repointed", 0),
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

    # 自定义配置：展示全部样式清单，每行提供 保留/删除 单选
    if mode == "自定义配置":
        st.markdown("---")
        h = st.columns([3.2, 1.8, 1.0, 3.0])
        h[0].markdown("**样式名称**")
        h[1].markdown("**使用情况**")
        h[2].markdown("**使用次数**")
        h[3].markdown("**操作**")

        for s in styles:
            sid = s["style_id"]
            c_name, c_status, c_count, c_action = st.columns([3.2, 1.8, 1.0, 3.0])
            with c_name:
                lock = "🔒" if s["protected"] else ""
                st.markdown(f"{lock} {s['name'] or sid}")
            with c_status:
                status = "使用" if s["usage_count"] > 0 else "未使用"
                if s["builtin"]:
                    status += "（内置）"
                st.caption(status)
            with c_count:
                st.caption(str(s["usage_count"]))
            with c_action:
                action = st.radio(
                    "操作",
                    options=["保留", "删除"],
                    index=1 if delete_map.get(sid, False) else 0,
                    horizontal=True,
                    key=f"sc_action_{sid}",
                    label_visibility="collapsed",
                    disabled=s["protected"],
                )
                if s["protected"]:
                    delete_map[sid] = False
                else:
                    delete_map[sid] = (action == "删除")
    else:
        st.caption(f"将删除全部未使用且非最小保留的样式，共 {cleanable} 个。")
