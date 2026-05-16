"""fix users table id column type - from UUID to VARCHAR(12)

Revision ID: 002
Revises: 001
Create Date: 2026-05-11 10:00:00.000000

说明：此迁移脚本用于将 users 表的 id 字段从 UUID 类型改为 VARCHAR(12) 类型，
以匹配应用层生成的 12 位字符串用户 ID。

由于 PostgreSQL 不允许直接修改主键列的类型，需要：
1. 删除依赖的外键约束
2. 删除主键约束
3. 删除旧的 UUID 类型 id 列
4. 添加新的 VARCHAR(12) 类型 id 列作为主键
5. 重新添加外键约束
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '20260510_2400_002'  # 依赖于 add_user_stats_fields
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库结构"""
    
    # 第1步：删除外键约束
    print("第1步：删除外键约束...")
    op.drop_constraint('orders_user_id_fkey', 'orders', type_='foreignkey')
    op.drop_constraint('conversion_tasks_user_id_fkey', 'conversion_tasks', type_='foreignkey')
    print("✅ 外键约束已删除")
    
    # 第2步：删除 users 表的主键约束
    print("第2步：删除主键约束...")
    op.drop_constraint('users_pkey', 'users', type_='primary')
    print("✅ 主键约束已删除")
    
    # 第3步：删除旧的 UUID 类型 id 列
    print("第3步：删除旧的 id 列...")
    op.drop_column('users', 'id')
    print("✅ 旧 id 列已删除")
    
    # 第4步：添加新的 VARCHAR(12) 类型 id 列（不带 primary_key 参数）
    print("第4步：添加新的 id 列...")
    op.add_column('users', sa.Column('id', sa.String(12), nullable=False))
    print("✅ 新 id 列已添加")
    
    # 第4b步：创建主键约束
    print("第4b步：创建主键约束...")
    op.create_primary_key('users_pkey', 'users', ['id'])
    print("✅ 主键约束已创建")
    
    # 第5步：修改 orders 表的 user_id 字段类型
    print("第5步：修改 orders.user_id 类型...")
    op.alter_column('orders', 'user_id',
                    existing_type=sa.String(36),  # UUID 字符串长度
                    type_=sa.String(12))
    print("✅ orders.user_id 类型已修改")
    
    # 第6步：修改 conversion_tasks 表的 user_id 字段类型
    print("第6步：修改 conversion_tasks.user_id 类型...")
    op.alter_column('conversion_tasks', 'user_id',
                    existing_type=sa.String(36),  # UUID 字符串长度
                    type_=sa.String(12))
    print("✅ conversion_tasks.user_id 类型已修改")
    
    # 第7步：重新添加外键约束
    print("第7步：重新添加外键约束...")
    op.create_foreign_key('orders_user_id_fkey', 'orders', 'users',
                          ['user_id'], ['id'])
    op.create_foreign_key('conversion_tasks_user_id_fkey', 'conversion_tasks', 'users',
                          ['user_id'], ['id'])
    print("✅ 外键约束已重新添加")
    
    print("\n🎉 数据库迁移完成！")


def downgrade():
    """回滚数据库结构（不推荐，因为会丢失数据）"""
    print("️  警告：回滚操作将删除所有用户数据！")
    print("如果需要回滚，请手动执行以下操作：")
    print("1. 备份当前数据")
    print("2. 删除外键约束")
    print("3. 修改字段类型回 UUID")
    print("4. 重新添加外键约束")
    pass
