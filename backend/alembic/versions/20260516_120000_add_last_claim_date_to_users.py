"""add last_claim_date to users table

Revision ID: 20260516_120000
Revises: 20260515_184559
Create Date: 2026-05-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260516_120000'
down_revision = '20260515_184559'  # 依赖于 add_device_fingerprint
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加last_claim_date字段到users表"""
    # 检查字段是否已存在（避免重复执行）
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'last_claim_date' not in columns:
        op.add_column('users', sa.Column('last_claim_date', sa.DateTime(timezone=True), nullable=True))
        print("✅ 已添加 last_claim_date 字段")
    else:
        print("⚠️ last_claim_date 字段已存在，跳过")


def downgrade() -> None:
    """回滚：删除last_claim_date字段"""
    op.drop_column('users', 'last_claim_date')
    print("✅ 已删除 last_claim_date 字段")
