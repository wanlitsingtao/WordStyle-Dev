"""initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2026-05-07 12:00:00.000000

说明：此迁移脚本用于创建所有数据库表结构。
适用于首次部署或新建数据库的场景。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """创建所有数据库表"""
    
    # 1. 创建 users 表
    print("创建 users 表...")
    op.create_table(
        'users',
        sa.Column('id', sa.String(12), primary_key=True),
        sa.Column('device_fingerprint', sa.String(32), unique=True, index=True),
        sa.Column('username', sa.String(50)),
        sa.Column('style_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('balance', sa.Float(), server_default='0.0'),
        sa.Column('paragraphs_remaining', sa.Integer(), server_default='0'),
        sa.Column('total_paragraphs_used', sa.Integer(), server_default='0'),
        sa.Column('total_converted', sa.Integer(), server_default='0'),
        sa.Column('conversion_history', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_login', sa.DateTime(timezone=True)),
        sa.Column('last_claim_date', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("[OK] users 表创建成功")
    
    # 2. 创建 conversion_tasks 表
    print("创建 conversion_tasks 表...")
    op.create_table(
        'conversion_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(12), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('source_file', sa.String(500), nullable=False),
        sa.Column('template_file', sa.String(500), nullable=False),
        sa.Column('converted_file', sa.String(500)),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('progress', sa.Integer(), server_default='0'),
        sa.Column('paragraphs', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("[OK] conversion_tasks 表创建成功")
    
    # 3. 创建 system_config 表
    print("创建 system_config 表...")
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('config_key', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('config_value', sa.Text(), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("[OK] system_config 表创建成功")
    
    # 4. 创建 comments 表
    print("创建 comments 表...")
    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(50)),
        sa.Column('username', sa.String(100)),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('rating', sa.Integer(), server_default='5'),
        sa.Column('likes', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    print("[OK] comments 表创建成功")
    
    # 5. 创建 feedbacks 表
    print("创建 feedbacks 表...")
    op.create_table(
        'feedbacks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(50)),
        sa.Column('feedback_type', sa.String(20)),
        sa.Column('title', sa.String(200)),
        sa.Column('description', sa.Text()),
        sa.Column('contact', sa.String(200)),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('reply', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("[OK] feedbacks 表创建成功")
    
    # 6. 创建 style_mappings 表
    print("创建 style_mappings 表...")
    op.create_table(
        'style_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.String(50), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('source_style', sa.String(255), nullable=False),
        sa.Column('target_style', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    print("[OK] style_mappings 表创建成功")
    
    # 7. 插入默认系统配置
    print("插入默认系统配置...")
    op.execute("""
        INSERT INTO system_config (config_key, config_value, description) VALUES
        ('free_paragraphs_on_first_login', '10000', '新用户首次登录赠送的免费段落数')
    """)
    print("[OK] 默认配置插入成功")


def downgrade():
    """回滚：删除所有表（按依赖顺序）"""
    print("开始回滚...")
    
    # 按相反顺序删除表
    op.drop_table('style_mappings')
    print("[OK] 已删除 style_mappings 表")
    
    op.drop_table('feedbacks')
    print("[OK] 已删除 feedbacks 表")
    
    op.drop_table('comments')
    print("[OK] 已删除 comments 表")
    
    op.drop_table('system_config')
    print("[OK] 已删除 system_config 表")
    
    op.drop_table('conversion_tasks')
    print("[OK] 已删除 conversion_tasks 表")
    
    op.drop_table('users')
    print("[OK] 已删除 users 表")
    
    print("[OK] 回滚完成")
