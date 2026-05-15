# 03-Bug修复记录文档

## Bug 修复记录

### Bug #002: 用户可通过修改URL参数伪造身份领取免费额度

**日期**: 2026-05-15  
**严重级别**: 🔴 高危（High）  
**影响范围**: 所有云端部署环境（https://wordstyle.streamlit.app）  
**发现者**: 用户反馈  

---

#### 问题描述

在云端部署环境中，用户可以通过修改URL地址栏中的`uid`参数来伪造用户身份，每次修改都能获得新的用户ID并领取10,000段落免费额度。

**攻击示例**：
```
原始URL: https://wordstyle.streamlit.app/?uid=222356562671
修改后:  https://wordstyle.streamlit.app/?uid=999999999999
结果:    系统识别为新用户，分配10,000免费段落
```

**实际影响**：
- **经济损失**：用户可以无限获取免费转换额度
- **资源滥用**：服务器资源被恶意消耗
- **数据混乱**：数据库中产生大量虚假用户记录
- **业务逻辑失效**：免费额度限制完全失效

#### 业务需求（根据 01-业务需求文档.md）

**用户身份识别要求**（第6.4节 - 安全约束）：
1. **禁止信任URL参数中的用户ID**
   - ❌ 严禁从 `st.query_params['uid']` 读取用户ID并直接使用
   - ❌ 严禁将用户ID写入URL参数（避免在地址栏暴露）
   - ✅ 必须基于设备指纹（IP + User-Agent）生成唯一标识

2. **防刷机制**
   - 用户无法通过修改URL参数（如 `?uid=xxx`）来伪造身份
   - 每个设备只能领取一次新用户免费额度（10,000段落）

#### Bug 根因分析

**问题代码位置**：
- `app.py` 第221-313行（用户ID识别逻辑）

**根本原因**：
1. **无条件信任URL参数**：程序直接从 `st.query_params['uid']` 读取用户ID并使用
2. **缺少设备验证**：没有验证URL中的uid是否属于当前设备
3. **URL暴露用户ID**：将用户ID写入URL参数，让用户可以看到并修改

**代码示例（Bug 代码）**：
```python
# ❌ 旧代码（存在漏洞）
url_user_id = None
if hasattr(st, 'query_params'):
    params = st.query_params
    if 'uid' in params:
        url_user_id = params['uid']
        logger.info(f"✅ 从 URL 参数恢复用户ID: {url_user_id}")

if url_user_id and len(url_user_id) == 12:
    # URL 中有有效的用户ID，直接使用
    st.session_state.user_id = url_user_id  # ❌ 直接信任URL参数
    logger.info(f"使用 URL 参数中的用户ID: {url_user_id}")
else:
    # ... 生成新用户的逻辑
    
# ❌ 还将用户ID写入URL，让用户看到
st.query_params['uid'] = new_user_id
logger.info(f"✅ 已将用户ID写入 URL 参数: {new_user_id}")
```

#### 修复方案

**修复策略**：
1. **移除URL参数信任机制**：不再从URL读取用户ID
2. **使用设备指纹识别**：基于IP + User-Agent生成唯一设备标识
3. **本地映射持久化**：通过user_mapping.json关联设备和用户ID
4. **删除URL写入逻辑**：不再将用户ID暴露在URL中

**具体修改**：

1. **移除URL参数读取逻辑**（`app.py` 第221-236行）：
```python
# ❌ 删除的代码
url_user_id = None
try:
    if hasattr(st, 'query_params'):
        params = st.query_params
        if 'uid' in params:
            url_user_id = params['uid']
except Exception as e:
    logger.debug(f"URL 参数读取失败: {e}")

if url_user_id and len(url_user_id) == 12:
    st.session_state.user_id = url_user_id
    logger.info(f"使用 URL 参数中的用户ID: {url_user_id}")
else:
    # ... 原有逻辑
```

2. **改用设备指纹识别**（`app.py` 第221-289行）：
```python
# ✅ 新代码（安全）
# 🔧 第一步：生成设备指纹（基于IP+User-Agent）
# ⚠️ 安全修复：不再信任URL参数中的uid，防止用户伪造身份
existing_user_id = None

# 获取客户端设备指纹
try:
    headers = st.context.headers if hasattr(st, 'context') and hasattr(st.context, 'headers') else {}
    client_ip = headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not client_ip:
        client_ip = headers.get('X-Real-IP', '')
    if not client_ip:
        client_ip = '127.0.0.1'
    
    user_agent = headers.get('User-Agent', 'unknown')
    device_key = f"{client_ip}|{user_agent}"
    device_fingerprint = hashlib.md5(device_key.encode()).hexdigest()[:16]
    
    logger.info(f"检测到客户端 - IP: {client_ip}, User-Agent: {user_agent[:50]}...")
except Exception as e:
    logger.warning(f"无法获取客户端信息: {e}，使用备用方案")
    import socket
    try:
        hostname = socket.gethostname()
    except:
        hostname = "default"
    device_fingerprint = hashlib.md5(f"fallback_{hostname}".encode()).hexdigest()[:16]

# 从本地文件读取该设备对应的用户ID
user_mapping_file = Path(__file__).parent / "user_mapping.json"

try:
    if user_mapping_file.exists():
        with open(user_mapping_file, 'r', encoding='utf-8') as f:
            user_mapping = json.load(f)
            if device_fingerprint in user_mapping:
                existing_user_id = user_mapping[device_fingerprint]
                logger.info(f"✅ 从 user_mapping.json 恢复用户ID: {existing_user_id}")
except Exception as e:
    logger.error(f"读取用户映射文件失败: {e}")

if existing_user_id:
    # 使用已存在的用户ID
    st.session_state.user_id = existing_user_id
    user_id_to_use = existing_user_id
    logger.info(f"恢复已有用户ID: {existing_user_id}")
else:
    # 🔧 第二步：生成新的用户ID
    unique_key = f"wordstyle_device_{device_fingerprint}"
    new_user_id = hashlib.md5(unique_key.encode()).hexdigest()[:12]
    st.session_state.user_id = new_user_id
    user_id_to_use = new_user_id
    logger.info(f"生成新用户ID: {new_user_id} (device: {device_fingerprint})")
    
    # ✅ 保存设备指纹到用户ID的映射（本地环境）
    try:
        user_mapping = {}
        if user_mapping_file.exists():
            with open(user_mapping_file, 'r', encoding='utf-8') as f:
                user_mapping = json.load(f)
        
        user_mapping[device_fingerprint] = new_user_id
        
        with open(user_mapping_file, 'w', encoding='utf-8') as f:
            json.dump(user_mapping, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 已保存设备指纹映射到文件: {device_fingerprint} -> {new_user_id}")
    except Exception as e:
        logger.error(f"保存用户映射文件失败: {e}")
        logger.warning("⚠️ 云端环境无法持久化 user_mapping.json")
```

3. **删除URL参数写入逻辑**（`app.py` 第307-313行）：
```python
# ❌ 删除的代码
try:
    if hasattr(st, 'query_params'):
        st.query_params['uid'] = new_user_id
        logger.info(f"✅ 已将用户ID写入 URL 参数: {new_user_id}")
except Exception as e:
    logger.warning(f"写入 URL 参数失败: {e}")
```

#### 修复验证

**测试步骤**：
1. ✅ 正常访问测试：访问 https://wordstyle.streamlit.app，观察是否生成了新的用户ID
2. ✅ 刷新页面测试：刷新页面，确认用户ID保持不变
3. ✅ URL篡改测试：访问 `https://wordstyle.streamlit.app/?uid=999999999999`，检查实际使用的用户ID是否为999999999999
   - **预期结果**：应该忽略URL参数，使用设备指纹生成的ID
4. ✅ 额度领取测试：新用户首次访问，检查是否获得10,000免费额度
5. ✅ 防刷测试：修改URL参数后再次访问，检查是否能再次领取额度
   - **预期结果**：只能领取一次，修改URL无效

**验证结果**：
- ✅ URL参数篡改测试通过
- ✅ 设备指纹识别正常工作
- ✅ 用户ID稳定性符合预期
- ✅ 免费额度防刷机制生效

#### 修复影响评估

**修改文件**：
1. ✅ `app.py` - 移除URL参数读取和写入逻辑，改用设备指纹识别

**代码变更统计**：
- 删除81行不安全代码
- 新增57行安全代码
- 净减少24行代码

**影响范围**：
- ✅ 前端应用：用户ID识别逻辑更新
- ✅ 用户体验：URL中不再显示uid参数
- ✅ 安全性：防止身份伪造和额度滥用
- ✅ 向后兼容：已有用户的转换记录和额度数据不受影响

**风险评估**：
- ✅ 低风险：仅修改用户识别逻辑，不影响其他功能
- ✅ 符合编程原则2（功能稳定性）和原则5（系统性思考）
- ✅ 解决了严重的安全漏洞，防止资源滥用

**剩余风险**：
- ⚠️ 高级用户可通过更换IP或User-Agent生成新用户ID
- **缓解措施**：
  - 对于普通用户，更换IP/UA的成本较高
  - 后端可添加速率限制和异常检测
  - 考虑引入验证码机制（对可疑行为要求人机验证）

#### 修复日期

**修复完成时间**: 2026年5月15日  
**修复人员**: AI Assistant (Lingma)  
**审核状态**: 已部署  
**Git提交**: `6815ab7` - "修复严重安全漏洞：防止用户通过修改URL参数伪造身份"  
**部署平台**: Streamlit Cloud (https://wordstyle.streamlit.app)  

**相关文档**：
- 📄 `安全漏洞修复_用户身份伪造.md` - 详细的安全修复说明文档
- 📄 `docs/01-业务需求文档.md` - 补充了第6.4节安全约束
- 📄 `docs/02-系统设计文档.md` - 更新了用户识别与持久化章节

---

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
