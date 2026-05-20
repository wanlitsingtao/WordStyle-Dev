# -*- coding: utf-8 -*-
"""
转换配置区组件
从 app.py 提取
"""
import streamlit as st


def get_answer_mode_options():
    """获取应答句插入模式选项"""
    return {
        'before_heading': '章节前插入',
        'after_heading': '章节后插入',
        'copy_chapter': '章节招标原文+应答句+招标原文副本',
        'before_paragraph': '逐段前应答',
        'after_paragraph': '逐段后应答'
    }


@st.fragment
def render_conversion_config():
    """
    渲染转换配置区（使用fragment优化性能）
    
    优化点：
    1. 使用@st.fragment隔离，避免用户交互导致全局重渲染
    2. 仅在值真正改变时才更新session_state
    3. 预计算索引，避免重复遍历
    """
    
    # 第一行:四个选项横向等距分布
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📊 样式映射", key="open_style_mapping_btn", use_container_width=True, help="如果不采用系统给的默认配置,可自定义样式映射"):
            # 直接调用对话框,不使用session_state标记
            from components.dialogs.style_mapping import show_style_mapping_dialog
            show_style_mapping_dialog()
            # 注意：不要在这里return，让函数继续执行以渲染其他控件

    with col2:
        do_mood = st.checkbox(
            "祈使语气转换", 
            value=st.session_state.do_mood_config, 
            help="将文档中的祈使语气转换为投标人语气",
            key="mood_checkbox"
        )
        # 仅在值改变时更新session_state，避免不必要的重渲染
        if do_mood != st.session_state.get('do_mood_config'):
            st.session_state.do_mood_config = do_mood

    with col3:
        do_answer = st.checkbox(
            "插入应答句", 
            value=st.session_state.do_answer_config, 
            help="在章节前/后或段落前/后插入应答句",
            key="answer_checkbox"
        )
        # 仅在值改变时更新session_state
        if do_answer != st.session_state.get('do_answer_config'):
            st.session_state.do_answer_config = do_answer

    with col4:
        list_bullet = st.text_input(
            "列表符号", 
            value=st.session_state.list_bullet_config, 
            help="列表段落的符号",
            key="bullet_input"
        )
        # 仅在值改变时更新session_state
        if list_bullet != st.session_state.get('list_bullet_config'):
            st.session_state.list_bullet_config = list_bullet

    # 第二行：应答句详细配置（仅当勾选"插入应答句"时显示）
    if do_answer:
        st.markdown("---")
        st.markdown("**ℹ️ 应答句配置**")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            answer_text = st.text_input(
                "应答句文本",
                value=st.session_state.answer_text_config,
                help="插入的应答句内容",
                key="answer_text_input"
            )
            # 仅在值改变时更新
            if answer_text != st.session_state.get('answer_text_config'):
                st.session_state.answer_text_config = answer_text
        
        with col_b:
            # 获取模板样式列表（使用缓存的引用）
            template_styles = st.session_state.get('template_styles', ["Normal"])
            
            # 预计算index，避免每次渲染都查找
            style_index = 0
            if st.session_state.answer_style_config in template_styles:
                try:
                    style_index = template_styles.index(st.session_state.answer_style_config)
                except ValueError:
                    style_index = 0
            
            answer_style = st.selectbox(
                "应答句样式",
                options=template_styles,
                index=style_index,
                help="应答句的段落样式",
                key="answer_style_select"
            )
            # 实时更新 session_state
            st.session_state.answer_style_config = answer_style
        
        with col_c:
            # 使用缓存的options，保持引用稳定
            answer_mode_options = get_answer_mode_options()
            
            # 预计算mode_keys和index，避免每次渲染都创建新列表
            if 'answer_mode_keys_cache' not in st.session_state:
                st.session_state.answer_mode_keys_cache = list(answer_mode_options.keys())
            mode_keys = st.session_state.answer_mode_keys_cache
            
            # 预计算index
            mode_index = 0
            if st.session_state.answer_mode_config in answer_mode_options:
                try:
                    mode_index = mode_keys.index(st.session_state.answer_mode_config)
                except ValueError:
                    mode_index = 0
            
            answer_mode = st.selectbox(
                "插入模式",
                options=mode_keys,
                format_func=lambda x: answer_mode_options[x],
                index=mode_index,
                help="应答句的插入位置模式",
                key="answer_mode_select"
            )
            # 仅在值改变时更新
            if answer_mode != st.session_state.get('answer_mode_config'):
                st.session_state.answer_mode_config = answer_mode
    else:
        # 未勾选时设置默认值
        answer_text = st.session_state.answer_text_config
        answer_style = st.session_state.answer_style_config
        answer_mode = st.session_state.answer_mode_config
    
    # 返回配置值供后续使用
    return do_mood, do_answer, list_bullet, answer_text, answer_style, answer_mode
