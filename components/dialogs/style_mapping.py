# -*- coding: utf-8 -*-
"""
样式映射对话框组件
从 app.py 提取

[2026-07-15] 同步桌面版改进：
1. 表格/图片样式决策从三级改为两级（不受样式映射影响）
2. 添加"设为默认"按钮（保存样式映射+表格/图片样式定义）
3. 新文件加载时回退到保存的默认配置
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
    
    # 如果当前文件没有配置映射，回退到保存的默认映射
    default_style_map = st.session_state.file_style_mappings.get('_default_style_map', {})
    default_tbl_img_config = st.session_state.file_style_mappings.get('_default_tbl_img_config', {})
    
    # 预计算默认值，避免在循环中重复计算
    # 优先级：当前文件配置 > 默认映射配置 > 系统默认
    default_values = {}
    for source_style in source_styles:
        if source_style in current_mapping:
            default_values[source_style] = current_mapping[source_style]
        elif source_style in default_style_map:
            default_values[source_style] = default_style_map[source_style]
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
    
    # ========== 表格/图片样式配置（按文件独立配置） ==========
    st.markdown("---")
    st.markdown("**📋 表格与图片样式（单独配置）**")
    st.markdown("_（选中后，表格/图片段落统一使用指定的模板样式；不选中则保留源文档样式）_")
    
    # 获取该文件的当前表格/图片样式配置
    current_file_config = st.session_state.file_style_mappings.get(selected_file.name, {})
    # 表格/图片样式配置单独存储在映射数据的特殊键中
    tbl_img_config = current_file_config.get('_table_image_style', {})
    
    # 如果当前文件没有 tbl_img_config，回退到默认配置
    if not tbl_img_config and default_tbl_img_config:
        tbl_img_config = default_tbl_img_config
    
    tbl_col1, tbl_col2 = st.columns(2)
    
    with tbl_col1:
        enable_table_style = st.checkbox(
            "表格样式",
            value=tbl_img_config.get('enable_table_style', False),
            help="选中后，表格内段落将统一使用指定的模板样式；不选中则保留源文档样式",
            key=f"enable_table_style_{selected_file.name}"
        )
        
        # 表格目标样式选择
        table_style_default = tbl_img_config.get('table_style', 'Body Text')
        table_style_index = 0
        if table_style_default in template_styles:
            try:
                table_style_index = template_styles.index(table_style_default)
            except ValueError:
                table_style_index = 0
        
        table_style = st.selectbox(
            "表格目标样式",
            options=template_styles,
            index=table_style_index,
            help="表格内段落的统一目标样式",
            key=f"table_style_{selected_file.name}",
            disabled=not enable_table_style
        )
    
    with tbl_col2:
        enable_image_style = st.checkbox(
            "图片样式",
            value=tbl_img_config.get('enable_image_style', False),
            help="选中后，图片段落将统一使用指定的模板样式；不选中则保留源文档样式",
            key=f"enable_image_style_{selected_file.name}"
        )
        
        # 图片目标样式选择
        image_style_default = tbl_img_config.get('image_style', 'Body Text')
        image_style_index = 0
        if image_style_default in template_styles:
            try:
                image_style_index = template_styles.index(image_style_default)
            except ValueError:
                image_style_index = 0
        
        image_style = st.selectbox(
            "图片目标样式",
            options=template_styles,
            index=image_style_index,
            help="图片段落的目标样式",
            key=f"image_style_{selected_file.name}",
            disabled=not enable_image_style
        )
    
    # 保存表格/图片样式配置到映射数据中
    tbl_img_config = {
        'enable_table_style': enable_table_style,
        'table_style': table_style,
        'enable_image_style': enable_image_style,
        'image_style': image_style
    }
    current_file_config['_table_image_style'] = tbl_img_config
    st.session_state.file_style_mappings[selected_file.name] = current_file_config
    
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
    
    with btn_col2:
        if st.button("⭐ 设为默认", key="save_default_mapping_btn", use_container_width=True):
            # 将当前文件的样式映射+表格/图片配置保存为全局默认
            st.session_state.file_style_mappings['_default_style_map'] = updated_mapping.copy()
            st.session_state.file_style_mappings['_default_tbl_img_config'] = tbl_img_config.copy()
            
            # 持久化到用户数据
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            configured_count = sum(1 for v in updated_mapping.values() if v)
            tbl_on = tbl_img_config.get('enable_table_style', False)
            img_on = tbl_img_config.get('enable_image_style', False)
            tbl_info = f"表格样式: {'启用 (' + tbl_img_config.get('table_style', '') + ')' if tbl_on else '未启用'}"
            tbl_info += f"，图片样式: {'启用 (' + tbl_img_config.get('image_style', '') + ')' if img_on else '未启用'}"
            st.success(f"⭐ 已设为默认！共 {configured_count} 个样式映射，{tbl_info}。新文件将自动使用此配置。")
    
    with btn_col3:
        if st.button("🔄 恢复默认", key="reset_mapping_btn", use_container_width=True):
            st.session_state.file_style_mappings[selected_file.name] = {}
            # 保存样式映射到用户数据
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            st.info(f"已恢复文件 '{selected_file.name}' 的默认映射，您可以继续配置其他文件。")
