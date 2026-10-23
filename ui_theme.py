# -*- coding: utf-8 -*-
"""
统一 UI 字号规范（静态变量 · 单一数据源）

设计目标：**改一处，全站生效。**
- 所有字号只在下方「字号规范」区定义一次；
- 各页 CSS 统一通过 `var(--ws-font-*)` 引用，不写死数值；
- app.py 启动时调用 `root_style_tag()` 把变量注入 `:root`。

新增字号规格时：
    1) 在「字号规范」区增加常量；
    2) 在 `_CSS_VAR_MAP` 登记变量名；
    3) 页面 CSS 用 `var(--ws-xxx)` 引用即可。

本模块不依赖 Streamlit，可独立导入 / 测试。
"""

# ==================== 字号规范（单一数据源）====================
# 系统主标题：「标书编写神器」（侧边栏品牌区）
FONT_SIZE_APP_TITLE = "1.4rem"

# 区块 / 提示标题：「上传源文档」「上传模板文档」「多字祈使词替换」等
# 与主标题保持一致 —— 修改 FONT_SIZE_APP_TITLE 即可同步全部区块标题。
FONT_SIZE_SECTION = FONT_SIZE_APP_TITLE

# 页面一级大标题（h1）
FONT_SIZE_H1 = "clamp(1.8rem, 3vw, 2.5rem)"

# 工具箱标签页（用户要求比正文大一倍）
FONT_SIZE_TAB = FONT_SIZE_APP_TITLE

# 正文 / 说明文字
# 注意：以下 4 项取值与 Streamlit 1.63 默认字号保持一致（base 1rem、
# sm 0.875rem），这样「统一接管」不会改变现有观感；
# 需要整体放大/缩小时只改这里即可。
FONT_SIZE_BODY = "1rem"
# 辅助说明（caption / 上传提示）
FONT_SIZE_CAPTION = "0.875rem"

# 统计卡片（st.metric）：「新写入编号 154 个」这类数字要让用户一眼看到，
# 因此比正文明显大一号、字重加粗（2026-10-23 用户要求）。
FONT_SIZE_STAT_VALUE = "2rem"
FONT_SIZE_STAT_LABEL = "1rem"
# 表单标签
FONT_SIZE_LABEL = "0.875rem"
# 按钮文字
FONT_SIZE_BUTTON = "0.875rem"

# ==================== 侧边栏字号 ====================
FONT_SIZE_NAV = "0.98rem"          # 功能菜单项 / 用户信息
FONT_SIZE_KPI_VALUE = "1.25rem"    # 额度 KPI 数值
FONT_SIZE_KPI_LABEL = "0.72rem"    # 额度 KPI 标签
FONT_SIZE_MINI = "0.88rem"         # 侧边栏小按钮
FONT_SIZE_MINI_TITLE = "0.95rem"   # 「功能菜单」分组标题
FONT_SIZE_FOOTER = "0.875rem"      # 页脚版本号
FONT_SIZE_SMALL = "0.75rem"        # 版权等极小文字
FONT_SIZE_TINY = "0.65rem"         # 紧凑控件内的微型提示（如配置面板拖拽区）


# ==================== 标题统一样式（主标题 / 区块标题共用）====================
# 系统主标题「标书编写神器」与所有区块标题（上传源文档 / 上传模板文档 /
# 多字祈使词替换……）全部由下面这一份声明驱动 —— 字号、字重、颜色、行高、
# 字距完全一致。改 FONT_SIZE_APP_TITLE 一处，两边同时变。
FONT_VAR_APP_TITLE = "--ws-font-app-title"   # 主标题字号变量
FONT_VAR_SECTION = "--ws-font-section"       # 区块标题字号变量

TITLE_COLOR = "#262730"
TITLE_FONT_WEIGHT = "700"
TITLE_LINE_HEIGHT = "1.2"
TITLE_LETTER_SPACING = "0"


def title_style(font_var: str = FONT_VAR_APP_TITLE) -> str:
    """返回主标题 / 区块标题共用的 CSS 声明串（供 inline style 使用）。

    字号以 CSS 变量引用，变量缺失时回退到本模块常量，因此
    「改 FONT_SIZE_APP_TITLE 一处 → 全站标题同步生效」。
    """
    fallback = _CSS_VAR_MAP.get(font_var, FONT_SIZE_APP_TITLE)
    return (
        f"font-size:var({font_var}, {fallback});"
        f"font-weight:{TITLE_FONT_WEIGHT};"
        f"color:{TITLE_COLOR};"
        f"line-height:{TITLE_LINE_HEIGHT};"
        f"letter-spacing:{TITLE_LETTER_SPACING};"
    )


def section_title_html(text: str, *, margin_top: str = "1.05rem",
                       margin_bottom: str = "0.45rem") -> str:
    """生成区块标题 HTML（与主标题「标书编写神器」完全同规格）。

    用 ``<h3>`` 保留语义，同时把字号/字重/颜色/行高以**行内样式**写出，
    避免被 Streamlit 默认的 h3 字号（1.75rem）或其它 CSS 规则覆盖。
    """
    return (
        f'<h3 class="ws-section-title" style="{title_style(FONT_VAR_SECTION)}'
        f'margin:{margin_top} 0 {margin_bottom} 0;">{text}</h3>'
    )


def render_section_title(text: str, *, margin_top: str = "1.05rem",
                         margin_bottom: str = "0.45rem") -> None:
    """在主内容区渲染一个区块标题。

    **统一入口**：页面里不要再直接写 ``st.subheader(...)`` 或
    ``st.markdown("### ...")``，改用本函数，即可保证与主标题同字号。
    """
    import streamlit as st  # 延迟导入：保持本模块可脱离 Streamlit 独立测试
    st.markdown(
        section_title_html(text, margin_top=margin_top, margin_bottom=margin_bottom),
        unsafe_allow_html=True,
    )


# ==================== CSS 变量映射 ====================
# 变量名 → 字号值；改字号只需改上面的常量，这里自动同步。
_CSS_VAR_MAP = {
    "--ws-font-app-title": FONT_SIZE_APP_TITLE,
    "--ws-font-section": FONT_SIZE_SECTION,
    "--ws-font-h1": FONT_SIZE_H1,
    "--ws-font-tab": FONT_SIZE_TAB,
    "--ws-font-body": FONT_SIZE_BODY,
    "--ws-font-caption": FONT_SIZE_CAPTION,
    "--ws-font-stat-value": FONT_SIZE_STAT_VALUE,
    "--ws-font-stat-label": FONT_SIZE_STAT_LABEL,
    "--ws-font-label": FONT_SIZE_LABEL,
    "--ws-font-button": FONT_SIZE_BUTTON,
    "--ws-font-nav": FONT_SIZE_NAV,
    "--ws-font-kpi-value": FONT_SIZE_KPI_VALUE,
    "--ws-font-kpi-label": FONT_SIZE_KPI_LABEL,
    "--ws-font-mini": FONT_SIZE_MINI,
    "--ws-font-mini-title": FONT_SIZE_MINI_TITLE,
    "--ws-font-footer": FONT_SIZE_FOOTER,
    "--ws-font-small": FONT_SIZE_SMALL,
    "--ws-font-tiny": FONT_SIZE_TINY,
}


def font_size(css_var_name: str, fallback: str = "1rem") -> str:
    """按变量名取字号常量（供 Python 侧需要数值时使用）。

    例如：font_size("--ws-font-tab") -> "2rem"
    """
    return _CSS_VAR_MAP.get(css_var_name, fallback)


def root_style_tag() -> str:
    """返回定义全部 `:root` CSS 变量的 `<style>` 片段。

    在 app.py 全局主题中注入一次，所有页面的 `var(--ws-*)` 即可生效。
    """
    declarations = "\n        ".join(
        f"{name}: {value};" for name, value in _CSS_VAR_MAP.items()
    )
    return (
        "<style>\n"
        "    :root {\n"
        f"        {declarations}\n"
        "    }\n"
        "    /* 区块标题：字号/字重/颜色由 render_section_title() 的行内样式给出，\n"
        "       此处仅保证块级排版（避免被 markdown 渲染成行内元素）。 */\n"
        "    .ws-section-title { display: block; }\n"
        "</style>"
    )
