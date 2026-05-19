# -*- coding: utf-8 -*-
"""
转换历史对话框组件
从 app.py 提取
"""
import streamlit as st
import logging

logger = logging.getLogger('WordStyle')

@st.dialog("📋 我的转换历史")
def show_history_dialog():
    """显示转换历史对话框"""
    # [OK] 修复：优先从后端API获取转换历史（API模式）
    conversion_history = []
    from config import DATA_SOURCE, BACKEND_URL
    
    if DATA_SOURCE == 'api' and BACKEND_URL:
        # API模式：通过后端API获取用户转换历史
        try:
            import requests
            api_url = f"{BACKEND_URL.rstrip('/')}/api/admin/users/{st.session_state.user_id}"
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                user_data_from_api = response.json()
                conversion_history = user_data_from_api.get('conversion_history', [])
                logger.info(f"[OK] 从API获取转换历史: {len(conversion_history)}条记录")
        except Exception as e:
            logger.warning(f"[WARN] 从API获取转换历史失败: {e}，尝试从本地加载")
    
    # 降级方案：从本地数据加载
    if not conversion_history:
        user_data = load_user_data(st.session_state.user_id)
        if user_data is None:
            st.warning("⚠️ 用户数据加载失败，请刷新页面重试")
            return
        conversion_history = user_data.get('conversion_history', [])
    
    if conversion_history:
        # 准备表格数据（倒序显示，最新的在前面）
        table_data = []
        for record in reversed(conversion_history[-20:]):  # 显示最近20条
            # [OK] 修复：将服务器时间转换为本地时间显示
            server_time = record.get('time', '未知')
            local_time = convert_server_time_to_local(server_time)
            
            # 构建状态显示
            if record.get('failed', 0) == 0:
                status = "[OK] 成功"
            else:
                status = f"[WARN] {record.get('failed', 0)}个失败"
            
            # 构建段落数显示
            paragraphs_display = f"{record['paragraphs_charged']:,}" if record.get('paragraphs_charged') else "-"
            
            table_data.append({
                '时间': local_time,
                '文件数': record.get('files', 0),
                '成功': record.get('success', 0),
                '失败': record.get('failed', 0),
                '段落数': paragraphs_display,
                '模式': record.get('mode', '前台'),
                '状态': status
            })
        
        # 使用DataFrame展示表格
        import pandas as pd
        df = pd.DataFrame(table_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                '时间': st.column_config.TextColumn('时间', width='medium'),
                '文件数': st.column_config.NumberColumn('文件数', width='small'),
                '成功': st.column_config.NumberColumn('成功', width='small'),
                '失败': st.column_config.NumberColumn('失败', width='small'),
                '段落数': st.column_config.TextColumn('段落数', width='small'),
                '模式': st.column_config.TextColumn('模式', width='small'),
                '状态': st.column_config.TextColumn('状态', width='medium')
            }
        )
    else:
        st.info("暂无转换历史记录")
    
    # 关闭按钮
    if st.button("❌ 关闭", key="close_history_btn", use_container_width=True):
        # [OK] 直接返回，对话框自动关闭
        return
