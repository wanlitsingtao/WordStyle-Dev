#!/usr/bin/env python
"""详细分析WSprj app.py的完整页面流程"""
app_path = r'E:\LingMa\WSprj\app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 分段标记
sections = []
current_section = "开头"
section_lines = []
for i, line in enumerate(lines):
    stripped = line.strip()
    # 检测分段标记
    if stripped.startswith('# =====') or stripped.startswith("st.subheader("):
        if stripped.startswith('# ====='):
            if section_lines:
                sections.append((current_section, section_lines[0][0], section_lines[-1][0], len(section_lines)))
            current_section = stripped[:80]
            section_lines = [(i+1, stripped)]
        else:
            if section_lines:
                sections.append((current_section, section_lines[0][0], section_lines[-1][0], len(section_lines)))
            current_section = stripped[:80]
            section_lines = [(i+1, stripped)]
    else:
        section_lines.append((i+1, stripped))

if section_lines:
    sections.append((current_section, section_lines[0][0], section_lines[-1][0], len(section_lines)))

# 只输出有意义的代码段（跳过空段和纯注释段）
print("="*70)
print("app.py 页面结构概览")
print("="*70)
for name, start, end, cnt in sections:
    if cnt > 2:  # 跳过太短的段
        print(f"  {start:4d}-{end:4d} ({cnt:3d}行) | {name[:80]}")

# 检查关键功能点
print("\n" + "="*70)
print("关键功能点检查")
print("="*70)

full_text = ''.join(lines)

checks = [
    ("render_conversion_config() 调用", "render_conversion_config(" in full_text),
    ("show_style_mapping_dialog() 调用", "show_style_mapping_dialog(" in full_text),
    ("开始转换按钮", "st.button" in full_text and "开始转换" in full_text),
    ("转换执行函数", "def do_convert" in full_text or "def convert" in full_text),
    ("st.rerun() 使用", "st.rerun()" in full_text),
    ("do_mood_config checkbox控件", "st.checkbox" in full_text and "do_mood" in full_text),
    ("list_bullet_config text_input控件", "st.text_input" in full_text and "list_bullet" in full_text),
    ("answer_style_config selectbox控件", "st.selectbox" in full_text),
    ("config_panel.py的get_answer_mode_options", "章节前插入" in full_text),
    ("app.py的get_answer_mode_options", "章节前插入" in full_text),
]

for desc, result in checks:
    status = "✅" if result else "❌"
    print(f"  {status} {desc}")
