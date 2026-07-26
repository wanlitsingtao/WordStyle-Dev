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

    包含：
    1. 祈使语气转换 checkbox
    2. 章节提示语配置（当勾选时显示类型/样式/文本或图片上传/清除/设为默认）

    返回与 `app.py` 兼容的配置元组。
    """
    # CSS：统一控件高度
    st.markdown("""
    <style>
        div[data-testid="column"] .stButton > button {
            height: 2.5em;
            line-height: 1;
            font-size: 0.9em;
        }
        div[data-testid="column"] .stCheckbox > label {
            min-height: 2.5em;
            display: flex;
            align-items: center;
            padding-top: 0.25em;
        }
        div[data-testid="column"] .stTextInput > div > div,
        div[data-testid="column"] .stSelectbox > div > div > div,
        div[data-testid="column"] .stFileUploader > div,
        div[data-testid="column"] .stButton > button {
            min-height: 3em;
            display: flex;
            align-items: center;
        }
        div[data-testid="column"] .stFileUploader > div {
            padding-bottom: 0.05em;
        }
        .hint-label {
            height: 3em;
            display: flex;
            align-items: center;
            padding-bottom: 0.1em;
            font-size: 0.95em;
        }
        div[data-testid="column"] .stRadio > div {
            display: flex;
            align-items: center;
            min-height: 2.5em;
        }
    </style>
    """, unsafe_allow_html=True)

    # ========== 转换选项（与桌面版"转换选项"区域一致：仅祈使语气转换） ==========
    st.markdown("**转换选项**")

    do_mood = st.checkbox(
        "进行祈使语气转换",
        value=st.session_state.get('do_mood_config', True),
        help="将文档中的祈使语气转换为投标人语气",
        key="mood_checkbox"
    )
    if do_mood != st.session_state.get('do_mood_config'):
        st.session_state.do_mood_config = do_mood

    # ========== 章节提示语配置（独立配置区） ==========
    st.markdown("---")
    st.markdown("**章节提示语**")

    # 模板样式列表
    template_styles = st.session_state.get('template_styles', ["Normal"])
    hint_style_idx = 0
    if st.session_state.get('hint_style_config', 'Normal') in template_styles:
        try:
            hint_style_idx = template_styles.index(st.session_state.hint_style_config)
        except ValueError:
            hint_style_idx = 0

    # 读取当前类型（保持选择状态）
    hint_type = st.session_state.get('hint_type_config', 'text')
    hint_text = st.session_state.get('hint_text_config', '招标文件原文')
    hint_image_path = st.session_state.get('hint_image_config', None)
    hint_style = st.session_state.get('hint_style_config', 'Normal')

    # 插入提示语复选框
    do_hint = st.checkbox(
        "插入提示语",
        value=st.session_state.get('do_hint_config', False),
        help="在每个章节标题后插入提示语（如'招标文件原文'）",
        key="hint_checkbox"
    )
    if do_hint != st.session_state.get('do_hint_config'):
        st.session_state.do_hint_config = do_hint

    # 未勾选时不显示任何与提示语相关的控件
    if not do_hint:
        # 确保临时图片变量存在
        if 'hint_image_config' not in st.session_state:
            hint_image_path = None
    else:
        # ========== 标签行 ==========
        lbl = st.columns([2, 2, 5, 1.5, 1.5])
        with lbl[0]:
            st.markdown("**类型**")
        with lbl[1]:
            st.markdown("**提示语样式**")
        with lbl[2]:
            st.markdown("**提示语文本**" if hint_type == "text" else "**上传提示语图片**")
        with lbl[3]:
            st.markdown("&nbsp;", unsafe_allow_html=True)
        with lbl[4]:
            st.markdown("&nbsp;", unsafe_allow_html=True)

        # ========== 控件行（全部 label_visibility="collapsed"，底端对齐） ==========
        ctrl = st.columns([2, 2, 5, 1.5, 1.5])
        with ctrl[0]:
            hint_type = st.radio(
                "类型",
                options=["text", "image"],
                format_func=lambda x: "文本" if x == "text" else "图片",
                index=0 if hint_type == "text" else 1,
                horizontal=True,
                key="hint_type_radio",
                label_visibility="collapsed"
            )
            if hint_type != st.session_state.get('hint_type_config'):
                st.session_state.hint_type_config = hint_type
        with ctrl[1]:
            hint_style = st.selectbox(
                "提示语样式",
                options=template_styles,
                index=hint_style_idx,
                key="hint_style_select",
                label_visibility="collapsed"
            )
            st.session_state.hint_style_config = hint_style
        with ctrl[2]:
            if hint_type == "text":
                hint_text = st.text_input(
                    "提示语文本",
                    value=hint_text,
                    help="提示语文本内容",
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
        with ctrl[3]:
            # 清除图片按钮：始终显示，无图片时禁用
            has_image = bool(hint_image_path and os.path.exists(hint_image_path) if hint_image_path else False)
            is_image_mode = (hint_type == "image")
            if st.button("🗑️ 清除", key="clear_hint_img_btn", use_container_width=True,
                        disabled=not (is_image_mode and has_image),
                        help="清除已上传的提示语图片"):
                if hint_image_path and os.path.exists(hint_image_path):
                    try:
                        os.remove(hint_image_path)
                    except Exception:
                        pass
                st.session_state.hint_image_config = None
                st.session_state.hint_image_uploaded = None
                st.rerun()
        with ctrl[4]:
            if st.button("⭐ 设为默认", key="save_default_hint_btn", use_container_width=True):
                _save_hint_defaults(do_hint, hint_type, hint_text, hint_image_path, hint_style)

    # 返回配置值（保持与 app.py 的兼容）
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
    
