# -*- coding: utf-8 -*-
"""
源文档标题预处理引擎（T04 / 工具箱：标题查漏 + 标题预处理）
无 Streamlit 依赖，可独立测试。

职责：
1. 检测以正文格式出现的编号标题（数字编号 + 空白分隔符 + 单列标题，如 "1.1 线路"）
2. 按编号层级推断大纲级别（1→H1, 1.1→H2, 1.1.1→H3）
3. 将选中段落应用对应 Heading N 样式（并设置大纲级别）
4. 判断文档是否已使用标题样式（供转换页引导提示）
5. 查漏：找出"本应是标题、却既非标题格式也无大纲级别"的编号段落（只检查、不修改）
"""
import os
import re
import tempfile
from typing import List, Dict, Optional

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# 编号标题检测：数字编号 + 空白分隔符 + 单列标题文本（如 "1.1 线路"、"1.1\t线路"）。
# 分隔符为半角空格 / 制表符 / 全角空格 / 不换行空格中的一种或多种。
# 注意：不要退回"只认制表符"。同一份源文档里空格与制表符经常混用（例如 8js1.docx
# 全篇编号标题都用半角空格），只认制表符会导致整批标题漏检（2026-09-17 修复）。
# 排除列表项（"1、"、"1）"、"2)"）：编号后紧跟标点而非空白，天然不匹配本条规则；
# 排除多列表格行（"1\t小于 300\t1.2\t65"）：正文部分不允许再出现制表符。
# 捕获组 1 = 纯数字编号（用于推断层级），组 2 = 标题正文。
HEADING_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)*)[ \t\u3000\xa0]+([^\t]*)$')

# 无分隔符的多级编号标题（如 "4.5.1非主体、非关键性部件采购"）：编号与标题文字之间
# 没有任何空白。仅认三级及以上（至少两个点）的编号 —— 一/两级编号直接跟文字的场景
# 多为"数值 + 单位"（如 "3.5万元/台"、"2.4G天线"）或目录行（"12.1质量管理\t127"），
# 不匹配，避免误判（2026-10-27）。正文部分不允许再出现制表符（与主规则口径一致，
# 排除 "5.1.10信息化管理\t175" 这类目录行）。
HEADING_PATTERN_NOSEP = re.compile(r'^\s*(\d+(?:\.\d+){2,})([^\d\s\t].*)$')

# 文本开头数字编号：用于已具有标题样式/大纲级别的段落统一按编号推断级别（如 "1.1 线路" / "1.1线路"）。
NUMBER_PREFIX_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)*)')

# 章节标题检测："第一章" / "第1章" / "第一章 概述" 等，默认大纲级别 1。
# 捕获组 1 = 章节编号（如 "第一章"），组 2 = 标题正文。
CHAPTER_PATTERN = re.compile(r'^\s*(第[一二三四五六七八九十百\d]+章)\s*(.*)$')

# 已有标题样式名 -> 大纲级别
HEADING_STYLE_LEVELS = {
    'heading 1': 1, 'heading 2': 2, 'heading 3': 3, 'heading 4': 4, 'heading 5': 5,
    'heading 6': 6, 'heading 7': 7, 'heading 8': 8, 'heading 9': 9,
    '标题 1': 1, '标题 2': 2, '标题 3': 3, '标题 4': 4, '标题 5': 5,
    '标题 6': 6, '标题 7': 7, '标题 8': 8, '标题 9': 9,
}


class TitlePreprocessor:
    """源文档标题预处理引擎（无状态工具类）"""

    MAX_LEVEL = 9

    @staticmethod
    def infer_level(number_part: str) -> int:
        """根据编号推断大纲级别：层级深度 = 点号数量 + 1，上限 9。

        Examples:
            "1"     -> 1
            "1.1"   -> 2
            "1.1.1" -> 3
        """
        depth = number_part.count('.') + 1
        return min(depth, TitlePreprocessor.MAX_LEVEL)

    @staticmethod
    def detect_headings(docx_file, progress_callback=None) -> List[Dict]:
        """检测文档中的编号标题段落。

        Args:
            docx_file: docx 文件路径，或可读的文件对象（如 io.BytesIO）。
            progress_callback: 可选，段落扫描进度回调 progress_callback(done: int, total: int)，
                用于非阻塞进度条（不影响识别结果）。

        Returns:
            List[Dict]，每个元素结构：
                {
                    "index": int,             # 段落索引（doc.paragraphs 中的位置）
                    "text": str,              # 段落原文
                    "number": str,            # 编号部分（如 "1.1.1"）
                    "detected_level": int,    # 自动推断的级别（1-9）
                }
        """
        return TitlePreprocessor._detect_headings_in(
            Document(docx_file), progress_callback=progress_callback
        )

    @staticmethod
    def _detect_headings_in(doc, progress_callback=None) -> List[Dict]:
        """在已打开的 Document 上执行标题识别（detect_headings 与 check_heading_leaks 共用）。

        识别规则、判断分支与顺序与 detect_headings 完全一致，仅把"加载文档"与"识别"拆开：
        查漏功能必须与预处理共用同一套识别逻辑，否则两处各写一份会产生口径分歧。

        Args:
            progress_callback: 可选，段落扫描进度回调 progress_callback(done: int, total: int)。
                仅在识别前对全部段落做一次扫描时按比例推进（用于查漏/预处理的进度条），
                不影响识别结果。
        """
        candidates = []
        total_paras = len(doc.paragraphs)
        for idx, para in enumerate(doc.paragraphs):
            if progress_callback:
                progress_callback(idx + 1, total_paras)
            # 用原始文本匹配（不 strip），以便区分"单列标题"与"多列表格行/列表项"。
            raw_text = para.text
            if not raw_text.strip():
                continue
            # 软回车合并段（标题行与正文被 w:br 软回车合并在同一段，如
            # "4.5.3.1 分供范围与备案\n卖方可将…"）：只取首行做标题匹配，
            # 首行即标题行，正文行不参与编号判断（2026-10-27）。
            first_line = raw_text.split('\n', 1)[0] if '\n' in raw_text else raw_text
            m = (HEADING_PATTERN.match(first_line)
                 or HEADING_PATTERN_NOSEP.match(first_line))
            if not m:
                continue
            number_part = m.group(1)
            content = m.group(2).strip()
            # 排除纯数字段落（如单纯的 "1" 后面无内容）
            if not content:
                continue
            # 正文部分不允许再出现制表符（与主规则口径一致，
            # 排除 "5.1.10信息化管理\t175" 这类目录行）
            if '\t' in content:
                continue
            # 三级及以上编号（如 4.5.2.1）：招标文件里大量合同条款是
            # "编号 + 整段正文（长、以句号结尾）"的条款段，按用户要求一并纳入
            # 疑似标题；一/二级编号维持原严格规则（60 字、句号/分号结尾排除）。
            deep_number = number_part.count('.') >= 2
            text = first_line.strip()
            max_len = 300 if deep_number else 60
            # 排除过长的段落（标题通常较短；三级以上编号放宽到条款段长度）
            if len(text) > max_len:
                continue
            # 排除以句号/分号结尾的正文条款（标题通常不以这些标点结尾；
            # 三级及以上编号的条款段不受此限）
            if not deep_number and (content.endswith('。') or content.endswith('；')):
                continue
            candidates.append({
                "index": idx,
                "text": text,
                "number": number_part,
                "content": content,
                "detected_level": TitlePreprocessor.infer_level(number_part),
            })

        # 先过滤掉内容以数字/符号开头的段落（多为数值、表格行，如 "1294.53～"、"100℃×…"、">10P 250"）。
        filtered = []
        for c in candidates:
            if c["content"][0] in '0123456789±><≥≤~～＋－':
                continue
            filtered.append(c)

        # 单级编号（无 "."）列表：按文档顺序记录其在 filtered 中的位置。
        single_positions = [k for k, c in enumerate(filtered) if '.' not in c["number"]]

        def _has_child(pos):
            """单级编号 N 到下一个单级编号之间，是否存在 N.x 子级。"""
            num = filtered[pos]["number"]
            nxt = None
            for sp in single_positions:
                if sp > pos:
                    nxt = sp
                    break
            end = nxt if nxt is not None else len(filtered)
            return any(
                '.' in filtered[j]["number"] and filtered[j]["number"].startswith(num + '.')
                for j in range(pos + 1, end)
            )

        # 连续性判断：把连续递增的单级编号归为一段（如 3、4、5 或 1、2、3、4）。
        # 段内只要有一个编号存在子级，整段都视为标题（用户规则：3 无子级但 4 有 4.1，则 3、4 都是）。
        single_runs = []  # 每项为位置列表
        for sp in single_positions:
            if single_runs and int(filtered[single_runs[-1][-1]]["number"]) + 1 == int(filtered[sp]["number"]):
                single_runs[-1].append(sp)
            else:
                single_runs.append([sp])

        heading_positions = set()
        for run in single_runs:
            if any(_has_child(p) for p in run):
                heading_positions.update(run)

        headings = []
        for k, c in enumerate(filtered):
            # 多级编号（如 1.1 / 1.1.1）直接视为标题；单级编号按连续性判断。
            if '.' in c["number"] or k in heading_positions:
                headings.append({
                    "index": c["index"],
                    "text": c["text"],
                    "number": c["number"],
                    "detected_level": c["detected_level"],
                })

        # 章节标题（"第一章" / "第1章"）检测：默认大纲级别 1。
        for idx, para in enumerate(doc.paragraphs):
            raw_text = para.text
            if not raw_text.strip():
                continue
            m = CHAPTER_PATTERN.match(raw_text)
            if not m:
                continue
            content = m.group(2).strip()
            # 排除章节号引用（如 "第二章 4.10.3 节 ..."）及句末标点结尾的正文；
            # 正文含制表符的多列行（目录行 "第一章  致投标人\t1"）同样排除
            if '\t' in content:
                continue
            if content and (
                content[0].isdigit()
                or content.endswith('。')
                or content.endswith('；')
            ):
                continue
            text = raw_text.strip()
            if len(text) > 60:
                continue
            headings.append({
                "index": idx,
                "text": text,
                "number": m.group(1),
                "detected_level": 1,
            })

        # 已有标题样式 / 大纲级别的段落：也纳入识别范围，但级别统一按编号规则推断，
        # 不再依据样式名 / outlineLvl 推断级别（真正的标题定级在文档格式转换阶段完成）。
        seen_idx = {h["index"] for h in headings}
        for idx, para in enumerate(doc.paragraphs):
            if idx in seen_idx:
                continue
            if not TitlePreprocessor._is_existing_heading(para):
                continue
            text = para.text.strip()
            if not text or len(text) > 60:
                continue
            number = TitlePreprocessor._extract_number_prefix(text)
            if number is None:
                continue
            headings.append({
                "index": idx,
                "text": text,
                "number": number,
                "detected_level": TitlePreprocessor.infer_level(number),
            })

        # 按段落索引排序，保持文档顺序
        headings.sort(key=lambda h: h["index"])
        return headings

    @staticmethod
    def _count_page_breaks_in(p_el) -> tuple:
        """统计段落元素内的分页事件，返回 (事件总数, 首个文字之前的事件数)。

        统计两类标记：① 显式分页符 w:br type="page"；
        ② Word 上次保存时的渲染分页标记 w:lastRenderedPageBreak（它标记的是
        上次 Word 打开/保存时真实分页的位置，标在新页第一个字符之前）。
        "首个文字之前的事件数"用于处理"段落恰好从新页开始"的情况：
        此时标记在段落开头，段落起始页应 +1。
        """
        total = 0
        before_text = 0
        seen_text = False
        for node in p_el.iter():
            tag = node.tag
            if tag == qn('w:t'):
                if node.text and node.text.strip():
                    seen_text = True
            elif tag == qn('w:br'):
                if node.get(qn('w:type')) == 'page':
                    total += 1
                    if not seen_text:
                        before_text += 1
            elif tag == qn('w:lastRenderedPageBreak'):
                total += 1
                if not seen_text:
                    before_text += 1
        return total, before_text

    @staticmethod
    def build_page_map(doc) -> List[int]:
        """推算每个正文段落（与 doc.paragraphs 顺序一致）的起始页码（1-based）。

        docx 格式本身不保存实时分页结果，页码只能依据文档内的分页标记推算：
        ① 显式分页符（w:br type="page"）；② Word 上次保存时的渲染分页标记
        （w:lastRenderedPageBreak）；③ "下一页"型分节符（w:sectPr 非 continuous）。
        结果与 Word 当前实际分页可能相差 1 页左右（文档保存后又被编辑过的情况），
        仅供定位参考。
        """
        page_map: List[int] = []
        page = 1
        body = doc.element.body
        for p_el in body.iter(qn('w:p')):
            total, before_text = TitlePreprocessor._count_page_breaks_in(p_el)
            # 分节符（段落 pPr 内）：非 continuous 型分节符开启新页，
            # 分节发生在该段落之后，不影响本段起始页
            pPr = p_el.find(qn('w:pPr'))
            if pPr is not None:
                sectPr = pPr.find(qn('w:sectPr'))
                if sectPr is not None:
                    sect_type = sectPr.find(qn('w:type'))
                    if sect_type is None or sect_type.get(qn('w:val')) != 'continuous':
                        total += 1
            # 只登记正文级段落（doc.paragraphs 的成员，父节点为 w:body）；
            # 表格/文本框内的段落只参与分页事件累计，不进入页码表
            if p_el.getparent() is body:
                page_map.append(page + before_text)
            page += total
        return page_map

    @staticmethod
    def check_heading_leaks(docx_file, progress_callback=None,
                            prefer_word_pages: bool = True,
                            stage_callback=None,
                            word_progress_callback=None) -> List[Dict]:
        """查漏：检查"本应是标题、却既非标题格式也无大纲级别"的编号段落。

        识别对象与 detect_headings 完全一致（同一个 _detect_headings_in，同一套
        识别规则与排除规则），区别只在于额外附带每段当前的样式说明，并标出格式异常项。

        Args:
            docx_file: docx 文件路径，或可读的文件对象（如 io.BytesIO）。
            progress_callback: 可选，**段落扫描阶段**进度回调 (done, total)。
                只用于扫描阶段，一定会推进到 (total, total)。
            prefer_word_pages: 是否优先用本机 Word 取「物理页码」（默认 True）。
                True 且环境可用时，页码为 Word 状态栏那个页号（准确）；
                否则退回按分页标记估算（文档编辑过就可能差几页）。
                两种情况在结果的 ``page_source`` 里区分：'word' / 'estimate'。
            stage_callback: 可选，阶段切换提示回调 (msg: str)。
            word_progress_callback: 可选，**Word 取页码阶段**进度回调 (done, total)。
                刻意与 progress_callback 分开：两个阶段的分母不同（段落数 vs 标题数），
                共用一个回调会让进度条在切换时倒退回 0（测试
                test_check_heading_leaks_progress_monotonic_and_complete 就是这么发现的）。

        Returns:
            List[Dict]，每个元素在 detect_headings 结果的基础上增加：
                {
                    "index": int,
                    "text": str,
                    "number": str,
                    "detected_level": int,
                    "style_name": str,          # 当前样式名，取不到时为 "无样式"
                    "is_heading_style": bool,   # 样式名是否为标题样式（Heading N / 标题 N）
                    "outline_level": int | None,# 显式大纲级别（1-9），未设置则 None
                    "is_heading": bool,         # 已是标题格式（标题样式或大纲级别任一成立）
                    "is_leak": bool,            # 格式异常：既非标题样式、也无大纲级别
                    "style_description": str,   # 当前样式说明，如 "Normal｜无大纲级别"
                    "page": int,                # 起始页码（1-based）
                    "page_source": str,         # 'word' = Word 物理页码；'estimate' = 标记估算
                }
        """
        # Word 只能打开**文件路径**，而本函数允许传入内存流（Streamlit 上传的对象）。
        # 需要精确页码时先落一份临时文件；不需要时（或流式调用）仍走原路径，零开销。
        tmp_path = None
        src = docx_file
        if prefer_word_pages and not isinstance(docx_file, (str, os.PathLike)):
            try:
                from page_locator import is_available as _word_available
                if _word_available():
                    buf = docx_file.getbuffer() if hasattr(docx_file, 'getbuffer') else docx_file.read()
                    fd, tmp_path = tempfile.mkstemp(suffix='.docx', prefix='ws_pages_')
                    with os.fdopen(fd, 'wb') as f:
                        f.write(bytes(buf))
                    src = tmp_path
            except Exception:
                tmp_path = None          # 落盘失败不影响主流程，继续用原流
                src = docx_file

        try:
            doc = Document(src)
            headings = TitlePreprocessor._detect_headings_in(
                doc, progress_callback=progress_callback)
            paragraphs = doc.paragraphs
            results = []
            for h in headings:
                idx = h["index"]
                if not 0 <= idx < len(paragraphs):
                    continue
                info = TitlePreprocessor.describe_paragraph_style(paragraphs[idx])
                item = dict(h)
                item.update(info)
                item["is_leak"] = not info["is_heading"]
                item["page"] = None
                item["page_source"] = 'estimate'
                results.append(item)

            # 顺序很重要：**先试 Word**，成功就完全跳过估算（估算本身要 15s，
            # 414 页文档实测；先算再用 Word 覆盖等于白烧 15 秒）。
            # Word 不可用 / 失败 / 有未命中的条目时，才算估算兜底。
            need_estimate = True
            if prefer_word_pages and results:
                if stage_callback is not None:
                    # Word 定位一段要 10 秒左右（414 页 / 314 条实测 12.6s），
                    # 必须让用户看到「还在干活」，否则会以为界面卡死。
                    try:
                        stage_callback("📄 正在用 Word 计算物理页码…")
                    except Exception:
                        pass
                pages = TitlePreprocessor._apply_word_pages(
                    src, results, progress_callback=word_progress_callback)
                # 全部命中 → 估算完全不需要；有缺口才补算。
                need_estimate = any(it["page"] is None for it in results)

            if need_estimate:
                page_map = TitlePreprocessor.build_page_map(doc)
                for it in results:
                    if it["page"] is None:
                        # 用 item 自己的 index，不要 zip(headings)——results 里
                        # 有被 `continue` 跳过的异常段落，两个列表并不等长。
                        idx = it.get("index")
                        if isinstance(idx, int) and 0 <= idx < len(page_map):
                            it["page"] = page_map[idx]
                            it["page_source"] = 'estimate'
            return results
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _apply_word_pages(src, results: List[Dict], progress_callback=None):
        """用 Word 的物理页码覆盖 results 里的页码（就地修改），返回 Pages 列表或 None。

        位置对应关系：results 已按文档顺序排列，locate_pages 也是单调向后查找，
        因此可以直接按序 zip，不需要段落索引（python-docx 与 Word 的段落集合
        口径不同：同一文档 python 侧 8297 段、Word 侧 8892 段，按索引对齐会错位）。
        定位不到的条目保持 page=None，由调用方用分页标记估算兜底。
        """
        try:
            from page_locator import locate_pages
        except Exception:
            return None
        pages = locate_pages(src, [str(it.get("text") or "") for it in results],
                             progress_callback=progress_callback)
        if not pages:
            return None
        for it, pg in zip(results, pages):
            if pg:
                it["page"] = pg
                it["page_source"] = 'word'
        return pages

    @staticmethod
    def describe_paragraph_style(paragraph) -> Dict:
        """描述段落当前的样式状态（供查漏功能展示"当前样式说明"）。

        Returns:
            {
                "style_name": str,          # 当前样式名，取不到时为 "无样式"
                "is_heading_style": bool,   # 样式名是否为标题样式
                "outline_level": int | None,# 显式大纲级别（1-9），未设置则 None
                "is_heading": bool,         # 标题样式或大纲级别任一成立
                "style_description": str,   # 人可读说明，如 "Normal｜无大纲级别"
            }
        """
        style_name = ''
        if paragraph.style is not None and paragraph.style.name:
            style_name = paragraph.style.name
        style_level = TitlePreprocessor._get_heading_style_level(paragraph)
        outline_level = TitlePreprocessor._get_outline_level(paragraph)
        display_name = style_name or '无样式'
        outline_text = (f'大纲级别 {outline_level}'
                        if outline_level is not None else '无大纲级别')
        return {
            "style_name": display_name,
            "is_heading_style": style_level is not None,
            "outline_level": outline_level,
            "is_heading": (style_level is not None) or (outline_level is not None),
            "style_description": f'{display_name}｜{outline_text}',
        }

    @staticmethod
    def _get_heading_style_level(paragraph) -> Optional[int]:
        """段落样式名对应的标题级别（Heading N / 标题 N）；非标题样式返回 None。"""
        if paragraph.style is not None and paragraph.style.name:
            return HEADING_STYLE_LEVELS.get(paragraph.style.name.lower())
        return None

    @staticmethod
    def _get_outline_level(paragraph) -> Optional[int]:
        """段落显式设置的大纲级别（w:outlineLvl，1-9）；未设置或非法返回 None。"""
        pPr = paragraph._p.find(qn('w:pPr'))
        if pPr is None:
            return None
        outline = pPr.find(qn('w:outlineLvl'))
        if outline is None:
            return None
        val = outline.get(qn('w:val'))
        if val is None:
            return None
        try:
            level = int(val) + 1  # outlineLvl 是 0-based
        except ValueError:
            return None
        return level if 1 <= level <= 9 else None

    @staticmethod
    def _is_existing_heading(paragraph) -> bool:
        """判断段落是否已具有标题样式（Heading N / 标题 N）或大纲级别。

        仅用于识别“已是标题”的段落，不再据此推断级别。
        """
        return (TitlePreprocessor._get_heading_style_level(paragraph) is not None
                or TitlePreprocessor._get_outline_level(paragraph) is not None)

    @staticmethod
    def _extract_number_prefix(text: str) -> Optional[str]:
        """按统一编号规则提取文本开头的数字编号；无编号返回 None。"""
        m = NUMBER_PREFIX_PATTERN.match(text)
        return m.group(1) if m else None

    @staticmethod
    def _set_outline_level(paragraph, level: int) -> None:
        """直接设置段落的大纲级别（w:outlineLvl）。"""
        pPr = paragraph._p.get_or_add_pPr()
        outline = pPr.find(qn('w:outlineLvl'))
        if outline is None:
            outline = OxmlElement('w:outlineLvl')
            pPr.append(outline)
        outline.set(qn('w:val'), str(level - 1))  # outlineLvl 是 0-based

    @staticmethod
    def _apply_heading_style(doc, paragraph, level: int) -> None:
        """将段落应用 Heading N 样式，并设置大纲级别。

        优先使用 python-docx 的样式赋值（按样式名解析 styleId）；
        若文档 styles.xml 未定义该样式，则回退到直接写 XML（pStyle + outlineLvl），
        保证 Word 打开时能识别为内置标题样式。
        """
        style_name = f"Heading {level}"
        applied = False
        try:
            paragraph.style = doc.styles[style_name]
            applied = True
        except Exception:
            applied = False

        if not applied:
            # 回退：直接写 pStyle（内置标题 styleId 为 "Heading1"、"Heading2"...）
            pPr = paragraph._p.get_or_add_pPr()
            pStyle = pPr.find(qn('w:pStyle'))
            if pStyle is None:
                pStyle = OxmlElement('w:pStyle')
                pPr.insert(0, pStyle)
            pStyle.set(qn('w:val'), f'Heading{level}')

        # 无论样式是否成功，都设置大纲级别（确保被大纲级别检测识别）
        TitlePreprocessor._set_outline_level(paragraph, level)

    @staticmethod
    def apply_headings(docx_file, output_file, selections: List[Dict], progress_callback=None) -> None:
        """将选中段落应用对应 Heading N 样式，保存为新文档。

        Args:
            docx_file: 输入 docx 路径。
            output_file: 输出 docx 路径。
            selections: List[Dict]，每个元素结构：
                {"index": int, "target_level": int}
                target_level 为 1-9；不在 selections 中的段落保持不变。
            progress_callback: 可选，每处理一个选中段落后调用
                progress_callback(done: int, total: int)。
        """
        doc = Document(docx_file)
        # 按 index 建立查找表
        sel_map = {s["index"]: s["target_level"] for s in selections if s.get("target_level", 0) >= 1}
        total = len(sel_map)
        done = 0
        for idx, para in enumerate(doc.paragraphs):
            if idx in sel_map:
                TitlePreprocessor._apply_heading_style(doc, para, sel_map[idx])
                done += 1
                if progress_callback:
                    progress_callback(done, total)
        doc.save(output_file)
        if progress_callback:
            progress_callback(total, total)

    @staticmethod
    def has_heading_styles(docx_file) -> bool:
        """判断文档是否已使用标题样式（Heading N / 标题 N / 大纲级别）。"""
        doc = Document(docx_file)
        heading_style_names = {
            'heading 1', 'heading 2', 'heading 3', 'heading 4', 'heading 5',
            'heading 6', 'heading 7', 'heading 8', 'heading 9',
            '标题 1', '标题 2', '标题 3', '标题 4', '标题 5',
            '标题 6', '标题 7', '标题 8', '标题 9',
        }
        for para in doc.paragraphs:
            if para.style and para.style.name:
                if para.style.name.lower() in heading_style_names:
                    return True
            # 检查大纲级别
            pPr = para._p.find(qn('w:pPr'))
            if pPr is not None and pPr.find(qn('w:outlineLvl')) is not None:
                return True
        return False
