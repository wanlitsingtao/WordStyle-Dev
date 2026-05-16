import requests

print("="*60)
print("检查管理后台数据源配置")
print("="*60)

try:
    r = requests.get('https://wsprj-admin.onrender.com', timeout=15)
    content = r.text
    
    if 'API (https://wstest-backend.onrender.com)' in content:
        print("数据源显示: API模式")
        print("BACKEND_URL配置正确!")
    elif '数据源: local' in content:
        print("数据源显示: local模式")
        print("需要检查环境变量配置:")
        print("  1. BACKEND_URL是否正确")
        print("  2. USE_SUPABASE是否为true")
    else:
        print("无法自动检测数据源模式")
        print("请手动访问 https://wsprj-admin.onrender.com 查看")
        
except Exception as e:
    print(f"检查失败: {e}")

print("="*60)
