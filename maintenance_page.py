# -*- coding: utf-8 -*-
"""
系统维护页面
当系统处于维护模式时显示此页面
"""
import streamlit as st
from pathlib import Path
import base64

# 页面配置
st.set_page_config(
    page_title="系统维护中",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 自定义CSS - 黑色背景，移除所有空白
st.markdown("""
<style>
    /* 全局样式 */
    .stApp {
        background-color: #000000;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 隐藏默认Streamlit元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none !important;}
    
    /* 移除所有默认内边距 */
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        max-width: 100% !important;
    }
    
    /* main容器 */
    main {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* 呼吸动画文字 */
    @keyframes breathe {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.05); }
    }
    
    .breathe-text {
        animation: breathe 3s ease-in-out infinite;
        color: #ffffff;
        font-size: 2rem;
        font-weight: bold;
        text-align: center;
        margin-top: 2rem;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.8);
    }
    
    /* 顶部提示文字 */
    .top-message {
        color: #ffffff;
        font-size: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# 直接使用HTML显示Logo，避免Streamlit的额外包装
logo_path = Path(__file__).parent / "resource" / "wh.png"
if logo_path.exists():
    # 将图片转换为base64嵌入HTML
    with open(logo_path, 'rb') as f:
        encoded_image = base64.b64encode(f.read()).decode()
    
    st.markdown(f'''
    <div style="width: 100%; margin: 0; padding: 0;">
        <img src="data:image/png;base64,{encoded_image}" 
             style="width: 100%; height: auto; display: block; margin: 0; padding: 0;">
    </div>
    ''', unsafe_allow_html=True)
else:
    st.warning("⚠️ Logo文件未找到：resource/wh.png")

# 顶部提示文字
st.markdown('''
<div class="top-message">
    更好的体验，需要你的支持！
</div>
''', unsafe_allow_html=True)

# 只显示"我会回来的！"呼吸文字
st.markdown('''
<div class="breathe-text">
    我会回来的！
</div>
''', unsafe_allow_html=True)

# 隐藏Streamlit默认菜单和footer
st.markdown("""
<script>
    // 隐藏Streamlit的部署按钮
    if (window.parent.document.querySelector('[data-testid="stToolbar"]')) {
        window.parent.document.querySelector('[data-testid="stToolbar"]').style.display = 'none';
    }
    
    // 移除顶部空白
    setTimeout(function() {
        var main = window.parent.document.querySelector('main');
        if (main) {
            main.style.paddingTop = '0';
            main.style.marginTop = '0';
        }
        
        var blockContainer = window.parent.document.querySelector('.block-container');
        if (blockContainer) {
            blockContainer.style.paddingTop = '0';
            blockContainer.style.marginTop = '0';
        }
    }, 100);
</script>
""", unsafe_allow_html=True)
