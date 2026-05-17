print("""
================================================================
                    WordStyle 问题诊断报告
================================================================

一、问题现象
-----------
用户页面：获取用户ID失败
管理页面：未找到用户数据
API返回：500 Internal Server Error
  ERROR: column users.conversion_history does not exist

二、根因分析
-----------
【直接原因】数据库 users 表缺少 conversion_history 列
【深层原因】Alembic 迁移链断裂

迁移文件 revision 链分析：
  001 (initial) ── 根迁移
    ↓ down_revision=20260507_1200_001 ❌ 不匹配！
  20260510_2400_002 (add_stats) ── revision=20260510_2400_002
    ↓ down_revision=20260510_2400_002 ✅
  002 (fix_id_type) ── revision=002
    ↓ down_revision=002 ✅
  20260515_184559 (add_device_fingerprint)
    ↓ down_revision=20260515_184559 ✅
  20260516_120000 (add_last_claim_date)
    ↓ down_revision=20260516_120000 ✅
  20260530_120000 (add_conversion_history) ── 无法应用！

关键断裂点：20260510_2400_002 的 down_revision 写的是 '20260507_1200_001'
但 001_initial.py 实际的 revision 是 '001'（不是加前缀的版本）
导致 Alembic 无法找到父迁移，整个链后续的迁移全部跳过

三、修复方案
-----------
方案A（推荐）：修正 20260510_2400_002 的 down_revision
  将 down_revision = '20260507_1200_001'
  改为 down_revision = '001'

方案B：在数据库中直接执行 SQL
  ALTER TABLE users ADD COLUMN conversion_history JSONB DEFAULT '[]'::jsonb;

四、验证方法
-----------
修复后重新部署 Render 服务
POST /api/admin/users/by-device 应返回 200
GET /api/admin/users 应返回用户列表
================================================================
""")
