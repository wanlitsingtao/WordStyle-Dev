# -*- coding: utf-8 -*-
"""
转换配置区组件
从 app.py 提取

[2026-07-15] 同步桌面版改进：
1. 章节提示语"设为默认"按钮保存全字段（do_hint、hint_type、hint_text、hint_image_path、hint_style）
2. 初始化时从保存的默认配置加载，而非硬编码
"""
import streamlit as st
from data_manager import load_user_data, save_user_data


def get_answer_mode_options():
    """获取应答句插入模式选项"""
    return {
        'before_heading': '章节前插入',
        'after_heading': '章节后插入',
        'copy_chapter': '原文+应答句+应答原文',
        'before_paragraph': '逐段前应答',
        'after_paragraph': '逐段后应答'
    }


def _load_hint_defaults():
    """从用户数据中加载章节提示语的默认配置"""
    try:
        user_data = load_user_data(st.session_state.user_id)
        if user_data is None:
            return None
        # 默认提示语配置存储在 style_mappings 的特殊键中
        style_mappings = user_data.get('style_mappings', {})
        return style_mappings.get('_default_hint_settings', None)
    except Exception:
        return None


def _save_hint_defaults(hint_settings):
    """将章节提示语默认配置保存到用户数据"""
    try:
        user_data = load_user_data(st.session_state.user_id)
        if user_data is None:
            return False
        if 'style_mappings' not in user_data:
            user_data['style_mappings'] = {}
        user_data['style_mappings']['_default_hint_settings'] = hint_settings
        save_user_data(user_data, st.session_state.user_id)
        return True
    except Exception:
        return False


def _ensure_hint_keys_initialized():
    """确保提示语相关的 session_state 键已初始化（fragment 内防 AttributeError）"""
    hint_defaults_keys = {
        'do_hint_config': False,
        'hint_type_config': 'text',
        'hint_text_config': '',
        'hint_image_config': None,
        'hint_style_config': 'Normal',
    }
    for key, default_val in hint_defaults_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


def _apply_hint_defaults_to_session():
    """将保存的默认提示语配置应用到 session_state（仅当 session_state 未初始化时）"""
    # 先确保键存在，防止 AttributeError
    _ensure_hint_keys_initialized()
    
    defaults = _load_hint_defaults()
    if defaults is None:
        return
    
    # 仅在首次加载时生效
    if st.session_state.get('_hint_defaults_applied', False):
        return
    
    st.session_state.do_hint_config = defaults.get('do_hint', st.session_state.get('do_hint_config', False))
    st.session_state.hint_type_config = defaults.get('hint_type', st.session_state.get('hint_type_config', 'text'))
    st.session_state.hint_text_config = defaults.get('hint_text', st.session_state.get('hint_text_config', ''))
    # 检查保存的默认图片路径是否还存在
    hint_image_default = defaults.get('hint_image_path')
    if hint_image_default:
        import os
        if os.path.exists(hint_image_default):
            st.session_state.hint_image_config = hint_image_default
        else:
            # 默认图片文件已不存在，清空配置
            st.session_state.hint_image_config = None
    elif 'hint_image_config' not in st.session_state:
        st.session_state.hint_image_config = None
    st.session_state.hint_style_config = defaults.get('hint_style', st.session_state.get('hint_style_config', 'Normal'))
    st.session_state._hint_defaults_applied = True


@st.fragment
def render_conversion_config():
    """
    渲染转换配置区（使用fragment优化性能）
    
    优化点：
    1. 使用@st.fragment隔离，避免用户交互导致全局重渲染
    2. 仅在值真正改变时才更新session_state
    3. 预计算索引，避免重复遍历
    4. 首次加载时从保存的默认配置恢复提示语设置
    """
    
    # 首次加载时应用保存的默认提示语配置
    _apply_hint_defaults_to_session()
    
    # CSS：统一控件高度，修复对齐问题
    st.markdown("""
    <style>
        /* 统一配置区所有行内控件高度 */
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
        div[data-testid="column"] .stTextInput > div > div > input {
            min-height: 2.5em;
        }
        div[data-testid="column"] .stSelectbox > div > div > div {
            min-height: 2.5em;
        }
        /* Radio 水平排列时垂直居中 */
        div[data-testid="column"] .stRadio > div {
            display: flex;
            align-items: center;
            min-height: 2.5em;
        }
        div[data-testid="column"] .stRadio > div > label {
            padding-top: 0;
        }
        /* file_uploader 高度统壹 */
        div[data-testid="column"] .stFileUploader > div {
            min-height: 2.5em;
        }
    </style>
    """, unsafe_allow_html=True)
    
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
        answer_text = st.session_state.get('answer_text_config', '')
        answer_style = st.session_state.get('answer_style_config', 'Normal')
        answer_mode = st.session_state.get('answer_mode_config', 'before_heading')
    
    # ========== 章节提示语配置（第三行） ==========
    st.markdown("---")
    st.markdown("**🏷️ 章节提示语**")
    
    # 使用比例列：checkbox(窄) + radio(中等) + selectbox(中等)
    hint_cols = st.columns([1, 2, 2])
    
    with hint_cols[0]:
        do_hint = st.checkbox(
            "插入提示语",
            value=st.session_state.do_hint_config,
            help="在每个章节标题后插入提示语（如'招标文件原文'）",
            key="hint_checkbox"
        )
        if do_hint != st.session_state.get('do_hint_config'):
            st.session_state.do_hint_config = do_hint
    
    if do_hint:
        with hint_cols[1]:
            hint_type = st.radio(
                "提示语类型",
                options=["text", "image"],
                format_func=lambda x: "文本" if x == "text" else "图片",
                index=0 if st.session_state.hint_type_config == "text" else 1,
                horizontal=True,
                key="hint_type_radio"
            )
            if hint_type != st.session_state.get('hint_type_config'):
                st.session_state.hint_type_config = hint_type
        
        with hint_cols[2]:
            # 获取模板样式列表
            template_styles = st.session_state.get('template_styles', ["Normal"])
            hint_style_index = 0
            if st.session_state.hint_style_config in template_styles:
                try:
                    hint_style_index = template_styles.index(st.session_state.hint_style_config)
                except ValueError:
                    hint_style_index = 0
            
            hint_style = st.selectbox(
                "提示语样式",
                options=template_styles,
                index=hint_style_index,
                key="hint_style_select"
            )
            st.session_state.hint_style_config = hint_style
        
        # 第四行：提示语内容 + 设为默认按钮
        hint_content_cols = st.columns([3, 1])
        
        with hint_content_cols[0]:
            if hint_type == "text":
                hint_text = st.text_input(
                    "提示语文本",
                    value=st.session_state.hint_text_config,
                    help="提示语文本内容",
                    key="hint_text_input"
                )
                if hint_text != st.session_state.get('hint_text_config'):
                    st.session_state.hint_text_config = hint_text
                hint_image_path = None
                # 切换为文本类型时，清除图片缓存
                if 'hint_image_uploaded' in st.session_state:
                    st.session_state.hint_image_uploaded = None
            else:
                # 图片类型：使用 file_uploader 上传图片文件
                hint_uploaded = st.file_uploader(
                    "上传提示语图片",
                    type=['png', 'jpg', 'jpeg', 'bmp', 'gif'],
                    help="上传要作为提示语的图片文件（支持 PNG/JPG/BMP/GIF）",
                    key="hint_image_uploader"
                )
                
                # 显示当前已上传的图片信息
                current_img_path = st.session_state.get('hint_image_config')
                if hint_uploaded is not None:
                    # 有新上传的图片，保存到临时文件
                    import os
                    user_id = st.session_state.get('user_id', 'default')
                    img_ext = os.path.splitext(hint_uploaded.name)[1] or '.png'
                    img_temp_path = f"temp_hint_image_{user_id}{img_ext}"
                    with open(img_temp_path, 'wb') as f:
                        f.write(hint_uploaded.getbuffer())
                    st.session_state.hint_image_config = img_temp_path
                    st.session_state.hint_image_uploaded = hint_uploaded.name
                    st.success(f"✅ 已上传: {hint_uploaded.name}")
                elif current_img_path and os.path.exists(current_img_path):
                    st.info(f"📎 当前图片: {os.path.basename(current_img_path)}")
                else:
                    st.caption("请上传一张提示语图片")
                
                hint_image_path = st.session_state.get('hint_image_config')
                hint_text = st.session_state.get('hint_text_config', '')
        
        with hint_content_cols[1]:
            # 章节提示语"设为默认"按钮（保存全字段：是否启用、类型、文本、图片路径、样式）
            if st.button("⭐ 设为默认", key="save_default_hint_btn", use_container_width=True,
                         help="保存当前提示语全部配置为默认（是否启用、类型、文本、图片路径、样式）"):
                hint_defaults = {
                    'do_hint': do_hint,
                    'hint_type': hint_type,
                    'hint_text': hint_text if hint_type == "text" else st.session_state.get('hint_text_config', ''),
                    'hint_image_path': hint_image_path if hint_type == "image" else (st.session_state.get('hint_image_config') or ""),
                    'hint_style': hint_style
                }
                if _save_hint_defaults(hint_defaults):
                    st.session_state._hint_defaults_applied = True
                    hint_enabled_str = "启用" if do_hint else "未启用"
                    hint_type_str = "文本" if hint_type == "text" else "图片"
                    st.success(f"⭐ 已将提示语配置设为默认！状态: {hint_enabled_str}, 类型: {hint_type_str}")
                else:
                    st.error("❌ 保存默认配置失败，请检查用户数据")
            
            # 图片提示语：在"设为默认"按钮下方增加"清除图片"按钮
            if hint_type == "image" and st.session_state.get('hint_image_config'):
                if st.button("🗑️ 清除图片", key="clear_hint_img_btn", use_container_width=True,
                             help="清除已上传的提示语图片"):
                    import os
                    img_path = st.session_state.hint_image_config
                    if img_path and os.path.exists(img_path):
                        try:
                            os.remove(img_path)
                        except Exception:
                            pass
                    st.session_state.hint_image_config = None
                    st.session_state.hint_image_uploaded = None
                    st.rerun()
    else:
        hint_type = st.session_state.get('hint_type_config', 'text')
        hint_text = st.session_state.get('hint_text_config', '')
        hint_image_path = st.session_state.get('hint_image_config', None)
        hint_style = st.session_state.get('hint_style_config', 'Normal')
        
        # 未启用时也显示"设为默认"按钮
        hint_off_cols = st.columns([3, 1])
        with hint_off_cols[1]:
            if st.button("⭐ 设为默认", key="save_default_hint_off_btn", use_container_width=True,
                         help="保存当前提示语配置为默认（包含是否启用的状态）"):
                hint_defaults = {
                    'do_hint': False,
                    'hint_type': hint_type,
                    'hint_text': hint_text,
                    'hint_image_path': hint_image_path or "",
                    'hint_style': hint_style
                }
                if _save_hint_defaults(hint_defaults):
                    st.session_state._hint_defaults_applied = True
                    st.success("⭐ 已将提示语配置设为默认！状态: 未启用")
                else:
                    st.error("❌ 保存默认配置失败")
    
    # 返回配置值供后续使用（表格/图片样式从样式映射对话框按文件配置，不再全局返回）
    return do_mood, do_answer, list_bullet, answer_text, answer_style, answer_mode, do_hint, hint_type, hint_text, hint_image_path, hint_style
