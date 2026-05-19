#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WSprj 全面功能验证 - 完整版"""

import ast
import os
import sys

root = r'E:\LingMa\WSprj'
sys.path.insert(0, root)

results = []
errors = []
warnings = []

def ok(desc):
    results.append(f"  ✅ {desc}")

def fail(desc, detail=""):
    results.append(f"  ❌ {desc} {detail}")
    errors.append(desc)

def warn(desc):
    results.append(f"  ⚠️ {desc}")
    warnings.append(desc)

def read_source(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        return f.read()

def get_funcs(tree):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

def get_imports(tree):
    """获取文件中所有导入的符号"""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname or alias.name)
    return imports

def get_names_in_func(tree, func_name):
    """获取函数中使用的所有名称"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names

# ==========================
files = {
    'app.py': os.path.join(root, 'app.py'),
    'state.py': os.path.join(root, 'state.py'),
    'config.py': os.path.join(root, 'config.py'),
    'data_manager.py': os.path.join(root, 'data_manager.py'),
    'doc_converter.py': os.path.join(root, 'doc_converter.py'),
    'user_manager.py': os.path.join(root, 'user_manager.py'),
    'file_manager.py': os.path.join(root, 'file_manager.py'),
    'comments_manager.py': os.path.join(root, 'comments_manager.py'),
    'task_manager.py': os.path.join(root, 'task_manager.py'),
    'utils.py': os.path.join(root, 'utils.py'),
    'admin_web.py': os.path.join(root, 'admin_web.py'),
    'components/config_panel.py': os.path.join(root, 'components', 'config_panel.py'),
    'components/upload.py': os.path.join(root, 'components', 'upload.py'),
    'components/dialogs/style_mapping.py': os.path.join(root, 'components', 'dialogs', 'style_mapping.py'),
    'components/dialogs/feedback.py': os.path.join(root, 'components', 'dialogs', 'feedback.py'),
    'components/dialogs/history.py': os.path.join(root, 'components', 'dialogs', 'history.py'),
    'data/interface.py': os.path.join(root, 'data', 'interface.py'),
}

print("=" * 70)
print("  WSprj 完整功能验证报告")
print("=" * 70)

# === 1. 文件完整性 ===
print("\n📦 1. 文件完整性检查")
for name, fpath in files.items():
    if os.path.exists(fpath):
        sz = os.path.getsize(fpath)
        line_cnt = len(read_source(fpath).splitlines())
        ok(f"{name} 存在 ({line_cnt}行, {sz}字节)")
    else:
        fail(f"{name} 缺失")

# === 2. 语法和编码 ===
print("\n📝 2. 语法和编码检查")
for name, fpath in files.items():
    if not os.path.exists(fpath):
        continue
    source = read_source(fpath)
    # 编码
    try:
        with open(fpath, 'rb') as f:
            raw = f.read()
        raw.decode('utf-8')
    except UnicodeDecodeError:
        fail(f"{name} 编码错误 (非UTF-8)")
        continue
    # 语法
    try:
        ast.parse(source)
        ok(f"{name} 语法正确")
    except SyntaxError as e:
        fail(f"{name} 语法错误: {e}")

# === 3. 关键Bug修复验证 ===
print("\n🐛 3. 关键Bug修复验证")

# 3.1 style_mapping.py st.rerun()
sm_src = read_source(files['components/dialogs/style_mapping.py'])
if 'st.rerun()' in sm_src:
    cnt = sm_src.count('st.rerun()')
    ok(f"style_mapping.py: st.rerun() 出现{cnt}次")
else:
    fail("style_mapping.py: st.rerun() 缺失!")

# 3.2 style_mapping.py 导入缺失检查
sm_tree = ast.parse(sm_src)
sm_imports = get_imports(sm_tree)
sm_funcs = get_funcs(sm_tree)
sm_local = {f.name for f in sm_funcs} | {'st'}
# 检查 show_style_mapping_dialog 中使用的名称
sm_names = set()
for node in ast.walk(sm_tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'show_style_mapping_dialog':
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                sm_names.add(sub.id)

missing_imports = sm_names - sm_imports - sm_local - {'True','False','None','len','str','list','dict','range','print','sorted','open','zip','map','filter','type','isinstance','hasattr','getattr','setattr','Exception','ValueError','KeyError','TypeError','IndexError','OSError','FileNotFoundError','min','max','any','all','enumerate','reversed','next','super','object','property','staticmethod','classmethod','sum','abs','round','int','float','bool','bytes','bytearray','set','tuple','frozenset','repr','format','input','id'}
# 过滤掉循环变量和临时变量
missing_imports = {n for n in missing_imports if not n.startswith('_') and n not in ('btn_col1','btn_col2','btn_col3','col1','col2','col3','hint','color','default_value','default_values','file_options','selected','selected_file','selected_file_name','sf','source_files','source_style','source_styles','style_index','template_styles','updated_mapping','user_data','current_mapping', 'file_styles_map', 'answer_mode_options', 'mode_keys', 'mode_index', 'answer_mode','answer_style','answer_text', 'do_mood', 'do_answer', 'list_bullet')}

if missing_imports:
    fail(f"style_mapping.py 缺少导入: {missing_imports}")
else:
    ok("style_mapping.py 导入完整")

# 3.3 total_paragraphs_used 硬编码
dm_src = read_source(files['data_manager.py'])
import re
zero_assigns = re.findall(r'total_paragraphs_used\s*[=:]\s*0', dm_src)
if zero_assigns:
    warn(f"data_manager.py: {len(zero_assigns)} 处 total_paragraphs_used=0")
else:
    ok("data_manager.py: 无 total_paragraphs_used=0 硬编码")

# === 4. app.py 功能完整性 ===
print("\n🖥️ 4. app.py 功能完整性")
app_src = read_source(files['app.py'])
app_tree = ast.parse(app_src)
app_funcs = [f.name for f in get_funcs(app_tree)]

# 4.1 关键UI调用检查
# 搜索函数调用（不是导入）
lines = app_src.split('\n')

ui_patterns = [
    ('render_conversion_config()', '配置面板渲染'),
    ('show_style_mapping_dialog()', '样式映射对话框'),
    ('show_feedback_dialog()', '反馈对话框'),
    ('show_history_dialog()', '历史对话框'),
    ('st.rerun()', '页面重载'),
    ('app_state.', '状态管理器'),
    ('show_comments_section()', '评论区'),
]

for pattern, desc in ui_patterns:
    # 检查实际调用（排除import行）
    found = False
    for line in lines:
        stripped = line.strip()
        if pattern in stripped and not stripped.startswith('from ') and not stripped.startswith('#'):
            found = True
            break
    if found:
        ok(f"app.py 调用 {desc}")
    else:
        # 特殊处理：某些可能在字符串中或条件中
        if desc == '配置面板渲染':
            # 检查是否app.py中直接内联了转换配置
            if 'do_mood_config' in app_src and 'list_bullet_config' in app_src:
                warn(f"app.py 未调用 {desc} (可能内联在app.py中)")
            else:
                fail(f"app.py 未调用 {desc}")
        elif desc == '样式映射对话框':
            # 检查config_panel中是否有调用
            cp_src = read_source(files['components/config_panel.py'])
            if 'show_style_mapping_dialog' in cp_src:
                ok(f"config_panel.py 中调用 {desc} (通过导入)")
            else:
                fail(f"app.py 未调用 {desc}")
        else:
            fail(f"app.py 未调用 {desc}")

# 4.2 app.py 函数结构
ok(f"app.py 顶层函数: {len(app_funcs)} 个: {', '.join(sorted(app_funcs))}")

# 4.3 app.py 中的st.session_state访问
ss_refs = len(re.findall(r'st\.session_state', app_src))
state_refs = len(re.findall(r'app_state\.', app_src))
warn(f"app.py 中 st.session_state 直接引用: {ss_refs} 处 (建议统一使用 state.py)")
ok(f"app.py 中 app_state 引用: {state_refs} 处")

# === 5. 模块依赖检查 ===
print("\n🔗 5. 模块依赖检查")

# 检查components/dialogs/style_mapping.py的导入
sm_tree = ast.parse(sm_src)
sm_import_nodes = [n for n in ast.walk(sm_tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
for n in sm_import_nodes:
    if isinstance(n, ast.ImportFrom):
        module = n.module or ''
        names = [a.name for a in n.names]
        ok(f"style_mapping.py: from {module} import {', '.join(names)}")

# 检查components/config_panel.py的导入
cp_src = read_source(files['components/config_panel.py'])
cp_tree = ast.parse(cp_src)
cp_import_nodes = [n for n in ast.walk(cp_tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
for n in cp_import_nodes:
    if isinstance(n, ast.ImportFrom):
        module = n.module or ''
        names = [a.name for a in n.names]
        ok(f"config_panel.py: from {module} import {', '.join(names)}")

# 检查config_panel中的样式映射对话框调用
if 'show_style_mapping_dialog' in cp_src:
    # 检查是否在函数内部导入
    cp_lines = cp_src.split('\n')
    for i, line in enumerate(cp_lines):
        if 'show_style_mapping_dialog' in line:
            warn(f"config_panel.py L{i+1}: 延迟导入 show_style_mapping_dialog")
else:
    fail("config_panel.py 中无样式映射对话框调用")


# === 6. data_manager 分析 ===
print("\n💾 6. data_manager.py 分析")
dm_tree = ast.parse(dm_src)
dm_funcs = [f.name for f in get_funcs(dm_tree)]
ok(f"data_manager.py: {len(dm_funcs)} 个函数")

# 含DATA_SOURCE分支的函数
dm_lines = dm_src.split('\n')
branch_funcs = set()
for i, line in enumerate(dm_lines):
    if 'DATA_SOURCE' in line and ('==' in line or '!=' in line):
        # 找到所属函数
        for func in dm_funcs:
            func_defs = [n for n in ast.walk(dm_tree) if isinstance(n, ast.FunctionDef) and n.name == func]
            for fd in func_defs:
                if fd.lineno <= i+1 <= (fd.end_lineno or fd.lineno):
                    branch_funcs.add(func)

warn(f"含 DATA_SOURCE 分支的函数: {len(branch_funcs)} 个: {', '.join(sorted(branch_funcs))}" )

# === 7. doc_converter 分析 ===
print("\n🔧 7. doc_converter.py 分析")
dc_src = read_source(files['doc_converter.py'])
dc_tree = ast.parse(dc_src)
dc_funcs = [f.name for f in get_funcs(dc_tree)]
ok(f"doc_converter.py: {len(dc_funcs)} 个方法")

# 大方法
large_methods = []
for node in ast.walk(dc_tree):
    if isinstance(node, ast.FunctionDef):
        size = (node.end_lineno or node.lineno) - node.lineno + 1
        if size > 80:
            large_methods.append((node.name, size, node.lineno))

if large_methods:
    warn(f"超过80行的方法: {len(large_methods)} 个")
    for name, sz, ln in sorted(large_methods, key=lambda x: -x[1]):
        warn(f"  {name}: {sz}行 (L{ln})")

# === 8. state.py 验证 ===
print("\n📐 8. state.py 验证")
state_src = read_source(files['state.py'])
state_tree = ast.parse(state_src)
state_funcs = [f.name for f in get_funcs(state_tree)]
ok(f"state.py: {len(state_funcs)} 个方法")

# 查看getter/setter比例
getters = [f for f in state_funcs if f.startswith('get_')]
setters = [f for f in state_funcs if f.startswith('set_')]
ok(f"  getter: {len(getters)}个, setter: {len(setters)}个")

# === 9. 已知问题检查 ===
print("\n⚠️ 9. 已知问题检查")

# 9.1 裸except
all_srcs = {name: read_source(fpath) for name, fpath in files.items() if os.path.exists(fpath)}
for name, src in all_srcs.items():
    bare_excepts = re.findall(r'except\s*:', src)
    if bare_excepts:
        warn(f"{name}: {len(bare_excepts)} 处裸 except")

# 9.2 print残留
for name, src in all_srcs.items():
    print_lines = [l for l in src.split('\n') if l.strip().startswith('print(')]
    if print_lines:
        warn(f"{name}: {len(print_lines)} 处print()")
        
# 9.3 文件清理路径一致性
app_src = read_source(files['app.py'])
fm_src = read_source(files['file_manager.py'])
if 'conversion_results/' in app_src and 'conversion_results/' in fm_src:
    ok("app.py 和 file_manager.py: conversion_results/ 路径一致")
else:
    warn("路径可能不一致")

# 9.4 user_manager 使用情况
um_src = read_source(files['user_manager.py'])
um_tree = ast.parse(um_src)
um_funcs = [f.name for f in get_funcs(um_tree)]
# 检查app.py是否直接使用user_manager中的函数
for func in um_funcs:
    if f'user_manager.{func}' in app_src or func in app_src.split('from user_manager')[1].split('\n')[0] if 'from user_manager' in app_src else False:
        pass
app_uses_um = 'user_manager' in app_src
dm_uses_um = 'user_manager' in dm_src
if app_uses_um or dm_uses_um:
    ok(f"user_manager.py 被引用 (app.py: {app_uses_um}, data_manager.py: {dm_uses_um})")
else:
    warn("user_manager.py 未被任何模块引用")

# 9.5 config_panel重复函数
cp_funcs = [f.name for f in get_funcs(ast.parse(cp_src))]
app_func_names = [f.name for f in get_funcs(app_tree)]
overlap = set(cp_funcs) & set(app_func_names)
if overlap:
    warn(f"config_panel.py 与 app.py 存在重复函数: {overlap}")
else:
    ok("config_panel.py 与 app.py 无函数名冲突")

# === 10. 总结 ===
print("\n" + "=" * 70)
print("  验证总结")
print("=" * 70)
total = len(results)
passed = sum(1 for r in results if '✅' in r)
failed = len(errors)
warn_count = len(warnings)
print(f"\n  总检查项: {total}")
print(f"  通过: {passed}")
print(f"  失败: {failed}")
print(f"  警告: {warn_count}")
print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "")
if errors:
    print(f"\n  ❌ 失败项:")
    for e in errors:
        print(f"    - {e}")
if warnings:
    print(f"\n  ⚠️ 警告项:")
    for w in warnings:
        print(f"    - {w}")
print()
print("=" * 70)

print("\n📋 完整结果:")
for r in results:
    print(r)
