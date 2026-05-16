"""
代码同步检查工具 - 对比发布目录和工作目录的关键文件
"""
import os

# 定义需要检查的文件列表
files_to_check = [
    'app.py',
    'config.py',
    'data_manager.py',
    'requirements.txt'
]

publish_dir = r'E:\LingMa\WordStyle'
work_dir = r'E:\LingMa\WSprj'

print("="*70)
print("代码同步检查报告")
print("="*70)
print(f"发布目录: {publish_dir}")
print(f"工作目录: {work_dir}")
print("="*70)

all_consistent = True

for filename in files_to_check:
    file1 = os.path.join(publish_dir, filename)
    file2 = os.path.join(work_dir, filename)
    
    if not os.path.exists(file1):
        print(f"❌ {filename}: 发布目录中不存在")
        all_consistent = False
        continue
    
    if not os.path.exists(file2):
        print(f"❌ {filename}: 工作目录中不存在")
        all_consistent = False
        continue
    
    try:
        with open(file1, 'r', encoding='utf-8') as f1, open(file2, 'r', encoding='utf-8') as f2:
            content1 = f1.read()
            content2 = f2.read()
            
            if content1 == content2:
                print(f"✅ {filename}: 完全一致 ({len(content1.splitlines())}行)")
            else:
                lines1 = len(content1.splitlines())
                lines2 = len(content2.splitlines())
                print(f"⚠️  {filename}: 不一致 (发布:{lines1}行 vs 工作:{lines2}行)")
                all_consistent = False
    except Exception as e:
        print(f"❌ {filename}: 读取失败 - {e}")
        all_consistent = False

print("="*70)
if all_consistent:
    print("✅ 所有文件都已同步！")
else:
    print("⚠️  存在不一致的文件，建议从发布目录同步到工作目录")
print("="*70)
