# -*- coding: utf-8 -*-
"""
反馈对话框组件
从 app.py 提取
"""
import streamlit as st
from datetime import datetime
import logging

logger = logging.getLogger('WordStyle')

@st.dialog("💡 提交需求或反馈")
def show_feedback_dialog():
    """显示反馈提交对话框"""
    # [OK] 修复：每次打开对话框时重置表单状态
    if 'feedback_form_reset' not in st.session_state:
        st.session_state.feedback_form_reset = 0
    
    # 使用唯一的key前缀，每次打开时递增，强制重置所有表单控件
    form_key_prefix = f"feedback_{st.session_state.feedback_form_reset}"
    
    st.markdown("我们非常重视您的意见，请告诉我们您的想法！")
    
    # 反馈类型
    feedback_type = st.selectbox(
        "反馈类型",
        ["功能建议", "Bug报告", "使用问题", "其他"],
        help="请选择反馈的类型",
        key=f"{form_key_prefix}_type"  # [OK] 新增：唯一key
    )
    
    # 标题（可选，有默认值）
    default_title = f"{feedback_type} - {datetime.now().strftime('%Y-%m-%d')}"
    feedback_title = st.text_input(
        "标题（可选）",
        value=default_title,
        placeholder="也可以自定义标题",
        help="如果不填写，将自动生成默认标题",
        key=f"{form_key_prefix}_title"  # [OK] 新增：唯一key
    )
    
    # 详细描述
    feedback_description = st.text_area(
        "详细描述",
        placeholder="请详细描述您的需求、问题或建议...\n\n例如：\n- 我希望增加XX功能\n- 我遇到了XX问题\n- 我觉得XX可以改进",
        height=150,
        help="越详细越好，帮助我们更好地理解您的需求",
        key=f"{form_key_prefix}_description"  # [OK] 新增：唯一key
    )
    
    # 联系方式（可选）
    feedback_contact = st.text_input(
        "联系方式（可选）",
        placeholder="微信/邮箱/电话",
        help="如果需要我们回复您，请留下联系方式",
        key=f"{form_key_prefix}_contact"  # [OK] 新增：唯一key
    )
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ 提交", type="primary", use_container_width=True):
            if not feedback_description:
                st.error("❌ 请填写详细描述")
            else:
                try:
                    # 映射反馈类型
                    type_map = {
                        "功能建议": "feature",
                        "Bug报告": "bug",
                        "使用问题": "question",
                        "其他": "other"
                    }
                    
                    # 如果标题为空，使用默认标题
                    if not feedback_title or feedback_title.strip() == "":
                        feedback_title = f"{feedback_type} - {datetime.now().strftime('%Y-%m-%d')}"
                    
                    # [OK] 修复：使用 API 提交反馈（兼容多实例部署）
                    from config import BACKEND_URL, DATA_SOURCE
                    import requests
                    
                    if BACKEND_URL and DATA_SOURCE == 'api':
                        # API 模式：通过后端 API 提交
                        api_url = f"{BACKEND_URL.rstrip('/')}/api/feedback/submit"
                        response = requests.post(
                            api_url,
                            json={
                                'user_id': st.session_state.user_id,
                                'feedback_type': type_map.get(feedback_type, 'other'),
                                'title': feedback_title,
                                'description': feedback_description,
                                'contact': feedback_contact
                            },
                            timeout=10
                        )
                        response.raise_for_status()
                        result = response.json()
                        feedback_id = result.get('id', result.get('feedback_id', 'N/A'))  # [OK] 修复：兼容两种字段名
                    else:
                        # 本地/Supabase 模式：使用本地存储（兜底逻辑）
                        feedback = add_feedback(
                            user_id=st.session_state.user_id,
                            feedback_type=type_map.get(feedback_type, 'other'),
                            title=feedback_title,
                            description=feedback_description,
                            contact=feedback_contact
                        )
                        feedback_id = feedback['id']
                    
                    st.balloons()  # 🎈 彩带庆祝
                    st.success(f"✅ 反馈提交成功！感谢您的宝贵意见")
                    st.info(f"ℹ️ 反馈ID: {feedback_id}")
                    
                    # [OK] 修复：递增表单重置计数器，下次打开对话框时会使用新的key
                    st.session_state.feedback_form_reset += 1
                    
                    # [OK] 直接返回，对话框自动关闭
                    return
                except Exception as e:
                    st.error(f"❌ 提交失败：{str(e)}")
                    logger.error(f"反馈提交失败: {e}")
    
    with col2:
        if st.button("❌ 关闭", use_container_width=True):
            return  # 直接返回，对话框自动关闭

