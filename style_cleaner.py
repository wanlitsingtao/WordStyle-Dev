# -*- coding: utf-8 -*-
"""
模板样式精简引擎（T04 / 工具箱：模板样式精简）
无 Streamlit 依赖，可独立测试。

职责：
1. 分析与文档转换模块一致的模板段落样式及使用次数（含表格内段落）
2. 对 Word 内置样式做最小保留（Normal / Heading / Body Text / List Paragraph / Header / Footer），其余可删
3. 删除样式：对 basedOn/next 引用自动重指向到首个保留祖先，清理 link 悬空引用，保证文档可正常打开
"""
from typing import List, Dict, Set, Optional

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

# 样式类型中文名
STYLE_TYPE_LABELS = {
    WD_STYLE_TYPE.PARAGRAPH: "段落",
    WD_STYLE_TYPE.CHARACTER: "字符",
    WD_STYLE_TYPE.TABLE: "表格",
    WD_STYLE_TYPE.LIST: "列表",
}

# Word 内置样式的最小保留集：这些样式即使未使用也必须保留，
# 否则会影响文档默认格式或文档转换模块的硬编码映射目标。
ESSENTIAL_STYLE_NAMES = {
    'Normal',
    'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4', 'Heading 5',
    'Heading 6', 'Heading 7', 'Heading 8', 'Heading 9',
    'Body Text',
    'List Paragraph',
    'Header', 'Footer',
}


class StyleCleaner:
    """模板样式精简引擎（无状态工具类）"""

    @staticmethod
    def _iter_all_paragraphs(doc):
        """遍历主体 + 表格 + 文本框段落。

        [2026-10-06] 与样式映射共用 doc_converter.iter_document_paragraphs 的同一实现，
        确保「样式使用次数统计」与「样式/直接格式快照提取」看到的是同一批段落——
        各自另写一份遍历会漏扫，导致在用的样式被误判成「未使用」而遭删除。
        """
        from doc_converter import iter_document_paragraphs
        return list(iter_document_paragraphs(doc))

    @staticmethod
    def _count_snapshot_usage(doc, paragraphs):
        """统计每个「样式 + 直接格式」快照在文档里出现的段落数。

        [2026-10-06] 快照的「使用情况」要与内置样式同一套写法
        （`使用（快照）` / `未使用（快照）`），因此不能恒为 0 —— 恒 0 会让
        清单里的快照永远显示「未使用」，而它们明明是从文档段落上提取出来的。

        这里复用 doc_converter 里生成快照名的同一批底层工具
        （build_style_id_name_map / paragraph_style_name /
        extract_paragraph_direct_format / build_snapshot_name），
        保证算出来的名字与快照清单里的显示名逐字一致，不会出现对不上的孤儿计数。
        """
        from doc_converter import (build_style_id_name_map, build_snapshot_name,
                                   extract_paragraph_direct_format,
                                   paragraph_style_name)
        counts = {}
        id2name, default_name = build_style_id_name_map(doc)
        for para in paragraphs:
            style_name = paragraph_style_name(para, id2name, default_name)
            if not style_name:
                continue
            run_fmt, para_fmt = extract_paragraph_direct_format(para)
            if not run_fmt and not para_fmt:
                continue
            name = build_snapshot_name(style_name, run_fmt, para_fmt)
            if name:
                counts[name] = counts.get(name, 0) + 1
        return counts

    @staticmethod
    def analyze_styles(docx_file, progress_callback=None) -> Dict:
        """分析模板文档样式及使用次数。

        Args:
            progress_callback: 可选，扫描进度回调 progress_callback(done: int, total: int)。
                在遍历全部段落统计样式使用次数时按比例推进（用于非阻塞进度条）。

        Returns:
            {
                "total": int,           # 真实段落样式数（不含快照条目）
                "total_with_snapshot": int,  # 清单条目总数 = 真实样式 + 快照
                                        # （样式精简模块的「总样式」用它；转换页沿用 total）
                "builtin_count": int,   # Word 内置样式数
                "custom_count": int,    # 自定义样式数
                "used": int,
                "unused": int,
                "cleanable": int,       # 可清理（未使用、非必需保留、且无 basedOn/next 依赖）
                "snapshot_count": int,  # 「样式 + 直接格式」快照条目数（与样式映射清单一致）
                "styles": [
                    {
                        "style_id": str,
                        "name": str,
                        "type": str,          # "段落"/"字符"/"表格"/"列表"
                        "usage_count": int,   # 真实样式=被引用的段落数；快照=该组合出现的段落数
                        "builtin": bool,      # 是否内置样式
                        "protected": bool,    # 是否属于最小保留集（默认不可删）
                        "snapshot": bool,     # True = 快照条目（非真实样式，不可删）
                        "base_style": str,    # 仅快照条目：该快照引用的真实样式名
                    }, ...
                ],
            }
        """
        doc = Document(docx_file)

        # [2026-10-06] 样式识别与「样式映射」共用同一份实现（common.collect_template_style_names）：
        #   real_names     = 模板真实段落样式名（按名排序，顺序与映射下拉框一致）
        #   snapshot_names = 模板段落上「样式 + 直接格式」快照名（如「标题 1 + 四号」）
        from common import collect_template_style_names
        from doc_converter import extract_template_format_snapshots
        real_names, snapshot_names = collect_template_style_names(doc)
        snapshots = extract_template_format_snapshots(doc)

        # 统计使用次数（按 style_id）—— 段落扫描与快照提取共用同一实现
        usage = {}
        paragraphs = StyleCleaner._iter_all_paragraphs(doc)
        total_paras = len(paragraphs)
        for i, para in enumerate(paragraphs):
            if progress_callback:
                progress_callback(i + 1, max(total_paras, 1))
            try:
                para_style = para.style
            except Exception:
                para_style = None
            if para_style is not None:
                sid = para_style.style_id
                if sid:
                    usage[sid] = usage.get(sid, 0) + 1

        # 快照条目的「使用次数」= 该「样式 + 直接格式」组合在文档里出现的段落数
        # （与真实样式统计共用同一批段落，算出的名字与快照清单逐字一致）
        snap_usage = (StyleCleaner._count_snapshot_usage(doc, paragraphs)
                      if snapshot_names else {})

        # 与文档转换模块一致：仅统计模板中的"段落样式且有名"
        # （见 doc_converter.get_template_styles / components.upload.get_template_styles_list）。
        # 真实段落样式：按共用识别的排序输出（与样式映射下拉框同序）；
        # 同名多条样式按样式表原顺序逐个保留，不丢条目。
        by_name = {}
        for style in doc.styles:
            try:
                stype = style.type
            except Exception:
                stype = None
            if stype != WD_STYLE_TYPE.PARAGRAPH:
                continue
            name = style.name or ""
            if not name:
                continue
            by_name.setdefault(name, []).append(style)

        styles = []
        for name in real_names:
            for style in by_name.get(name, []):
                try:
                    stype = style.type
                except Exception:
                    stype = None
                type_label = STYLE_TYPE_LABELS.get(stype, "未知")
                sid = style.style_id
                is_builtin = bool(getattr(style, 'builtin', False))
                count = usage.get(sid, 0)
                # 最小保留集：仅内置且属于必需样式的才默认保护，
                # 其余内置样式若未使用也可清理。
                protected = is_builtin and (name in ESSENTIAL_STYLE_NAMES)
                styles.append({
                    "style_id": sid,
                    "name": name,
                    "type": type_label,
                    "usage_count": count,
                    "builtin": is_builtin,
                    "protected": protected,
                    "snapshot": False,
                })

        # 「样式 + 直接格式」快照条目：与样式映射下拉框一致，统一排在真实样式之后。
        # 快照不是文档里的真实样式（没有 styleId），无法删除，
        # 固定 protected=True 只作提示，不参与「删除全部未使用」。
        # usage_count 用真实出现段落数 —— 界面按内置样式那一套显示「使用（快照）」。
        for sname in snapshot_names:
            snap = snapshots.get(sname) or {}
            styles.append({
                "style_id": "__snapshot__::" + sname,
                "name": sname,
                "type": STYLE_TYPE_LABELS.get(WD_STYLE_TYPE.PARAGRAPH, "未知"),
                "usage_count": snap_usage.get(sname, 0),
                "builtin": False,
                "protected": True,
                "snapshot": True,
                "base_style": snap.get("style") or "",
            })

        # 指标口径（[2026-10-06] 定稿）：
        #   · total / builtin_count / custom_count / used / unused / cleanable
        #     —— **只统计真实样式**，这样既有调用方（components.upload.count_template_styles
        #        的「模板样式数」、转换页引导提示）语义不变；
        #   · snapshot_count —— 快照条目单列；
        #   · total_with_snapshot —— 清单条目总数（真实样式 + 快照），
        #     样式精简模块的「总样式」卡片用它，这样「总样式 = 自定义 + 内置 + 快照」
        #     与界面上那份清单的长度一致。
        real_styles = [s for s in styles if not s.get("snapshot")]
        used_count = sum(1 for s in real_styles if s["usage_count"] > 0)
        builtin_count = sum(1 for s in real_styles if s["builtin"])
        # 可清理数：未使用且非最小保留集的样式数（依赖引用会被自动重指向）
        cleanable = sum(
            1 for s in real_styles
            if s["usage_count"] == 0 and not s["protected"]
        )
        return {
            "total": len(real_styles),
            "total_with_snapshot": len(styles),
            "builtin_count": builtin_count,
            "custom_count": len(real_styles) - builtin_count,
            "used": used_count,
            "unused": len(real_styles) - used_count,
            "cleanable": cleanable,
            "snapshot_count": len(styles) - len(real_styles),
            "styles": styles,
        }

    @staticmethod
    def _resolve_reference(sid, delete_set: Set[str], ref_map: Dict, default: Optional[str] = None):
        """沿引用链找到第一个不在删除集合中的样式 id。

        Args:
            sid: 起始样式 id（通常在删除集合中）。
            delete_set: 待删除样式 id 集合。
            ref_map: styleId -> 引用目标（如 basedOn / next）。
            default: 找不到可保留祖先时返回的默认值。

        Returns:
            第一个非删除样式 id；若引用链断裂或成环，返回 default。
        """
        seen = set()
        cur = sid
        while cur is not None:
            if cur not in delete_set:
                return cur
            if cur in seen:
                return default
            seen.add(cur)
            cur = ref_map.get(cur)
        return default

    @staticmethod
    def cleanup_styles(docx_file, output_file, delete_style_ids: List[str], progress_callback=None) -> Dict:
        """删除指定样式并保存新文档。

        Args:
            docx_file: 输入 docx 路径。
            output_file: 输出 docx 路径。
            delete_style_ids: 要删除的 styleId 列表（内部会过滤最小保留集，
                并对 basedOn/next 引用自动重指向，对 link 引用清理）。
            progress_callback: 可选，处理进度回调 progress_callback(done: int, total: int)。
                按「过滤保护集 → 建引用链 → 物理删除 → 重指向 → 保存」分阶段推进，
                删除/重指向阶段按真实处理的样式数推进（用于非阻塞进度条）。

        Returns:
            {"deleted": int, "skipped_protected": int, "repointed": int, "message": str}
        """
        def _tick(step, total_steps):
            """把 0..total_steps 归一成 0..100 的百分比推进（内部不直接写满 100）。"""
            if progress_callback:
                progress_callback(step, total_steps)

        doc = Document(docx_file)
        delete_set = set(delete_style_ids or [])
        _tick(0, 100)

        # 1. 过滤最小保留集样式（内置且必需：Normal / Heading 1-9 / Body Text / List Paragraph / Header / Footer）
        skipped_protected = 0
        for style in doc.styles:
            if style.style_id in delete_set:
                if bool(getattr(style, 'builtin', False)) and (style.name or "") in ESSENTIAL_STYLE_NAMES:
                    delete_set.discard(style.style_id)
                    skipped_protected += 1
        _tick(5, 100)

        # 构建删除前的引用链（用于重指向）
        styles_elm = doc.styles.element
        basedon_map = {}
        next_map = {}
        for style_elm in styles_elm.findall(qn('w:style')):
            sid = style_elm.get(qn('w:styleId'))
            b = style_elm.find(qn('w:basedOn'))
            n = style_elm.find(qn('w:next'))
            basedon_map[sid] = b.get(qn('w:val')) if b is not None else None
            next_map[sid] = n.get(qn('w:val')) if n is not None else None
        _tick(10, 100)

        # 2. 物理删除样式元素（按待删样式数推进 10% -> 60%）
        deleted = 0
        delete_list = [s for s in list(styles_elm.findall(qn('w:style')))
                       if s.get(qn('w:styleId')) in delete_set]
        total_delete = max(len(delete_list), 1)
        for i, style_elm in enumerate(delete_list):
            styles_elm.remove(style_elm)
            deleted += 1
            _tick(10 + int((i + 1) / total_delete * 50), 100)

        # 3. 重指向 / 清理保留样式中指向已删除样式的引用（按保留样式数推进 60% -> 95%）
        repointed = 0
        remain_list = list(styles_elm.findall(qn('w:style')))
        total_remain = max(len(remain_list), 1)
        for i, style_elm in enumerate(remain_list):
            # basedOn：重指向到被删样式的第一个非删除祖先；无祖先则移除（等价于基于 Normal）
            b = style_elm.find(qn('w:basedOn'))
            if b is not None and b.get(qn('w:val')) in delete_set:
                new_base = StyleCleaner._resolve_reference(
                    b.get(qn('w:val')), delete_set, basedon_map
                )
                if new_base:
                    b.set(qn('w:val'), new_base)
                else:
                    style_elm.remove(b)
                repointed += 1
            # next：重指向到第一个非删除样式，找不到则移除（移除后 Word 默认使用 Normal）
            n = style_elm.find(qn('w:next'))
            if n is not None and n.get(qn('w:val')) in delete_set:
                new_next = StyleCleaner._resolve_reference(
                    n.get(qn('w:val')), delete_set, next_map
                )
                if new_next:
                    n.set(qn('w:val'), new_next)
                else:
                    style_elm.remove(n)
                repointed += 1
            # link：直接移除指向已删除样式的悬空链接
            link = style_elm.find(qn('w:link'))
            if link is not None and link.get(qn('w:val')) in delete_set:
                style_elm.remove(link)
                repointed += 1
            _tick(60 + int((i + 1) / total_remain * 35), 100)

        _tick(95, 100)
        doc.save(output_file)
        _tick(100, 100)

        message = f"已删除 {deleted} 个样式"
        if skipped_protected:
            message += f"，跳过 {skipped_protected} 个最小保留样式"
        if repointed:
            message += f"，重指向 {repointed} 处引用"
        return {
            "deleted": deleted,
            "skipped_protected": skipped_protected,
            "repointed": repointed,
            "message": message,
        }
