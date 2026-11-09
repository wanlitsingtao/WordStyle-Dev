# -*- coding: utf-8 -*-
"""
源文档标题预处理交互组件（T04 / 工具箱标签：源文档标题预处理）
检测表格 + 级别编辑 + 处理下载。
"""
import hashlib
import html
import logging
import os
import threading
import time

import streamlit as st

from title_preprocessor import TitlePreprocessor

logger = logging.getLogger('WordStyle')

# 目标级别选项：H1-H9 + "不转换"
LEVEL_OPTIONS = [f"H{i}" for i in range(1, 10)] + ["不转换"]

# 列表列宽（表头与数据行共用同一组比例，否则列会错位）
_COL_WIDTHS = [0.55, 3.6, 0.9, 1.15, 3.0, 1.2]
_HEAD_LABELS = ['选', '原文', '原级别', '新编号', '新标题', '新级别']


def _heading_content(h) -> str:
    """取「剥离编号后的标题正文」。

    引擎已经返回 content；这里再兜一层，兼容旧缓存/外部直接构造的 headings
    （没有 content 时从 text 里剥掉 number 前缀）。
    """
    content = h.get('content')
    if isinstance(content, str) and content.strip():
        return content.strip()
    text = str(h.get('text') or '')
    number = str(h.get('number') or '')
    if number and text.startswith(number):
        text = text[len(number):]
    return text.lstrip(' \t\u3000\xa0.、．').strip()


def _short(text: str, limit: int) -> str:
    """列表里截断显示（完整内容放进 tooltip，避免千人千面的列宽抖动）。"""
    text = text or ''
    return text if len(text) <= limit else text[:limit] + '…'


def _widget_value(key: str, fallback):
    """优先取控件在 session_state 里的**本轮最新值**，取不到才用 fallback。

    为什么不能只读自己维护的 dict：
        「处理并下载」按钮渲染在列表**上方**，它执行时本轮列表还没渲染，
        自己维护的 numbers/levels dict 还停留在上一轮。用户「改完编号立刻点按钮」
        时，控件的新值已经写进 session_state[key]（rerun 前），dict 却还没更新 →
        新编号会被静默丢弃（2026-11-06 实测：改成 2.7，下载回来仍是 1.1）。
    """
    val = st.session_state.get(key)
    return fallback if val is None else val


class _TitleTask:
    """标题处理后台任务状态（线程安全，带代次防止旧线程覆盖新任务）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._gen = 0
        self.running = False
        self.done = 0
        self.total = 0
        self.finished = False
        self.error = None
        self.result = None

    def reset(self):
        with self._lock:
            self._gen += 1
            self.running = False
            self.done = 0
            self.total = 0
            self.finished = False
            self.error = None
            self.result = None

    def start(self, total):
        with self._lock:
            self._gen += 1
            gen = self._gen
            self.running = True
            self.done = 0
            self.total = total
            self.finished = False
            self.error = None
            self.result = None
            return gen

    def update(self, gen, done, total):
        with self._lock:
            if gen != self._gen:
                return
            self.done = done
            self.total = total

    def finish(self, gen, error=None, result=None):
        with self._lock:
            if gen != self._gen:
                return
            self.running = False
            self.finished = True
            self.error = error
            self.result = result

    def snapshot(self):
        with self._lock:
            return self.running, self.done, self.total, self.finished, self.error, self.result


_title_task = _TitleTask()


@st.fragment(run_every="0.5s")
def _render_task_progress():
    """轮询后台任务状态并渲染进度条 / 处理结果。"""
    running, done, total, finished, error, result = _title_task.snapshot()
    if running:
        st.progress(done / total if total else 1.0)
        st.caption(f"⏳ 正在处理… {done}/{total}")
    if finished:
        if error:
            st.error(f"❌ 处理失败：{error}")
        elif result and os.path.exists(result["path"]):
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


def _level_to_int(level_label):
    if level_label == "不转换":
        return 0
    return int(level_label[1:])


def _detect(user_id, uploaded_file, progress_callback=None):
    """保存上传文件并检测标题。返回 (headings, temp_path)。"""
    from config import TEMP_DIR
    temp_path = str(TEMP_DIR / f"temp_title_preprocess_{user_id}.docx")
    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.getbuffer())
    headings = TitlePreprocessor.detect_headings(temp_path, progress_callback=progress_callback)
    return headings, temp_path


@st.fragment
def render_title_preprocess():
    """渲染标题预处理交互区（@st.fragment 局部刷新）。"""
    st.markdown(
        "提取文档中的编号标题，统一按编号层级赋予大纲级别（Heading 1-9），"
        "生成可被样式映射识别的新文档；已具有标题样式/大纲级别的编号段落也一并按编号统一处理。"
        "\n\n**列表一次展示全部信息**：原文 / 原标题级别 / 新编号 / 新标题 / 新级别。"
        "「新编号」默认沿用原文编号，可直接改成任意值 —— 改过的编号会写进新文档，"
        "并替换掉正文里的旧编号；同时会关闭标题的 Word 自动编号，"
        "避免出现「16.1. 1.1 一致性」这种新旧两个编号并存的情况。"
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
    # 带进度条：检测阶段按段落扫描推进，处理阶段由后台任务轮询推进。
    detect_bar = st.progress(0)
    detect_status = st.empty()
    _detect_ts = [0.0]

    def _on_detect_progress(done, total):
        frac = done / total if total else 0.0
        _now = time.time()
        if frac >= 1.0 or _now - _detect_ts[0] >= 0.1:
            _detect_ts[0] = _now
            detect_bar.progress(min(frac, 1.0))
            detect_status.caption(f"🔍 正在检测标题… {done}/{total} 段")

    try:
        headings, temp_path = _detect(user_id, uploaded, progress_callback=_on_detect_progress)
    except Exception as e:
        st.error(f"❌ 文档解析失败：{e}")
        return

    detect_bar.progress(1.0)
    detect_status.caption("✅ 检测完成")

    if not headings:
        st.warning("未检测到编号标题（数字编号 + 制表符 + 标题文本 格式）。")
        return

    st.markdown(f"**检测到 {len(headings)} 个疑似标题段落：**")
    st.caption(
        "「原文」是文档里的原始一行（含旧编号）；「新编号」可编辑，留空或不改则沿用原文；"
        "「新标题」是剥掉编号后的正文，写入时与「新编号」拼成一行；"
        "「新级别」决定套用哪个 Heading 样式。"
    )

    # 初始化/同步勾选状态与目标级别到 session_state
    detect_key = f"title_detect_{uploaded.name}_{len(headings)}"
    # 控件 key 带文件指纹：换文档后行下标 idx 会重复，用固定 key 会把上一份文档的
    # 编辑值（编号/级别/勾选）串到新文档上。加后缀天然隔离（2026-11-06）。
    row_suffix = hashlib.md5(detect_key.encode('utf-8')).hexdigest()[:8]
    st.session_state.setdefault('title_preprocess_detect_key', '')
    if st.session_state.get('title_preprocess_detect_key') != detect_key:
        st.session_state.title_preprocess_detect_key = detect_key
        st.session_state.title_preprocess_selected = {h["index"]: True for h in headings}
        st.session_state.title_preprocess_levels = {
            h["index"]: f"H{h['detected_level']}" for h in headings
        }
        # 新编号默认沿用原文编号：这一步只把编号从正文里「拆出来」变成独立可编辑字段，
        # 不擅自改动用户的编号体系；用户想换号直接在列表里改，改完写进新文档。
        st.session_state.title_preprocess_numbers = {
            h["index"]: h["number"] for h in headings
        }
        _title_task.reset()

    selected = st.session_state.title_preprocess_selected
    levels = st.session_state.title_preprocess_levels
    # 兼容热重载/旧会话：detect_key 没变时上面的初始化块不会执行，
    # 而老会话里可能还没有 numbers 这个键（2026-11-06 新增）。
    if not isinstance(st.session_state.get('title_preprocess_numbers'), dict):
        st.session_state.title_preprocess_numbers = {
            h["index"]: h["number"] for h in headings
        }
    numbers = st.session_state.title_preprocess_numbers

    # 处理操作区（重新检测 / 处理并下载 + 结果展示），放在"全选/反选"之上
    col_re, col_go = st.columns([1, 2])
    with col_re:
        re_detect = st.button("🔄 重新检测", key="tp_redetect", use_container_width=True)
    with col_go:
        do_process = st.button("🚀 处理并下载", key="tp_process", type="primary", use_container_width=True)

    if re_detect:
        st.session_state.title_preprocess_detect_key = ''
        _title_task.reset()
        st.rerun()

    if do_process:
        selections = []
        for h in headings:
            idx = h["index"]
            if selected.get(idx, True):
                level_label = _widget_value(f"tp_level_{row_suffix}_{idx}",
                                            levels.get(idx, f"H{h['detected_level']}"))
                target_level = _level_to_int(level_label)
                if target_level >= 1:
                    selections.append({
                        "index": idx,
                        "target_level": target_level,
                        # 新编号交给引擎：与原文不同就改写正文里的旧编号，
                        # 相同则一字不改（只套样式 + 关自动编号）。
                        "new_number": str(_widget_value(
                            f"tp_num_{row_suffix}_{idx}",
                            numbers.get(idx, h["number"])) or "").strip(),
                    })

        if not selections:
            st.error("❌ 请至少选择一个要转换的标题段落。")
        elif _title_task.running:
            st.info("⏳ 正在处理中，请稍候…")
        else:
            from config import TEMP_DIR
            out_path = str(TEMP_DIR / f"title_preprocessed_{user_id}.docx")
            gen = _title_task.start(len(selections))

            def _work():
                try:
                    def _on_progress(done, total):
                        _title_task.update(gen, done, total)

                    TitlePreprocessor.apply_headings(
                        temp_path, out_path, selections, progress_callback=_on_progress
                    )
                    _title_task.finish(gen, result={
                        "path": out_path,
                        "name": f"标题预处理_{uploaded.name}",
                        "count": len(selections),
                    })
                except Exception as e:
                    _title_task.finish(gen, error=str(e))

            threading.Thread(target=_work, daemon=True).start()

    # 后台任务进度 / 结果展示（每 0.5s 轮询更新，不阻塞主界面）
    _render_task_progress()

    st.markdown("---")

    # 批量操作（全选 / 反选）
    # 注意：必须同时写控件的 session_state[key]，只改 dict 是无效的 ——
    # checkbox 一旦有了 key，之后每轮都以控件自身状态为准，value 参数会被忽略，
    # 表现就是"点了全选，勾选纹丝不动"（已有实现的老问题，2026-11-06 一并修）。
    col_sel, col_inv, col_only = st.columns(3)
    with col_sel:
        if st.button("全选", key="tp_select_all", use_container_width=True):
            for h in headings:
                selected[h["index"]] = True
                st.session_state[f"tp_check_{row_suffix}_{h['index']}"] = True
    with col_inv:
        if st.button("反选", key="tp_invert", use_container_width=True):
            for h in headings:
                new_val = not st.session_state.get(
                    f"tp_check_{row_suffix}_{h['index']}", selected.get(h["index"], True))
                selected[h["index"]] = new_val
                st.session_state[f"tp_check_{row_suffix}_{h['index']}"] = new_val

    # 渲染检测表格
    # 表头与数据行共用 _COL_WIDTHS，保证列严格对齐（列宽改一处即可）。
    head_cols = st.columns(_COL_WIDTHS, vertical_alignment="center")
    for col, label in zip(head_cols, _HEAD_LABELS):
        with col:
            st.markdown(
                "<div style='font-size:0.82rem;font-weight:700;color:#64748b;"
                f"line-height:1.6;'>{label}</div>",
                unsafe_allow_html=True,
            )
    st.markdown(
        "<div style='height:1px;background:#e2e8f0;margin:0 0 0.4rem 0;'></div>",
        unsafe_allow_html=True,
    )

    for i, h in enumerate(headings):
        idx = h["index"]
        content = _heading_content(h)
        col_check, col_text, col_detected, col_number, col_new, col_target = st.columns(
            _COL_WIDTHS, vertical_alignment="center")
        with col_check:
            selected[idx] = st.checkbox(
                "选",
                value=selected.get(idx, True),
                key=f"tp_check_{row_suffix}_{idx}",
                label_visibility="collapsed",
            )
        with col_text:
            # 原文整段放进 title 属性：列里截断，鼠标悬停能看全文
            st.markdown(
                f"<div title=\"{html.escape(h['text'])}\" "
                "style='font-size:0.88rem;line-height:1.5;color:#0f172a;'>"
                f"{html.escape(_short(h['text'], 60))}</div>",
                unsafe_allow_html=True,
            )
        with col_detected:
            st.markdown(
                "<div style='font-size:0.88rem;color:#64748b;'>"
                f"H{h['detected_level']}</div>",
                unsafe_allow_html=True,
            )
        with col_number:
            numbers[idx] = st.text_input(
                "新编号",
                value=numbers.get(idx, h["number"]),
                key=f"tp_num_{row_suffix}_{idx}",
                label_visibility="collapsed",
            ).strip()
        with col_new:
            st.markdown(
                f"<div title=\"{html.escape(content)}\" "
                "style='font-size:0.88rem;line-height:1.5;color:#334155;'>"
                f"{html.escape(_short(content, 40))}</div>",
                unsafe_allow_html=True,
            )
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
                key=f"tp_level_{row_suffix}_{idx}",
                label_visibility="collapsed",
            )
