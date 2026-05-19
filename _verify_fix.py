#!/usr/bin/env python
"""验证修复后的代码完整性"""
import ast, sys

root = r'E:\LingMa\WSprj'

files = {
    'app.py': root + r'\app.py',
    'components/config_panel.py': root + r'\components\config_panel.py',
    'components/dialogs/style_mapping.py': root + r'\components\dialogs\style_mapping.py',
}

for name, path in files.items():
    source = open(path, 'r', encoding='utf-8').read()
    try:
        ast.parse(source)
        lines = len(source.splitlines())
        print(f'  ✅ {name}: {lines}行, 语法正确')
    except SyntaxError as e:
        print(f'  ❌ {name}: 语法错误: {e}')

# 验证app.py中调用了render_conversion_config
app_src = open(root + r'\app.py', 'r', encoding='utf-8').read()
if 'render_conversion_config()' in app_src and 'do_mood, do_answer' in app_src:
    print('  ✅ app.py: 已调用 render_conversion_config()')
else:
    print('  ❌ app.py: 未正确调用 render_conversion_config()')

# 验证config_panel.py中调用了show_style_mapping_dialog
cp_src = open(root + r'\components\config_panel.py', 'r', encoding='utf-8').read()
if 'show_style_mapping_dialog()' in cp_src:
    print('  ✅ config_panel.py: 样式映射对话框调用存在')
else:
    print('  ❌ config_panel.py: 样式映射对话框调用缺失')

# 验证style_mapping.py的导入
sm_src = open(root + r'\components\dialogs\style_mapping.py', 'r', encoding='utf-8').read()
if 'load_user_data' in sm_src and 'save_user_data' in sm_src:
    print('  ✅ style_mapping.py: load_user_data/save_user_data 导入存在')
else:
    print('  ❌ style_mapping.py: 导入缺失')

# 检查config_panel与app.py中的重复函数
if 'get_answer_mode_options' in app_src:
    print('  ⚠️ app.py 仍有 get_answer_mode_options 定义（可能与config_panel.py重复）')

print()
print('=== 完整的配置区调用链 ===')
print('  app.py')
print('    └─ render_conversion_config()  ← components/config_panel.py')
print('         ├─ st.checkbox("祈使语气转换")')
print('         ├─ st.checkbox("插入应答句")')
print('         ├─ st.text_input("列表符号")')
print('         ├─ st.button("📊 样式映射")')
print('         │    └─ show_style_mapping_dialog()')
print('         │         └─ load_user_data() ← data_manager')
print('         │         └─ save_user_data() ← data_manager')
print('         └─ (应答句配置区 3列)')
print('              ├─ st.text_input("应答句文本")')
print('              ├─ st.selectbox("应答句样式")')
print('              └─ st.selectbox("插入模式")')
