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

# 标题文字长度过滤的默认阈值（用户 2026-11-06 指定：默认 20 字符）。
DEFAULT_MAX_TITLE_CHARS = 20


def _title_text(item) -> str:
    """取「标题文字」——不含编号与分隔符，作为长度过滤的计量口径。

    识别结果里的 ``text`` 是整行（编号 + 分隔符 + 标题），``number`` 是编号；
    因此从 text 开头剥掉编号，再剥掉可能残留的分隔符（空格/制表符/全角空格/
    点号/顿号），剩下的就是用户所说的「标题文字」。
    注意不能直接数 ``text``：那样 ``7.4.17`` 这 6 个字符会被算进长度里。
    """
    content = item.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    text = str(item.get("text") or "")
    number = str(item.get("number") or "")
    if number and text.startswith(number):
        text = text[len(number):]
    return text.lstrip(" \t\u3000.、．").strip()


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
        for _k in ("_tlc_sig", "_tlc_items", "tlc_only_leak", "tlc_level_filter",
                   "tlc_hide_long", "tlc_max_chars"):
            st.session_state.pop(_k, None)
        st.info("📤 上传源文档后自动检查标题格式。")
        return

    # 结果缓存：按（文件名, 大小, 引擎版本）缓存检查结果到 session_state。
    # 复选框切换、其他界面交互触发的整页重跑直接命中缓存，
    # 不重新解析文档（同一文件只在首次上传/换文件时解析一次）。
    # 引擎版本参与缓存签名：识别规则升级后旧缓存自动失效，避免展示过时结果。
    # [2026-11-05] 页码列移除，旧缓存里的 page/page_source 字段不再展示，
    # 但仍要让它失效，避免同一文档命中旧结构继续走老渲染分支。
    _ENGINE_VER = '2026-11-05-nopage'
    sig = (uploaded.name, uploaded.size, _ENGINE_VER)
    if st.session_state.get("_tlc_sig") != sig or "_tlc_items" not in st.session_state:
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
            items = TitlePreprocessor.check_heading_leaks(
                data, progress_callback=_on_progress)
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
        # 长度过滤也回到默认：不启用 + 20 字符（对应「全部显示」的初始状态）。
        st.session_state["tlc_hide_long"] = False
        st.session_state["tlc_max_chars"] = DEFAULT_MAX_TITLE_CHARS

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

    # 筛选控件第一行：格式异常复选框 + 标题级别下拉（可复选），条件叠加生效。
    # [2026-11-06] 用户要求「多选框的 label 也要和框排在同一行」：
    # 与下面「字符数上限」行同构 —— 内层拆成【标签 / 控件】，控件用
    # label_visibility="collapsed" 隐去上方自带标签（aria 标签保留）。
    # 两行的标签列宽必须一致（都 1.2），否则两个控件的左边缘差一截，
    # 与上一轮定的「纵向对齐」冲突。
    col_leak, col_level = st.columns([1.1, 2.9], vertical_alignment="center")
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
        col_lvlab, col_ms = st.columns([1.2, 2.8], vertical_alignment="top")
        with col_lvlab:
            # 2.5rem = multiselect 收起 label 后的框高（实测 40px）。等高 + flex 居中
            # 才能和右侧框共用同一垂直中心；写 2.75rem 会低 2px（实测 cy 差 +2）。
            st.markdown(
                "<div style='height:2.5rem; display:flex; align-items:center; "
                "text-align:left; font-size:1rem; white-space:nowrap;'>"
                "只看所选标题级别（可多选）</div>",
                unsafe_allow_html=True,
            )
        with col_ms:
            picked = st.multiselect(
                "只看所选标题级别（可多选）",
                options=level_options,
                default=level_options,
                key="tlc_level_filter",
                label_visibility="collapsed",
                placeholder="默认全部显示；取消勾选即隐藏该级别",
            )
    sel_levels = set(picked or [])

    # 第三个筛选控件：按「标题文字长度」过滤（2026-11-06 用户需求）。
    # 口径见 _title_text()：只数标题文字，不含编号/分隔符，默认 20 字符；
    # 「20 字符以上」按「超过 20 才隐藏」实现，即保留 ≤ 20 的条目。
    #
    # [2026-11-06] 用户要求「与上一行纵向对齐」：
    # 外层列宽**必须与上面「只看格式异常」那行完全一致（[1.1, 2.9]）**。
    # st.columns 的列宽是「按比例分配剩余宽度」，比例不同 → 第二列起点就不同。
    # 之前这里用 [1.25, 0.70, …]，第二列起点实测 669px，而上行下拉框起点 664px，
    # 差 5px 肉眼可见；改成同一组比例后两者精确重合。
    # 内层再分「标签 / 输入框 / 留白」三列：number_input 只能把 label 放上方，
    # 所以标签用 st.markdown 单独渲染、输入框 label_visibility="collapsed"
    # （aria 标签仍保留，不影响可访问性）。
    col_hide, col_len = st.columns([1.1, 2.9], vertical_alignment="center")
    with col_hide:
        hide_long = st.checkbox(
            "不显示过长的标题",
            value=False,
            key="tlc_hide_long",
            help="勾选后隐藏标题文字超过右侧字符数的条目；不统计编号。",
        )
    with col_len:
        # 内层比例：标签列 1.2 与上一行**完全相同** → 两行的控件（多选框 /
        # 数字框）左边缘落在同一条竖线上；1.2 是按最长那行文字（13 个全角字
        # ≈ 208px）定的，写死 1.05 会把文字压到框上去。
        # 标签不加 padding-left —— 要和上面下拉框的左边缘严格对齐就必须贴列边。
        # white-space:nowrap：窗口变窄时列会按比例缩水，宁可轻微溢出也不换行错位。
        # vertical_alignment 必须是 "top"：实测这一行的高度由 number_input
        # 撑到 56px，而两列内容都只有 40px，用 "center" 会给较矮的 label 列
        # 补 8px 偏移（文字比「20」低 8px），用 "bottom" 则偏 16px。
        # "top" 让两者都从行顶开始，40px 容器内的 flex 居中正好与输入框同轴。
        col_lab, col_num, _ = st.columns([1.2, 0.85, 1.95],
                                         vertical_alignment="top")
        with col_lab:
            # 高度写死 2.5rem（= number_input 的 40px）并用 flex 垂直居中：
            # 只靠 columns(vertical_alignment="center") 不够——markdown 容器
            # 自身高度只有一行文字高（26px），实测文字中心比输入框高 8px，
            # 放大看肉眼可见。等高 + flex 后两边共用同一个垂直中心。
            st.markdown(
                "<div style='height:2.5rem; display:flex; align-items:center; "
                "text-align:left; font-size:1rem; white-space:nowrap;'>"
                "字符数上限（不含编号）</div>",
                unsafe_allow_html=True,
            )
        with col_num:
            max_chars = st.number_input(
                "字符数上限（不含编号）",
                min_value=1,
                max_value=300,
                value=DEFAULT_MAX_TITLE_CHARS,
                step=1,
                key="tlc_max_chars",
                label_visibility="collapsed",
                help="默认 20。只数标题文字本身，标题编号（如 7.4.17）不计入。",
            )

    rows = [it for it in (leaks if only_leak else items)
            if "H%d" % it["detected_level"] in sel_levels]

    hidden_long = 0
    if hide_long:
        limit = int(max_chars)
        kept = []
        for it in rows:
            if len(_title_text(it)) > limit:
                hidden_long += 1
            else:
                kept.append(it)
        rows = kept

    if not rows:
        if not sel_levels:
            st.info("未在上方选择任何标题级别，请在「只看所选标题级别」中至少选择一个。")
        elif only_leak and not leaks:
            st.info("没有格式异常的条目。")
        elif hidden_long:
            st.info(
                f"当前筛选条件下没有可显示的条目："
                f"{hidden_long} 条标题文字超过 {int(max_chars)} 字符，"
                "已被「不显示过长的标题」隐藏。可调大字符数上限或取消勾选。"
            )
        else:
            st.info("当前筛选条件下没有匹配的条目。")
        return

    st.markdown(f"**识别结果（{len(rows)} 条）：**")
    if hide_long and hidden_long:
        st.caption(
            f"已隐藏 {hidden_long} 条标题文字超过 {int(max_chars)} 字符的条目"
            "（只统计标题文字，不含编号）。"
        )
    # [2026-11-05] 页码列已整体移除，本地与云端行为完全一致（用户明确要求）。
    #   * Word COM 只有本地 Windows 能用 → 两端不一致；
    #   * LibreOffice 渲染 PDF 整篇膨胀 ~12%（578 页标书给 645）；
    #   * 按 docx 分页标记估算更不可信（1137 条全算第 25 页）。
    # 既然做不到与 Word 一致，就不显示，避免把错数字当准数。

    def _row(i, it):
        return {
            "序号": i + 1,
            "编号": it["number"],
            "标题文本": ((it["text"][:60] + "…") if len(it["text"]) > 60
                       else it["text"].replace('\t', ' ')),
            "推断级别": f"H{it['detected_level']}",
            "当前样式说明": it["style_description"],
            "判定": LEAK_LABEL if it["is_leak"] else OK_LABEL,
        }

    st.dataframe(
        [_row(i, it) for i, it in enumerate(rows)],
        use_container_width=True,
        hide_index=True,
    )

    if leaks:
        st.info(
            "💡 格式异常的条目可切换到「📑 标题预处理」标签，"
            "用「🚀 处理并下载」统一赋予标题级别。"
        )
