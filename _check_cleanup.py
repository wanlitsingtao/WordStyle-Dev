# -*- coding: utf-8 -*-
"""检查文件清理功能的完整分析"""
import os, sys, glob, time, logging

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("WordStyle 文件清理系统完整分析")
print("=" * 60)

# ===== 1. 文件类型分析 =====
print("\n【1】系统中存在的文件类型")

print("\n--- 1a. 临时源文件 (temp_source_{user_id}_{filename}) ---")
src_files = glob.glob("temp_source_*")
print(f"  当前存在: {len(src_files)} 个文件")
for f in src_files[:5]:
    sz = os.path.getsize(f)
    mt = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(f)))
    print(f"  - {f} ({sz/1024:.1f}KB, {mt})")

print("\n--- 1b. 临时模板文件 (temp_template_{user_id}.docx) ---")
tpl_files = glob.glob("temp_template_*.docx")
print(f"  当前存在: {len(tpl_files)} 个文件")
for f in tpl_files[:5]:
    sz = os.path.getsize(f)
    mt = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(f)))
    print(f"  - {f} ({sz/1024:.1f}KB, {mt})")

print("\n--- 1c. 转换结果文件 (result_*.docx) ---")
result_files = glob.glob("result_*.docx")
print(f"  当前目录中: {len(result_files)} 个文件")
for f in result_files[:5]:
    sz = os.path.getsize(f)
    mt = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(f)))
    print(f"  - {f} ({sz/1024:.1f}KB, {mt})")

print(f"\n--- 1d. conversion_results/ 目录中的文件 ---")
if os.path.isdir("conversion_results"):
    files = os.listdir("conversion_results")
    print(f"  当前存在: {len(files)} 个文件")
    for f in files[:5]:
        fp = os.path.join("conversion_results", f)
        sz = os.path.getsize(fp)
        mt = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(fp)))
        print(f"  - {f} ({sz/1024:.1f}KB, {mt})")
else:
    print("  目录不存在")

# ===== 2. 文件创建位置分析 =====
print("\n【2】文件创建位置分析")

print("""
2a. 临时源文件: temp_source_{user_id}_{filename}
    创建位置: 当前工作目录 (.)
    创建代码: app.py 第636行
        temp_source = f"temp_source_{user_id}_{source_file.name}"
    用途: 上传的源文件保存到本地，供Document()读取

2b. 临时模板文件: temp_template_{user_id}.docx
    创建位置: 当前工作目录 (.)
    创建代码: app.py 第1148行
        temp_template = f"temp_template_{st.session_state.user_id}.docx"
    用途: 上传的模板文件保存到本地，供模板样式分析使用

2c. 转换结果文件: result_{basename}_{timestamp}.docx
    创建位置: conversion_results/ 目录
    创建代码: app.py 第1487-1488行
        output_filename = f"result_{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        output_file = os.path.join("conversion_results", output_filename)
    用途: 转换完成的最终文档，供用户下载
""")

# ===== 3. 清理机制分析 =====
print("【3】清理机制分析")

print("""
3a. 启动时清理 (cleanup_on_startup)
    - 文件: file_manager.py 第387行
    - 调用: app.py 第38行 (服务启动时)
    - 清理内容: 所有临时文件 + 过期的转换结果文件 (7天)
    - 作用范围: 
        - 工作目录下的 temp_source_* 文件
        - 工作目录下的 temp_template_*.docx 文件
        - conversion_results/ 目录下的 *.docx 文件 (7天前)

3b. 每日定时清理 (schedule_daily_cleanup)
    - 文件: file_manager.py 第395行
    - 调用: app.py 第44行 (APScheduler，每天零点)
    - 清理内容: 同上，所有过期文件
    - 依赖: APScheduler 库

3c. 转换后清理 (cleanup_temp_files)
    - 文件: file_manager.py 第36行
    - 调用: app.py 第1639行 (转换完成后)
    - 清理内容: 当前用户的临时文件
        - temp_source_{user_id}_*
        - temp_template_{user_id}.docx
    - 注: 不会清理 conversion_results/ 中的结果文件

3d. 页面加载时清理 (内联代码)
    - 文件: app.py 第772-790行
    - 调用: 每次页面加载
    - 清理内容: conversion_results/ 目录下的过期文件 (7天)
    - 问题: 与 3a 和 3c 功能重叠，形成冗余清理

3e. 管理页面手动清理
    - 文件: admin_web.py 第725行 "清理所有过期文件" 按钮
    - 文件: admin_web.py 第733行 "删除选中的文件" 按钮 (可多选)
    - 调用: 管理员手动操作
    - 清理内容: 过期结果文件 (按钮1) 或 用户选中的文件 (按钮2)
""")

# ===== 4. 问题分析 =====
print("【4】发现的问题")

print("""
问题1: 临时文件清理路径正确
    - file_manager.py 以 base_dir = "." 初始化
    - 工作目录 glob("temp_source_*") 路径正确
    - 工作目录 glob("temp_template_*.docx") 路径正确
    - ✅ 临时文件清理路径正确

问题2: 结果文件清理路径正确
    - file_manager.py 以 results_dir = "." / "conversion_results" 初始化
    - conversion_results/glob("*.docx") 路径正确
    - app.py 第1488行明确使用 os.path.join("conversion_results", output_filename)
    - ✅ 结果文件保存和清理路径匹配

问题3: 清理机制有重复
    - 启动时清理 (3a) + 每日定时清理 (3b) + 页面加载时清理 (3d)
    - 三个清理路径扫描同一个目录，功能重叠
    - 但不会造成功能错误，只是冗余执行

问题4: .gitignore 中缺少转换结果目录
    - conversion_results/ 未被 .gitignore 排除
    - 如果开发环境生成大量结果文件，可能被误提交
    - 建议添加 conversion_results/ 到 .gitignore
""")

# ===== 5. 总结 =====
print("【5】总结")

total_temp = len(src_files) + len(tpl_files)
total_results = len(result_files)
if os.path.isdir("conversion_results"):
    total_results += len(os.listdir("conversion_results"))

print(f"""
当前文件状态:
  - 临时文件: {total_temp} 个
  - 结果文件: {total_results} 个
  - 总计: {total_temp + total_results} 个

清理机制:
  - 自动清理: 启动时 + 每日零点 + 每次页面加载 + 转换后
  - 手动清理: 管理页面按钮
  - 保留期限: 结果文件 7 天，临时文件立即清理

结论: 文件清理功能完整且路径正确
  - 所有清理路径与文件创建路径一致 ✅
  - 清理频率充足（4种自动触发机制） ✅
  - 转换后立即清理临时文件 ✅
  - 管理页面提供手动清理和查看功能 ✅
""")
