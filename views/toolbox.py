# -*- coding: utf-8 -*-
"""
工具箱页（T04）
st.tabs 组合三个工具：源文档标题查漏 + 源文档标题预处理 + 模板样式精简。
"""
import streamlit as st


def render_toolbox_page():
    """工具箱页入口（供 st.navigation 调用）。"""
    from components.sidebar import render_sidebar
    render_sidebar("toolbox")

    st.markdown(
        """
        <style>
            /* 工具箱的三个工作区标签（CSS 兜底）。
               字号统一引用 --ws-font-tab（定义见 ui_theme.py），
               当前值与系统主标题一致，改 ui_theme.py 一处即同步。 */
            [data-testid="stAppViewContainer"] [data-testid="stTabs"] [data-baseweb="tab"],
            [data-testid="stAppViewContainer"] [data-testid="stTabs"] [role="tab"] {
                min-height: 2.9rem;
                padding: 0.7rem 1.2rem;
                color: #475569;
                font-size: var(--ws-font-tab, 1.4rem) !important;
                font-weight: 650 !important;
            }
            [data-testid="stAppViewContainer"] [data-testid="stTabs"] [data-baseweb="tab"] *,
            [data-testid="stAppViewContainer"] [data-testid="stTabs"] [role="tab"] * {
                color: inherit !important;
                font-size: var(--ws-font-tab, 1.4rem) !important;
                font-weight: 650 !important;
                line-height: 1.25 !important;
            }
            [data-testid="stAppViewContainer"] [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"],
            [data-testid="stAppViewContainer"] [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
                color: #1d4ed8;
            }
        </style>
        <script>
            (function() {
                // 注意：下面是"按文字内容定位标签节点"的兜底匹配词。
                // 各标签正文中不要出现这些词的完整字样，否则那段正文会被误判成标签被一并放大。
                var TARGET_TERMS = ['源文档标题查漏', '源文档标题预处理', '模板样式精简'];

                // 从 ui_theme.py 注入的 :root 变量读取字号，保证全局统一。
                function readTabFont() {
                    var v = '';
                    try {
                        v = getComputedStyle(document.documentElement)
                            .getPropertyValue('--ws-font-tab');
                    } catch (e) { v = ''; }
                    v = (v || '').trim();
                    return v || '1.4rem';
                }

                function styleAsToolboxTab(el) {
                    var font = readTabFont();
                    el.style.fontSize = font;
                    el.style.fontWeight = '650';
                    el.style.lineHeight = '1.25';
                    el.style.minHeight = '2.9rem';
                    el.style.padding = '0.7rem 1.2rem';
                    el.querySelectorAll('*').forEach(function(child) {
                        child.style.fontSize = font;
                        child.style.fontWeight = '650';
                        child.style.lineHeight = '1.25';
                    });
                }

                function applyToolboxTabFont() {
                    var font = readTabFont();
                    // 1) 标准 BaseWeb / role="tab" 命中
                    var containers = document.querySelectorAll('[data-testid="stTabs"]');
                    containers.forEach(function(c) {
                        c.querySelectorAll('[data-baseweb="tab"], [role="tab"]')
                            .forEach(styleAsToolboxTab);
                    });

                    // 2) 兜底：按文字内容直接定位 tab 标题节点
                    TARGET_TERMS.forEach(function(term) {
                        var all = document.body.getElementsByTagName('*');
                        for (var i = 0; i < all.length; i++) {
                            var el = all[i];
                            if (el.children.length === 0) continue;
                            var directText = '';
                            for (var j = 0; j < el.childNodes.length; j++) {
                                var n = el.childNodes[j];
                                if (n.nodeType === 3 && n.nodeValue.indexOf(term) >= 0) {
                                    directText += n.nodeValue;
                                }
                            }
                            if (directText.indexOf(term) >= 0) {
                                styleAsToolboxTab(el);
                                // 父链上的若干层容器也加大（避免父容器 max-height / overflow 限制）
                                var p = el.parentElement;
                                for (var k = 0; k < 4 && p; k++, p = p.parentElement) {
                                    p.style.fontSize = font;
                                    p.style.lineHeight = '1.25';
                                }
                            }
                        }
                    });
                }

                applyToolboxTabFont();
                var obs = new MutationObserver(applyToolboxTabFont);
                obs.observe(document.body, { childList: true, subtree: true });
                setInterval(applyToolboxTabFont, 500);
            })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    tab_leak, tab_title, tab_style = st.tabs([
        "🔍 源文档标题查漏",
        "📑 源文档标题预处理",
        "🧹 模板样式精简",
    ])

    with tab_leak:
        from components.title_leak_check import render_title_leak_check
        render_title_leak_check()

    with tab_title:
        from components.title_preprocess import render_title_preprocess
        render_title_preprocess()

    with tab_style:
        from components.style_cleanup import render_style_cleanup
        render_style_cleanup()
