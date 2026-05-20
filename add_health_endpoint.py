# -*- coding: utf-8 -*-
"""
为Streamlit应用添加Health端点支持
用于UptimeRobot监控
"""
import sys
import os

def add_health_endpoint_to_streamlit(filepath):
    """
    为Streamlit应用文件添加health端点支持
    
    在set_page_config之前插入health检查逻辑
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经添加了health端点
    if "st.query_params" in content and "'health' in query_params" in content:
        print(f"✅ {filepath} 已包含health端点支持")
        return
    
    # 在set_page_config之前插入health检查代码
    health_check_code = """
# [OK] 支持UptimeRobot健康检查：通过URL参数检测
import sys
from urllib.parse import urlparse, parse_qs
try:
    # 获取当前URL参数
    query_params = st.query_params
    if 'health' in query_params:
        # 返回health检查响应
        import json
        st.json({"status": "healthy", "service": "user-page", "version": "1.0.0"})
        st.stop()
except Exception:
    # 如果query_params不可用（旧版本Streamlit），忽略
    pass

"""
    
    # 找到set_page_config的位置
    if 'st.set_page_config(' in content:
        # 在set_page_config之前插入
        lines = content.split('\n')
        insert_index = -1
        for i, line in enumerate(lines):
            if 'st.set_page_config(' in line:
                insert_index = i
                break
        
        if insert_index > 0:
            # 在insert_index之前插入health检查代码
            new_lines = lines[:insert_index] + health_check_code.strip().split('\n') + lines[insert_index:]
            new_content = '\n'.join(new_lines)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ 已为 {filepath} 添加health端点支持")
        else:
            print(f"❌ 无法找到set_page_config位置：{filepath}")
    else:
        print(f"⚠️  {filepath} 未找到set_page_config，跳过")

if __name__ == "__main__":
    # 处理两个Streamlit应用文件
    files_to_update = [
        'app.py',
        'admin_web.py'
    ]
    
    for filepath in files_to_update:
        if os.path.exists(filepath):
            add_health_endpoint_to_streamlit(filepath)
        else:
            print(f"⚠️  文件不存在：{filepath}")
