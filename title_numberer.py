# -*- coding: utf-8 -*-
"""
标题编号补全引擎（T04 / 工具箱：补全标题编号）
无 Streamlit 依赖，可独立测试。

与 `title_preprocessor.py` 的分工（两者互补，不要混淆）：
    - 源文档标题预处理：编号标题（"1.1 线路"）→ 补 **标题样式/大纲级别**
    - 补全标题编号（本模块）：标题样式/大纲级别 → 补 **编号文字**（"1.1"）

职责：
1. 检测全文已具有标题样式（Heading N）或大纲级别（w:outlineLvl）的段落
2. 按标题层级结构自动生成编号 1 / 1.1 / 1.1.1（跳级时缺失层级按 1 补齐）
3. 支持统一前缀（填 "C" → C1 / C1.1 / C1.1.1）
4. 识别"文本里已经有编号"的段落（含 "★1.2 工程范围" 这类带标记符号的），默认原样保留，
   但仍占号，保证后续标题的编号连续正确
5. 把编号以**纯文本**写入段落开头（不生成 Word 多级列表 numPr），沿用首个 run 的字体格式

为什么用纯文本编号而不是 w:numPr 多级列表：
    numPr 的编号与模板的 numbering.xml 强绑定，换模板后极易错乱；而纯文本编号
    1.1 / 1.1.1 能被 `title_preprocessor.HEADING_PATTERN` 直接识别，下游
    转换时的层级推断、样式映射都能正常工作。
"""
import copy
import re
from typing import Dict, List, Optional

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from title_preprocessor import TitlePreprocessor


# 已有编号前常见的标记符号（重要条款常用 ★，其他为项目符号类）。
# 这些符号属于标题文本的一部分，补编号时**不能**被当成编号本身，也不能被覆盖。
SIGN_CHARS = '★☆▲△◆◇●○■□▪▫*※'

# 「可选标记符号 + 数字编号 + 必须跟随空白/结尾」
#
# 三个必须保留的细节：
#   1. 符号与编号之间允许空白："★ 1.2 工程范围" 与 "★1.2 工程范围" 都要命中；
#   2. 编号后必须跟空白或字符串结束 —— 否则 "1.2.3方法" 这类正文条款会被误判，
#      也会把 "2024.01" 这种小数当成编号；
#   3. 只匹配**开头**，不做全文搜索，避免把正文中间的交叉引用当成标题编号。
SIGNED_NUMBER_PATTERN = re.compile(
    r'^\s*(?:(?P<sign>[' + SIGN_CHARS + r'])\s*)?'
    r'(?P<num>\d+(?:\.\d+)*)'
    r'(?=[\s\u3000\xa0]|$)'
)

# 疑似编号但格式不规范：形如 "1.1范围"（编号紧贴中文、无分隔符）。
#
# 为什么不直接当编号保留：
#     放宽 SIGNED_NUMBER_PATTERN 让它匹配 "1.1范围"，会把 "2024.01年度"、"1.2.3方法"
#     这类正文数字一并误判成编号 —— 误判是静默的（用户看不出该加号却没加），
#     而漏判是可见的（预览里看到 "1.1 1.1范围" 会被立刻发现）。两害相权取其轻，
#     这里只做**提示**，不改变 action，由用户在预览里自行取消勾选。
SUSPECTED_NUMBER_PATTERN = re.compile(
    r'^\s*(?:[' + SIGN_CHARS + r']\s*)?\d+(?:\.\d+)+[^\s\d.]'
)

# 中文编号：投标/标书类文档大量使用「第一章」「一、」体系。
#
# 为什么必须识别（而不是当无编号处理）：
#     若不识别，"第一章 总则" 会被插入结构编号 → "1 第一章 总则"，一眼可见的重号。
#     这类编号与阿拉伯多级编号（1 / 1.1）不是同一体系，无法解析成层级数字回填计数，
#     所以只做 **keep（原样保留、仍占号）**，不尝试换算。
#
# 只收两类最典型的写法，不做通用中文数字解析：
#     - 第X章 / 第X节 / 第X部分 / 第X条 / 第X款（X 可以是中文或阿拉伯数字）
#     - X、  （一、 十一、）
# 不收「（一）」「（1）」：括号编号更多见于正文条款列表，误判收益比不划算。
CJK_NUMBER_PATTERN = re.compile(
    r'^\s*(?:'
    r'第(?P<cn1>[一二三四五六七八九十百千零〇两\d]+)(?P<unit>章|节|部分|篇|条|款)'
    r'|(?P<cn2>[一二三四五六七八九十]+)、'
    r')'
)

# 编号与标题正文之间的分隔符默认值：与源文档里 "★1.2 工程范围" 的写法一致。
DEFAULT_SEPARATOR = ' '


class TitleNumberer:
    """标题编号补全引擎（无状态工具类）。"""

    MAX_LEVEL = 9

    # ==================================================================
    # 一、检测
    # ==================================================================
    @staticmethod
    def detect(docx_file, progress_callback=None) -> List[Dict]:
        """检测全文的标题段落，并解析其级别、级别来源、是否已有编号。

        Args:
            docx_file: docx 路径，或可读文件对象（io.BytesIO）。
            progress_callback: 可选，段落扫描进度 progress_callback(done, total)。

        Returns:
            List[Dict]，按文档顺序，每项结构：
                {
                    "index": int,              # doc.paragraphs 中的位置
                    "text": str,               # 段落原文（已 strip）
                    "level": int,              # 1-9
                    "level_source": str,       # "style" | "outline"
                    "style_name": str,         # 原样式名，取不到时 "无样式"
                    "existing_number": str|None,  # 已有阿拉伯编号（如 "1.2"）；无则 None
                    "existing_sign": str|None,    # 编号前的标记符号（如 "★"）；无则 None
                    "existing_cjk_number": str|None,  # 已有中文编号（如 "第一章"、"一、"）；无则 None
                    "suspected_number": bool,  # 疑似已有编号但无分隔符（"1.1范围"），仅提示
                    "level_conflict": bool,    # 样式级别与大纲级别不一致
                    "outline_level": int|None, # 显式大纲级别（1-9）
                    "style_level": int|None,   # 样式名对应级别（1-9）
                }
        """
        return TitleNumberer._detect_in(
            Document(docx_file), progress_callback=progress_callback
        )

    @staticmethod
    def _detect_in(doc, progress_callback=None) -> List[Dict]:
        """在已打开的 Document 上执行检测（便于测试与复用，避免重复加载）。"""
        paragraphs = doc.paragraphs
        total = len(paragraphs)
        items: List[Dict] = []

        for idx, para in enumerate(paragraphs):
            if progress_callback:
                progress_callback(idx + 1, total)

            style_level = TitlePreprocessor._get_heading_style_level(para)
            outline_level = TitlePreprocessor._get_outline_level(para)
            # 既无标题样式也无大纲级别 → 不是本模块的处理对象。
            # 注意：这里**不**做"文本看起来像标题"的启发式猜测 —— 误把正文条款
            # 编上号比漏掉几个标题更难挽回，漏掉的可以在预览里人工补（后续可扩展）。
            if style_level is None and outline_level is None:
                continue

            text = para.text.strip()
            if not text:
                continue

            # 级别优先级：Heading 样式优先（它是作者的显式意图，且决定正文外观），
            # 样式缺失时才回退到 w:outlineLvl（导航窗格层级）。
            # 两者都有但不一致时记 level_conflict，在预览里标出来让用户判断。
            if style_level is not None:
                level, level_source = style_level, 'style'
            else:
                level, level_source = outline_level, 'outline'

            m = SIGNED_NUMBER_PATTERN.match(text)
            existing_number = m.group('num') if m else None
            existing_sign = (m.group('sign') if m and m.group('sign') else None)
            existing_end = m.end() if m else 0

            # 阿拉伯编号没命中时才看中文编号：两者互斥，避免 "第1章" 被拆成阿拉伯编号 1。
            existing_cjk = None
            if existing_number is None:
                cm = CJK_NUMBER_PATTERN.match(text)
                if cm:
                    existing_cjk = cm.group(0).strip()
                    existing_end = cm.end()

            # 两种编号都没识别到、但文本开头确实是 "1.1" 形态 → 疑似编号缺分隔符，仅提示
            suspected = bool(
                existing_number is None and existing_cjk is None
                and SUSPECTED_NUMBER_PATTERN.match(text)
            )

            items.append({
                'index': idx,
                'text': text,
                'level': min(level, TitleNumberer.MAX_LEVEL),
                'level_source': level_source,
                'style_name': (para.style.name if para.style and para.style.name else '无样式'),
                'existing_number': existing_number,
                'existing_sign': existing_sign,
                'existing_cjk_number': existing_cjk,
                # 原文编号前缀（含标记符号）在段落纯文本里的字符数，用于 replace 时裁剪。
                # 只对"用户改了编号"的行有值，keep 的行用不到。
                'existing_end': existing_end,
                'suspected_number': suspected,
                'level_conflict': bool(
                    style_level is not None and outline_level is not None
                    and style_level != outline_level
                ),
                'outline_level': outline_level,
                'style_level': style_level,
            })

        return items

    # ==================================================================
    # 二、编号计算
    # ==================================================================
    @staticmethod
    def _split_levels(value: str, prefix: str, level: int) -> Optional[List[int]]:
        """把 "C1.2" / "1.2" 解析成前 level 段的整数列表；解析不了返回 None。

        prefix 先剥掉再解析 —— 用户手动输入的编号可能是带前缀的 "C1.2"，
        不剥掉的话 `isdigit()` 直接失败，计数栈就不会回填。
        """
        v = value
        if prefix and v.startswith(prefix):
            v = v[len(prefix):]
        parts = v.split('.')
        if (len(parts) >= level
                and all(p.isdigit() and int(p) > 0 for p in parts[:level])):
            return [int(p) for p in parts[:level]]
        return None

    @staticmethod
    def compute_numbers(items: List[Dict],
                        prefix: str = '',
                        separator: str = DEFAULT_SEPARATOR,
                        overrides: Optional[Dict[int, str]] = None) -> List[Dict]:
        """按标题层级结构计算每个标题的最终编号与写入动作。

        规则（顺序敏感，改动前先读）：
          1. 只有 apply=True 的标题参与计数；未勾选的标题不编号、**也不占号**
             —— 这样用户取消勾选中间某个标题后，后续同级标题编号保持连续。
             **编号列被手动清空**视为同一种"不要编号"，同样不占号。
          2. 进入某一级时，把更深的级别计数清零（1.2 之后的下一个 H3 回到 1.2.1）。
          3. 跳级（H1 之后直接 H3）时，缺失层级按 1 补齐并**写回计数** → "1.1.1"。
             写回是必须的：否则紧接着出现的真正 H2 也会拿到 "1.1"，与 1.1.1 的父级撞车。
          4. **编号以"编号列的值"为准**（2026-10-22 用户要求）：
             - 默认值：原文已有阿拉伯编号 → `prefix + 原文编号`；
               原文已有中文编号 → 原文（中文体系不叠加前缀）；
               原文没有编号 → `prefix + 结构编号`。
             - 用户在 overrides 里给了值 → **直接用该值**，并把它回填计数栈，
               后续标题从它之后续号（编号必须连续，否则又会撞车）。
             - 默认值与原文编号相同 → action="keep"（一字不动，不重复写）；
               不同 → action="replace"（替换段首编号，保留 ★ 等标记符号）；
               原文本来没有编号 → action="insert"。
          5. 中文编号（第一章 / 一、）无法与阿拉伯编号换算，默认只占号不回填。
             用户在编号列把它改成 "1" → 走 replace，按阿拉伯体系写入。

        Args:
            items: detect() 的结果，每项可带 "apply"（默认 True）与 "level"（可被用户改写）。
            prefix: 统一前缀，如 "C" → "C1"、"C1.1"。
            separator: 编号与标题正文之间的分隔符，默认半角空格。
            overrides: {items 下标: 用户在"编号"列输入的文本}。键存在即视为"用户显式指定"，
                值为空串表示用户清空该行编号（不编号、不占号）。

        Returns:
            List[Dict]，与入参等长、同序，在原字段基础上增加：
                {
                    "apply": bool,
                    "number": str,          # 层级编号（不含前缀），未编号时 ""
                    "display_number": str,  # 实际写入的编号（含前缀），未编号时 ""
                    "action": str,          # "insert" / "keep" / "replace" / "skip"
                    "new_text": str,        # 写入后的完整段落文本
                    "replace_len": int,     # action=replace 时要裁掉的段首字符数
                    "replace_text": str,    # action=replace 时替换成的前缀（含符号与分隔符）
                }
        """
        counters = [0] * (TitleNumberer.MAX_LEVEL + 2)  # 下标 1..MAX_LEVEL 有效
        result: List[Dict] = []
        overrides = overrides or {}

        for pos, raw in enumerate(items):
            item = dict(raw)
            apply = bool(item.get('apply', True))
            level = int(item.get('level') or 1)
            level = max(1, min(level, TitleNumberer.MAX_LEVEL))
            item['level'] = level
            text = item.get('text', '')

            manual = pos in overrides
            manual_value = (overrides.get(pos) or '').strip()

            # 1) 不参与：取消勾选，或用户把编号清空
            if not apply or (manual and not manual_value):
                item.update({
                    'apply': False, 'number': '', 'display_number': '',
                    'action': 'skip', 'new_text': text,
                })
                result.append(item)
                continue

            # 2) 进入本级别前清空更深的计数；3) 本级别 +1
            for deeper in range(level + 1, TitleNumberer.MAX_LEVEL + 1):
                counters[deeper] = 0
            counters[level] += 1

            existing = item.get('existing_number')
            cjk = item.get('existing_cjk_number')

            # 回填前的"纯结构编号"，只用于对照提示与无编号行的实际编号。
            #
            # 跳级（H1 之后直接 H3）时该层计数仍为 0：视为 1，并**写回** counters。
            # 不写回的话，后面出现的真正 H2 还会拿到 1.1，与刚补出的 1.1.1 的父级撞车
            # （2026-10-22 实测发现）。
            struct_parts = []
            for d in range(1, level + 1):
                if counters[d] == 0:
                    counters[d] = 1
                struct_parts.append(counters[d])
            structural_number = '.'.join(str(x) for x in struct_parts)

            if manual:
                # 用户显式指定 → 以编号列为准，并回填计数保证后续连续
                display = manual_value
                number = (display[len(prefix):]
                          if prefix and display.startswith(prefix) else display)
                segs = TitleNumberer._split_levels(display, prefix, level)
                if segs:
                    for depth, val in enumerate(segs, 1):
                        counters[depth] = val
            elif existing:
                # 原文已有阿拉伯编号 → 默认沿用（前缀一并加上）
                display = f'{prefix}{existing}' if prefix else existing
                segs = TitleNumberer._split_levels(existing, '', level)
                if segs:
                    for depth, val in enumerate(segs, 1):
                        counters[depth] = val
                    # 段数多于层级时按层级截断（"1.2.3" 在 H2 上占位为 "1.2"）
                    number = '.'.join(str(x) for x in segs)
                else:
                    number = existing
            elif cjk:
                # 中文编号：不叠加前缀、不回填计数，原样占号
                display, number = cjk, ''
            else:
                number = structural_number
                display = f'{prefix}{number}' if prefix else number

            # 4) 决定动作：与原文编号相同就不写（避免重复），不同则替换
            old_display = existing or cjk
            if old_display:
                action = 'keep' if display == old_display else 'replace'
            else:
                action = 'insert'

            if action == 'keep':
                new_text = text
            elif action == 'replace':
                # 保留原文编号前的标记符号（★ 等），只换编号本身
                sign = item.get('existing_sign') or ''
                cut = item.get('existing_end') or 0
                rest = text[cut:].lstrip()
                new_prefix = f'{sign}{display}{separator}'
                new_text = f'{new_prefix}{rest}'
                item['replace_len'] = cut
                item['replace_text'] = new_prefix
            else:
                new_text = f'{display}{separator}{text}' if text else display

            item.update({
                'apply': True,
                'number': number,
                'display_number': display,
                'action': action,
                'new_text': new_text,
                # 纯结构编号（不受原文编号/手动覆盖影响），供预览对照
                'generated_number': structural_number,
                # 与结构位置不一致 → 预览里提示，便于人工核对
                # （段数多于层级也算不一致，如 H2 写 "1.2.3"）
                'number_mismatch': bool(
                    existing and not manual and structural_number != existing
                ),
                'manual_number': manual,
            })

            result.append(item)

        return result

    # ==================================================================
    # 三、写入
    # ==================================================================
    @staticmethod
    def apply(docx_file, output_file, plan: List[Dict],
              separator: str = DEFAULT_SEPARATOR, progress_callback=None) -> Dict:
        """把编号写入文档并保存。

        Args:
            docx_file: 输入 docx 路径。
            output_file: 输出 docx 路径。
            plan: compute_numbers() 的结果（使用其中的 index / action / display_number）。
            separator: 编号与标题正文之间的分隔符，必须与 compute_numbers 时一致，
                否则预览看到的文本与实际写入的不一致。
            progress_callback: 可选，每写入一项调用 progress_callback(done, total)。

        Returns:
            {"inserted": int, "kept": int, "skipped": int, "failed": int}
            统计口径：inserted=新写入编号的标题数，kept=已有编号原样保留数，
            skipped=用户取消勾选数，failed=定位不到可插入 run 而放弃的段数。
        """
        doc = Document(docx_file)
        paragraphs = doc.paragraphs
        todo = [p for p in plan if p.get('action') in ('insert', 'keep', 'replace')]
        total = len(todo)
        done = 0
        stats = {'inserted': 0, 'kept': 0, 'replaced': 0, 'skipped': 0, 'failed': 0}

        for item in plan:
            action = item.get('action')
            if action == 'skip':
                stats['skipped'] += 1
            elif action == 'keep':
                # 编号与原文一致，文字一字不动
                stats['kept'] += 1
                done += 1
                if progress_callback:
                    progress_callback(done, total)
            elif action == 'insert':
                idx = item.get('index')
                number = item.get('display_number') or ''
                if not number or idx is None or not (0 <= idx < len(paragraphs)):
                    stats['failed'] += 1
                    continue
                ok = TitleNumberer._insert_number_prefix(
                    paragraphs[idx], f'{number}{separator}'
                )
                stats['inserted' if ok else 'failed'] += 1
                done += 1
                if progress_callback:
                    progress_callback(done, total)
            elif action == 'replace':
                # 原文有编号、但用户在编号列改成了别的 → 裁掉段首旧编号再写新的
                idx = item.get('index')
                if idx is None or not (0 <= idx < len(paragraphs)):
                    stats['failed'] += 1
                    continue
                ok = TitleNumberer._replace_number_prefix(
                    paragraphs[idx],
                    int(item.get('replace_len') or 0),
                    item.get('replace_text') or '',
                )
                stats['replaced' if ok else 'failed'] += 1
                done += 1
                if progress_callback:
                    progress_callback(done, total)

        doc.save(output_file)
        if progress_callback:
            progress_callback(total, total)
        return stats

    @staticmethod
    def _first_run_element(paragraph) -> Optional[object]:
        """取段落里第一个可插入的 run 元素。

        为什么不能直接用 `paragraph.runs[0]`：
            `Paragraph.runs` 只返回 `w:p` 的**直接子级** `w:r`，被 `<w:ins>`
            （修订-插入标记）包裹的 run 完全不可见。本工程在图片修复时踩过这个坑
            （见 doc_converter.iter_paragraph_run_elements），这里做同样的展开。
        """
        p = paragraph._p
        # 1) 直接子级 w:r
        for child in p:
            if child.tag == qn('w:r'):
                return child
        # 2) w:ins 内的 w:r（修订插入的内容）
        for ins in p.findall(qn('w:ins')):
            for child in ins:
                if child.tag == qn('w:r'):
                    return child
        return None

    @staticmethod
    def _insert_number_prefix(paragraph, prefix_text: str) -> bool:
        """在段落最前面插入编号文本，沿用首个 run 的字符格式（rPr）。

        只复制 rPr、不复用整个 run：首个 run 里可能还挂着图片（w:drawing）、
        换行（w:br）、域代码（w:fldChar）等，整段复制会把它们一并复制出一份。

        Returns:
            True 表示插入成功；False 表示段落里找不到可用的 run（如空段落），
            此时**不写入**，由调用方计入 failed，避免产生"只有编号没有正文"的段落。
        """
        first = TitleNumberer._first_run_element(paragraph)
        if first is None:
            return False

        new_run = OxmlElement('w:r')
        rPr = first.find(qn('w:rPr'))
        if rPr is not None:
            new_run.append(copy.deepcopy(rPr))

        t = OxmlElement('w:t')
        t.set(qn('xml:space'), 'preserve')   # 编号后带空格，必须保留空白
        t.text = prefix_text
        new_run.append(t)

        first.addprevious(new_run)
        return True

    @staticmethod
    def _replace_number_prefix(paragraph, old_len: int, new_prefix: str) -> bool:
        """把段落开头 old_len 个字符（旧编号）替换成 new_prefix，保留其余正文与格式。

        为什么要按字符"消费"而不是按 run 删除：
            旧编号可能横跨多个 run（"★"、"1.2"、" " 常是三个独立 run），
            也可能和正文挤在同一个 run 里（"★1.2 工程范围"）。逐 run 累加字符数、
            在边界处切开，两种情况都能正确处理。

        只在 `paragraph.runs` 上操作，不用 `w:ins` 展开：
            编号文本来自 `paragraph.text`，而它只含直接子级 run —— 两者必须同源，
            否则字符数对不上，裁剪位置会偏。

        Returns:
            True 成功；False 表示 old_len 超出段落实际字符数（多半是段落结构异常），
            此时**一个字符都不动**，由调用方计入 failed。
        """
        runs = paragraph.runs
        if old_len <= 0 or not runs or not new_prefix:
            return False

        # 先校验总长度再动手：边裁边发现不够长的话，文档已经被改坏了
        if old_len > sum(len(r.text) for r in runs):
            return False

        remaining = old_len
        for run in runs:
            if remaining <= 0:
                break
            t = run.text
            if len(t) <= remaining:
                remaining -= len(t)
                run.text = ''
            else:
                run.text = t[remaining:]
                remaining = 0

        # 旧编号后面往往跟着一个空格，而 new_prefix 自带分隔符 → 去掉后续前导空白，
        # 避免出现 "1.5  工程范围" 双空格。
        for run in runs:
            if run.text:
                run.text = run.text.lstrip()
                break

        first = runs[0]._r
        new_run = OxmlElement('w:r')
        rPr = first.find(qn('w:rPr'))
        if rPr is not None:
            new_run.append(copy.deepcopy(rPr))
        t = OxmlElement('w:t')
        t.set(qn('xml:space'), 'preserve')
        t.text = new_prefix
        new_run.append(t)
        first.addprevious(new_run)
        return True
