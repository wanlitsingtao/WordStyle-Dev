# -*- coding: utf-8 -*-
"""
样式映射对话框组件
从 app.py 提取
"""
import streamlit as st
from data_manager import load_user_data, save_user_data

@st.dialog("📊 样式映射配置", width="large")
def show_style_mapping_dialog():
    """显示样式映射配置对话框（使用Streamlit原生dialog）"""
    st.markdown("**请为源文档中的每个样式选择对应的模板样式：**")
    st.markdown("_（未配置的样式将使用系统默认映射规则）_")
    
    # 从 session_state 获取已分析的样式
    file_styles_map = st.session_state.get('file_styles_map', {})
    template_styles = st.session_state.get('template_styles', [])
    source_files = st.session_state.get('current_source_files', None)
    
    if not file_styles_map or not source_files:
        st.warning("⚠️ 请先上传源文档并等待样式分析完成")
        return
    
    if not template_styles:
        st.warning("⚠️ 请先上传模板文档")
        return
    
    # 初始化或加载样式映射（按文件分别存储）
    if 'file_style_mappings' not in st.session_state:
        # 从用户数据中加载样式映射
        user_data = load_user_data(st.session_state.user_id)
        if user_data is None:
            st.warning("⚠️ 用户数据加载失败，请刷新页面重试")
            return
        st.session_state.file_style_mappings = user_data.get('style_mappings', {})
    
    # 如果有多个文件，先选择要配置的文件
    selected_file = None
    if len(source_files) > 1:
        file_options = [sf.name for sf in source_files]
        selected_file_name = st.selectbox("选择要配置的文件", file_options, key="style_mapping_file_selector")
        selected_file = next(sf for sf in source_files if sf.name == selected_file_name)
    else:
        selected_file = source_files[0]
    
    # 获取该文件的样式列表
    source_styles = file_styles_map.get(selected_file.name, [])
    
    if not source_styles:
        st.warning(f"⚠️ 文件 {selected_file.name} 中没有检测到段落样式")
        return
    
    # 获取该文件的当前映射配置
    if selected_file.name not in st.session_state.file_style_mappings:
        st.session_state.file_style_mappings[selected_file.name] = {}
    
    current_mapping = st.session_state.file_style_mappings[selected_file.name]
    
    # 预计算默认值，避免在循环中重复计算
    default_values = {}
    for source_style in source_styles:
        if source_style in current_mapping:
            default_values[source_style] = current_mapping[source_style]
        elif source_style in template_styles:
            default_values[source_style] = source_style
        else:
            default_values[source_style] = "Normal"
    
    # 为每个源样式创建映射行（参照桌面版逻辑）
    updated_mapping = {}
    for source_style in source_styles:
        col1, col2, col3 = st.columns([2.5, 2.5, 1])
        
        with col1:
            st.text(source_style)
        
        with col2:
            # 使用预计算的默认值
            default_value = default_values[source_style]
            
            # 预计算index，避免每次渲染都查找
            style_index = 0
            if default_value in template_styles:
                try:
                    style_index = template_styles.index(default_value)
                except ValueError:
                    style_index = 0
            
            selected = st.selectbox(
                "→",
                options=template_styles,
                index=style_index,
                key=f"mapping_{selected_file.name}_{source_style}",
                label_visibility="collapsed"
            )
            updated_mapping[source_style] = selected
        
        with col3:
            hint = "✓ 已配置" if source_style in current_mapping else "○ 使用默认"
            color = "green" if source_style in current_mapping else "gray"
            st.markdown(f"<span style='color:{color};font-size:0.9em;'>{hint}</span>", unsafe_allow_html=True)
    
    # 保存更新后的映射
    st.session_state.file_style_mappings[selected_file.name] = updated_mapping
    
    # 操作按钮
    st.markdown("---")
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    
    with btn_col1:
        if st.button("✅ 确定", key="confirm_mapping_btn", type="primary", use_container_width=True):
            # 保存样式映射到用户数据
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            st.success(f"✅ 文件 '{selected_file.name}' 的样式映射已保存！您可以继续配置其他文件。")
            # 注意：不要调用st.rerun()，让用户可以继续配置其他文件
    
    with btn_col2:
        if st.button(" 恢复默认", key="reset_mapping_btn", use_container_width=True):
            st.session_state.file_style_mappings[selected_file.name] = {}
            # 保存样式映射到用户数据
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            st.info(f"已恢复文件 '{selected_file.name}' 的默认映射，您可以继续配置其他文件。")
            # 注意：不要调用st.rerun()，让用户可以继续配置其他文件
    
    with btn_col3:
        if st.button("❌ 关闭", key="cancel_mapping_btn", use_container_width=True):
            # [OK] 直接返回，对话框会自然关闭
            return
