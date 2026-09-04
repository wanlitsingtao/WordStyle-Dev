# -*- coding: utf-8 -*-
"""
模板样式精简引擎（T04 / 工具箱 Tab B）
无 Streamlit 依赖，可独立测试。

职责：
1. 分析模板文档中所有样式及使用次数（含表格内段落）
2. 识别内置样式（style.builtin + Heading 1-9 + Normal + List Paragraph 等）并保护
3. 删除未使用样式（保守策略：保护样式依赖闭包，避免悬空引用）
"""
from typing import List, Dict, Set, Optional

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

# 内置样式保护名单（名称匹配，用于 style.builtin 之外的双重保护）
PROTECTED_STYLE_NAMES = {
    'Normal', 'Default Paragraph Font', 'Normal Table', 'No List',
    'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4', 'Heading 5',
    'Heading 6', 'Heading 7', 'Heading 8', 'Heading 9',
    'Title', 'Subtitle', 'List Paragraph', 'Header', 'Footer',
    '正文', '标题 1', '标题 2', '标题 3', '标题 4', '标题 5',
    '标题 6', '标题 7', '标题 8', '标题 9',
}

# 样式类型中文名
STYLE_TYPE_LABELS = {
    WD_STYLE_TYPE.PARAGRAPH: "段落",
    WD_STYLE_TYPE.CHARACTER: "字符",
    WD_STYLE_TYPE.TABLE: "表格",
    WD_STYLE_TYPE.LIST: "列表",
}


class StyleCleaner:
    """模板样式精简引擎（无状态工具类）"""

    @staticmethod
    def _iter_all_paragraphs(doc):
        """遍历主体 + 表格 + 文本框段落。"""
        paragraphs = list(doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.extend(cell.paragraphs)
        try:
            from docx.text.paragraph import Paragraph
            body_parent = doc.paragraphs[0]._parent if doc.paragraphs else None
            if body_parent is not None:
                for txbx in doc.element.body.iter(qn('w:txbxContent')):
                    for p in txbx.findall(qn('w:p')):
                        paragraphs.append(Paragraph(p, body_parent))
        except Exception:
            pass
        return paragraphs

    @staticmethod
    def analyze_styles(docx_file) -> Dict:
        """分析模板文档样式及使用次数。

        Returns:
            {
                "total": int,
                "used": int,
                "unused": int,
                "styles": [
                    {
                        "style_id": str,
                        "name": str,
                        "type": str,          # "段落"/"字符"/"表格"/"列表"
                        "usage_count": int,
                        "builtin": bool,      # 是否内置样式
                        "protected": bool,    # 是否默认保护（不可删）
                    }, ...
                ],
            }
        """
        doc = Document(docx_file)

        # 统计使用次数（按 style_id）
        usage = {}
        for para in StyleCleaner._iter_all_paragraphs(doc):
            if para.style is not None:
                sid = para.style.style_id
                if sid:
                    usage[sid] = usage.get(sid, 0) + 1

        # 遍历 styles.xml 定义的所有样式
        styles = []
        for style in doc.styles:
            sid = style.style_id
            name = style.name or ""
            try:
                stype = style.type
            except Exception:
                stype = None
            type_label = STYLE_TYPE_LABELS.get(stype, "未知")
            is_builtin = bool(getattr(style, 'builtin', False))
            count = usage.get(sid, 0)
            protected = is_builtin or (name in PROTECTED_STYLE_NAMES)
            styles.append({
                "style_id": sid,
                "name": name,
                "type": type_label,
                "usage_count": count,
                "builtin": is_builtin,
                "protected": protected,
            })

        used_count = sum(1 for s in styles if s["usage_count"] > 0)
        return {
            "total": len(styles),
            "used": used_count,
            "unused": len(styles) - used_count,
            "styles": styles,
        }

    @staticmethod
    def _compute_keep_closure(doc, delete_ids: Set[str]) -> Set[str]:
        """计算需保留的 styleId 闭包（处理 basedOn / link / next 依赖）。

        删除某样式前，若存在被保留样式通过 basedOn / link / next 引用它，
        则该样式必须一并保留，避免产生悬空引用。
        """
        keep = set(delete_ids)  # 初始：默认删除集合，后续被依赖的会移出
        # 收集所有样式的依赖关系
        # 遍历 styles.xml 中的 style 元素
        styles_elm = doc.styles.element
        # 找出会被删除的样式 ID 集合之外，仍需保留的样式所引用的 basedOn/link/next
        # 迭代固定次数即可收敛（样式继承链通常很短）
        for _ in range(10):
            changed = False
            for style_elm in styles_elm.findall(qn('w:style')):
                sid = style_elm.get(qn('w:styleId'))
                # 若该样式本身是要删除的，跳过（它引用的依赖暂时不考虑，因为引用它的样式被删后引用也消失）
                if sid in delete_ids and sid not in keep:
                    continue
                # 该样式会保留，检查它引用的 basedOn/link/next
                for ref_tag in ('w:basedOn', 'w:link', 'w:next'):
                    ref = style_elm.find(qn(ref_tag))
                    if ref is not None:
                        ref_val = ref.get(qn('w:val'))
                        if ref_val and ref_val in delete_ids:
                            # 被引用的样式不能删，从删除集合移出
                            delete_ids.discard(ref_val)
                            changed = True
            if not changed:
                break
        return delete_ids

    @staticmethod
    def cleanup_styles(docx_file, output_file, delete_style_ids: List[str]) -> Dict:
        """删除指定样式并保存新文档。

        Args:
            docx_file: 输入 docx 路径。
            output_file: 输出 docx 路径。
            delete_style_ids: 要删除的 styleId 列表（引擎内部会做保护 + 依赖闭包过滤）。

        Returns:
            {"deleted": int, "skipped_protected": int, "skipped_dependency": int, "message": str}
        """
        doc = Document(docx_file)
        delete_set = set(delete_style_ids or [])

        # 1. 过滤内置/保护样式
        skipped_protected = 0
        protected_ids = set()
        for style in doc.styles:
            if style.style_id in delete_set:
                if bool(getattr(style, 'builtin', False)) or (style.name or "") in PROTECTED_STYLE_NAMES:
                    protected_ids.add(style.style_id)
                    delete_set.discard(style.style_id)
                    skipped_protected += 1

        # 2. 依赖闭包过滤（被保留样式引用的样式不能删）
        before_dependency = len(delete_set)
        delete_set = StyleCleaner._compute_keep_closure(doc, delete_set)
        skipped_dependency = before_dependency - len(delete_set)

        # 3. 物理删除样式元素
        styles_elm = doc.styles.element
        deleted = 0
        for style_elm in list(styles_elm.findall(qn('w:style'))):
            sid = style_elm.get(qn('w:styleId'))
            if sid in delete_set:
                styles_elm.remove(style_elm)
                deleted += 1

        doc.save(output_file)

        message = f"已删除 {deleted} 个样式"
        if skipped_protected:
            message += f"，跳过 {skipped_protected} 个内置/保护样式"
        if skipped_dependency:
            message += f"，保留 {skipped_dependency} 个被引用样式"
        return {
            "deleted": deleted,
            "skipped_protected": skipped_protected,
            "skipped_dependency": skipped_dependency,
            "message": message,
        }
