# -*- coding: utf-8 -*-
"""
账号绑定/登录管理模块 (独立可复用)

提供两套并行用户方案：
  轨道一：设备指纹（现有，零门槛，自动分配）
  轨道二：账号绑定/登录（新增，可选，跨设备识别）

设计原则：
  - 独立模块，不依赖段落额度逻辑
  - 可在其他程序复用
  - 密码使用 SHA-256 哈希存储
  - 用户名不区分大小写、不可重复
  - 一个设备指纹只能绑定一个用户名

使用方式：
  from account_manager import AccountManager
  mgr = AccountManager(data_source="local")       # 本地 JSON
  mgr = AccountManager(data_source="supabase")    # Supabase
  mgr = AccountManager(data_source="api")         # 后端 API
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """SHA-256 哈希密码（不依赖任何额度逻辑）"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


class AccountManager:
    """
    账号管理器 —— 纯账号绑定/登录逻辑，不涉及段落额度。

    存储结构 (local 模式):
        data/accounts.json:
        {
            "by_device": {                    # 设备指纹 → 用户名
                "<device_fingerprint>": "<username_lower>"
            },
            "accounts": {                     # 用户名 → 账号信息
                "<username_lower>": {
                    "username": "<原始用户名>",
                    "password_hash": "<sha256>",
                    "bound_device": "<device_fingerprint>",
                    "created_at": "<iso_datetime>"
                }
            }
        }
    """

    def __init__(self, data_source: str = "local", db_url: str = None, backend_url: str = None):
        """
        Args:
            data_source: "local" | "supabase" | "api"
            db_url: 数据库连接 URL（supabase 模式）
            backend_url: 后端 API 地址（api 模式）
        """
        self.data_source = data_source
        self.db_url = db_url
        self.backend_url = backend_url
        self._accounts_file = None

    # ==================== 本地模式 ====================

    def _get_accounts_file(self) -> Path:
        if self._accounts_file is None:
            self._accounts_file = Path(__file__).parent / "data" / "accounts.json"
        return self._accounts_file

    def _load_local_accounts(self) -> dict:
        f = self._get_accounts_file()
        if f.exists():
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    return json.load(fh)
            except Exception:
                pass
        return {"by_device": {}, "accounts": {}}

    def _save_local_accounts(self, data: dict):
        f = self._get_accounts_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    # ==================== 公共 API ====================

    def bind_account(self, device_fingerprint: str, username: str, password: str) -> Tuple[bool, str]:
        """
        将设备指纹绑定到用户名/密码。

        Args:
            device_fingerprint: 设备指纹
            username: 用户名（不区分大小写）
            password: 明文密码

        Returns:
            (success, message)
        """
        username_lower = username.strip().lower()
        if not username_lower:
            return False, "用户名不能为空"
        if not password or len(password.strip()) < 1:
            return False, "密码不能为空"

        if self.data_source == "local":
            return self._bind_local(device_fingerprint, username, username_lower, password)
        elif self.data_source == "supabase":
            return self._bind_supabase(device_fingerprint, username, username_lower, password)
        elif self.data_source == "api":
            return self._bind_api(device_fingerprint, username, username_lower, password)

    def login_account(self, username: str, password: str) -> Tuple[bool, str, Optional[str]]:
        """
        使用用户名和密码登录。

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            (success, message, user_id_or_None)
        """
        username_lower = username.strip().lower()
        if not username_lower or not password:
            return False, "用户名和密码不能为空", None

        if self.data_source == "local":
            return self._login_local(username_lower, password)
        elif self.data_source == "supabase":
            return self._login_supabase(username_lower, password)
        elif self.data_source == "api":
            return self._login_api(username_lower, password)

    def get_bound_account(self, device_fingerprint: str) -> Optional[dict]:
        """
        查询设备指纹绑定的账号。

        Returns:
            {"username": ..., "created_at": ...} 或 None
        """
        if self.data_source == "local":
            data = self._load_local_accounts()
            username_lower = data.get("by_device", {}).get(device_fingerprint)
            if username_lower and username_lower in data.get("accounts", {}):
                acct = data["accounts"][username_lower]
                return {"username": acct["username"], "created_at": acct["created_at"]}
        elif self.data_source == "supabase":
            return self._get_bound_supabase(device_fingerprint)
        return None

    def is_username_taken(self, username: str) -> bool:
        """检查用户名是否已被占用（不区分大小写）"""
        username_lower = username.strip().lower()
        if self.data_source == "local":
            data = self._load_local_accounts()
            return username_lower in data.get("accounts", {})
        elif self.data_source == "supabase":
            return self._username_taken_supabase(username_lower)
        return False

    def get_user_id_for_username(self, username: str) -> Optional[str]:
        """
        通过用户名获取 user_id。用于登录后切换身份。

        Returns: user_id 或 None
        """
        username_lower = username.strip().lower()
        if self.data_source == "local":
            data = self._load_local_accounts()
            if username_lower in data.get("accounts", {}):
                acct = data["accounts"][username_lower]
                # 查找 user_mapping.json 中该设备指纹的 user_id
                mapping_file = Path(__file__).parent / "user_mapping.json"
                if mapping_file.exists():
                    try:
                        with open(mapping_file, 'r', encoding='utf-8') as f:
                            mapping = json.load(f)
                        return mapping.get(acct["bound_device"])
                    except Exception:
                        pass
        elif self.data_source == "supabase":
            return self._get_user_id_supabase(username_lower)
        return None

    # ==================== Local 实现 ====================

    def _bind_local(self, device_fp: str, username: str, username_lower: str, password: str) -> Tuple[bool, str]:
        data = self._load_local_accounts()

        # 检查该设备指纹是否已绑定
        if device_fp in data.get("by_device", {}):
            existing = data["by_device"][device_fp]
            return False, f"该设备已绑定账号「{existing}」，一个设备只能绑定一个账号"

        # 检查用户名是否已存在
        if username_lower in data.get("accounts", {}):
            return False, f"用户名「{username}」已被使用，请更换"

        data["by_device"][device_fp] = username_lower
        data["accounts"][username_lower] = {
            "username": username.strip(),
            "password_hash": _hash_password(password),
            "bound_device": device_fp,
            "created_at": datetime.now().isoformat(),
        }
        self._save_local_accounts(data)
        logger.info(f"账号绑定成功: 设备 {device_fp[:12]}... → 用户名 {username}")
        return True, f"账号「{username}」绑定成功！"

    def _login_local(self, username_lower: str, password: str) -> Tuple[bool, str, Optional[str]]:
        data = self._load_local_accounts()
        acct = data.get("accounts", {}).get(username_lower)
        if not acct:
            return False, "用户名或密码错误", None
        if acct["password_hash"] != _hash_password(password):
            return False, "用户名或密码错误", None

        # 获取该账号绑定设备的 user_id
        mapping_file = Path(__file__).parent / "user_mapping.json"
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)
                user_id = mapping.get(acct["bound_device"])
                if user_id:
                    return True, f"登录成功，欢迎 {acct['username']}！", user_id
            except Exception as e:
                logger.error(f"读取 user_mapping 失败: {e}")

        return False, "账号数据异常，请联系管理员", None

    # ==================== Supabase 实现 ====================

    def _get_supabase_engine(self):
        """获取 Supabase 数据库引擎"""
        import sys
        from pathlib import Path
        backend_path = Path(__file__).parent / "backend"
        sys.path.insert(0, str(backend_path))
        from app.core.database import SessionLocal
        return SessionLocal

    def _bind_supabase(self, device_fp: str, username: str, username_lower: str, password: str) -> Tuple[bool, str]:
        try:
            SessionLocal = self._get_supabase_engine()
            db = SessionLocal()
            try:
                from app.models import User

                # 检查该设备是否已有绑定的用户名
                existing = db.query(User).filter(
                    User.device_fingerprint == device_fp
                ).first()
                if existing and existing.username and existing.username.strip():
                    return False, f"该设备已绑定账号「{existing.username}」，一个设备只能绑定一个账号"

                # 检查用户名是否已存在（不区分大小写）
                from sqlalchemy import func
                dup = db.query(User).filter(
                    func.lower(User.username) == username_lower
                ).first()
                if dup:
                    return False, f"用户名「{username}」已被使用，请更换"

                # 更新用户记录
                if existing:
                    existing.username = username.strip()
                    existing.password_hash = _hash_password(password)
                    existing.updated_at = datetime.now()
                else:
                    # 创建新用户
                    import hashlib as hl
                    user_id = hl.md5(f"wordstyle_device_{device_fp}".encode()).hexdigest()[:12]
                    new_user = User(
                        id=user_id,
                        device_fingerprint=device_fp,
                        username=username.strip(),
                        password_hash=_hash_password(password),
                        paragraphs_remaining=10000,  # 默认额度，后续由 claim 逻辑刷新
                        is_active=True,
                        created_at=datetime.now(),
                        last_login=datetime.now(),
                    )
                    db.add(new_user)
                db.commit()
                logger.info(f"[Supabase] 账号绑定成功: 设备 {device_fp[:12]}... → 用户名 {username}")
                return True, f"账号「{username}」绑定成功！"
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[Supabase] 绑定账号失败: {e}")
            return False, f"绑定失败: {e}"

    def _login_supabase(self, username_lower: str, password: str) -> Tuple[bool, str, Optional[str]]:
        try:
            SessionLocal = self._get_supabase_engine()
            db = SessionLocal()
            try:
                from app.models import User
                from sqlalchemy import func

                user = db.query(User).filter(
                    func.lower(User.username) == username_lower
                ).first()
                if not user:
                    return False, "用户名或密码错误", None
                stored_hash = getattr(user, 'password_hash', None)
                if not stored_hash or stored_hash != _hash_password(password):
                    return False, "用户名或密码错误", None

                # 更新最后登录时间
                user.last_login = datetime.now()
                db.commit()
                return True, f"登录成功，欢迎 {user.username}！", user.id
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[Supabase] 登录失败: {e}")
            return False, f"登录失败: {e}", None

    def _get_bound_supabase(self, device_fp: str) -> Optional[dict]:
        try:
            SessionLocal = self._get_supabase_engine()
            db = SessionLocal()
            try:
                from app.models import User
                user = db.query(User).filter(User.device_fingerprint == device_fp).first()
                if user and user.username:
                    return {
                        "username": user.username,
                        "created_at": user.created_at.isoformat() if user.created_at else "",
                    }
            finally:
                db.close()
        except Exception:
            pass
        return None

    def _username_taken_supabase(self, username_lower: str) -> bool:
        try:
            SessionLocal = self._get_supabase_engine()
            db = SessionLocal()
            try:
                from app.models import User
                from sqlalchemy import func
                return db.query(User).filter(
                    func.lower(User.username) == username_lower
                ).count() > 0
            finally:
                db.close()
        except Exception:
            return False

    def _get_user_id_supabase(self, username_lower: str) -> Optional[str]:
        try:
            SessionLocal = self._get_supabase_engine()
            db = SessionLocal()
            try:
                from app.models import User
                from sqlalchemy import func
                user = db.query(User).filter(
                    func.lower(User.username) == username_lower
                ).first()
                return user.id if user else None
            finally:
                db.close()
        except Exception:
            return None

    # ==================== API 模式实现（占位） ====================

    def _bind_api(self, device_fp: str, username: str, username_lower: str, password: str) -> Tuple[bool, str]:
        return False, "API 模式暂不支持账号绑定，请使用设备指纹"

    def _login_api(self, username_lower: str, password: str) -> Tuple[bool, str, Optional[str]]:
        return False, "API 模式暂不支持账号登录，请使用设备指纹"


# ==================== 便捷工厂函数 ====================

def create_account_manager(data_source: str = None, db_url: str = None, backend_url: str = None) -> AccountManager:
    """
    根据数据源创建 AccountManager 实例。

    若未传入参数，自动从 config 读取。
    """
    if data_source is None:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from config import DATA_SOURCE, DATABASE_URL, BACKEND_URL
        data_source = DATA_SOURCE
        db_url = DATABASE_URL
        backend_url = BACKEND_URL
    return AccountManager(data_source=data_source, db_url=db_url, backend_url=backend_url)
