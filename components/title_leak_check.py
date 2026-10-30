# -*- coding: utf-8 -*-
"""
源文档标题查漏交互组件（T04 / 工具箱标签）
只检查、只提示，不修改文档：列出识别到的编号标题及其当前样式说明，
并标出"本应是标题、却既非标题样式也无大纲级别"的格式异常项。
检查过程带进度条（按已扫描段落数节流推进，不静止、不阻塞）。
"""
import io
import logging
import time

import streamlit as st

from title_preprocessor import TitlePreprocessor

logger = logging.getLogger('WordStyle')

LEAK_LABEL = '⚠️ 未使用标题格式'
OK_LABEL = '✅ 已是标题格式'


def render_title_leak_check():
    """渲染标题查漏交互区（识别对象与标题预处理完全一致）。"""
    st.markdown(
        "检查文档中**本应是标题、却既未使用标题样式也无大纲级别**的编号段落。"
        "识别范围与标题预处理一致（数字编号 + 制表符 + 单列标题、第一章 等章节标题），"
        "本功能只检查、只提示，不修改文档。"
    )

    uploaded = st.file_uploader(
        "上传源文档（支持 .docx）",
        type=['docx'],
        key="title_leak_check_uploader",
    )

    if uploaded is None:
        # 文档被移除（用户点了上传框的删除）：连同筛选状态一起清空。
        # 否则下次上传新文档时，会沿用上一份文档的「只看异常 / 所选级别」。
        # 此刻筛选控件尚未渲染，写 session_state 不会被 widget 状态覆盖。
        for _k in ("_tlc_sig", "_tlc_items", "tlc_only_leak", "tlc_level_filter"):
            st.session_state.pop(_k, None)
        st.info("📤 上传源文档后自动检查标题格式。")
        return

    # 结果缓存：按（文件名, 大小, 引擎版本）缓存检查结果到 session_state。
    # 复选框切换、其他界面交互触发的整页重跑直接命中缓存，
    # 不重新解析文档（同一文件只在首次上传/换文件时解析一次）。
    # 引擎版本参与签名：识别规则升级后旧缓存自动失效，避免展示过时结果。
    # 引擎版本参与缓存签名：加了「Word 物理页码」后，旧缓存里的页码是估算值
    # 且没有 page_source 字段，必须让它失效。
    _ENGINE_VER = '2026-10-27-word'
    sig = (uploaded.name, uploaded.size, _ENGINE_VER)
    if st.session_state.get("_tlc_sig") != sig or "_tlc_items" not in st.session_state:
        # 直接读上传流（内存流，不落临时文件，本功能只读）
        data = io.BytesIO(uploaded.getbuffer())

        # 带进度条检查：引擎按段落扫描回传进度，UI 按节流阈值更新进度条，
        # 保证处理过程中进度条持续推进，最后推满 100%（对齐文档转换页的进度条）。
        progress_bar = st.progress(0)
        status_text = st.empty()
        _last_ts = [0.0]
        # [2026-10-27] 进度条按两个阶段连续推进，绝不倒退：
        #   扫描段落 → 0~40%；Word 算页码 → 40~100%。
        # 不这么做的话，Word 阶段要么进度条静止十几秒（像卡死），
        # 要么重新从 0 开始（用户以为要重来一遍）。
        _SCAN_SHARE = 0.4

        def _on_progress(done, total):
            frac = done / total if total else 0.0
            _now = time.time()
            if frac >= 1.0 or _now - _last_ts[0] >= 0.1:
                _last_ts[0] = _now
                progress_bar.progress(min(frac * _SCAN_SHARE, 1.0))
                status_text.caption(f"🔍 正在检查… {done}/{total} 段")

        def _on_word_progress(done, total):
            frac = done / total if total else 0.0
            _now = time.time()
            if frac >= 1.0 or _now - _last_ts[0] >= 0.1:
                _last_ts[0] = _now
                progress_bar.progress(min(_SCAN_SHARE + frac * (1 - _SCAN_SHARE), 1.0))
                status_text.caption(f"📄 正在用 Word 计算物理页码… {done}/{total} 条")

        def _on_stage(msg):
            status_text.caption(msg)

        try:
            items = TitlePreprocessor.check_heading_leaks(
                data, progress_callback=_on_progress, stage_callback=_on_stage,
                word_progress_callback=_on_word_progress)
        except Exception as e:
            logger.exception("标题查漏解析失败")
            st.error(f"❌ 文档解析失败：{e}")
            return

        progress_bar.progress(1.0)
        status_text.caption("✅ 检查完成")

        st.session_state["_tlc_sig"] = sig
        st.session_state["_tlc_items"] = items

        # 换文档（或引擎升级）后筛选条件回到默认：不只看异常 + 级别全选 = 全部显示。
        # 必须写在筛选控件渲染之前（此时 widget 尚未实例化，写 session_state 才生效）；
        # fragment 局部重跑不走这里，因此用户在本文件内的筛选不会被重置。
        st.session_state["tlc_only_leak"] = False
        st.session_state["tlc_level_filter"] = [
            "H%d" % n for n in sorted({int(it["detected_level"]) for it in items})
        ]

    items = st.session_state["_tlc_items"]

    if not items:
        st.success("✅ 未识别到编号标题，没有可检查的标题对象。")
        return

    # 结果展示放在独立 fragment 中：切换「只看格式异常的条目」复选框时
    # 只重绘本 fragment（直接过滤已缓存的表格数据），不重新解析文档、不刷新整个界面。
    _render_leak_results(items)


@st.fragment
def _render_leak_results(items):
    """渲染查漏结果（fragment：复选框交互只局部重绘）。"""
    leaks = [it for it in items if it["is_leak"]]
    if leaks:
        st.warning(
            f"⚠️ 共识别 {len(items)} 个疑似标题，"
            f"其中 **{len(leaks)} 个未使用标题格式/大纲级别**（下表标为「{LEAK_LABEL}」）。"
        )
    else:
        st.success(
            f"✅ 共识别 {len(items)} 个疑似标题，"
            "全部已使用标题格式或大纲级别，未发现格式异常。"
        )

    # 两个筛选控件并排：格式异常复选框 + 标题级别下拉（可复选），条件叠加生效。
    col_leak, col_level = st.columns([1.1, 2.9])
    with col_leak:
        only_leak = st.checkbox("只看格式异常的条目", value=False, key="tlc_only_leak")
    with col_level:
        # 只列出本文档实际出现的级别，按 H1→H9 升序；默认全选（= 不按级别过滤）。
        # 换文件后选项集合会变，先把残留的旧取值收敛掉，避免出现不存在的级别。
        level_options = ["H%d" % n
                         for n in sorted({int(it["detected_level"]) for it in items})]
        _prev = st.session_state.get("tlc_level_filter")
        if isinstance(_prev, list) and any(v not in level_options for v in _prev):
            st.session_state["tlc_level_filter"] = [v for v in _prev if v in level_options]
        picked = st.multiselect(
            "只看所选标题级别（可多选）",
            options=level_options,
            default=level_options,
            key="tlc_level_filter",
            placeholder="默认全部显示；取消勾选即隐藏该级别",
        )
    sel_levels = set(picked or [])

    rows = [it for it in (leaks if only_leak else items)
            if "H%d" % it["detected_level"] in sel_levels]

    if not rows:
        if not sel_levels:
            st.info("未在上方选择任何标题级别，请在「只看所选标题级别」中至少选择一个。")
        elif only_leak and not leaks:
            st.info("没有格式异常的条目。")
        else:
            st.info("当前筛选条件下没有匹配的条目。")
        return

    st.markdown(f"**识别结果（{len(rows)} 条）：**")
    # [2026-10-27] 页码来源分两种，必须在界面上说清楚，否则用户会拿估算值当准数：
    #   word     = 本机 Word 算出的物理页码（= Word 窗口底部「第 X 页」，准确）
    #   estimate = docx 分页标记推算（文档编辑过就可能差几页）
    _srcs = {it.get("page_source", "estimate") for it in rows}
    if _srcs == {"word"}:
        st.caption("页码为 **Word 物理页码**（与 Word 窗口底部「第 X 页」一致）。")
    elif "word" in _srcs:
        st.caption(
            "页码以 **Word 物理页码**为准；个别条目未能定位，退回分页标记估算值。"
        )
    else:
        st.caption(
            "页码为**估算值**：docx 不保存实时分页，只能按文档内分页标记"
            "（显式分页符 / Word 上次渲染的分页 / 分节符）推算，"
            "文档被编辑过可能相差数页。"
        )
    _mixed = len(_srcs) > 1
    st.dataframe(
        [
            {
                "序号": i + 1,
                # 混合来源时逐行标记：估算值前面加 "~"，否则用户会把 20 当成准数。
                "页码": (f"~{it['page']}" if _mixed and it.get("page_source") == "estimate"
                         else it.get("page", "—")),
                "编号": it["number"],
                "标题文本": (
                    (it["text"][:60] + "…") if len(it["text"]) > 60
                    else it["text"].replace('\t', ' ')
                ),
                "推断级别": f"H{it['detected_level']}",
                "当前样式说明": it["style_description"],
                "判定": LEAK_LABEL if it["is_leak"] else OK_LABEL,
            }
            for i, it in enumerate(rows)
        ],
        use_container_width=True,
        hide_index=True,
    )

    if leaks:
        st.info(
            "💡 格式异常的条目可切换到「📑 标题预处理」标签，"
            "用「🚀 处理并下载」统一赋予标题级别。"
        )
