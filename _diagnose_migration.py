print("""
=====================================================
   迁移未执行的根本原因分析
=====================================================

关键发现：main.py 中的 run_migrations() 函数有一个
严重的逻辑错误：

    # 第39-45行: 先 stamp head
    command.stamp(alembic_cfg, "head")  
    
    # 第47-49行: 再执行迁移
    command.upgrade(alembic_cfg, "head")

问题：
1. command.stamp(cfg, "head") 会将 alembic_version 表
   中的版本号直接设置为 head（即最新的迁移版本）
   
2. 然后 command.upgrade(cfg, "head") 检查发现当前版本
   已经是 head，所以不会执行任何迁移！

3. 结果：conversion_history 列从未被实际创建！

更详细的说明：
- 假设数据库原来版本是 20260516_120000
- stamp head 会把版本改为 20260530_120000（最新）
- upgrade 发现版本已经是 head，什么都不做
- 但 20260530_120000 的 upgrade() 函数从未被执行！

修复方案：
方案A（推荐）：删除 stamp 步骤，只保留 upgrade
  将 main.py 中 command.stamp(...) 那部分删除
  只保留 command.upgrade(alembic_cfg, "head")
  
方案B：在 upgrade 之前不要 stamp
  将 stamp 移到 upgrade 之后（作为失败回退）
  
方案C：直接手动在数据库中执行 SQL
  ALTER TABLE users ADD COLUMN conversion_history JSONB DEFAULT '[]'::jsonb;

当前代码：
    try:
        command.stamp(alembic_cfg, "head")  # 这一行！提前标记导致跳过
        logger.info("Stamp 成功")
    except Exception as stamp_error:
        logger.warning(f"Stamp 失败: {stamp_error}")
    
    logger.info("执行数据库迁移...")
    command.upgrade(alembic_cfg, "head")  # 检测到已是 head，跳过！
""")
