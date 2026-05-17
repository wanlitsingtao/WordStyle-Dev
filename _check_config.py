import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, '.')
os.environ['STREAMLIT_RUN'] = 'false'

# 清除config模块缓存
for mod in list(sys.modules.keys()):
    if 'config' in mod:
        del sys.modules[mod]

# 手动读取config.py的关键变量，避免print emoji
exec(open('config.py', 'r', encoding='utf-8').read())

print('='*50)
print('DATA_SOURCE =', repr(DATA_SOURCE))
print('BACKEND_URL =', repr(BACKEND_URL))
print('USE_SUPABASE =', repr(USE_SUPABASE))
print('='*50)
