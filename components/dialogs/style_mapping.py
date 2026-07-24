# -*- coding: utf-8 -*-
"""
样式映射对话框组件
从 app.py 提取

[2026-07-15] 同步桌面版改进：
1. 表格/图片样式决策从三级改为两级（不受样式映射影响）
2. 添加"设为默认"按钮（保存样式映射+表格/图片样式定义）
3. 新文件加载时回退到保存的默认配置

[2026-07-16] 同步桌面版全部功能：
1. 支持双列样式映射（原文目标样式 + 应答目标样式，copy_chapter模式）
2. 表格/图片/列表兜底配置支持原文+应答原文双列
3. 完整的四步配置流程（标题映射、应答句配置、样式映射、兜底配置）
"""
import streamlit as st
from data_manager import load_user_data, save_user_data


@st.dialog("📊 样式映射配置", width="large")
def show_style_mapping_dialog():
    """显示样式映射配置对话框（使用Streamlit原生dialog）"""
    # 判断是否处于copy_chapter模式（需要双列）
    answer_mode = st.session_state.get('answer_mode_config', 'before_heading')
    do_answer = st.session_state.get('do_answer_config', False)
    is_dual = (do_answer and answer_mode == 'copy_chapter')
    
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
    
    # 分离标题样式和正文样式
    heading_styles = []
    body_styles = []
    for s in source_styles:
        is_heading = False
        if s.startswith('[大纲级别') or s.startswith('[Outline'):
            is_heading = True
        for i in range(1, 10):
            if s == f'Heading {i}' or s == f'heading {i}' or s == f'Heading{i}':
                is_heading = True
                break
            # 中文标题
            if s == f'标题 {i}' or s == f'标题{i}':
                is_heading = True
                break
        if is_heading:
            heading_styles.append(s)
        else:
            body_styles.append(s)
    
    # 获取该文件的当前映射配置
    if selected_file.name not in st.session_state.file_style_mappings:
        st.session_state.file_style_mappings[selected_file.name] = {}
    
    current_mapping = st.session_state.file_style_mappings[selected_file.name]
    
    # 如果当前文件没有配置映射，回退到保存的默认映射
    default_style_map = st.session_state.file_style_mappings.get('_default_style_map', {})
    default_tbl_img_config = st.session_state.file_style_mappings.get('_default_tbl_img_config', {})
    
    # ===== 步骤1: 标题样式映射 =====
    st.markdown("---")
    st.markdown("**1. 标题样式映射（统一，不分原文/应答句）**")
    
    if not heading_styles:
        st.caption("（当前源文档未检测到标题样式）")
    else:
        heading_mapping = {}
        for source_style in heading_styles:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.text(source_style)
            with col2:
                # 预计算默认值
                default_val = current_mapping.get(source_style, default_style_map.get(source_style, 
                                                   source_style if source_style in template_styles else "Normal"))
                if default_val not in template_styles:
                    default_val = source_style if source_style in template_styles else "Normal"
                
                style_index = 0
                if default_val in template_styles:
                    try:
                        style_index = template_styles.index(default_val)
                    except ValueError:
                        style_index = 0
                
                selected = st.selectbox(
                    "→",
                    options=template_styles,
                    index=style_index,
                    key=f"heading_{selected_file.name}_{source_style}",
                    label_visibility="collapsed"
                )
                heading_mapping[source_style] = selected
    
    # ===== 步骤2: 样式映射（正文+列表段落）- 根据是否双列模式 =====
    st.markdown("---")
    if is_dual:
        st.markdown("**2. 样式映射（正文+列表段落）- 双列模式（原文/应答原文）**")
    else:
        st.markdown("**2. 样式映射（正文+列表段落）**")
    
    if not body_styles:
        st.warning("⚠️ 当前源文档未检测到正文样式")
        body_mapping = {}
        answer_mapping = {}
    else:
        # 表头
        if is_dual:
            hdr_col1, hdr_col2, hdr_col3 = st.columns([2, 2, 2])
            with hdr_col1:
                st.markdown("**源样式**")
            with hdr_col2:
                st.markdown("**原文目标样式**")
            with hdr_col3:
                st.markdown("**应答目标样式**")
        else:
            hdr_col1, hdr_col2 = st.columns([2, 2])
            with hdr_col1:
                st.markdown("**源样式**")
            with hdr_col2:
                st.markdown("**目标样式**")
        
        body_mapping = {}
        answer_mapping = {}
        
        for source_style in body_styles:
            if is_dual:
                col1, col2, col3 = st.columns([2, 2, 2])
                with col1:
                    st.text(source_style)
                with col2:
                    # 原文目标样式
                    default_val = current_mapping.get(source_style, default_style_map.get(source_style, "Body Text"))
                    if default_val not in template_styles:
                        default_val = "Body Text"
                    
                    style_index = 0
                    if default_val in template_styles:
                        try:
                            style_index = template_styles.index(default_val)
                        except ValueError:
                            style_index = 0
                    
                    selected = st.selectbox(
                        "原文→",
                        options=template_styles,
                        index=style_index,
                        key=f"body_{selected_file.name}_{source_style}",
                        label_visibility="collapsed"
                    )
                    body_mapping[source_style] = selected
                
                with col3:
                    # 应答目标样式
                    answer_key = f"answer_{source_style}"
                    answer_default = current_mapping.get(answer_key, default_style_map.get(answer_key, default_val))
                    if answer_default not in template_styles:
                        answer_default = default_val
                    
                    answer_index = 0
                    if answer_default in template_styles:
                        try:
                            answer_index = template_styles.index(answer_default)
                        except ValueError:
                            answer_index = 0
                    
                    answer_selected = st.selectbox(
                        "应答→",
                        options=template_styles,
                        index=answer_index,
                        key=f"answer_{selected_file.name}_{source_style}",
                        label_visibility="collapsed"
                    )
                    answer_mapping[source_style] = answer_selected
            else:
                col1, col2 = st.columns([2, 2])
                with col1:
                    st.text(source_style)
                with col2:
                    # 单列模式
                    default_val = current_mapping.get(source_style, default_style_map.get(source_style, 
                                                       source_style if source_style in template_styles else "Body Text"))
                    if default_val not in template_styles:
                        default_val = source_style if source_style in template_styles else "Body Text"
                    
                    style_index = 0
                    if default_val in template_styles:
                        try:
                            style_index = template_styles.index(default_val)
                        except ValueError:
                            style_index = 0
                    
                    selected = st.selectbox(
                        "→",
                        options=template_styles,
                        index=style_index,
                        key=f"body_{selected_file.name}_{source_style}",
                        label_visibility="collapsed"
                    )
                    body_mapping[source_style] = selected
    
    # 合并映射（标题 + 正文）
    updated_mapping = {}
    updated_mapping.update(heading_mapping)
    updated_mapping.update(body_mapping)
    # 双列模式：保存应答映射
    if is_dual:
        for src, val in answer_mapping.items():
            updated_mapping[f"answer_{src}"] = val
    
    # 保存更新后的映射
    st.session_state.file_style_mappings[selected_file.name] = updated_mapping
    
    # ========== 表格/图片样式配置（按文件独立配置，支持双列） ==========
    st.markdown("---")
    st.markdown("**3. 表格/图片/列表兜底配置**")
    
    # 获取该文件的当前表格/图片样式配置
    current_file_config = st.session_state.file_style_mappings.get(selected_file.name, {})
    # 表格/图片样式配置单独存储在映射数据的特殊键中
    tbl_img_config = current_file_config.get('_table_image_style', {})
    
    # 如果当前文件没有 tbl_img_config，回退到默认配置
    if not tbl_img_config and default_tbl_img_config:
        tbl_img_config = default_tbl_img_config
    
    # ---- 表格与图片（原文+应答原文双列） ----
    st.markdown("**表格与图片兜底样式**")
    st.markdown("_（选中后，表格/图片段落统一使用指定的模板样式）_")
    
    # 使用列布局：表格(原文+应答原文) + 图片(原文+应答原文)
    tbl_img_header_cols = st.columns([1, 2, 2, 1, 2, 2])
    labels = ["", "原文", "应答原文", "", "原文", "应答原文"]
    for i, label in enumerate(labels):
        if label:
            tbl_img_header_cols[i].markdown(f"**{label}**")
    
    tbl_img_row = st.columns([1, 2, 2, 1, 2, 2])
    
    with tbl_img_row[0]:
        enable_table_style = st.checkbox(
            "表格",
            value=tbl_img_config.get('enable_table_style', False),
            help="选中后，表格内段落将统一使用指定的模板样式",
            key=f"enable_table_style_{selected_file.name}"
        )
    
    with tbl_img_row[1]:
        table_style_default = tbl_img_config.get('table_style', 'Body Text')
        table_style_index = 0
        if table_style_default in template_styles:
            try:
                table_style_index = template_styles.index(table_style_default)
            except ValueError:
                table_style_index = 0
        
        table_style = st.selectbox(
            "表格原文目标样式",
            options=template_styles,
            index=table_style_index,
            key=f"table_style_{selected_file.name}",
            disabled=not enable_table_style,
            label_visibility="collapsed"
        )
    
    with tbl_img_row[2]:
        table_answer_default = tbl_img_config.get('table_answer_style', table_style_default)
        table_answer_index = 0
        if table_answer_default in template_styles:
            try:
                table_answer_index = template_styles.index(table_answer_default)
            except ValueError:
                table_answer_index = 0
        
        table_answer_style = st.selectbox(
            "表格应答目标样式",
            options=template_styles,
            index=table_answer_index,
            key=f"table_answer_style_{selected_file.name}",
            disabled=not (enable_table_style and is_dual),
            label_visibility="collapsed"
        )
    
    with tbl_img_row[3]:
        enable_image_style = st.checkbox(
            "图片",
            value=tbl_img_config.get('enable_image_style', False),
            help="选中后，图片段落将统一使用指定的模板样式",
            key=f"enable_image_style_{selected_file.name}"
        )
    
    with tbl_img_row[4]:
        image_style_default = tbl_img_config.get('image_style', 'Body Text')
        image_style_index = 0
        if image_style_default in template_styles:
            try:
                image_style_index = template_styles.index(image_style_default)
            except ValueError:
                image_style_index = 0
        
        image_style = st.selectbox(
            "图片原文目标样式",
            options=template_styles,
            index=image_style_index,
            key=f"image_style_{selected_file.name}",
            disabled=not enable_image_style,
            label_visibility="collapsed"
        )
    
    with tbl_img_row[5]:
        image_answer_default = tbl_img_config.get('image_answer_style', image_style_default)
        image_answer_index = 0
        if image_answer_default in template_styles:
            try:
                image_answer_index = template_styles.index(image_answer_default)
            except ValueError:
                image_answer_index = 0
        
        image_answer_style = st.selectbox(
            "图片应答目标样式",
            options=template_styles,
            index=image_answer_index,
            key=f"image_answer_style_{selected_file.name}",
            disabled=not (enable_image_style and is_dual),
            label_visibility="collapsed"
        )
    
    # ---- 列表段落兜底（原文+应答原文） ----
    st.markdown("---")
    st.markdown("**列表段落（未映射）兜底**")
    
    list_row = st.columns([1, 1, 2, 1, 1, 2])
    
    with list_row[0]:
        st.caption("**原文**")
    
    with list_row[1]:
        # 原文：符号/样式 radio
        list_method = st.radio(
            "原文方式",
            options=["bullet", "style"],
            format_func=lambda x: "符号" if x == "bullet" else "样式",
            index=0 if st.session_state.get('list_method_config', 'bullet') == "bullet" else 1,
            horizontal=True,
            key=f"list_method_{selected_file.name}",
            label_visibility="collapsed"
        )
    
    with list_row[2]:
        if list_method == "bullet":
            list_bullet_val = st.text_input(
                "原文符号",
                value=st.session_state.get('list_bullet_config', '•'),
                key=f"list_bullet_{selected_file.name}",
                label_visibility="collapsed"
            )
            list_style_val = st.session_state.get('list_style_config', 'Body Text')
        else:
            list_style_idx = 0
            list_style_cfg = st.session_state.get('list_style_config', 'Body Text')
            if list_style_cfg in template_styles:
                try:
                    list_style_idx = template_styles.index(list_style_cfg)
                except ValueError:
                    list_style_idx = 0
            list_style_val = st.selectbox(
                "原文目标样式",
                options=template_styles,
                index=list_style_idx,
                key=f"list_style_{selected_file.name}",
                label_visibility="collapsed"
            )
            list_bullet_val = st.session_state.get('list_bullet_config', '•')
    
    with list_row[3]:
        st.caption("**答原文**")
    
    with list_row[4]:
        list_answer_method = st.radio(
            "答原文方式",
            options=["bullet", "style"],
            format_func=lambda x: "符号" if x == "bullet" else "样式",
            index=0 if st.session_state.get('list_answer_method_config', 'bullet') == "bullet" else 1,
            horizontal=True,
            key=f"list_answer_method_{selected_file.name}",
            label_visibility="collapsed"
        )
    
    with list_row[5]:
        if list_answer_method == "bullet":
            list_answer_bullet_val = st.text_input(
                "答原文符号",
                value=st.session_state.get('list_answer_bullet_config', '•'),
                key=f"list_answer_bullet_{selected_file.name}",
                label_visibility="collapsed"
            )
            list_answer_style_val = st.session_state.get('list_answer_style_config', 'Body Text')
        else:
            list_answer_style_idx = 0
            list_answer_style_cfg = st.session_state.get('list_answer_style_config', 'Body Text')
            if list_answer_style_cfg in template_styles:
                try:
                    list_answer_style_idx = template_styles.index(list_answer_style_cfg)
                except ValueError:
                    list_answer_style_idx = 0
            list_answer_style_val = st.selectbox(
                "答原文目标样式",
                options=template_styles,
                index=list_answer_style_idx,
                key=f"list_answer_style_{selected_file.name}",
                disabled=not is_dual,
                label_visibility="collapsed"
            )
            list_answer_bullet_val = st.session_state.get('list_answer_bullet_config', '•')
    
    # 保存表格/图片样式配置到映射数据中
    tbl_img_config_new = {
        'enable_table_style': enable_table_style,
        'table_style': table_style,
        'table_answer_style': table_answer_style,
        'enable_image_style': enable_image_style,
        'image_style': image_style,
        'image_answer_style': image_answer_style,
    }
    current_file_config['_table_image_style'] = tbl_img_config_new
    
    # 保存列表兜底配置到映射数据
    list_config_new = {
        'method': list_method,
        'bullet': list_bullet_val,
        'style': list_style_val,
        'answer_method': list_answer_method,
        'answer_bullet': list_answer_bullet_val,
        'answer_style': list_answer_style_val,
    }
    current_file_config['_list_config'] = list_config_new
    
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
            st.session_state.file_style_mappings['_default_tbl_img_config'] = tbl_img_config_new.copy()
            
            # 持久化到用户数据
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            configured_count = sum(1 for v in updated_mapping.values() if v)
            st.success(f"⭐ 已设为默认！共 {configured_count} 个样式映射。新文件将自动使用此配置。")
    
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
