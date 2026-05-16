"""add device_fingerprint to users table

Revision ID: 20260515_184559
Revises: 
Create Date: 2026-05-15 18:45:59.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260515_184559'
down_revision = '002'  # 依赖于 fix_users_id_type
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加device_fingerprint字段到users表"""
    # 检查字段是否已存在（避免重复执行）
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'device_fingerprint' not in columns:
        op.add_column('users', sa.Column('device_fingerprint', sa.String(64), nullable=True))
        op.create_index(op.f('ix_users_device_fingerprint'), 'users', ['device_fingerprint'], unique=False)
        print("✅ 已添加 device_fingerprint 字段")
    else:
        print("⚠️ device_fingerprint 字段已存在，跳过")


def downgrade() -> None:
    """回滚：删除device_fingerprint字段"""
    op.drop_index(op.f('ix_users_device_fingerprint'), table_name='users')
    op.drop_column('users', 'device_fingerprint')
    print("✅ 已删除 device_fingerprint 字段")
