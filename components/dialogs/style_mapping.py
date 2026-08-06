# -*- coding: utf-8 -*-
"""
样式映射对话框组件（完全参照桌面版四步配置流程）

四步配置流程（与桌面版完全一致）：
Step 1: 标题样式映射（统一配置，不分原文/应答句）
Step 2: 应答句配置（是否启用、文本、样式、模式、原文样式、应答原文样式）
Step 3: 样式映射（正文+列表段落，根据应答模式动态切换单列/双列）
Step 4: 表格/图片/列表兜底配置（支持双列）+ 清除章节标签

功能：
- 按文件分别存储映射配置
- 支持设为默认（持久化到用户数据）
- 支持恢复默认
- 双列模式联动（与桌面版一致）
"""
import streamlit as st
from data_manager import load_user_data, save_user_data


def get_answer_mode_options():
    """获取应答句插入模式选项（与桌面版保持一致）"""
    return {
        'before_heading': '章节标题后插入',
        'after_heading': '章节末尾插入',
        'copy_chapter': '原文+应答句+应答原文',
        'before_paragraph': '逐段前应答',
        'after_paragraph': '逐段后应答'
    }


@st.fragment
def _render_step4_fallback(selected_file_name, template_styles, current_file_mapping,
                            default_tbl_img_config, default_list_config,
                            default_remove_chapter_label, is_dual):
    """Step 4: 表格/图片/列表兜底配置（使用 fragment 避免每次操作都刷新整个页面）"""
    st.markdown("---")
    st.markdown("**4. 表格/图片/列表兜底配置**")

    # 获取表格/图片现有配置
    tbl_img_config = current_file_mapping.get('_table_image_style', {})
    if not tbl_img_config and default_tbl_img_config:
        tbl_img_config = default_tbl_img_config

    # ---- 表格与图片（带原文/应答原文双列） ----
    st.markdown("**表格与图片兜底样式**")
    st.markdown("_（选中后，表格/图片段落统一使用指定的模板样式）_")

    # 布局：使用grid对齐（与桌面版一致）
    tbl_img_hdr = st.columns([1, 2, 2, 1, 1, 2, 2])
    tbl_img_hdr[1].markdown("**原文**")
    tbl_img_hdr[2].markdown("**应答原文**")
    tbl_img_hdr[5].markdown("**原文**")
    tbl_img_hdr[6].markdown("**应答原文**")

    # 第1行：表格
    tbl_img_row = st.columns([1, 2, 2, 1, 1, 2, 2])

    with tbl_img_row[0]:
        enable_table = st.checkbox("表格",
            value=tbl_img_config.get('enable_table_style', False),
            key=f"enable_table_{selected_file_name}")

    with tbl_img_row[1]:
        td = tbl_img_config.get('table_style', 'Body Text')
        ti = template_styles.index(td) if td in template_styles else 0
        table_style = st.selectbox("表格原文", options=template_styles, index=ti,
            key=f"table_style_{selected_file_name}", disabled=not enable_table,
            label_visibility="collapsed")

    with tbl_img_row[2]:
        tad = tbl_img_config.get('table_answer_style', table_style)
        tai = template_styles.index(tad) if tad in template_styles else 0
        table_answer_style = st.selectbox("表格答原文", options=template_styles, index=tai,
            key=f"table_answer_{selected_file_name}",
            disabled=not (enable_table and is_dual),
            label_visibility="collapsed")

    with tbl_img_row[4]:
        enable_image = st.checkbox("图片",
            value=tbl_img_config.get('enable_image_style', False),
            key=f"enable_image_{selected_file_name}")

    with tbl_img_row[5]:
        imd = tbl_img_config.get('image_style', 'Body Text')
        imi = template_styles.index(imd) if imd in template_styles else 0
        image_style = st.selectbox("图片原文", options=template_styles, index=imi,
            key=f"image_style_{selected_file_name}", disabled=not enable_image,
            label_visibility="collapsed")

    with tbl_img_row[6]:
        iad = tbl_img_config.get('image_answer_style', image_style)
        iai = template_styles.index(iad) if iad in template_styles else 0
        image_answer_style = st.selectbox("图片答原文", options=template_styles, index=iai,
            key=f"image_answer_{selected_file_name}",
            disabled=not (enable_image and is_dual),
            label_visibility="collapsed")

    # ---- 列表段落兜底 ----
    st.markdown("---")
    st.markdown("**列表段落（未映射）兜底**")
    st.caption("配置源文档中未在样式映射中配置的列表段落的处理方式")

    # 获取列表配置
    list_config = current_file_mapping.get('_list_config', default_list_config)
    enable_list_val = list_config.get('enable_list', st.session_state.get('enable_list_style_config', True))
    list_method_val = list_config.get('method', st.session_state.get('list_method_config', 'bullet'))
    list_bullet_val = list_config.get('bullet', st.session_state.get('list_bullet_config', '•'))
    list_style_val = list_config.get('style', st.session_state.get('list_style_config', 'Body Text'))
    list_answer_method_val = list_config.get('answer_method', st.session_state.get('list_answer_method_config', 'bullet'))
    list_answer_bullet_val = list_config.get('answer_bullet', st.session_state.get('list_answer_bullet_config', '•'))
    list_answer_style_val = list_config.get('answer_style', st.session_state.get('list_answer_style_config', 'Body Text'))

    # 列表段落兜底：3列布局
    list_row = st.columns([3, 5, 5])
    with list_row[0]:
        list_enable = st.checkbox("列表段落\n（未映射）", value=enable_list_val,
            key=f"enable_list_{selected_file_name}",
            help="勾选后，未映射的列表段落将按照下方配置的方式处理")
    with list_row[1]:
        st.markdown("**原文**")
    with list_row[2]:
        st.markdown("**答原文**")

    # 第二行：原文设置 + 答原文设置
    list_cols = st.columns([3, 5, 5])
    with list_cols[0]:
        st.text("")
    with list_cols[1]:
        l_method = st.radio("原文方式",
            options=["bullet", "style"],
            format_func=lambda x: "符号" if x == "bullet" else "样式",
            index=0 if list_method_val == "bullet" else 1,
            horizontal=True, key=f"list_method_{selected_file_name}",
            label_visibility="collapsed",
            disabled=not list_enable)

        if l_method == "bullet":
            l_bullet = st.text_input("原文符号", value=list_bullet_val,
                key=f"list_bullet_{selected_file_name}", label_visibility="collapsed",
                disabled=not list_enable)
        else:
            lsi = template_styles.index(list_style_val) if list_style_val in template_styles else 0
            st.selectbox("原文目标样式", options=template_styles, index=lsi,
                key=f"list_style_{selected_file_name}", label_visibility="collapsed",
                disabled=not list_enable)

    with list_cols[2]:
        la_method = st.radio("答原文方式",
            options=["bullet", "style"],
            format_func=lambda x: "符号" if x == "bullet" else "样式",
            index=0 if list_answer_method_val == "bullet" else 1,
            horizontal=True, key=f"list_answer_method_{selected_file_name}",
            label_visibility="collapsed",
            disabled=not (list_enable and is_dual))

        if la_method == "bullet":
            st.text_input("答原文符号", value=list_answer_bullet_val,
                key=f"list_answer_bullet_{selected_file_name}", label_visibility="collapsed",
                disabled=not (list_enable and is_dual))
        else:
            lasi = template_styles.index(list_answer_style_val) if list_answer_style_val in template_styles else 0
            st.selectbox("答原文目标样式", options=template_styles, index=lasi,
                key=f"list_answer_style_{selected_file_name}", label_visibility="collapsed",
                disabled=not (list_enable and is_dual))

    # 清除章节标签 checkbox
    st.markdown("---")
    st.checkbox(
        '清除标题中的"第X章/第X节"等字样',
        value=current_file_mapping.get('_remove_chapter_label',
               default_remove_chapter_label if isinstance(default_remove_chapter_label, bool)
               else st.session_state.get('remove_chapter_label_config', False)),
        key=f"remove_chapter_label_{selected_file_name}"
    )


@st.dialog("📊 样式映射配置", width="large")
def show_style_mapping_dialog():
    """显示样式映射配置对话框（完整四步流程，完全参照桌面版）"""
    # 从 session_state 获取配置（允许空值，对话框仍可打开显示空内容）
    file_styles_map = st.session_state.get('file_styles_map', {})
    template_styles = st.session_state.get('template_styles', [])
    source_files = st.session_state.get('current_source_files', None)

    # 初始化或加载样式映射（健壮处理：user_id 可能为空）
    if 'file_style_mappings' not in st.session_state:
        try:
            uid = st.session_state.get('user_id', 'default')
        except Exception:
            uid = 'default'
        try:
            user_data = load_user_data(uid)
        except Exception:
            user_data = None
        if user_data is None:
            user_data = {}
        st.session_state.file_style_mappings = user_data.get('style_mappings', {}) if user_data else {}

    # 选择当前配置的文件
    selected_file = None
    if source_files:
        if len(source_files) > 1:
            file_options = [sf.name for sf in source_files]
            selected_file_name = st.selectbox("选择要配置的文件", file_options, key="style_mapping_file_selector")
            selected_file = next(sf for sf in source_files if sf.name == selected_file_name)
        else:
            selected_file = source_files[0]

    # 获取该文件的样式列表
    source_styles = []
    if selected_file and selected_file.name in file_styles_map:
        source_styles = file_styles_map.get(selected_file.name, [])

    # 分离标题样式和正文样式
    heading_styles = []
    body_styles = []
    for s in source_styles:
        is_heading = False
        if s.startswith('[大纲级别') or s.startswith('[Outline'):
            is_heading = True
        for i in range(1, 10):
            if s in (f'Heading {i}', f'heading {i}', f'Heading{i}', f'标题 {i}', f'标题{i}'):
                is_heading = True
                break
        if is_heading:
            heading_styles.append(s)
        else:
            body_styles.append(s)

    # 获取当前文件映射 — 未选择文件时显示完整引导界面
    if not selected_file:
        st.warning("⚠️ 未检测到源文档，无法配置样式映射")
        st.markdown("""
        **请先完成以下操作：**
        
        1. 📄 上传**源文档**（.docx 格式）
        2. 📋 上传**模板文档**（.docx 格式）
        3. 🔄 重新点击 **"📊 配置样式映射"** 按钮
        
        ---
        💡 *源文档和模板文档上传后，系统自动分析样式，届时即可在此配置映射关系。*
        """)
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            if st.button("🔙 关闭对话框", key="close_empty_style_map", use_container_width=True):
                st.rerun()
        return

    # 保护：模板样式为空时无法配置映射
    if not template_styles:
        st.warning("⚠️ 未检测到模板文档样式，无法配置样式映射")
        st.markdown("""
        **请先完成以下操作：**
        
        1. 📋 上传**模板文档**（.docx 格式）
        2. 🔄 重新点击 **"📊 配置样式映射"** 按钮
        
        ---
        💡 *模板文档定义了目标样式，上传后系统自动提取所有段落样式。*
        """)
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            if st.button("🔙 关闭对话框", key="close_no_template_style_map", use_container_width=True):
                st.rerun()
        return

    if selected_file.name not in st.session_state.file_style_mappings:
        st.session_state.file_style_mappings[selected_file.name] = {}

    current_file_mapping = st.session_state.file_style_mappings[selected_file.name]

    # 回退默认映射
    default_style_map = st.session_state.file_style_mappings.get('_default_style_map', {})
    default_tbl_img_config = st.session_state.file_style_mappings.get('_default_tbl_img_config', {})
    default_answer_config = st.session_state.file_style_mappings.get('_default_answer_config', {})
    default_list_config = st.session_state.file_style_mappings.get('_default_list_config', {})
    # ★ 修复：remove_chapter_label 也需从默认配置中恢复
    # _default_style_map 可能包含 _remove_chapter_label（与桌面版 default_config.json 一致）
    default_remove_chapter_label = (
        st.session_state.file_style_mappings.get('_default_remove_chapter_label')
        if '_default_remove_chapter_label' in st.session_state.file_style_mappings
        else default_style_map.get('_remove_chapter_label', False)
    )

    # ====================================================================
    # Step 1: 标题样式映射（统一，不分原文/应答句）
    # ====================================================================
    st.markdown("---")
    st.markdown("**1. 标题样式映射（统一，不分原文/应答句）**")

    heading_mapping = {}
    if not heading_styles:
        st.caption("（当前源文档未检测到标题样式）")
    else:
        for source_style in heading_styles:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.text(source_style)
            with col2:
                default_val = current_file_mapping.get(source_style, default_style_map.get(source_style,
                                                       source_style if source_style in template_styles else "Normal"))
                if default_val not in template_styles:
                    default_val = source_style if source_style in template_styles else "Normal"
                style_index = template_styles.index(default_val) if default_val in template_styles else 0
                selected = st.selectbox(
                    "→", options=template_styles, index=style_index,
                    key=f"heading_{selected_file.name}_{source_style}", label_visibility="collapsed"
                )
                heading_mapping[source_style] = selected

    # ====================================================================
    # Step 2: 应答句配置（完全参照桌面版）
    # ====================================================================
    st.markdown("---")
    st.markdown("**2. 应答句配置**")

    # 初始化应答句配置值
    default_answer_cfg = current_file_mapping.get('_answer_config', default_answer_config)
    do_answer_val = default_answer_cfg.get('do_answer', st.session_state.get('do_answer_config', False))
    answer_text_val = default_answer_cfg.get('answer_text', st.session_state.get('answer_text_config', '应答：本投标人理解并满足要求。'))
    answer_style_val = default_answer_cfg.get('answer_style', st.session_state.get('answer_style_config', 'Normal'))
    answer_mode_val = default_answer_cfg.get('answer_mode', st.session_state.get('answer_mode_config', 'copy_chapter'))
    answer_source_style_val = default_answer_cfg.get('answer_source_style', st.session_state.get('answer_source_style_config', ''))
    answer_copy_style_val = default_answer_cfg.get('answer_copy_style', st.session_state.get('answer_copy_style_config', ''))

    # 第1行：启用 + 文本
    ans_row1 = st.columns([1, 4])
    with ans_row1[0]:
        do_answer = st.checkbox("插入应答句", value=do_answer_val,
                                help="在章节前/后或段落前/后插入应答句",
                                key=f"ans_do_answer_{selected_file.name}")
    with ans_row1[1]:
        answer_text = st.text_input("文本", value=answer_text_val,
                                    help="插入的应答句内容",
                                    key=f"ans_text_{selected_file.name}",
                                    label_visibility="collapsed",
                                    disabled=not do_answer)

    # 第2行：答样式 + 插入模式 + 原文 + 答原文（与桌面版完全一致）
    ans_row2 = st.columns(4)
    with ans_row2[0]:
        style_idx = template_styles.index(answer_style_val) if answer_style_val in template_styles else 0
        answer_style = st.selectbox("答样式", options=template_styles, index=style_idx,
                                    key=f"ans_style_{selected_file.name}",
                                    disabled=not do_answer)
    with ans_row2[1]:
        mode_options = get_answer_mode_options()
        mode_keys = list(mode_options.keys())
        mode_idx = mode_keys.index(answer_mode_val) if answer_mode_val in mode_keys else 2
        answer_mode = st.selectbox("插入模式", options=mode_keys,
                                   format_func=lambda x: mode_options[x], index=mode_idx,
                                   key=f"ans_mode_{selected_file.name}",
                                   disabled=not do_answer)
    with ans_row2[2]:
        src_idx = template_styles.index(answer_source_style_val) if answer_source_style_val in template_styles else 0
        is_copy = (do_answer and answer_mode == 'copy_chapter')
        answer_source_style = st.selectbox("原文", options=template_styles, index=src_idx,
                                           key=f"ans_source_{selected_file.name}",
                                           disabled=not (do_answer and is_copy))
    with ans_row2[3]:
        cpy_idx = template_styles.index(answer_copy_style_val) if answer_copy_style_val in template_styles else 0
        answer_copy_style = st.selectbox("答原文", options=template_styles, index=cpy_idx,
                                         key=f"ans_copy_{selected_file.name}",
                                         disabled=not (do_answer and is_copy))

    # 判断是否为双列模式（copy_chapter 模式且启用了应答句）
    is_dual = (do_answer and answer_mode == 'copy_chapter')

    # ====================================================================
    # Step 3: 样式映射（正文+列表段落）- 根据双列模式动态切换
    # ====================================================================
    st.markdown("---")
    if is_dual:
        st.markdown("**3. 样式映射（正文+列表段落）- 双列模式（原文/应答原文）**")
    else:
        st.markdown("**3. 样式映射（正文+列表段落）**")

    body_mapping = {}
    answer_mapping = {}

    if not body_styles:
        st.warning("⚠️ 当前源文档未检测到正文样式")
    else:
        # 表头
        if is_dual:
            h_cols = st.columns([2, 2, 2])
            h_cols[0].markdown("**源样式**")
            h_cols[1].markdown("**原文目标样式**")
            h_cols[2].markdown("**应答目标样式**")
        else:
            h_cols = st.columns([2, 2])
            h_cols[0].markdown("**源样式**")
            h_cols[1].markdown("**目标样式**")

        # 样式映射行
        body_list_shown = False
        for source_style in body_styles:
            body_list_shown = True
            if is_dual:
                cols = st.columns([2, 2, 2])
                with cols[0]:
                    st.text(source_style)
                with cols[1]:
                    default_val = current_file_mapping.get(source_style, default_style_map.get(source_style, "Body Text"))
                    if default_val not in template_styles:
                        default_val = "Body Text"
                    idx = template_styles.index(default_val) if default_val in template_styles else 0
                    selected = st.selectbox("原文→", options=template_styles, index=idx,
                                            key=f"body_{selected_file.name}_{source_style}",
                                            label_visibility="collapsed")
                    body_mapping[source_style] = selected
                with cols[2]:
                    akey = f"answer_{source_style}"
                    a_default = current_file_mapping.get(akey, default_style_map.get(akey, default_val))
                    if a_default not in template_styles:
                        a_default = default_val
                    aidx = template_styles.index(a_default) if a_default in template_styles else 0
                    a_selected = st.selectbox("应答→", options=template_styles, index=aidx,
                                              key=f"answer_{selected_file.name}_{source_style}",
                                              label_visibility="collapsed",
                                              disabled=not is_dual)
                    answer_mapping[source_style] = a_selected
            else:
                cols = st.columns([2, 2])
                with cols[0]:
                    st.text(source_style)
                with cols[1]:
                    default_val = current_file_mapping.get(source_style, default_style_map.get(source_style,
                                                           source_style if source_style in template_styles else "Body Text"))
                    if default_val not in template_styles:
                        default_val = source_style if source_style in template_styles else "Body Text"
                    idx = template_styles.index(default_val) if default_val in template_styles else 0
                    selected = st.selectbox("→", options=template_styles, index=idx,
                                            key=f"body_{selected_file.name}_{source_style}",
                                            label_visibility="collapsed")
                    body_mapping[source_style] = selected

        if not body_list_shown:
            st.caption("（当前源文档未检测到正文样式）")

    # ====================================================================
    # Step 4: 表格/图片/列表兜底配置（使用 @st.fragment 避免每次操作刷新页面）
    # ====================================================================
    _render_step4_fallback(
        selected_file_name=selected_file.name,
        template_styles=template_styles,
        current_file_mapping=current_file_mapping,
        default_tbl_img_config=default_tbl_img_config,
        default_list_config=default_list_config,
        default_remove_chapter_label=default_remove_chapter_label,
        is_dual=is_dual,
    )

    # ====================================================================
    # 保存所有配置到 session_state
    # ====================================================================

    # ★ Step 4 的 widget 值从 session_state 读取（因为 Step 4 在 @st.fragment 中运行，
    #    其局部变量在外部不可见，但 widget 值已自动写入 session_state）
    fname = selected_file.name
    enable_table = st.session_state.get(f"enable_table_{fname}", False)
    table_style = st.session_state.get(f"table_style_{fname}", "Body Text")
    table_answer_style = st.session_state.get(f"table_answer_{fname}", table_style)
    enable_image = st.session_state.get(f"enable_image_{fname}", False)
    image_style = st.session_state.get(f"image_style_{fname}", "Body Text")
    image_answer_style = st.session_state.get(f"image_answer_{fname}", image_style)
    list_enable = st.session_state.get(f"enable_list_{fname}", True)
    l_method = st.session_state.get(f"list_method_{fname}", "bullet")
    l_bullet = st.session_state.get(f"list_bullet_{fname}", "•")
    l_style = st.session_state.get(f"list_style_{fname}", "Body Text")
    la_method = st.session_state.get(f"list_answer_method_{fname}", "bullet")
    la_bullet = st.session_state.get(f"list_answer_bullet_{fname}", "•")
    la_style = st.session_state.get(f"list_answer_style_{fname}", "Body Text")
    remove_chapter_label = st.session_state.get(f"remove_chapter_label_{fname}", False)

    # 1. 保存样式映射
    updated_mapping = {}
    updated_mapping.update(heading_mapping)
    updated_mapping.update(body_mapping)
    if is_dual:
        for src, val in answer_mapping.items():
            updated_mapping[f"answer_{src}"] = val

    # 2. 保存应答句配置到映射
    answer_config = {
        'do_answer': do_answer,
        'answer_text': answer_text,
        'answer_style': answer_style,
        'answer_mode': answer_mode,
        'answer_source_style': answer_source_style,
        'answer_copy_style': answer_copy_style,
    }
    updated_mapping['_answer_config'] = answer_config

    # 3. 保存表格/图片配置
    tbl_img_config_new = {
        'enable_table_style': enable_table,
        'table_style': table_style,
        'table_answer_style': table_answer_style,
        'enable_image_style': enable_image,
        'image_style': image_style,
        'image_answer_style': image_answer_style,
    }
    updated_mapping['_table_image_style'] = tbl_img_config_new

    # 4. 保存列表段落兜底配置
    list_config_new = {
        'enable_list': list_enable,
        'method': l_method,
        'bullet': l_bullet,
        'style': l_style,
        'answer_method': la_method,
        'answer_bullet': la_bullet,
        'answer_style': la_style,
    }
    updated_mapping['_list_config'] = list_config_new

    # 5. 保存清除章节标签
    updated_mapping['_remove_chapter_label'] = remove_chapter_label

    # 更新 session_state
    st.session_state.file_style_mappings[selected_file.name] = updated_mapping

    # 同步到全局 session_state（供转换时使用）
    st.session_state.do_answer_config = do_answer
    st.session_state.answer_text_config = answer_text
    st.session_state.answer_style_config = answer_style
    st.session_state.answer_mode_config = answer_mode
    st.session_state.answer_source_style_config = answer_source_style
    st.session_state.answer_copy_style_config = answer_copy_style
    st.session_state.remove_chapter_label_config = remove_chapter_label
    st.session_state.list_method_config = l_method
    st.session_state.list_bullet_config = l_bullet
    st.session_state.list_style_config = l_style
    st.session_state.list_answer_method_config = la_method
    st.session_state.list_answer_bullet_config = la_bullet
    st.session_state.list_answer_style_config = la_style
    st.session_state.enable_list_style_config = list_enable
    st.session_state.table_style_config = table_style
    st.session_state.table_answer_style_config = table_answer_style
    st.session_state.image_style_config = image_style
    st.session_state.image_answer_style_config = image_answer_style
    st.session_state.enable_table_style_config = enable_table
    st.session_state.enable_image_style_config = enable_image

    # ====================================================================
    # 底部操作按钮（与桌面版一致：恢复默认、设为默认、确认）
    # ====================================================================
    st.markdown("---")
    btn_cols = st.columns(3)

    with btn_cols[0]:
        if st.button("🔄 恢复默认", use_container_width=True, key="reset_mapping_btn"):
            st.session_state.file_style_mappings[selected_file.name] = {}
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            st.info(f"已恢复文件 '{selected_file.name}' 的默认映射")
            st.rerun()

    with btn_cols[1]:
        if st.button("⭐ 设为默认", use_container_width=True, key="save_default_mapping_btn"):
            # ★ 样式映射：合并并集——新配置覆盖同名键，旧配置中不同的键保留
            old_default = st.session_state.file_style_mappings.get('_default_style_map', {})
            merged_style_map = dict(old_default)        # 先复制旧的
            merged_style_map.update(updated_mapping)     # 新值覆盖同名键，新键追加
            st.session_state.file_style_mappings['_default_style_map'] = merged_style_map
            
            # 完整配置块：整体替换（非键值映射，不存在并集语义）
            st.session_state.file_style_mappings['_default_tbl_img_config'] = dict(tbl_img_config_new)
            st.session_state.file_style_mappings['_default_answer_config'] = dict(answer_config)
            st.session_state.file_style_mappings['_default_list_config'] = dict(list_config_new)
            # ★ 修复：显式保存 remove_chapter_label 默认值（与桌面版 default_config.json 一致）
            st.session_state.file_style_mappings['_default_remove_chapter_label'] = remove_chapter_label
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            configured_count = sum(1 for v in updated_mapping.values() if isinstance(v, str) and v)
            st.success(f"⭐ 已设为默认！共 {configured_count} 个样式映射。新文件将自动使用此配置。")

    with btn_cols[2]:
        if st.button("✅ 确定", type="primary", use_container_width=True, key="confirm_mapping_btn"):
            # 保存到用户数据
            user_data = load_user_data(st.session_state.user_id)
            if user_data is None:
                st.error("❌ 用户数据加载失败，无法保存")
                return
            user_data['style_mappings'] = st.session_state.file_style_mappings
            save_user_data(user_data, st.session_state.user_id)
            st.success(f"✅ 文件 '{selected_file.name}' 的样式映射已保存！")
            st.rerun()
