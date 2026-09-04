# -*- coding: utf-8 -*-
"""
工具箱页（T04）
st.tabs 组合两个预处理功能：源文档标题预处理 + 模板样式精简。
"""
import streamlit as st


def render_toolbox_page():
    """工具箱页入口（供 st.navigation 调用）。"""
    from components.sidebar import render_sidebar
    render_sidebar("toolbox")

    st.markdown(
        """
        <style>
            /* 工具箱的两个工作区标签需要比主区提示文字更醒目。 */
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [data-baseweb="tab"],
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [role="tab"] {
                min-height: 2.85rem;
                padding: 0.65rem 1.1rem;
                color: #475569;
                font-size: 1rem !important;
                font-weight: 650 !important;
            }
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [data-baseweb="tab"] p,
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [data-baseweb="tab"] span,
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [role="tab"] p,
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [role="tab"] span {
                color: inherit !important;
                font-size: 1rem !important;
                font-weight: 650 !important;
                line-height: 1.25 !important;
            }
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"],
            [data-testid="stAppViewContainer"] main [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
                color: #1d4ed8;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    tab_title, tab_style = st.tabs(["📑 源文档标题预处理", "🧹 模板样式精简"])

    with tab_title:
        from components.title_preprocess import render_title_preprocess
        render_title_preprocess()

    with tab_style:
        from components.style_cleanup import render_style_cleanup
        render_style_cleanup()
