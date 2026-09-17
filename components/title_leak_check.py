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
        st.info("📤 上传源文档后自动检查标题格式。")
        return

    # 直接读上传流（内存流，不落临时文件，本功能只读）
    data = io.BytesIO(uploaded.getbuffer())

    # 带进度条检查：引擎按段落扫描回传进度，UI 按节流阈值更新进度条，
    # 保证处理过程中进度条持续推进，最后推满 100%（对齐文档转换页的进度条）。
    progress_bar = st.progress(0)
    status_text = st.empty()
    _last_ts = [0.0]

    def _on_progress(done, total):
        frac = done / total if total else 0.0
        _now = time.time()
        if frac >= 1.0 or _now - _last_ts[0] >= 0.1:
            _last_ts[0] = _now
            progress_bar.progress(min(frac, 1.0))
            status_text.caption(f"🔍 正在检查… {done}/{total} 段")

    try:
        items = TitlePreprocessor.check_heading_leaks(data, progress_callback=_on_progress)
    except Exception as e:
        logger.exception("标题查漏解析失败")
        st.error(f"❌ 文档解析失败：{e}")
        return

    progress_bar.progress(1.0)
    status_text.caption("✅ 检查完成")

    if not items:
        st.success("✅ 未识别到编号标题，没有可检查的标题对象。")
        return

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

    only_leak = st.checkbox("只看格式异常的条目", value=False, key="tlc_only_leak")
    rows = leaks if only_leak else items

    if not rows:
        st.info("没有格式异常的条目。")
        return

    st.markdown(f"**识别结果（{len(rows)} 条）：**")
    st.dataframe(
        [
            {
                "序号": i + 1,
                "段落序号": it["index"],
                "编号": it["number"],
                "标题文本": it["text"].replace('\t', ' '),
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
