"""add conversion_history to users table

Revision ID: 20260530_120000
Revises: 20260516_120000
Create Date: 2026-05-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '20260530_120000'
down_revision = '20260516_120000'  # 依赖于 add_last_claim_date
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加conversion_history字段到users表"""
    # 检查字段是否已存在（避免重复执行）
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'conversion_history' not in columns:
        # PostgreSQL 使用 JSONB，SQLite 使用 JSON
        if conn.dialect.name == 'postgresql':
            op.add_column('users', sa.Column('conversion_history', JSONB, nullable=True, server_default='[]'))
            print("✅ 已添加 conversion_history 字段 (JSONB)")
        else:
            # SQLite 不支持 JSONB，使用 TEXT 存储 JSON
            op.add_column('users', sa.Column('conversion_history', sa.Text, nullable=True))
            print("✅ 已添加 conversion_history 字段 (TEXT for SQLite)")
    else:
        print("⚠️ conversion_history 字段已存在，跳过")


def downgrade() -> None:
    """回滚：删除conversion_history字段"""
    op.drop_column('users', 'conversion_history')
    print("✅ 已删除 conversion_history 字段")
