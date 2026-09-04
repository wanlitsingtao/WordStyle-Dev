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

    st.title("🛠️ 工具箱")

    tab_title, tab_style = st.tabs(["📑 源文档标题预处理", "🧹 模板样式精简"])

    with tab_title:
        from components.title_preprocess import render_title_preprocess
        render_title_preprocess()

    with tab_style:
        from components.style_cleanup import render_style_cleanup
        render_style_cleanup()
