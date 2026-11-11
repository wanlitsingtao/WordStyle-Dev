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
import logging
import re
from typing import List, Dict, Optional

from docx import Document

logger = logging.getLogger('WordStyle')
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

# 纯日期行（"2024 年 6 月"、"2024年6月30日"、"2024 年"）。
# 为什么要单独排除（2026-11-11 用户实测反馈）：`HEADING_PATTERN` 把行首数字当编号，
# "2024 年 6 月" 因此被切成「编号 2024 + 标题文字 年 6 月」——内容首字符是"年"，
# 逃过了"内容以数字/符号开头"的过滤，又因为短、无正文特征，最终被判「漏检」并
# 默认勾选转标题。日期行在任何标书里都不是标题，直接在候选阶段丢弃。
# 只认「整行就是日期」：`2024 年度财务报告` 这类仍按正常规则处理，不会误杀。
_DATE_ONLY_PATTERN = re.compile(
    r'^\s*(?:19|20)\d{2}\s*年(?:\s*\d{1,2}\s*月)?(?:\s*\d{1,2}\s*日)?\s*$')

# 文本开头数字编号：用于已具有标题样式/大纲级别的段落统一按编号推断级别（如 "1.1 线路" / "1.1线路"）。
NUMBER_PREFIX_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)*)')

# 章节标题检测："第一章" / "第1章" / "第一章 概述" 等，默认大纲级别 1。
# 捕获组 1 = 章节编号（如 "第一章"），组 2 = 标题正文。
CHAPTER_PATTERN = re.compile(r'^\s*(第[一二三四五六七八九十百\d]+章)\s*(.*)$')

# 「短句 + 编号」的判定上限（正文字符数，不含编号前缀）。
# 标书里 `3.1 综合监控系统与乘客信息系统需按照以下接口要求一览表提供有关的接口设备。`
# 这类引导句以句号结尾，但确实是节内条目；而真正的正文条款通常是一段更长的多句文字。
# 45 字是实测分界：`test/混合标题.docx` 中 5 条候选全部 ≤38 字，其余长条款均超此线。
SHORT_SENTENCE_MAX = 45

# 已有标题样式名 -> 大纲级别
HEADING_STYLE_LEVELS = {
    'heading 1': 1, 'heading 2': 2, 'heading 3': 3, 'heading 4': 4, 'heading 5': 5,
    'heading 6': 6, 'heading 7': 7, 'heading 8': 8, 'heading 9': 9,
    '标题 1': 1, '标题 2': 2, '标题 3': 3, '标题 4': 4, '标题 5': 5,
    '标题 6': 6, '标题 7': 7, '标题 8': 8, '标题 9': 9,
}


def _number_depth(number: str) -> int:
    """编号的层级深度：按「编号主体」数点号，忽略末尾的分隔标点。

    例：`3.1.1` → 3；`1.` → 1（末尾的点是 list 模板的分隔符，不是层级）；
    `（1）` → 1。识别级别与「父级前缀」判断都依赖这个口径。
    """
    core = str(number or '').strip().rstrip(' \t.．、,，)）]】')
    return (core.count('.') + 1) if core else 1


def _paragraph_style_id(paragraph) -> str:
    """段落的 pStyle 值（styleId）；没有 pStyle 时返回空串。

    为什么不用 `paragraph.style`：python-docx 每次取 style 都会在 styles.xml 上跑一次
    XPath（`DocumentPart.get_style` → `Styles._get_by_id`）。实测 3481 段文档里
    3.4k 次调用要 ~6 秒，是标题识别的主要耗时。这里只读一个 XML 属性，
    配合「styleId → 标题级别」字典即可判断是否标题样式。
    """
    pPr = paragraph._p.find(qn('w:pPr'))
    if pPr is None:
        return ''
    p_style = pPr.find(qn('w:pStyle'))
    return (p_style.get(qn('w:val')) or '') if p_style is not None else ''


def _read_outline_level(pPr_or_none) -> Optional[int]:
    """从任意 `w:pPr`（段落 / 样式 / 编号级别的 pPr）读取大纲级别（1-9）。

    只读显式声明的 `w:outlineLvl`（0-based 存储），没有则返回 None。
    抽成独立函数是为了让「段落 pPr」「样式 pPr」「编号级别 pPr」三处共用同一口径。
    """
    if pPr_or_none is None:
        return None
    outline = pPr_or_none.find(qn('w:outlineLvl'))
    if outline is None:
        return None
    val = outline.get(qn('w:val'))
    if val is None:
        return None
    try:
        level = int(val) + 1  # outlineLvl 是 0-based
    except (TypeError, ValueError):
        return None
    return level if 1 <= level <= 9 else None


class _StyleIndex:
    """一次解析 styles.xml，供逐段查询「样式名 + 标题级别 + 大纲级别」。

    为什么不逐段用 `paragraph.style`：每次都会在 styles.xml 上跑 XPath，
    3481 段实测 ~6 秒（占识别总耗时的大头）。`_detect_headings_in` 已用同款优化，
    这里把它收成一个可复用的索引，分类阶段（还要再扫两遍）不必重复解析。
    """

    def __init__(self, doc):
        self.level_by_id: Dict[str, Optional[int]] = {}
        self.name_by_id: Dict[str, str] = {}
        # 样式自身声明的大纲级别 + basedOn 继承链（2026-11-11）：
        # 「JZ标题3」这类自定义样式名字不在 HEADING_STYLE_LEVELS 里，
        # 但它自己在 styles.xml 里写了 outlineLvl，Word 大纲视图照样按标题显示。
        self._own_outline_by_id: Dict[str, Optional[int]] = {}
        self._based_on: Dict[str, str] = {}
        self._resolved_outline: Dict[str, Optional[int]] = {}
        # 编号级别链接的样式（2026-11-11）：Word 的「多级列表 → 将级别链接到样式」
        # 会在 numbering.xml 的 w:lvl 里写 w:pStyle。此时段落本身既没有 pStyle
        # 也没有 outlineLvl，但 Word 实际按该样式渲染（大纲视图可见）。
        self._num_to_abs: Dict[str, str] = {}
        self._lvl_style: Dict[tuple, str] = {}
        self._lvl_outline: Dict[tuple, int] = {}
        # 段落 → styleId 的缓存。同一段落在分类阶段会被问 4 次
        # （是否标题 / 样式名 / 级别 / 说明），每次都要读一次 pPr。
        # 键用底层 XML 元素的 id：`doc.paragraphs` 每次返回新的包装对象，
        # 用包装对象做键会一直命中不了。
        self._sid_cache: Dict[int, str] = {}
        self._outline_cache: Dict[int, Optional[int]] = {}
        self._numbering_cache: Dict[int, tuple] = {}
        try:
            for style in doc.styles.element.findall(qn('w:style')):
                sid = style.get(qn('w:styleId')) or ''
                name_el = style.find(qn('w:name'))
                name = ((name_el.get(qn('w:val')) if name_el is not None else '') or '')
                self.name_by_id[sid] = name
                self.level_by_id[sid] = HEADING_STYLE_LEVELS.get(name.lower())
                based = style.find(qn('w:basedOn'))
                self._based_on[sid] = (based.get(qn('w:val')) if based is not None else '') or ''
                pPr = style.find(qn('w:pPr'))
                self._own_outline_by_id[sid] = _read_outline_level(pPr)
        except Exception:  # 样式表异常：退化为「全部按非标题样式」处理
            self.level_by_id = {}
            self.name_by_id = {}
        try:
            numbering = doc.part.numbering_part.element
            for num in numbering.findall(qn('w:num')):
                nid = num.get(qn('w:numId')) or ''
                abs_el = num.find(qn('w:abstractNumId'))
                if abs_el is not None:
                    self._num_to_abs[nid] = abs_el.get(qn('w:val')) or ''
            for abstract in numbering.findall(qn('w:abstractNum')):
                aid = abstract.get(qn('w:abstractNumId')) or ''
                for lvl in abstract.findall(qn('w:lvl')):
                    ilvl = lvl.get(qn('w:ilvl')) or '0'
                    ps = lvl.find(qn('w:pStyle'))
                    if ps is not None and ps.get(qn('w:val')):
                        self._lvl_style[(aid, ilvl)] = ps.get(qn('w:val'))
                    # outlineLvl 可能直接挂在 w:lvl 下，也可能在 w:lvl/w:pPr 下
                    lvl_outline = _read_outline_level(lvl)
                    if lvl_outline is None:
                        lvl_outline = _read_outline_level(lvl.find(qn('w:pPr')))
                    if lvl_outline is not None:
                        self._lvl_outline[(aid, ilvl)] = lvl_outline
        except Exception:  # 无 numbering.xml / 解析异常：退化为不支持编号级联
            self._num_to_abs = {}
            self._lvl_style = {}
            self._lvl_outline = {}

    def style_id(self, paragraph) -> str:
        key = id(paragraph._p)
        cached = self._sid_cache.get(key)
        if cached is None:
            cached = _paragraph_style_id(paragraph)
            self._sid_cache[key] = cached
        return cached

    def name_of(self, paragraph) -> str:
        """样式名；未显式设置 pStyle 时返回空串（调用方自行决定兜底名）。"""
        return self.name_by_id.get(self.style_id(paragraph), '')

    def level_of(self, paragraph) -> Optional[int]:
        """样式名对应的标题级别（Heading N）；非标题样式返回 None。"""
        return self.level_by_id.get(self.style_id(paragraph))

    def outline_level(self, paragraph) -> Optional[int]:
        """段落显式设置的大纲级别（1-9）；未设置返回 None。"""
        key = id(paragraph._p)
        if key not in self._outline_cache:
            self._outline_cache[key] = TitlePreprocessor._get_outline_level(paragraph)
        return self._outline_cache[key]

    # ------------------------------------------------------------------
    # 大纲身份的完整口径（2026-11-11）
    # ------------------------------------------------------------------
    def _style_outline(self, sid: str) -> Optional[int]:
        """样式（含 basedOn 继承链）声明的大纲级别；未声明返回 None。"""
        if not sid:
            return None
        if sid in self._resolved_outline:
            return self._resolved_outline[sid]
        seen = set()
        cur = sid
        found = None
        while cur and cur not in seen:
            seen.add(cur)
            own = self._own_outline_by_id.get(cur)
            if own is not None:
                found = own
                break
            cur = self._based_on.get(cur, '')
        self._resolved_outline[sid] = found
        return found

    def _numbering_info(self, paragraph) -> tuple:
        """段落 numPr → (编号级别链接的样式ID, 编号级别自带的大纲级别)。

        为什么需要：Word 的多级列表可以把某个级别「链接到样式」（numbering.xml 的
        `w:lvl/w:pStyle`）。此时**段落本身既没有 pStyle 也没有 outlineLvl**，但 Word
        按链接样式渲染，大纲视图里能看到 —— 深圳地铁招标文件的 `5.3.1 总体要求`
        就是这种情况（numId=2/ilvl=2 → JZ3 → 大纲级别 3），旧实现判成了「漏检」。
        """
        key = id(paragraph._p)
        cached = self._numbering_cache.get(key)
        if cached is not None:
            return cached
        result = ('', None)
        try:
            pPr = paragraph._p.find(qn('w:pPr'))
            numPr = pPr.find(qn('w:numPr')) if pPr is not None else None
            if numPr is not None:
                nid_el = numPr.find(qn('w:numId'))
                ilvl_el = numPr.find(qn('w:ilvl'))
                nid = nid_el.get(qn('w:val')) if nid_el is not None else ''
                ilvl = ilvl_el.get(qn('w:val')) if ilvl_el is not None else '0'
                aid = self._num_to_abs.get(nid or '', '')
                if aid:
                    result = (self._lvl_style.get((aid, ilvl or '0'), ''),
                              self._lvl_outline.get((aid, ilvl or '0')))
        except Exception:
            result = ('', None)
        self._numbering_cache[key] = result
        return result

    def numbering_style_id(self, paragraph) -> str:
        """编号级别链接的样式ID（没有则空串）。"""
        return self._numbering_info(paragraph)[0]

    def numbering_level(self, paragraph) -> Optional[int]:
        """由编号级联得到的标题级别（链接样式的大纲/标题级别，或级别自带 outlineLvl）。"""
        sid, lvl_outline = self._numbering_info(paragraph)
        if lvl_outline is not None:
            return lvl_outline
        if not sid:
            return None
        return self.level_by_id.get(sid) or self._style_outline(sid)

    def effective_style_level(self, paragraph) -> Optional[int]:
        """段落当前**实际生效**的标题样式级别（直接样式 ∪ 编号级联样式）。"""
        return self.level_of(paragraph) or self.numbering_level(paragraph)

    def effective_outline_level(self, paragraph) -> Optional[int]:
        """段落当前**实际生效**的大纲级别（显式 ∪ 编号级联）。"""
        explicit = self.outline_level(paragraph)
        if explicit is not None:
            return explicit
        _, lvl_outline = self._numbering_info(paragraph)
        if lvl_outline is not None:
            return lvl_outline
        return self._style_outline(self.style_id(paragraph)) \
            or self._style_outline(self.numbering_style_id(paragraph))

    def effective_name_of(self, paragraph) -> str:
        """展示用样式名；编号级联时补注来源，避免界面显示「无样式」误导用户。"""
        name = self.name_of(paragraph)
        if name:
            return name
        nsid = self.numbering_style_id(paragraph)
        if nsid:
            return f"{self.name_by_id.get(nsid, nsid)}（编号级联）"
        return ''

    def is_heading(self, paragraph) -> bool:
        """已是标题格式：直接标题样式 / 显式大纲级别 / 编号级联样式 任一成立。"""
        return (self.level_of(paragraph) is not None
                or self.outline_level(paragraph) is not None
                or self.numbering_level(paragraph) is not None)

    def description(self, paragraph) -> str:
        """人可读的样式说明，如 "Heading 2｜大纲级别 2"。"""
        name = self.effective_name_of(paragraph) or '无样式'
        level = self.effective_outline_level(paragraph)
        return f"{name}｜" + (f"大纲级别 {level}" if level is not None else "无大纲级别")


# ---------------------------------------------------------------------------
# 分类（2026-11-10：合并「标题查漏」与「标题预处理」；2026-11-11 增加第五类）
# ---------------------------------------------------------------------------
# 引擎不再"只输出要处理的条目"，而是把**全部**候选分类；处理动作交给用户，
# 引擎只给建议。这样「尽量多识别、不遗漏」与「不擅自改动」可以同时成立。
CATEGORY_MISSING = 'missing'      # 漏检：应为标题，当前不是标题格式，文本也像标题
CATEGORY_NORMAL = 'normal'        # 正常标题：已是标题格式、文本也像标题
CATEGORY_MISUSE = 'misuse'        # 误套：是标题格式，但语义是正文 → 建议降级
CATEGORY_SUSPECT = 'suspect'      # 疑似条款（2026-11-11 新增）：带标题编号、无标题
                                  # 样式也无大纲级别，文本又超过标题合理长度 ——
                                  # 说不准是标题还是正文，交给用户逐条确认
CATEGORY_BODY = 'body'            # 正文条款：带编号、且有明确正文特征（冒号/句末
                                  # 标点/整句/超 300 字）→ 建议保持不动

CATEGORY_ORDER = [CATEGORY_MISSING, CATEGORY_NORMAL, CATEGORY_MISUSE,
                  CATEGORY_SUSPECT, CATEGORY_BODY]

CATEGORY_LABELS = {
    CATEGORY_MISSING: '漏检',
    CATEGORY_NORMAL: '正常标题',
    CATEGORY_MISUSE: '误套',
    CATEGORY_SUSPECT: '疑似条款',
    CATEGORY_BODY: '正文条款',
}

ACTION_HEADING = 'heading'   # 转标题（套 Heading N + 关自动编号 + 写编号）
ACTION_KEEP = 'keep'         # 保持不动
ACTION_DEMOTE = 'demote'     # 降为正文（换正文样式 + 删大纲级别，保留自动编号）

ACTION_LABELS = {
    ACTION_HEADING: '转标题',
    ACTION_KEEP: '保持不动',
    ACTION_DEMOTE: '降为正文',
}

# 正文特征动词：判定"已被套上标题样式、但语义是正文"的辅助证据（只作加分项，
# 不单独决定分类，避免把「投标人须知」这类真标题误降级）。
BODY_VERB_PATTERN = re.compile(
    r'(应|须|不得|不应|投标人|招标人|卖方|买方|甲方|乙方|承包商|供应商|'
    r'按照|根据|负责|确保|提供|承诺|采用|满足|符合|提交|出具)'
)


def _looks_like_body(text: str) -> bool:
    """粗判一段文字更像正文而不是标题（只用于「已经套了标题样式」的段落）。

    为什么只对已套标题样式的段落用：对普通正文用这个判据会把大量带编号的
    小标题也算成正文（`2.1.1 …如图 2-1 所示。` 就是完整的句子）。这里的
    用途是找出"排版时把一句正文误设成 Heading"的段落，前提是它**已经**是标题格式。

    判据（2026-11-10 扩充，均来自用户实测反馈）：
        1) 以句号/分号结尾 —— 标题极少带句末标点；
        2) **句子中间出现「。」** —— 标题不会在一句话中间结束。原实现只查结尾，
           导致 `系统所需…正版软件，并提供相应授权文件。同时，卖方应`
           这类「一句话被拆成多个段落、首段套了 Heading」的条目被判成正常标题；
        3) **含逗号分句 + 义务动词** —— 真实标题极少写成含逗号的完整句。
           原实现要求 ≥60 字才看动词，`投标人应根据本工程接口说明，结合…，对中心级`
           （38 字）正好卡在门槛下被漏判；
        4) 长度 ≥ 60 且含义务动词（应/须/投标人/负责…）。
    """
    t = (text or '').strip()
    if not t:
        return False
    if t[-1] in '。；':
        return True
    if '。' in t[:-1] and len(t) >= 20:
        return True
    if '，' in t and len(t) >= 20 and BODY_VERB_PATTERN.search(t):
        return True
    if len(t) >= 60 and BODY_VERB_PATTERN.search(t):
        return True
    return False


def _body_clause_reason(content: str, text: str = '') -> Optional[str]:
    """「编号 + 正文条款」的统一判据，返回原因文案；不像正文则返回 None。

    为什么单独抽出来（2026-11-11 用户实测反馈）：识别阶段对三级以上编号放宽到
    300 字、且不排除冒号（为了"尽量多识别"），于是 `1.1.1招标人：见投标须知前
    附表。` 这类纯正文条款也会进候选。合并分类后，第一阶段只按「有没有标题格式」
    一刀切，把这些候选全部打成「漏检」（且默认勾选），深圳地铁那份文件一次冒出
    677 条误判。这里把「正文条款」的判据收成一处，识别/分类两阶段共用同一口径。

    判据（与原来第二阶段 body 分支完全一致，只是提前到第一阶段）：
        1) 含冒号 —— 多为定义、缩略语、参数说明；
        2) 句末标点结尾且超过一句话长度 —— 完整条文，不是标题；
        3) `_looks_like_body` 命中 —— 句号/分号结尾，或含逗号分句 + 义务动词。
    """
    c = (content or '').strip()
    t = (text or '').strip()
    if not c:
        return None
    if '：' in c or ':' in c:
        return '含冒号，多为定义/缩略语列表'
    if c[-1:] in '。；' and len(c) > SHORT_SENTENCE_MAX:
        return '句子结尾的正文，不是标题'
    if _looks_like_body(c):
        return '内容是完整句子，不像标题'
    if len(t) > 300:
        return '超过 300 字'
    return None


def _is_title_numbered(number: str) -> bool:
    """是否带「标题式编号」——多级编号（`5.1.11.2.2`、`3.1`）。

    单级列表编号（`1)`、`（1）`、`1.`）是正文枚举，不算标题编号。

    为什么单独抽出来（用户 2026-11-11 纠正）：「疑似条款」与「正文条款」的
    最大区别就是**有没有标题编号**。编号形态像标题（`5.1.11.2.2`）的条目，
    哪怕内容读起来是条文，也可能是"漏了标题格式的标题"，必须单独列出来让
    用户确认；不能直接埋进「正文条款」里，否则用户永远看不到这批候选。
    """
    return _number_depth(number) >= 2


def _is_list_marker_number(number: str) -> bool:
    """是否单级列表编号（`2.`、`1）`、`（1）`、`4)`、`第五章`）。

    与 `1`（章节号，`1 概述`）区分开：章节号后面没有分隔符，形态仍像标题；
    带分隔符的是正文枚举项，本来就不是标题候选。
    """
    n = str(number or '').strip()
    if not n:
        return False
    if n[0] in '（([' or n.startswith('第'):
        return True
    return n[-1] in '.．、)）]】'


def _classify_non_heading(content: str, text: str, number: str):
    """无标题格式（无标题样式、无显式/级联大纲级别）候选的统一归类。

    返回 `(category, confidence, reasons)`。识别/分类两阶段共用，
    避免两处判据分叉（2026-11-11 之前的教训：一处分歧就出现大批误判）。

    判定顺序：

    1. **带标题编号**（多级）且（文本超过 45 字 或 有正文特征）→ 疑似条款
       编号像标题、却没有标题身份，还可能是整段条文 —— 既不能默认转标题，
       也不能埋进正文条款，交给用户逐条确认，默认保持不动。
    2. **不带标题编号**（单级枚举 / 无编号）且（有正文特征 或 文本过长）
       → 正文条款。`1) 2) 3)` 这种是正文枚举，本来就不是标题候选。
    3. 其余（短、形态像标题）→ 漏检（默认勾选转标题）。

    注意：这只是**逐条**判据。返回「漏检」的条目还会经过
    `_inherit_suspect_from_prev_sibling()`（2026-11-11 第二轮）做一次上下文
    校验：同父级编号连续、上一条是疑似条款时改判疑似条款。所以调用方不要
    假设「本函数返回 missing 就一定是漏检」。
    """
    c = (content or '').strip()
    t = (text or '').strip()
    body_reason = _body_clause_reason(c, t)
    too_long = len(c) > SHORT_SENTENCE_MAX

    if _is_title_numbered(number):
        if too_long or body_reason:
            reasons = ['带标题编号但没有标题格式（无标题样式、无大纲级别）']
            if body_reason:
                reasons.append('内容是正文：' + body_reason)
            if too_long:
                reasons.append(f'文本超过 {SHORT_SENTENCE_MAX} 字，不像典型标题')
            reasons.append('说不准是标题还是正文，建议保持不动、人工确认')
            return CATEGORY_SUSPECT, 'medium', reasons
        return CATEGORY_MISSING, 'high', [
            '当前不是标题格式，Word 大纲视图里看不到',
            '多级编号，挂在标题编号链上',
        ]

    # 不带标题编号的分支：
    #  · `2.`、`1）`、`（1）` 这类**列表编号**是正文枚举，即使文本很短也不是标题
    #    候选（旧实现一律归正文条款，这里保持同样的保守口径，避免把
    #    `4) 气体灭火系统` 当漏检、默认勾选转标题）；
    #  · `1 概述` 这种**章节号**（无分隔符）仍是标题形态，短文本判漏检。
    if body_reason or too_long or _is_list_marker_number(number):
        reason = body_reason or (f'单级列表编号，正文枚举'
                                 if _is_list_marker_number(number)
                                 else f'没有标题编号，文本超过 {SHORT_SENTENCE_MAX} 字，按正文处理')
        return CATEGORY_BODY, 'medium', [reason]
    return CATEGORY_MISSING, 'high', ['当前不是标题格式，Word 大纲视图里看不到']


# 纯数字多级编号（`6.2.6`、`5.1.11.2.2`），用于拆「父编号 + 末段序号」。
_DOTTED_NUMBER_PATTERN = re.compile(r'^\s*(\d+(?:[.．]\d+)*)\s*$')


def _number_sibling_key(number: str):
    """把 `6.2.6` 拆成 `('6.2', 6)`：父编号 + 末段序号。拆不出返回 `(None, None)`。

    为什么需要（用户 2026-11-11 实测反馈第二轮）：
        `6.2.6 开标审查` 只有 4 个字、无句末标点，单看文本确实像标题，于是被判
        「漏检」并默认勾选「转标题」。但它夹在 `6.2.1`~`6.2.11` 一整串开标条款
        中间，前后各条都是整句条文（`6.2.5` 已判「疑似条款」）——同一父级下连续
        编号的相邻条目属于同一组条款，不能因为其中一条恰好很短就单独当成标题。

    只认纯数字编号：`（1）`、`第X章`、`附录A` 这类拆不出序号，一律不参与上下文
    推断（宁可不动，也不能凭猜测改分类）。
    """
    # 与 `_number_depth()` 同口径：先去掉末尾的分隔标点（`6.2.6.` 也算 `6.2.6`）
    raw = str(number or '').strip().rstrip(' \t.．、,，)）]】')
    m = _DOTTED_NUMBER_PATTERN.match(raw)
    if not m:
        return None, None
    parts = [p for p in re.split(r'[.．]', m.group(1)) if p != '']
    if len(parts) < 2:   # 至少 `6.2` 才有「父编号 6 + 序号 2」；单级 `6` 不参与
        return None, None
    parent = '.'.join(parts[:-1])
    try:
        return parent, int(parts[-1])
    except ValueError:
        return None, None


def _inherit_suspect_from_prev_sibling(items: List[Dict]) -> List[int]:
    """同父级连续编号：上一条为疑似条款时，紧随其后的短条目也判疑似条款。

    用户 2026-11-11 的规则原话：「同级别连续编号，上一条为疑似条款，当前也建议
    判断成疑似条款」。落地为**只在同时满足下列条件时**改判，其余一概不动：

        1. 当前条目原本是「漏检」（短、形态像标题、无正文特征）；
        2. 当前带多级标题编号（`6.2.6`）；
        3. 同一父编号（`6.2`）下**上一条**已收录候选是「疑似条款」；
        4. 两者末段序号连续（`6` = `5` + 1）。

    只做「漏检 → 疑似条款」单向改判：不碰正常标题/误套/正文条款，也不反向把
    前面的短条目追认成疑似条款（用户没提，且反向推断没有「已确认的条文」作锚点）。

    链式传递：改判后的条目会成为下一条的「上一条」，因此一整段连续的条款列表
    只要开头有一条被确认为疑似条款，后面同样形态的短条目会跟着归入同类——这正是
    「同组条款」的语义。

    返回被改判的 index 列表（供测试与日志断言）。
    """
    last_by_parent: Dict[str, Dict] = {}
    changed: List[int] = []
    for it in items:
        number = it.get('number') or ''
        parent, seq = _number_sibling_key(number)
        if parent is None:
            continue
        prev = last_by_parent.get(parent)
        last_by_parent[parent] = it
        if (it.get('category') != CATEGORY_MISSING
                or not _is_title_numbered(number)
                or prev is None
                or prev.get('category') != CATEGORY_SUSPECT):
            continue
        prev_seq = _number_sibling_key(prev.get('number') or '')[1]
        if prev_seq is None or seq != prev_seq + 1:
            continue
        it['category'] = CATEGORY_SUSPECT
        it['suggestion'] = ACTION_KEEP
        it['confidence'] = 'medium'
        # 整组覆盖而不是追加：原「漏检」的依据（`当前不是标题格式…`）会让人误以为
        # 这条仍需转标题，留着与最终建议矛盾。
        it['reasons'] = [
            '带标题编号但没有标题格式（无标题样式、无大纲级别）',
            f'同一父级编号（{parent}）的上一条（{prev.get("number")}）是疑似条款',
            '编号连续、同组条款，本条的短文本不单独按标题处理，建议保持不动、人工确认',
        ]
        changed.append(it['index'])
    return changed


class _AutoNumberingResolver:
    """按文档顺序还原 Word 自动编号（`w:numPr`）的可见编号文本。

    为什么必须做（2026-11-10 用户反馈）：
        很多标书用「一个多级列表」给全篇编号 —— 一、二级套 Heading 样式，
        三、四级却用「列出段落」（List Paragraph）样式。这些段落的编号来自
        `numbering.xml`，`paragraph.text` 里**不含任何编号字符**，所以按文本
        正则识别必然漏掉（例：`3.1.1 调度指挥中心云平台概况` 的 text 只有
        「调度指挥中心云平台概况」）。这里按 Word 的计数规则逐段推进，
        还原出 `3.1.1` 这样的编号，供识别与「查漏」展示使用。

    实现范围（够用即止，不做完整 OOXML 编号引擎）：
        - `w:num` → `w:abstractNumId` 映射
        - 每级 `w:start` / `w:numFmt` / `w:lvlText`
        - `w:lvlOverride/w:startOverride`（列表重启）
        - `bullet` / `none` 视为「无编号」——项目符号列表项不是标题
    不支持（对本功能无影响）：
        - 只认段落**显式**的 `numPr`，不追溯段落样式里继承的编号
        - 表格内段落不推进计数器

    注意：必须对**每一个**段落调用 `number_of()`（包括空段落），否则计数器
    会与 Word 的显示错位 —— 调用方在 `_detect_headings_in` 里一次性预扫。
    """

    _MAX_LEVELS = 9

    def __init__(self, doc):
        self._counters: Dict[str, List[Optional[int]]] = {}
        self._num_to_abs: Dict[str, str] = {}
        self._abs_levels: Dict[str, Dict[int, Dict]] = {}
        self._overrides: Dict[str, Dict[int, int]] = {}
        self._parse(doc)

    @staticmethod
    def _val(el) -> Optional[str]:
        return el.get(qn('w:val')) if el is not None else None

    def _parse(self, doc) -> None:
        try:
            numbering = doc.part.numbering_part.element
        except Exception:
            return  # 文档没有 numbering.xml（无自动编号）

        for num in numbering.findall(qn('w:num')):
            num_id = num.get(qn('w:numId'))
            abs_id = self._val(num.find(qn('w:abstractNumId')))
            if not num_id or abs_id is None:
                continue
            self._num_to_abs[num_id] = abs_id
            overrides = {}
            for lo in num.findall(qn('w:lvlOverride')):
                try:
                    ilvl = int(lo.get(qn('w:ilvl')))
                except (TypeError, ValueError):
                    continue
                start = self._val(lo.find(qn('w:startOverride')))
                if start is not None:
                    try:
                        overrides[ilvl] = int(start)
                    except ValueError:
                        pass
            if overrides:
                self._overrides[num_id] = overrides

        for abstract in numbering.findall(qn('w:abstractNum')):
            abs_id = abstract.get(qn('w:abstractNumId'))
            levels = {}
            for lvl in abstract.findall(qn('w:lvl')):
                try:
                    ilvl = int(lvl.get(qn('w:ilvl')))
                except (TypeError, ValueError):
                    continue
                start = self._val(lvl.find(qn('w:start')))
                levels[ilvl] = {
                    'start': int(start) if (start or '').lstrip('-').isdigit() else 1,
                    'fmt': self._val(lvl.find(qn('w:numFmt'))) or 'decimal',
                    'text': self._val(lvl.find(qn('w:lvlText'))) or '',
                }
            self._abs_levels[abs_id] = levels

    @staticmethod
    def _level_value(counters, levels, index: int) -> int:
        value = counters[index] if 0 <= index < len(counters) else None
        if value is None:
            value = levels.get(index, {}).get('start', 1)
        return value

    def number_of(self, paragraph) -> Optional[Dict]:
        """返回该段落的自动编号信息；无编号 / 项目符号 / 编号为 0 时返回 None。

        Returns:
            {"number": "3.1.1", "depth": 3, "ilvl": 2, "num_id": "1"}
        """
        pPr = paragraph._p.find(qn('w:pPr'))
        if pPr is None:
            return None
        numPr = pPr.find(qn('w:numPr'))
        if numPr is None:
            return None
        num_id = self._val(numPr.find(qn('w:numId')))
        if not num_id or num_id == '0':
            return None
        try:
            ilvl_el = numPr.find(qn('w:ilvl'))
            ilvl = int(ilvl_el.get(qn('w:val'))) if ilvl_el is not None else 0
        except (TypeError, ValueError):
            ilvl = 0

        levels = self._abs_levels.get(self._num_to_abs.get(num_id, ''), {})
        level = levels.get(ilvl)
        if not level or level['fmt'] in ('bullet', 'none'):
            return None

        counters = self._counters.setdefault(num_id, [None] * self._MAX_LEVELS)
        if counters[ilvl] is None:
            counters[ilvl] = self._overrides.get(num_id, {}).get(ilvl, level['start'])
        else:
            counters[ilvl] += 1
        for deeper in range(ilvl + 1, self._MAX_LEVELS):
            counters[deeper] = None

        template = level['text'] or ('%' + str(ilvl + 1))
        number = re.sub(
            r'%([1-9])',
            lambda m: str(self._level_value(counters, levels, int(m.group(1)) - 1)),
            template,
        )
        number = number.strip()
        if not number:
            return None
        # 层级要按「编号主体」算：`%1.` 这种模板会得到 "1."，末尾的点是分隔符、
        # 不是层级（否则 "1." 会被当成两级，列表项就混进标题了）。
        return {
            'number': number,
            'depth': _number_depth(number),
            'ilvl': ilvl,
            'num_id': num_id,
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
        depth = _number_depth(number_part)
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
                    "text": str,              # 段落原文（含编号）
                    "number": str,            # 编号部分（如 "1.1.1"）
                    "content": str,           # 剥离编号后的标题正文
                    "detected_level": int,    # 自动推断的级别（1-9）
                }
        """
        return TitlePreprocessor._detect_headings_in(
            Document(docx_file), progress_callback=progress_callback
        )

    @staticmethod
    def _detect_headings_in(doc, progress_callback=None) -> List[Dict]:
        """在已打开的 Document 上执行标题候选识别（classify_headings 内部第一遍扫描）。

        识别规则、判断分支与顺序与 detect_headings 完全一致，仅把"加载文档"与"识别"拆开：
        分类功能必须与预处理共用同一套识别逻辑，否则两处各写一份会产生口径分歧。

        Args:
            progress_callback: 可选，段落扫描进度回调 progress_callback(done: int, total: int)。
                仅在识别前对全部段落做一次扫描时按比例推进（用于查漏/预处理的进度条），
                不影响识别结果。
        """
        # [2026-11-10] 先按文档顺序还原全部段落的自动编号（含空段，否则计数会错位）。
        # 为什么必须先跑：`paragraph.text` 不含自动编号字符，下面所有基于文本正则的
        # 判断都看不到 "3.1.1"；只有这里算出编号，才能识别「列出段落」样式的标题。
        resolver = _AutoNumberingResolver(doc)
        # 段落列表与纯文本各取一次：`Paragraph.text` 每次都会在 w:p 上跑 xpath 取 runs，
        # 本函数要扫四遍（候选 / 章节 / 标题样式 / 自动编号），不缓存的话
        # 3481 段的文档光读文本就要 4~5 秒（实测）。
        paragraphs = doc.paragraphs
        texts = [p.text for p in paragraphs]
        auto_info: Dict[int, Dict] = {}
        for _i, _p in enumerate(paragraphs):
            _info = resolver.number_of(_p)
            if _info:
                auto_info[_i] = _info

        candidates = []
        total_paras = len(paragraphs)
        # 同一 (numId, ilvl) 的编号段落计数。用来判断「这组编号是不是结构化的条目序列」：
        # 标书里常见一个 numId 从 3 起编号（start=3）却不写 ilvl=0 段落 —— 此时父级
        # 编号 `3` 在本篇根本不存在，但 3.1/3.2/3.3 显然是小节标题。只看父级会整组漏检。
        seq_counts: Dict[tuple, int] = {}
        for _info in auto_info.values():
            _key = (_info.get("num_id"), _info.get("ilvl"))
            seq_counts[_key] = seq_counts.get(_key, 0) + 1
        for idx, para in enumerate(paragraphs):
            if progress_callback:
                progress_callback(idx + 1, total_paras)
            # 用原始文本匹配（不 strip），以便区分"单列标题"与"多列表格行/列表项"。
            raw_text = texts[idx]
            if not raw_text.strip():
                continue
            # 软回车合并段（标题行与正文被 w:br 软回车合并在同一段，如
            # "4.5.3.1 分供范围与备案\n卖方可将…"）：只取首行做标题匹配，
            # 首行即标题行，正文行不参与编号判断（2026-10-27）。
            first_line = raw_text.split('\n', 1)[0] if '\n' in raw_text else raw_text
            # 纯日期行（"2024 年 6 月"）不是标题候选：行首年份会被当成编号，
            # 详见 _DATE_ONLY_PATTERN 的说明。识别/分类两阶段都从这里过，只需拦一次。
            if _DATE_ONLY_PATTERN.match(first_line):
                continue
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
            # 句末标点：标题通常不带，但标书里「短编号 + 一句话」常是条目的引导句，
            # 后面紧跟一张接口/参数表（例：`3.1 综合监控系统与乘客信息系统需按照
            # 以下接口要求一览表提供有关的接口设备。`）。这类段落在 Word 大纲里
            # 不显示，却是实打实的节内条目，用户要求一并识别（2026-11-10）。
            # 因此只在超出一句话长度时才按正文条款排除；三级以上编号不受此限。
            if not deep_number and (content.endswith('。') or content.endswith('；')) \
                    and len(content) > SHORT_SENTENCE_MAX:
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
                    # 剥离编号后的标题正文：界面用它做「新标题」，
                    # 改写编号时也只动前缀、不碰这段正文（2026-11-06）。
                    "content": c["content"],
                    "detected_level": c["detected_level"],
                })

        # 章节标题（"第一章" / "第1章"）检测：默认大纲级别 1。
        for idx, para in enumerate(paragraphs):
            raw_text = texts[idx]
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
                "content": content,
                "detected_level": 1,
            })

        # 「是否为标题样式」在下面几个分支里会反复用到（样式分支 + 自动编号分支 +
        # 分组统计），缓存一次，避免同一段落重复解析 pPr/style。
        # [2026-11-11] 改用 _StyleIndex：除直接标题样式 / 显式大纲级别外，
        # 还要认「编号级别链接的标题样式」（numbering.xml 的 w:lvl/w:pStyle）。
        # 否则 `5.3.1 总体要求`（numId=2/ilvl=2 → JZ3，段落无 pStyle/outlineLvl）
        # 在识别阶段就被当成普通正文，后续只能被判「漏检」。
        _style_index = _StyleIndex(doc)

        def _style_level_of(para) -> Optional[int]:
            return _style_index.effective_style_level(para)

        def _is_heading_style(idx: int, para) -> bool:
            return _style_index.is_heading(para)

        # 同一自动编号组 (numId, ilvl) 内「标题样式 / 正文样式」各多少条。
        # 用于识别「正文枚举列表里个别行被误套标题样式」的情况（见下方排除判据）。
        style_groups: Dict[tuple, list] = {}
        for _i, _p in enumerate(paragraphs):
            _a = auto_info.get(_i)
            if not _a:
                continue
            _g = style_groups.setdefault((_a.get("num_id"), _a.get("ilvl")), [0, 0])
            _g[0 if _is_heading_style(_i, _p) else 1] += 1

        # 已有标题样式 / 大纲级别的段落：也纳入识别范围，但级别统一按编号规则推断，
        # 不再依据样式名 / outlineLvl 推断级别（真正的标题定级在文档格式转换阶段完成）。
        seen_idx = {h["index"] for h in headings}
        for idx, para in enumerate(paragraphs):
            if idx in seen_idx:
                continue
            if not _is_heading_style(idx, para):
                continue
            text = texts[idx].strip()
            if not text or len(text) > 60:
                continue
            number = TitlePreprocessor._extract_number_prefix(text)
            auto = auto_info.get(idx)
            if number is None:
                # [2026-11-10] 自动编号段落：正文里没有编号字符，用 numbering.xml
                # 还原出来的编号补上（例：Heading 2「调度指挥中心云平台概述」= 3.1）。
                if not auto:
                    continue
                number = auto["number"]
                content = text
                display_text = f"{number} {text}"
            else:
                content = text[len(number):].lstrip(' \t\u3000\xa0.、．')
                display_text = text
            # [2026-11-10] 排除「正文枚举列表里误套标题样式的行」（用户 2026-11-10 反馈）。
            # 例：`4) 所有操作系统软件及应用软件均应为正版软件。` —— 它夹在 1)~9) 的
            # 正文要求列表里，前后兄弟都是「列出段落」，只有这一行被误设成 Heading 3。
            # 它在 Word 大纲视图里确实会出现（所以用户会问"已经是标题格式了"），但语义
            # 是正文；若按标题处理，会把一句要求抬进目录。
            # 三条同时成立才排除（宁可少收，不可把条款抬成标题）：
            #   ① 编号是单级列表项（`4)`、`1）`、`a.`），不是 `3.1` 这种多级编号；
            #   ② 同 (numId, ilvl) 组内正文段落 ≥3 条，且**多于**标题段落
            #      （说明这组本质是正文枚举，标题样式只是偶发）；
            #   ③ 文本以句号/分号结尾（标题极少带句末标点）。
            if auto:
                grp = style_groups.get((auto.get("num_id"), auto.get("ilvl")), [0, 0])
                if (_number_depth(auto["number"]) == 1
                        and grp[1] >= 3 and grp[1] > grp[0]
                        and text[-1] in '。；'):
                    continue
            headings.append({
                "index": idx,
                "text": display_text,
                "number": number,
                "content": content,
                # [2026-11-10] 有标题样式时以样式级别为准：Word 的大纲视图就是按
                # 样式 / outlineLvl 显示的，例如 "4)" 这种编号形态推不出层级，
                # 但它是 Heading 3，就该是 H3（改前会算成 H1）。
                # 没有样式时才退回按编号深度推断。
                "detected_level": (_style_level_of(para)
                                   or TitlePreprocessor.infer_level(number)),
            })

        # [2026-11-10] 自动编号的「列出段落」标题（用户 2026-11-10 反馈）：
        # 样式不是 Heading，但处在本篇的标题编号链上，Word 大纲视图里看不到。
        # 例：`3.1.1 调度指挥中心云平台概况` 用的是「列出段落」，父级 3.1 是 Heading 2。
        #
        # 判据刻意保守，避免把正文列表项（"投标人应…"）误判成标题：
        #   1) 深度不超过「已识别标题的最大深度 + 1」—— 再深基本是正文条款；
        #   2) 该编号要么挂在已识别标题的编号下，要么属于同一 numId 的结构化编号序列；
        #   3) 短文本、不以句末标点结尾、不含冒号（冒号多为定义/缩略语列表）。
        title_numbers = {h["number"] for h in headings if h.get("number")}
        max_depth = max((_number_depth(h["number"]) for h in headings), default=0) or 3
        seen_idx = {h["index"] for h in headings}
        for idx, para in enumerate(paragraphs):
            if idx in seen_idx:
                continue
            auto = auto_info.get(idx)
            if not auto:
                continue
            if _is_heading_style(idx, para):
                continue  # 标题样式段落已在上一段处理（含无编号的自动编号标题）
            text = texts[idx].strip()
            # 长度口径与文本路径对齐（2026-11-10）：同一个编号形态不能两套标准。
            # 文本路径三级及以上编号（4.5.2.1）早就放宽到 300 字，自动编号路径
            # 却卡 60 字 —— `2.1.1 综合监控系统与乘客信息系统的接口位置…（61 字）`
            # 就是这样被一票否决的。现在按同一口径：深级 300 字，一/二级 60 字。
            _auto_depth = auto["depth"]
            if not text or len(text) > (300 if _auto_depth >= 3 else 60):
                continue
            _seq_size = seq_counts.get((auto.get("num_id"), auto.get("ilvl")), 0)
            if text[0] in '0123456789±><≥≤~～＋－':
                # 数值/表格行特征（"1294.53～"、">10P 250"）。但设备名也常以数字开头
                # （"6W 扬声器（车站）"、"65 寸 LCD 显示屏"）：同组编号已成序列时放行，
                # 否则整组设备清单里的数字开头条目会单独消失。
                if _seq_size < 2:
                    continue
            # 句末的逗号/顿号/冒号一律排除（正文特征）；句号/分号只在长句时排除，
            # 短句是"接口一览表如下"这类条目引导语，仍属标题（同文本路径口径）。
            if text[-1] in '，、：:;':
                continue
            if text[-1] in '。；' and _auto_depth < 3 and len(text) > SHORT_SENTENCE_MAX:
                continue
            if '：' in text or ':' in text:
                continue
            if auto["depth"] < 2 or auto["depth"] > max_depth + 1:
                continue
            # 父级链判据（2026-11-10 放宽）：多 numId 续接写法下父级可能通篇不存在，
            # 例如 numId=182 的 `start=3` 直接产出 3.1/3.2/3.3，没有 ilvl=0 段落。
            # 此时改看「同 numId + 同 ilvl 是否成组」—— 成组即结构化编号，按标题处理。
            # 三级及以上再放宽：与文本路径口径一致（深级编号段落本就多为小节/条款），
            # 不再要求父级 —— 否则 `5.3.4. 系统主要技术指标` 这种孤立条目会漏。
            parent = auto["number"].rsplit('.', 1)[0] if '.' in auto["number"] else ''
            in_heading_chain = bool(parent) and parent in title_numbers
            in_sequence = _seq_size >= 2
            if not (auto["depth"] >= 3 or in_heading_chain or in_sequence):
                continue
            headings.append({
                "index": idx,
                "text": f'{auto["number"]} {text}',
                "number": auto["number"],
                "content": text,
                "detected_level": min(auto["depth"], TitlePreprocessor.MAX_LEVEL),
            })

        # 按段落索引排序，保持文档顺序
        headings.sort(key=lambda h: h["index"])
        return headings

    @staticmethod
    def classify_headings(docx_file, progress_callback=None) -> List[Dict]:
        """把文档中的标题候选**全部分类**，并给出建议动作（合并后的唯一入口）。

        与旧 `detect_headings` 的区别不是"多识别几条"，而是"不再悄悄丢弃"：
        旧实现用一票否决（超长、句末标点、单级编号、组内少数派、含冒号）把这些
        段落直接扔掉，用户在界面上既看不到、也无法判断它们该不该是标题。
        现在它们全部进结果，只是被归到「疑似条款」或「误套」，默认不处理。

        分类（category）：
            missing  漏检     应为标题，但当前既无标题样式也无大纲级别 → 建议转标题
            normal   正常标题 已有标题格式，文本也像标题               → 建议保持
            misuse   误套     是标题格式，但语义是正文                 → 建议降为正文
            body     疑似条款 带编号、但语义是正文的条文               → 建议保持不动

        Args:
            docx_file: docx 路径或可读文件对象（io.BytesIO）。
            progress_callback: 可选，progress_callback(done, total)，两阶段扫描共用。

        Returns:
            List[Dict]，按段落顺序，每项包含：
                index / text / number / content / detected_level
                category / category_label / suggestion / suggestion_label
                confidence（high|medium）/ reasons（list[str]）/ reason_text
                is_heading / is_heading_style / outline_level
                style_name / style_description
                body_style_hint（降级时建议改用的正文样式名）
                group_heading_count / group_body_count（同自动编号组的标题/正文条数）
        """
        doc = Document(docx_file)
        return TitlePreprocessor._classify_in(doc, progress_callback=progress_callback)

    @staticmethod
    def _split_number(raw: str, auto=None):
        """拆出段落的「编号 / 正文 / 展示整行」：文本编号优先，其次 Word 自动编号。

        为什么不能只看正文文本：自动编号段落的 text 里没有任何编号字符
        （编号在 numbering.xml），必须用 `_AutoNumberingResolver` 还原出来的值。

        参数是**纯文本**而不是 Paragraph：分类阶段要对 3000+ 段落各拆一次，
        传段落对象会让 `paragraph.text` 每次都重跑一遍 xpath（实测多耗 2 秒）。
        """
        raw = raw or ''
        first_line = raw.split('\n', 1)[0] if '\n' in raw else raw
        # 纯日期行不算"编号 + 内容"：否则第二阶段会把 "2024 年 6 月" 拆成
        # 编号 2024 + 内容 "年 6 月"，重新走一遍分类又变成「漏检」。
        # 返回 None 后，调用方的 `number is None` 分支会把它当普通正文跳过（非标题格式时）。
        if _DATE_ONLY_PATTERN.match(first_line):
            return None, raw.strip(), raw.strip()
        m = (HEADING_PATTERN.match(first_line)
             or HEADING_PATTERN_NOSEP.match(first_line))
        if m:
            return m.group(1), m.group(2).strip(), first_line.strip()
        m = CHAPTER_PATTERN.match(first_line)
        if m:
            return m.group(1), m.group(2).strip(), first_line.strip()
        if auto:
            content = raw.strip()
            return auto['number'], content, f'{auto["number"]} {content}'
        return None, raw.strip(), raw.strip()

    @staticmethod
    def _classify_in(doc, progress_callback=None) -> List[Dict]:
        """在已打开的 Document 上执行分类（classify_headings 的实现）。"""
        paragraphs = doc.paragraphs
        total = len(paragraphs) or 1

        def _phase(lo, hi):
            """把某一阶段的 (done,total) 映射到整体进度 [lo, hi]（满分 100）。"""
            def _cb(done, tot):
                if not progress_callback:
                    return
                frac = (done / tot) if tot else 1.0
                progress_callback(int(lo + (hi - lo) * frac), 100)
            return _cb if progress_callback else None

        # 第一阶段：复用既有的标题识别（占 45% 进度），保持 300+ 条既有结果零回归。
        heads = TitlePreprocessor._detect_headings_in(
            doc, progress_callback=_phase(0, 45))

        index = _StyleIndex(doc)
        texts = [p.text for p in paragraphs]
        resolver = _AutoNumberingResolver(doc)
        auto_info: Dict[int, Dict] = {}
        for i, para in enumerate(paragraphs):
            info = resolver.number_of(para)
            if info:
                auto_info[i] = info

        # 同 (numId, ilvl) 组内的标题/正文条数 + 正文样式分布。
        # 「同组多数是正文」是判断 `4) 所有操作系统软件…。` 这类误套的关键证据。
        groups: Dict[tuple, Dict] = {}
        doc_body_styles: Dict[str, int] = {}
        for i, para in enumerate(paragraphs):
            is_h = index.is_heading(para)
            style_name = index.name_of(para) or 'Normal'
            if not is_h:
                doc_body_styles[style_name] = doc_body_styles.get(style_name, 0) + 1
            auto = auto_info.get(i)
            if not auto:
                continue
            g = groups.setdefault((auto['num_id'], auto['ilvl']),
                                  {'heading': 0, 'body': 0, 'styles': {}})
            if is_h:
                g['heading'] += 1
            else:
                g['body'] += 1
                g['styles'][style_name] = g['styles'].get(style_name, 0) + 1

        default_body_style = (max(doc_body_styles, key=doc_body_styles.get)
                              if doc_body_styles else 'Normal')

        def _group_of(idx):
            auto = auto_info.get(idx)
            return groups.get((auto['num_id'], auto['ilvl'])) if auto else None

        def _body_hint(idx):
            """降级时建议改用的正文样式：同组最常见正文样式 → 全篇最常见正文样式。"""
            g = _group_of(idx)
            if g and g['styles']:
                return max(g['styles'], key=g['styles'].get)
            return default_body_style

        def _item(idx, number, content, display, level):
            para = paragraphs[idx]
            group = _group_of(idx) or {}
            return {
                'index': idx,
                'text': display,
                'number': number or '',
                'content': content,
                'detected_level': level,
                'is_heading': index.is_heading(para),
                'is_heading_style': index.effective_style_level(para) is not None,
                'outline_level': index.effective_outline_level(para),
                'style_name': index.effective_name_of(para) or '无样式',
                'style_description': index.description(para),
                'body_style_hint': _body_hint(idx),
                'group_heading_count': group.get('heading', 0),
                'group_body_count': group.get('body', 0),
            }

        items: List[Dict] = []
        for h in heads:
            idx = h['index']
            if not 0 <= idx < len(paragraphs):
                continue
            content = h.get('content') or ''
            number = h.get('number') or ''
            depth = _number_depth(number)
            ends_sentence = bool(content) and content[-1] in '。；'
            item = _item(idx, number, content, h['text'], h['detected_level'])
            reasons: List[str] = []
            auto = auto_info.get(idx)
            if auto and auto.get('number') == number:
                reasons.append('编号来自 Word 自动编号（正文里看不到）')

            if not item['is_heading']:
                # [2026-11-11] 第一阶段不能只按「有没有标题格式」一刀切：
                # 识别阶段对三级以上编号放宽到 300 字、不排除冒号，大量条文
                # （`1.1.1招标人：见投标须知前附表。`）也会进 heads。判据统一
                # 收在 `_classify_non_heading()`：带标题编号的进「疑似条款」，
                # 不带标题编号的正文进「正文条款」，剩下的才是真漏检。
                cat, conf, why = _classify_non_heading(content, h['text'], number)
                item['category'] = cat
                item['suggestion'] = (ACTION_HEADING if cat == CATEGORY_MISSING
                                      else ACTION_KEEP)
                item['confidence'] = conf
                reasons.extend(why)
            elif depth == 1 and ends_sentence:
                # 已套标题样式 + 单级列表编号 + 整句结尾：标书里这类段落几乎都是
                # 正文枚举（`1) 2) 3)` 要求列表），个别行被误设成了 Heading。
                g_head = item['group_heading_count']
                g_body = item['group_body_count']
                item['category'] = CATEGORY_MISUSE
                item['suggestion'] = ACTION_DEMOTE
                reasons.append('单级列表编号 + 句子结尾，不像标题')
                if g_body >= 3 and g_body > g_head:
                    item['confidence'] = 'high'
                    reasons.append(f'同编号组内正文 {g_body} 条、标题仅 {g_head} 条')
                else:
                    item['confidence'] = 'medium'
            elif _looks_like_body(content):
                # 多级编号 + 标题样式，但正文本身是完整句子（句中/句末有句号，
                # 或含逗号分句 + 义务动词）。这类是"一句话被拆成多段、首段套了
                # 标题样式"的典型误套，不分编号深度都要抓（用户 2026-11-10）。
                item['category'] = CATEGORY_MISUSE
                item['suggestion'] = ACTION_DEMOTE
                item['confidence'] = 'high'
                reasons.append('已是标题格式，但内容是完整句子，不像标题')
            else:
                item['category'] = CATEGORY_NORMAL
                item['suggestion'] = ACTION_KEEP
                item['confidence'] = 'high'
                reasons.append('已是标题格式')
            item['reasons'] = reasons
            items.append(item)

        # 第二阶段：识别"没进标题结果"的段落 —— 漏检的深级编号、被误套标题样式的
        # 正文、以及带编号的正文长句。这里不再有"丢弃"，只有分类。
        head_idx = {h['index'] for h in heads}
        for idx, para in enumerate(paragraphs):
            if progress_callback and idx % 25 == 0:
                progress_callback(45 + int(55 * idx / total), 100)
            if idx in head_idx:
                continue
            text = texts[idx].strip()
            if not text:
                continue
            number, content, display = TitlePreprocessor._split_number(
                texts[idx], auto_info.get(idx))
            if content and '\t' in content:
                # 多列行（目录行、表格行）：`第一章  致投标人\t1`、`1.1 线路\t12`。
                # 它们不是标题候选，也不该占「疑似条款」的名额 —— 直接不收。
                continue
            is_h = index.is_heading(para)
            level = (index.effective_style_level(para)
                     or (min(_number_depth(number), TitlePreprocessor.MAX_LEVEL)
                         if number else 1))
            item = _item(idx, number or '', content, display, level)
            reasons: List[str] = []

            if number is None:
                if not is_h:
                    continue  # 普通正文段落，与标题无关
                if _looks_like_body(text):
                    # 无编号、却被套了标题样式（例：Heading 3 的「卖方必须承诺…」）
                    item['category'] = CATEGORY_MISUSE
                    item['suggestion'] = ACTION_DEMOTE
                    item['confidence'] = 'high'
                    item['reasons'] = ['无编号的整句正文，却被套了标题样式']
                else:
                    item['category'] = CATEGORY_NORMAL
                    item['suggestion'] = ACTION_KEEP
                    item['confidence'] = 'high'
                    item['reasons'] = ['已是标题格式（无编号的真标题）']
                items.append(item)
                continue

            depth = _number_depth(number)
            if is_h:
                # 有编号、也有标题样式，但第一阶段的规则没有收进来（超长/含冒号，
                # 或正好是被 `_detect_headings_in` 里那条「正文枚举」判据挡下的
                # `4) 所有操作系统软件…。`）。这里按同一口径补判为误套。
                if depth == 1 and content[-1:] in '。；':
                    item['category'] = CATEGORY_MISUSE
                    item['suggestion'] = ACTION_DEMOTE
                    g_head = item['group_heading_count']
                    g_body = item['group_body_count']
                    if g_body >= 3 and g_body > g_head:
                        item['confidence'] = 'high'
                        item['reasons'] = [
                            '单级列表编号 + 句子结尾，不像标题',
                            f'同编号组内正文 {g_body} 条、标题仅 {g_head} 条',
                        ]
                    else:
                        item['confidence'] = 'medium'
                        item['reasons'] = ['单级列表编号 + 句子结尾，不像标题']
                elif _looks_like_body(text):
                    # 长度门槛已收敛进 _looks_like_body（按标点/动词分级），
                    # 这里不要再加 len(text) > 60 —— 那会把 38 字的拆句误套放过去。
                    item['category'] = CATEGORY_MISUSE
                    item['suggestion'] = ACTION_DEMOTE
                    item['confidence'] = 'high'
                    item['reasons'] = ['已是标题格式，但内容是完整句子，不像标题']
                else:
                    item['category'] = CATEGORY_NORMAL
                    item['suggestion'] = ACTION_KEEP
                    item['confidence'] = 'high'
                    item['reasons'] = ['已是标题格式']
            elif depth >= 3 and len(content) <= SHORT_SENTENCE_MAX \
                    and '：' not in content and not _looks_like_body(content):
                # 深级编号 + 标题式短文本：第一阶段因父级链/序列判据没收进来，
                # 但形态就是小节标题（如孤立出现的 `5.3.4. 系统主要技术指标`）。
                # [2026-11-11 第二轮] 长度阈值由 60 收敛到 SHORT_SENTENCE_MAX(45)，
                # 与「疑似条款」的判据衔接：超过 45 字的无特征长文本归疑似条款。
                item['category'] = CATEGORY_MISSING
                item['suggestion'] = ACTION_HEADING
                item['confidence'] = 'medium'
                item['reasons'] = ['深级编号 + 标题式短文本，疑似漏检']
            else:
                # 与第一阶段同一口径（`_classify_non_heading`）：
                # 带标题编号的长文本/条文 → 疑似条款；不带标题编号的 → 正文条款。
                cat, conf, why = _classify_non_heading(content, text, number)
                item['category'] = cat
                item['suggestion'] = (ACTION_HEADING if cat == CATEGORY_MISSING
                                      else ACTION_KEEP)
                # 第二阶段是「第一阶段没收进来」的补判，置信度比第一阶段保守一档。
                item['confidence'] = 'medium' if cat == CATEGORY_MISSING else conf
                item['reasons'] = why
            items.append(item)

        items.sort(key=lambda x: x['index'])
        # 上下文补判（2026-11-11 第二轮，用户实测反馈）：必须在**排序后**做，
        # 「上一条」指文档顺序上的上一条同父级编号候选，不是判定过程中的上一条。
        # 放在分类完成之后而不是塞进 `_classify_non_heading()`：那个函数是逐条
        # 纯函数、被两个阶段共用，加状态会让两阶段口径重新分叉。
        _inherit_suspect_from_prev_sibling(items)

        for it in items:
            it['category_label'] = CATEGORY_LABELS[it['category']]
            it['suggestion_label'] = ACTION_LABELS[it['suggestion']]
            it.setdefault('reasons', [])
            it['reason_text'] = '；'.join(it['reasons'])

        if progress_callback:
            progress_callback(100, 100)
        return items

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
        # [2026-11-11] 与分类引擎同口径：把「编号级别链接样式」也算作标题格式，
        # 否则同一段落在分类列表里是「正常标题」、在这里却显示「无样式」。
        try:
            index = _StyleIndex(paragraph.part.document)
            style_level = index.effective_style_level(paragraph)
            outline_level = index.effective_outline_level(paragraph)
            display_name = index.effective_name_of(paragraph) or style_name or '无样式'
        except Exception:
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
    def _suppress_auto_numbering(paragraph) -> None:
        """关闭段落继承/自带的 Word 自动编号（w:numId=0）。

        为什么必须做（2026-11-06 用户反馈）：
            很多标书的 Heading 样式链着多级列表。正文段落一旦被套上 Heading N，
            Word 就会自动渲染出 "16.1." 这类编号；而原文正文里本来就写着
            "1.1 一致性" → 输出变成 "16.1. 1.1 一致性"，两个编号并存，
            且自动编号在界面上完全不可见、不可编辑。
            本工具统一改为「编号写进正文文本」（可预览、可逐行编辑），
            因此必须显式关闭自动编号，否则同一行永远显示两个号。

        `w:numId=0` 是 OOXML 里「明确无编号」的写法，可覆盖样式继承来的编号。
        """
        pPr = paragraph._p.get_or_add_pPr()
        # get_or_add_numPr 会按 schema 顺序插入（numPr 在 pPr 里有固定位置），
        # 直接 append 到末尾 Word 可能忽略。
        numPr = pPr.get_or_add_numPr()
        # ilvl 对「无编号」没有意义，留着反而可能让 Word 仍按列表项处理
        for child in list(numPr):
            if child.tag != qn('w:numId'):
                numPr.remove(child)
        numId = numPr.find(qn('w:numId'))
        if numId is None:
            numId = OxmlElement('w:numId')
            numPr.append(numId)
        numId.set(qn('w:val'), '0')

    @staticmethod
    def _replace_leading_number(paragraph, old_number: str, new_number: str) -> bool:
        """把段落开头那段编号替换成新编号，保留其余文字与各 run 的格式。

        只替换**第一个**匹配（编号一定在最前面），且逐 run 处理：
        编号常常与标题正文分属不同的 run（编号是西文、正文是中文），
        整段重写会把两个 run 的字体统一成一个，中英文混排的标书会变形。

        Returns:
            True 表示已替换；False 表示段落文本里找不到 old_number（不动）。
        """
        full = paragraph.text
        start = full.find(old_number)
        if start < 0:
            return False
        end = start + len(old_number)

        offset = 0
        replaced = False
        for run in paragraph.runs:
            r_text = run.text
            r_start = offset
            r_end = offset + len(r_text)
            offset = r_end
            # 与 [start, end) 无交集 → 不碰这个 run
            if r_end <= start or r_start >= end:
                continue
            local_start = max(start - r_start, 0)
            local_end = min(end - r_start, len(r_text))
            if not replaced:
                # 新编号写进编号起始所在的 run，保持该 run 的字体（通常是数字字体）
                run.text = r_text[:local_start] + new_number + r_text[local_end:]
                replaced = True
            else:
                # 编号跨了多个 run → 后续 run 里属于旧编号的部分直接删掉
                run.text = r_text[:local_start] + r_text[local_end:]
        return replaced

    @staticmethod
    def _insert_leading_number(paragraph, new_number: str) -> bool:
        """段落正文里没有可见编号时，把编号写到最前面（自动编号段落专用）。

        为什么要单独一个函数：`_replace_leading_number` 需要先找到旧编号，
        而自动编号段落的 `text` 里根本没有编号字符，找不到就什么都不做 ——
        结果就是「关了自动编号 + 没写新编号」= 标题号凭空消失（2026-11-10）。
        """
        number = (new_number or '').strip()
        if not number:
            return False
        if paragraph.runs:
            first = paragraph.runs[0]
            first.text = f"{number} {first.text}"
        else:
            paragraph.add_run(f"{number} ")
        return True

    @staticmethod
    def apply_headings(docx_file, output_file, selections: List[Dict], progress_callback=None) -> None:
        """（兼容接口）把选中段落应用 Heading N 样式并保存。

        旧调用方只需要「转标题」一种动作；内部统一走 `apply_changes`，
        避免同一套「套样式 + 关自动编号 + 写编号」存两份实现。

        Args:
            selections: List[Dict]，每项 {"index", "target_level", "new_number"}。
                target_level 为 1-9；new_number 与原文不同时改写正文里的旧编号。
        """
        changes = []
        for sel in selections:
            if int(sel.get("target_level") or 0) < 1:
                continue
            changes.append({
                "index": sel["index"],
                "action": ACTION_HEADING,
                "target_level": int(sel["target_level"]),
                "new_number": sel.get("new_number") or "",
            })
        TitlePreprocessor.apply_changes(
            docx_file, output_file, changes, progress_callback=progress_callback)

    @staticmethod
    def apply_changes(docx_file, output_file, changes: List[Dict],
                      progress_callback=None) -> Dict[str, int]:
        """按「每条一个动作」修改文档：转标题 / 降为正文（保持不动直接跳过）。

        Args:
            docx_file / output_file: 输入、输出 docx 路径。
            changes: List[Dict]，每项：
                {"index": int,
                 "action": "heading" | "demote" | "keep",
                 "target_level": int,   # heading 必填，1-9
                 "new_number": str,     # heading 可选：改写正文里的编号
                 "body_style": str}     # demote 可选：改用的正文样式名
            progress_callback: 可选，progress_callback(done, total)。

        Returns:
            {"heading": n, "demote": m, "keep": 0} —— 各动作实际执行条数。

        输出约定（2026-11-06 用户要求「新旧编号只保留新编号」）：
            1) 转标题时关掉段落的 Word 自动编号（否则 Heading 样式会再生成一个号）；
            2) 正文里的旧编号按 new_number 替换（未改则原样保留）；
            3) 降为正文时保留自动编号和文字，只换样式 + 删大纲级别。
        """
        doc = Document(docx_file)
        todo = {c["index"]: c for c in changes
                if c.get("action") in (ACTION_HEADING, ACTION_DEMOTE)}
        total = len(todo)
        done = 0
        summary = {ACTION_HEADING: 0, ACTION_DEMOTE: 0, ACTION_KEEP: 0}

        for idx, para in enumerate(doc.paragraphs):
            change = todo.get(idx)
            if not change:
                continue
            if change.get("action") == ACTION_HEADING:
                level = int(change.get("target_level") or 0)
                if not 1 <= level <= TitlePreprocessor.MAX_LEVEL:
                    continue
                TitlePreprocessor._apply_heading_style(doc, para, level)
                # 先关自动编号，再改正文编号：两步互不依赖，但顺序固定便于排查
                TitlePreprocessor._suppress_auto_numbering(para)
                new_number = str(change.get("new_number") or "").strip()
                if new_number:
                    old_number = TitlePreprocessor._extract_number_prefix(para.text)
                    if old_number and old_number != new_number:
                        TitlePreprocessor._replace_leading_number(para, old_number, new_number)
                    elif not old_number:
                        # [2026-11-10] 自动编号段落：正文里从来没有可见编号（编号在
                        # numbering.xml，已被上一步 numId=0 关掉）。若只套样式，输出
                        # 文档会把这个号整条丢掉 → 必须把新编号写进正文开头。
                        TitlePreprocessor._insert_leading_number(para, new_number)
                summary[ACTION_HEADING] += 1
            else:
                TitlePreprocessor._demote_to_body(doc, para, change.get("body_style"))
                summary[ACTION_DEMOTE] += 1
            done += 1
            if progress_callback:
                progress_callback(done, total)

        doc.save(output_file)
        if progress_callback:
            progress_callback(total, total)
        return summary

    @staticmethod
    def _demote_to_body(doc, paragraph, style_name: Optional[str] = None) -> bool:
        """把误套标题样式的段落降为正文：换正文样式 + 删大纲级别。

        刻意**不做**的三件事（与「转标题」相反，尽量少改）：
            1) 不关自动编号 —— `4)`、`1)` 这些号本来就该留在正文里，删了正文
               就丢了序号；
            2) 不把编号写进正文 —— 同上，编号仍在 numbering.xml 里；
            3) 不动文字、不动 run 级格式 —— 只换段落样式。

        必须删 `w:outlineLvl`：不删的话 Word 大纲视图里仍然会出现这一条，
        等于没降级。
        """
        name = (style_name or '').strip()
        # 目标必须是正文样式；传进来 Heading 名字说明调用方有问题，直接忽略。
        if name.lower() in HEADING_STYLE_LEVELS:
            name = ''
        applied = False
        if name:
            try:
                paragraph.style = doc.styles[name]
                applied = True
            except Exception:
                applied = False
        if not applied:
            # 回退：删掉 pStyle，回到文档默认样式（通常就是正文）
            pPr = paragraph._p.find(qn('w:pPr'))
            if pPr is not None:
                pStyle = pPr.find(qn('w:pStyle'))
                if pStyle is not None:
                    pPr.remove(pStyle)
        pPr = paragraph._p.find(qn('w:pPr'))
        if pPr is not None:
            outline = pPr.find(qn('w:outlineLvl'))
            if outline is not None:
                pPr.remove(outline)
        return True

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
