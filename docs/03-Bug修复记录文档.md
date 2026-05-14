# 03-Bug修复记录文档

## Bug 修复记录

### Bug #001: Supabase 模式下文档转换页面刷新重复领取免费额度

**日期**: 2026-04-30  
**严重级别**:  严重  
**影响范围**: 所有 Supabase 模式下的用户  
**发现者**: 用户反馈  

---

#### 问题描述

在 Supabase 模式下，用户每次刷新文档转换页面，系统都会自动增加 10,000 段落免费额度，导致用户段落额度无限增长，违反业务需求。

#### 业务需求（根据 01-业务需求文档.md）

**免费额度规则**（第134-137行、303-305行、430行）：
1. **每日免费额度**：10,000 段落
2. **每日自动重置，不累计**
3. **新用户首次访问自动领取**
4. **检查是否是今日首次访问，如是则自动领取**

**业务流程**（第4.1节 - 用户首次访问流程）：
```
1. 用户打开应用
2. 系统检查是否存在用户ID
3. 如无，生成新的用户ID（12位字符串）
4. 检查用户数据是否存在
5. 如无，创建新用户记录
6. 检查是否是今日首次访问 ✅ 关键步骤
7. 如是，自动领取每日免费额度（10,000段落）
8. 显示用户界面，展示剩余段落数
```

#### Bug 根因分析

**问题代码位置**：
- `data_manager.py` 第210-227行（Supabase 模式的 `_claim_free` 函数）
- `backend/app/api/admin.py` 第281-299行（API 模式的 `claim_free_paragraphs` 函数）

**根本原因**：
1. **缺少日期检查逻辑**：`_claim_free` 函数每次调用时直接执行 `user.paragraphs_remaining += FREE_PARAGRAPHS_DAILY`，没有检查今日是否已领取
2. **缺少 `last_claim_date` 字段**：User 模型中没有字段记录上次领取日期，无法判断是否重复领取
3. **违反"不累计"规则**：使用 `+=` 累加操作，而不是重置为固定额度

**代码示例（Bug 代码）**：
```python
def _claim_free(user_id=None):
    """领取免费段落（Supabase 模式）"""
    from config import FREE_PARAGRAPHS_DAILY
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.paragraphs_remaining += FREE_PARAGRAPHS_DAILY  #  Bug：直接累加
            db.commit()
            return FREE_PARAGRAPHS_DAILY
        return 0
    ...
```

#### 修复方案

**修复策略**：
1. 添加 `last_claim_date` 字段到 User 模型，记录上次领取日期
2. 修改 `_claim_free` 函数，添加日期检查逻辑
3. 修改为"重置"而非"累加"（`user.paragraphs_remaining = FREE_PARAGRAPHS_DAILY`）
4. 同时修复 Supabase 模式和 API 模式

**具体修改**：

1. **User 模型修改**（`backend/app/models.py`）：
```python
class User(Base):
    # ... 其他字段
    last_claim_date = Column(DateTime(timezone=True))  # ✅ 新增：上次领取免费额度日期
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

2. **数据访问层修改**（`data_manager.py` 第210-239行）：
```python
def _claim_free(user_id=None):
    """领取免费段落（Supabase 模式）- 每日只领取一次"""
    from config import FREE_PARAGRAPHS_DAILY
    from datetime import date
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            today = date.today()
            
            # ✅ 检查今日是否已领取
            if user.last_claim_date:
                last_claim = user.last_claim_date.date() if hasattr(user.last_claim_date, 'date') else user.last_claim_date
                if last_claim == today:
                    return 0  # ✅ 今日已领取，不再重复发放
            
            # ✅ 今日首次领取：重置为免费额度（不累计）
            user.paragraphs_remaining = FREE_PARAGRAPHS_DAILY
            user.last_claim_date = datetime.now()
            db.commit()
            return FREE_PARAGRAPHS_DAILY
        return 0
    except Exception as e:
        db.rollback()
        print(f"[WARN] 领取免费段落失败: {e}")
        return 0
    finally:
        db.close()
```

3. **后端 API 修改**（`backend/app/api/admin.py` 第281-313行）：
```python
@router.post("/users/{user_id}/claim-free")
def claim_free_paragraphs(user_id: str, db: Session = Depends(get_db)):
    """领取免费段落（供 API 模式调用）- 每日只领取一次"""
    from config import FREE_PARAGRAPHS_DAILY
    from datetime import datetime, date
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {'success': False, 'error': '用户不存在'}
    
    today = date.today()
    
    # ✅ 检查今日是否已领取
    if user.last_claim_date:
        last_claim = user.last_claim_date.date() if hasattr(user.last_claim_date, 'date') else user.last_claim_date
        if last_claim == today:
            return {
                'success': True,
                'paragraphs': 0,
                'message': '今日已领取过免费额度'
            }
    
    # ✅ 今日首次领取：重置为免费额度（不累计）
    user.paragraphs_remaining = FREE_PARAGRAPHS_DAILY
    user.last_claim_date = datetime.now()
    db.commit()
    
    return {
        'success': True,
        'paragraphs': FREE_PARAGRAPHS_DAILY,
        'message': f'已领取 {FREE_PARAGRAPHS_DAILY} 个免费段落'
    }
```

4. **数据库迁移脚本**（`migrate_add_last_claim_date.py`）：
```python
def add_last_claim_date_column():
    """添加 last_claim_date 字段"""
    db = SessionLocal()
    try:
        # 检查字段是否已存在
        check_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'last_claim_date'
        """
        result = db.execute(text(check_sql)).fetchone()
        
        if result:
            print("✅ last_claim_date 字段已存在，无需添加")
            return True
        
        # 添加字段
        add_sql = """
            ALTER TABLE users 
            ADD COLUMN last_claim_date TIMESTAMP WITH TIME ZONE
        """
        db.execute(text(add_sql))
        db.commit()
        
        print("✅ last_claim_date 字段添加成功")
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ 添加字段失败: {e}")
        return False
    finally:
        db.close()
```

#### 修复验证

**测试步骤**：
1. ✅ 执行数据库迁移脚本：`python migrate_add_last_claim_date.py`
2. ✅ 验证 `last_claim_date` 字段已成功添加到 Supabase 数据库
3. ⏳ 重启应用，刷新页面测试免费额度领取逻辑
4. ⏳ 验证今日首次刷新时正常领取10,000段落
5.  验证同一天内再次刷新时不再增加额度
6. ⏳ 验证跨天后再次刷新时重新领取10,000段落

**数据库迁移结果**：
```
✅ last_claim_date 字段添加成功
✅ 数据库迁移完成
```

#### 连锁Bug修复（重要发现）

**问题描述**：
在修复主Bug过程中，发现了一个严重的连锁Bug：
- `app.py` 第335行调用 `claim_free_paragraphs()` 设置了 `paragraphs_remaining = 10000`
- 但第338行调用 `register_or_login_user()` 时，传入的 `user_data['paragraphs_remaining']` 仍然是 0
- 导致数据库中的免费额度被覆盖为 0

**修复方案**：
```python
# ✅ 修复Bug：更新 user_data 中的 paragraphs_remaining，防止被 register_or_login_user 覆盖
if free_paragraphs > 0:
    user_data['paragraphs_remaining'] = free_paragraphs
```

**修改文件**：
- ✅ `app.py` 第334-340行

#### 修复影响评估

**修改文件**：
1. ✅ `backend/app/models.py` - User 模型添加 `last_claim_date` 字段
2. ✅ `data_manager.py` - Supabase 模式的 `_claim_free` 函数
3. ✅ `backend/app/api/admin.py` - API 模式的 `claim_free_paragraphs` 函数
4. ✅ `migrate_add_last_claim_date.py` - 新建数据库迁移脚本
5. ✅ `app.py` - 修复连锁Bug（更新 user_data 防止覆盖免费额度）

**影响范围**：
- ✅ 数据库：新增1个字段（向后兼容）
- ✅ Supabase 模式：免费额度领取逻辑更新
- ✅ API 模式：免费额度领取逻辑更新
- ✅ Local 模式：不受影响（已有独立实现）

**风险评估**：
- ✅ 低风险：新增字段有默认值 NULL，不影响现有数据
- ✅ 逻辑变更符合业务需求，修复了严重 Bug
- ✅ 向后兼容：旧用户的 `last_claim_date` 为 NULL，下次刷新会自动领取

#### 修复日期

**修复完成时间**: 2026-04-30  
**修复人员**: AI Assistant  
**审核状态**: 待验证  

---

## Bug 修复流程规范

### 1. 问题确认
- 明确 Bug 描述和复现步骤
- 提取业务需求文档中的相关要求
- 评估严重级别和影响范围

### 2. 根因分析
- 定位问题代码位置
- 分析代码逻辑与业务需求的差异
- 识别遗漏的检查或处理逻辑

### 3. 修复方案设计
- 制定修复策略（最小化改动原则）
- 考虑数据库变更（如需要添加字段）
- 评估影响范围和兼容性

### 4. 代码修改
- 遵循编程原则（不影响已有功能）
- 系统性地修改所有相关位置
- 添加必要的注释和日志

### 5. 数据库迁移
- 创建迁移脚本
- 执行迁移并验证
- 确保向后兼容

### 6. 测试验证
- 制定测试步骤
- 执行回归测试
- 验证 Bug 已修复且未引入新问题

### 7. 文档记录
- 在本文档中详细记录 Bug 修复过程
- 包含：问题描述、业务需求、根因分析、修复方案、验证结果
- 更新相关需求文档或设计文档（如需要）
