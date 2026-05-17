"""添加用户统计字段

Revision ID: 20260510_2400_002
Revises: 20260507_1200_001
Create Date: 2026-05-10 24:00:00.000000

说明：为users表添加total_paragraphs_used和total_converted字段
用于统计用户的累计使用情况和转换文件数量
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260510_2400_002'
down_revision = '001'  # ✅ 修复：指向正确的父迁移revision
branch_labels = None
depends_on = None


def upgrade():
    """升级：添加缺失的用户统计字段"""
    # 添加累计使用的段落数字段
    op.add_column('users', sa.Column('total_paragraphs_used', sa.Integer(), server_default=sa.text('0'), nullable=False))
    
    # 添加累计转换的文件数字段
    op.add_column('users', sa.Column('total_converted', sa.Integer(), server_default=sa.text('0'), nullable=False))


def downgrade():
    """降级：删除添加的字段"""
    op.drop_column('users', 'total_converted')
    op.drop_column('users', 'total_paragraphs_used')
