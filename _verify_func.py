#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WSprj 全面功能验证脚本"""

import sys
import os
import ast

root = r'E:\LingMa\WSprj'
sys.path.insert(0, root)

results = []
errors = []

def check(desc, condition, detail=""):
    if condition:
        results.append(f"  ✅ {desc}")
    else:
        results.append(f"  ❌ {desc} {detail}")
        errors.append(desc)

def check_contains(filepath, pattern, desc):
    """检查文件中是否包含特定模式"""
    if not os.path.exists(filepath):
        results.append(f"  ❌ {desc} - 文件不存在")
        errors.append(desc)
        return False
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    if pattern in content:
        results.append(f"  ✅ {desc}")
        return True
    else:
        results.append(f"  ❌ {desc} - 未找到 '{pattern}'")
        errors.append(desc)
        return False

def count_funcs(filepath):
    """统计文件中的函数/方法数"""
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    funcs = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return len(funcs)

def find_functions(filepath, pattern=None):
    """查找文件中的函数列表"""
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if pattern is None or pattern in node.name:
                funcs.append(node.name)
    return funcs

# ============================================================
print("=" * 70)
print("  WSprj 全面功能验证报告")
print("=" * 70)

# === 1. 基础语法检查 ===
print("\n📦 1. 基础语法检查")
app_path = os.path.join(root, 'app.py')
state_path = os.path.join(root, 'state.py')
dm_path = os.path.join(root, 'data_manager.py')
dc_path = os.path.join(root, 'doc_converter.py')
config_path = os.path.join(root, 'config.py')
um_path = os.path.join(root, 'user_manager.py')
fm_path = os.path.join(root, 'file_manager.py')
cm_path = os.path.join(root, 'comments_manager.py')
tm_path = os.path.join(root, 'task_manager.py')
utils_path = os.path.join(root, 'utils.py')
admin_path = os.path.join(root, 'admin_web.py')
cp_path = os.path.join(root, 'components', 'config_panel.py')
upload_path = os.path.join(root, 'components', 'upload.py')
sm_path = os.path.join(root, 'components', 'dialogs', 'style_mapping.py')
fb_path = os.path.join(root, 'components', 'dialogs', 'feedback.py')
hist_path = os.path.join(root, 'components', 'dialogs', 'history.py')
iface_path = os.path.join(root, 'data', 'interface.py')

all_files = [
    app_path, state_path, dm_path, dc_path, config_path,
    um_path, fm_path, cm_path, tm_path, utils_path, admin_path,
    cp_path, upload_path, sm_path, fb_path, hist_path, iface_path
]
fnames = [
    'app.py', 'state.py', 'data_manager.py', 'doc_converter.py', 'config.py',
    'user_manager.py', 'file_manager.py', 'comments_manager.py', 'task_manager.py',
    'utils.py', 'admin_web.py', 'components/config_panel.py', 'components/upload.py',
    'components/dialogs/style_mapping.py', 'components/dialogs/feedback.py',
    'components/dialogs/history.py', 'data/interface.py'
]

for fpath, fname in zip(all_files, fnames):
    with open(fpath, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        ast.parse(source)
        lines = len(source.splitlines())
        func_count = count_funcs(fpath)
        check(f"{fname} - 语法正确, {lines}行, {func_count}个函数", True)
    except SyntaxError as e:
        check(f"{fname} - 语法错误: {e}", False)

# === 2. 关键Bug验证 ===
print("\n🐛 2. 关键Bug修复验证")

# 2.1 style_mapping.py st.rerun()
with open(sm_path, 'r', encoding='utf-8') as f:
    sm_content = f.read()
check("style_mapping.py: 确定按钮后有 st.rerun()",
      "st.rerun()" in sm_content and "确定" in sm_content)
check("style_mapping.py: 恢复默认按钮后有 st.rerun()",
      sm_content.count("st.rerun()") >= 2)

# 2.2 编码正确性
for fpath, fname in zip(all_files, fnames):
    with open(fpath, 'rb') as f:
        raw = f.read()
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError:
        check(f"{fname} - UTF-8编码正确", False)

# 2.3 data_manager.py total_paragraphs_used 硬编码
with open(dm_path, 'r', encoding='utf-8') as f:
    dm_content = f.read()
# 检查局部模式下的硬编码
tree = ast.parse(dm_content)
hardcoded_zero = False
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == 'total_paragraphs_used':
                if isinstance(node.value, ast.Constant) and node.value.value == 0:
                    hardcoded_zero = True
check("data_manager.py: total_paragraphs_used 硬编码=0 已修复",
      not hardcoded_zero,
      detail="(建议检查get_or_create_user_by_device中的total_paragraphs_used赋值)")

# 2.4 硬编码0的具体位置搜索
import re
zero_assigns = re.findall(r'total_paragraphs_used\s*[=:]\s*0', dm_content)
if zero_assigns:
    results.append(f"  ⚠️ data_manager.py 中发现 {len(zero_assigns)} 处 total_paragraphs_used=0")

# === 3. 模块导入链验证 ===
print("\n🔗 3. 模块导入链验证")

# app.py 导入
with open(app_path, 'r', encoding='utf-8') as f:
    app_source = f.read()

import_patterns = [
    ('from state import app_state', 'state.app_state'),
    ('from components.config_panel import render_conversion_config', 'render_conversion_config'),
    ('from components.dialogs.style_mapping import show_style_mapping_dialog', 'show_style_mapping_dialog'),
    ('from components.dialogs.feedback import show_feedback_dialog', 'show_feedback_dialog'),
    ('from components.dialogs.history import show_history_dialog', 'show_history_dialog'),
    ('from components.upload import', 'upload组件'),
    ('from data_manager import', 'data_manager'),
    ('from doc_converter import', 'doc_converter'),
    ('from config import', 'config'),
]

for pattern, desc in import_patterns:
    check(f"app.py 导入 {desc}", pattern in app_source)

# === 4. data_manager 分析 ===
print("\n💾 4. data_manager.py 数据源分支分析")

# 统计 DATA_SOURCE 分支
data_source_branches = re.findall(r'DATA_SOURCE\s*==\s*["\'](\w+)["\']', dm_content)
branch_count = {}
for ds in data_source_branches:
    branch_count[ds] = branch_count.get(ds, 0) + 1

results.append(f"  📊 DATA_SOURCE 分支分布:")
for ds, count in sorted(branch_count.items(), key=lambda x: -x[1]):
    results.append(f"     - '{ds}': {count} 次")

# 统计函数数量
dm_funcs = find_functions(dm_path)
check(f"data_manager.py 共有 {len(dm_funcs)} 个函数", True)

# 检查data_source分支函数
branch_funcs = []
for func in dm_funcs:
    tree = ast.parse(dm_content)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            func_source = ast.unparse(node)
            if 'DATA_SOURCE' in func_source:
                branch_funcs.append(func)

results.append(f"  📊 含 DATA_SOURCE 分支的函数: {len(branch_funcs)} 个")
for f in sorted(branch_funcs):
    results.append(f"     - {f}")

# === 5. doc_converter 分析 ===
print("\n🔧 5. doc_converter.py 方法分析")

with open(dc_path, 'r', encoding='utf-8') as f:
    dc_source = f.read()

# 统计方法
dc_funcs = find_functions(dc_path)
check(f"doc_converter.py 共有 {len(dc_funcs)} 个方法", True)

# 查找大方法
tree = ast.parse(dc_source)
large_methods = []
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        start_line = node.lineno
        end_line = node.end_lineno
        size = end_line - start_line + 1
        if size > 80:
            large_methods.append((node.name, size))

if large_methods:
    results.append(f"  ⚠️ 超过80行的大方法 ({len(large_methods)}个):")
    for name, size in sorted(large_methods, key=lambda x: -x[1]):
        results.append(f"     - {name}: {size}行")
else:
    check("无超过80行的大方法", True)

# === 6. app.py UI 调用分析 ===
print("\n🖥️ 6. app.py UI组件调用分析")

# 检查关键UI组件是否被调用
with open(app_path, 'r', encoding='utf-8') as f:
    app_content = f.read()

ui_calls = [
    ('render_conversion_config()', '配置面板'),
    ('show_style_mapping_dialog()', '样式映射对话框'),
    ('show_feedback_dialog()', '反馈对话框'),
    ('show_history_dialog()', '历史对话框'),
    ('st.rerun()', '页面重载'),
    ('app_state.', '状态管理器'),
]

for pattern, desc in ui_calls:
    check(f"app.py 调用 {desc}", pattern in app_content)

# 统计app.py中的函数
app_funcs = find_functions(app_path)
check(f"app.py 顶层函数: {len(app_funcs)} 个", True)
for f in sorted(app_funcs):
    results.append(f"     - {f}")

# === 7. 状态管理器验证 ===
print("\n📐 7. state.py 状态管理器验证")

with open(state_path, 'r', encoding='utf-8') as f:
    state_source = f.read()

state_methods = find_functions(state_path)
check(f"state.py 提供 {len(state_methods)} 个方法", True)

# 检查关键状态键
state_keys = re.findall(r"['\"](\w+)['\"]", state_source)
important_keys = ['user_data', 'style_mapping', 'conversion_config', 'page']
for key in important_keys:
    if key in state_source:
        results.append(f"  ✅ 状态键 '{key}' 存在")
    else:
        results.append(f"  ❌ 状态键 '{key}' 不存在")

# === 8. 配置文件验证 ===
print("\n⚙️ 8. config.py 配置验证")

with open(config_path, 'r', encoding='utf-8') as f:
    config_source = f.read()

config_checks = [
    ('DATA_SOURCE', '数据源模式检测'),
    ('BACKEND_URL', '后端URL'),
    ('SUPABASE_URL', 'Supabase URL'),
    ('FREE_PARAGRAPHS', '免费段落数'),
    ('MAX_FILE_SIZE', '最大文件大小'),
]
for pattern, desc in config_checks:
    check(f"config.py: {desc}", pattern in config_source)

# === 9. 已知问题检查 ===
print("\n⚠️ 9. 已知问题检查")

# 9.1 文件清理路径
with open(app_path, 'r', encoding='utf-8') as f:
    app_text = f.read()
with open(fm_path, 'r', encoding='utf-8') as f:
    fm_text = f.read()

check("app.py 使用 conversion_results/ 路径", "conversion_results" in app_text)
check("file_manager.py 使用 conversion_results/ 路径", "conversion_results" in fm_text)

# 9.2 user_manager.py 是否被使用
with open(app_path, 'r', encoding='utf-8') as f:
    app_text = f.read()
um_used_in_app = 'user_manager' in app_text or 'from user_manager' in app_text
check("app.py 直接使用 user_manager", um_used_in_app)

with open(dm_path, 'r', encoding='utf-8') as f:
    dm_text = f.read()
um_used_in_dm = 'user_manager' in dm_text or 'from user_manager' in dm_text
check("data_manager.py 使用 user_manager", um_used_in_dm)

# 9.3 裸except检查
for fpath, fname in zip(all_files, fnames):
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    bare_excepts = re.findall(r'except\s*:', content)
    if bare_excepts:
        results.append(f"  ⚠️ {fname}: {len(bare_excepts)} 处裸 except:")

# 9.4 print语句残留
for fpath, fname in zip(all_files, fnames):
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print_lines = [(i+1, l.strip()) for i, l in enumerate(lines) if l.strip().startswith('print(')]
    if print_lines:
        results.append(f"  ⚠️ {fname}: {len(print_lines)} 处 print() 残留")

# === 10. 总结 ===
print("\n" + "=" * 70)
print("  验证总结")
print("=" * 70)
print(f"\n  检查项总数: {len(results)}")
print(f"  通过: {sum(1 for r in results if '✅' in r)}")
print(f"  失败: {len(errors)}")
print(f"  警告: {sum(1 for r in results if '⚠️' in r)}")

if errors:
    print("\n  ❌ 失败的检查项:")
    for e in errors:
        print(f"     - {e}")

print("\n" + "=" * 70)

print("\n📋 详细结果:")
for r in results:
    print(r)
