# -*- coding: utf-8 -*-
"""
转换配置区组件（完全参照桌面版）

桌面版在主界面"转换选项"区域仅保留：
1. "进行祈使语气转换" checkbox
2. 章节提示语配置（独立配置区）

样式映射配置通过样式信息区域的按钮打开对话框管理。
所有其他配置（应答句、列表段落、清除章节标签等）均在样式映射对话框中管理。
"""
import streamlit as st
import os


def _save_hint_defaults(do_hint, hint_type, hint_text, hint_image_path, hint_style):
    """保存提示语默认配置到用户数据"""
    from data_manager import load_user_data, save_user_data
    hint_defaults = {
        'do_hint': do_hint,
        'hint_type': hint_type,
        'hint_text': hint_text,
        'hint_image_path': hint_image_path or "",
        'hint_style': hint_style
    }
    try:
        user_id = st.session_state.get('user_id', 'default')
        user_data = load_user_data(user_id)
        if user_data and 'style_mappings' not in user_data:
            user_data['style_mappings'] = {}
        if user_data:
            user_data['style_mappings']['_default_hint_settings'] = hint_defaults
            save_user_data(user_data, user_id)
            st.success("⭐ 已将提示语配置设为默认！")
        else:
            st.error("❌ 保存默认配置失败")
    except Exception:
        st.error("❌ 保存默认配置失败")


def render_conversion_config():
    """
    渲染转换配置区（完全参照桌面版）
    
    仅包含：
    1. 祈使语气转换 checkbox
    if not do_hint:
        # 确保清理可能存在的临时图片路径变量
        if 'hint_image_config' not in st.session_state:
            hint_image_path = None
        # 不显示其他控件
        pass
    else:
        # 单行布局：类型、样式、文本/图片上传、清除按钮 在同一行
        row = st.columns([2, 2, 6, 1])
        with row[0]:
            hint_type = st.radio(
                "类型",
                options=["text", "image"],
                format_func=lambda x: "文本提示语" if x == "text" else "图片提示语",
                index=0 if hint_type == "text" else 1,
                horizontal=True,
                key="hint_type_radio"
            )
            if hint_type != st.session_state.get('hint_type_config'):
                st.session_state.hint_type_config = hint_type
        with row[1]:
            hint_style = st.selectbox(
                "提示语样式",
                options=template_styles,
                index=hint_style_idx,
                key="hint_style_select",
            )
            st.session_state.hint_style_config = hint_style
        with row[2]:
            # 动态标签
            label_text = "提示语文本:" if hint_type == "text" else "上传提示语图片:"
            st.markdown(label_text)
            if hint_type == "text":
                hint_text = st.text_input(
                    "提示语文本",
                    value=hint_text,
                    help="提示语文本内容（图片模式下作为alt文本）",
                    key="hint_text_input",
                    label_visibility="collapsed",
                )
                if hint_text != st.session_state.get('hint_text_config'):
                    st.session_state.hint_text_config = hint_text
            else:
                hint_uploaded = st.file_uploader(
                    "上传提示语图片",
                    type=['png', 'jpg', 'jpeg', 'bmp', 'gif'],
                    help="上传要作为提示语的图片文件",
                    key="hint_image_uploader",
                    label_visibility="collapsed"
                )
                if hint_uploaded is not None:
                    user_id = st.session_state.get('user_id', 'default')
                    img_ext = os.path.splitext(hint_uploaded.name)[1] or '.png'
                    img_temp_path = f"temp_hint_image_{user_id}{img_ext}"
                    with open(img_temp_path, 'wb') as f:
                        f.write(hint_uploaded.getbuffer())
                    st.session_state.hint_image_config = img_temp_path
                    st.session_state.hint_image_uploaded = hint_uploaded.name
                    st.success(f"✅ 已上传: {hint_uploaded.name}")
                    hint_image_path = img_temp_path
                elif hint_image_path and os.path.exists(hint_image_path):
                    st.info(f"📎 当前图片: {os.path.basename(hint_image_path)}")
                else:
                    st.caption("请选择提示语图片文件")
        with row[3]:
            # 仅在图片模式下显示清除图片按钮
            if hint_type == "image":
                has_image = bool(hint_image_path and os.path.exists(hint_image_path) if hint_image_path else False)
                if st.button("清除图片", key="clear_hint_img_btn", use_container_width=True, disabled=not has_image):
                    if hint_image_path and os.path.exists(hint_image_path):
                        try:
                            os.remove(hint_image_path)
                        except Exception:
                            pass
                    st.session_state.hint_image_config = None
                    st.session_state.hint_image_uploaded = None
                    st.rerun()

        # 设为默认按钮：在启用时以全宽显示，便于与页面其他主操作按钮一致
        if st.button("⭐ 设为默认", key="save_default_hint_btn", use_container_width=True):
            _save_hint_defaults(do_hint, hint_type, hint_text, hint_image_path, hint_style)
    else:
        # 显示提示语控件（两行布局以提高对齐和可读性）
        top_row = st.columns([1, 2, 2])
        with top_row[0]:
            # 类型选择
            hint_type = st.radio(
                "类型",
                options=["text", "image"],
                format_func=lambda x: "文本提示语" if x == "text" else "图片提示语",
                index=0 if hint_type == "text" else 1,
                horizontal=True,
                key="hint_type_radio"
            )
            if hint_type != st.session_state.get('hint_type_config'):
                st.session_state.hint_type_config = hint_type
        with top_row[1]:
            # 提示语样式
            hint_style = st.selectbox(
                "提示语样式",
                options=template_styles,
                index=hint_style_idx,
                key="hint_style_select",
            )
            st.session_state.hint_style_config = hint_style
        with top_row[2]:
            # 占位，用于右侧对齐
            st.write("")

        # 第二行：提示语文本或图片 + 清除按钮
        bottom_row = st.columns([1, 5, 1])
        with bottom_row[0]:
            st.markdown("提示语文本:")
        with bottom_row[1]:
            if hint_type == "text":
                hint_text = st.text_input(
                    "提示语文本",
                    value=hint_text,
                    help="提示语文本内容（图片模式下作为alt文本）",
                    key="hint_text_input",
                    label_visibility="collapsed",
                )
                if hint_text != st.session_state.get('hint_text_config'):
                    st.session_state.hint_text_config = hint_text
            else:
                hint_uploaded = st.file_uploader(
                    "上传提示语图片",
                    type=['png', 'jpg', 'jpeg', 'bmp', 'gif'],
                    help="上传要作为提示语的图片文件",
                    key="hint_image_uploader",
                    label_visibility="collapsed"
                )
                if hint_uploaded is not None:
                    user_id = st.session_state.get('user_id', 'default')
                    img_ext = os.path.splitext(hint_uploaded.name)[1] or '.png'
                    img_temp_path = f"temp_hint_image_{user_id}{img_ext}"
                    with open(img_temp_path, 'wb') as f:
                        f.write(hint_uploaded.getbuffer())
                    st.session_state.hint_image_config = img_temp_path
                    st.session_state.hint_image_uploaded = hint_uploaded.name
                    st.success(f"✅ 已上传: {hint_uploaded.name}")
                    hint_image_path = img_temp_path
                elif hint_image_path and os.path.exists(hint_image_path):
                    st.info(f"📎 当前图片: {os.path.basename(hint_image_path)}")
                else:
                    st.caption("请选择提示语图片文件")
        with bottom_row[2]:
            # 仅在图片模式下显示清除图片按钮
            if hint_type == "image":
                has_image = bool(hint_image_path and os.path.exists(hint_image_path) if hint_image_path else False)
                if st.button("清除图片", key="clear_hint_img_btn", use_container_width=True, disabled=not has_image):
                    if hint_image_path and os.path.exists(hint_image_path):
                        try:
                            os.remove(hint_image_path)
                        except Exception:
                            pass
                    st.session_state.hint_image_config = None
                    st.session_state.hint_image_uploaded = None
                    st.rerun()

        # 设为默认按钮：在启用时以全宽显示，便于与页面其他主操作按钮一致
        if st.button("⭐ 设为默认", key="save_default_hint_btn", use_container_width=True):
            _save_hint_defaults(do_hint, hint_type, hint_text, hint_image_path, hint_style)
    
    # 返回配置值（保持与 app.py 的兼容）
    # 注意：应答句配置、列表段落配置、清除章节标签等现在从样式映射对话框同步到 session_state
    do_answer = st.session_state.get('do_answer_config', False)
    list_bullet = st.session_state.get('list_bullet_config', '•')
    answer_text = st.session_state.get('answer_text_config', '')
    answer_style = st.session_state.get('answer_style_config', 'Normal')
    answer_mode = st.session_state.get('answer_mode_config', 'copy_chapter')
    answer_source_style = st.session_state.get('answer_source_style_config', '')
    answer_copy_style = st.session_state.get('answer_copy_style_config', '')
    list_method = st.session_state.get('list_method_config', 'bullet')
    list_style = st.session_state.get('list_style_config', 'Body Text')
    list_answer_method = st.session_state.get('list_answer_method_config', 'bullet')
    list_answer_style = st.session_state.get('list_answer_style_config', 'Body Text')
    list_answer_bullet = st.session_state.get('list_answer_bullet_config', '•')
    enable_list_style = st.session_state.get('enable_list_style_config', True)
    remove_chapter_label = st.session_state.get('remove_chapter_label_config', False)

    return (do_mood, do_answer, list_bullet, answer_text, answer_style, answer_mode,
            do_hint, hint_type, hint_text, hint_image_path, hint_style,
            answer_source_style, answer_copy_style,
            list_method, list_style, list_answer_method, list_answer_style, list_answer_bullet,
            remove_chapter_label, enable_list_style)
