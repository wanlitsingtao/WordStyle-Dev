# -*- coding: utf-8 -*-
"""
用户身份解析模块（Identity v2）

==================== 为什么需要这个模块 ====================
原实现的"设备指纹"其实是 **User-Agent 的 md5**（`data_manager.generate_device_fingerprint`），
而 UA 字符串里只有「浏览器名+版本、操作系统+版本、渲染引擎」，不含任何设备唯一信息。
由此产生两个方向都错的身份缺陷（均已在生产库中被证实）：

  1. 【撞车】不同电脑但同版本浏览器 → 同一个 device_fingerprint
     → 命中同一行 users 记录 → 互相看到对方的额度、转换历史、样式映射，
       并能访问对方按 user_id 命名的临时文件（招投标原始文档）。
     生产证据：`ab3d99d04d8e` 反推 UA 为 "Edge 155 / Windows"，其指纹是
     md5("...Edg/155...")，凡 Edge 155 用户都会落到这一行。

  2. 【漂移】同一台电脑但浏览器自动升级 → UA 变了 → 指纹变了
     → 系统认为"新用户"，新建账号，老账号的额度与历史"凭空消失"。
     生产证据：Edge 148→150→151→152→153→154→155 各对应一个新账号。

  3. 【兜底并桶】`headers.get('User-Agent', 'unknown')` 取不到时，
     所有人都落到 md5("unknown") 这一行。
     生产证据：`38626eb82dc1` 即 md5("unknown")，该路径已在生产触发过。

==================== v2 方案 ====================
身份来源改为**浏览器端持久化随机 ID**（cookie `ws_bid`，UUID4，2 年）：
    device_fingerprint = md5("ws2|" + ws_bid)
它与浏览器版本、操作系统更新完全解耦，因此同时修好上面三个缺陷。

实现上刻意做到 **零第三方依赖、零数据库结构变更**：
  * 读 cookie：Streamlit 1.57 原生支持 `st.context.cookies`（只读 Mapping）。
  * 写 cookie：Streamlit 原生没有公开的写 cookie API，但 `st.html(..., unsafe_allow_javascript=True)`
    会把 `<script>` 保留（DOMPurify 配置为 ADD_TAGS:['script']）并**在主文档中执行**
    （`Html.js` → `unsafeAllowJavascript ? 重建 script 元素 : innerHTML`），
    因此可以直接用 `document.cookie` 写第一方 cookie，无需引入任何组件包。
  * 历史账号认领：不新增表/列，用一条原子 UPDATE 把老行的 device_fingerprint
    改写为 v2 指纹（见 `data_manager._claim_legacy_identity` / `backend admin /users/by-device`）。
    由于 v1 指纹在改写后即不再存在，天然**恰好一次**，无需额外的标记列。
  * 有效期续期：浏览器对 cookie 有效期有 400 天上限，且 max-age 不会因"用户又来了"
    而自动延长。故每次新会话顺带重写一次 cookie（`renew_identity_cookie`），
    使其成为**滑动窗口** —— 只要用户 400 天内来过一次，身份就持续有效。

==================== 稳定性边界（实测结论）====================
经过真实浏览器（Chromium 无头 + 持久化 profile）验证：
    首次访问写 cookie → ✓ 写入成功（有效期中止于浏览器 400 天上限）
    刷新 / 新开标签 / 关闭浏览器再打开 → ✓ 始终是同一个 bid，同一 user_id
    浏览器升级 / 系统升级（UA 变化）→ ✓ 完全不影响（身份已与 UA 解耦）

会让身份"换人"的情况（设计边界，非缺陷）：
    1) 清除浏览器 Cookie / 站点数据  → 下次是新 bid → 新账号（老额度仍在库里，但没有入口）
    2) 无痕/隐私窗口                  → 关闭即失效
    3) 换浏览器 / 换电脑 / 换用户配置 → 各自独立身份（这正是修复目标）
    4) iframe 嵌入（?embed=true）     → cookie 变第三方 cookie 被拦截，退化为 UA 指纹
    5) 域名不同（x.streamlit.app vs 自定义域名 / localhost vs 127.0.0.1）→ 视为不同站点

==================== 兼容与灰度 ====================
`config.IDENTITY_MODE` 三档：
  * "v1"   —— 完全回到旧行为（用于紧急回滚）
  * "dual" —— 默认。有 cookie 走 v2；无 cookie 先用 v1 身份跑完本次会话（保证老用户
              本次不丢数据），同时写入 cookie，下次访问即切到 v2 并认领历史账号
  * "v2"   —— 只认 cookie（用于灰度观察结束后的收口）
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Optional

# ==================== 常量 ====================
IDENTITY_COOKIE_NAME = "ws_bid"
COOKIE_MAX_AGE = 2 * 365 * 24 * 3600  # 2 年（秒）
_COOKIE_SAMESITE = "Lax"

_BID_RE = re.compile(r"^[0-9a-f]{32}$")
_V2_PREFIX = "ws2|"

# 身份来源（用于日志与界面提示）
SOURCE_COOKIE = "cookie"        # 命中了浏览器持久化 ID（正常态）
SOURCE_COOKIE_NEW = "cookie_new"  # 首次写入 cookie（本次仍用旧身份）
SOURCE_LEGACY = "legacy_ua"     # 无 cookie，降级用 UA（仅过渡期）
SOURCE_FALLBACK = "fallback"    # UA 也取不到，退化为会话级临时身份

# v1 兜底黑名单：这些输入产生的指纹是"多人共用桶"，禁止被认领
_UNTRUSTED_V1_INPUTS = frozenset({"", "unknown", "none", "null", "fallback"})

_MODE_V1, _MODE_DUAL, _MODE_V2 = "v1", "dual", "v2"


# ==================== 基础工具 ====================
def md5_hex(text: str) -> str:
    """32 位 MD5 十六进制。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# 对应的"共用桶"指纹（禁止被认领），如 md5("unknown") 就是生产库里那行 38626eb82dc1
_UNTRUSTED_V1_FINGERPRINTS = frozenset(md5_hex(x) for x in _UNTRUSTED_V1_INPUTS)


def fingerprint_from_ua(user_agent: str) -> str:
    """v1 指纹：md5(User-Agent)。

    保留此函数仅为**兼容与历史账号认领**，不再作为主身份使用。
    """
    return md5_hex(user_agent or "")


def fingerprint_from_bid(bid: str) -> str:
    """v2 指纹：md5("ws2|" + 浏览器持久化 ID)。"""
    return md5_hex(_V2_PREFIX + (bid or ""))


def new_bid() -> str:
    """生成浏览器持久化 ID（32 位 hex，等同 UUID4 无连字符形态）。"""
    return uuid.uuid4().hex


def new_user_id() -> str:
    """生成 12 位用户 ID。

    刻意改为**随机**而非 `md5("wordstyle_device_" + 指纹)[:12]`：
    旧写法使任何人在知道某人 UA 的情况下都能推算出其 user_id，属信息泄露。
    """
    return uuid.uuid4().hex[:12]


def is_trusted_legacy_input(user_agent: str) -> bool:
    """判断该 UA 是否可用于历史账号认领（排除 unknown/空 等共用桶）。"""
    return (user_agent or "").strip().lower() not in _UNTRUSTED_V1_INPUTS


def is_trusted_legacy_fingerprint(fingerprint) -> bool:
    """判断某个 v1 指纹是否允许被认领。

    拦截 md5("unknown") / md5("") 这类"多人共用桶"，
    以及形态不合法（非 32 位 hex）或已被改写成 v2 形态的值。
    """
    if not isinstance(fingerprint, str):
        return False
    fp = fingerprint.strip().lower()
    if not re.match(r"^[0-9a-f]{32}$", fp):
        return False
    return fp not in _UNTRUSTED_V1_FINGERPRINTS


def is_valid_bid(value) -> bool:
    return isinstance(value, str) and bool(_BID_RE.match(value.strip().lower()))


# ==================== 身份对象 ====================
@dataclass(frozen=True)
class Identity:
    """一次会话的身份解析结果。"""

    fingerprint: str                  # 用于 users.device_fingerprint 的值
    source: str                       # SOURCE_* 之一
    bid: Optional[str] = None         # 本次生效/待写入的浏览器持久化 ID
    legacy_fingerprint: Optional[str] = None  # 供服务端认领历史账号的 v1 指纹
    user_agent: str = ""
    should_write_cookie: bool = False # 是否需要在本次渲染中写入 cookie

    @property
    def is_legacy(self) -> bool:
        return self.source in (SOURCE_LEGACY, SOURCE_FALLBACK)

    @property
    def is_trusted(self) -> bool:
        """身份是否可信到"可以认领一个历史账号"。"""
        return self.source in (SOURCE_COOKIE, SOURCE_LEGACY) and bool(self.legacy_fingerprint)

    @property
    def should_renew_cookie(self) -> bool:
        """本次是否需要给 cookie 续期（滑动窗口）。

        仅在"身份已来自 cookie"时为真；此时每开一个新会话就把有效期重新计时，
        否则 cookie 会在**首次写入后固定天数**到期 —— 详见 `renew_identity_cookie`。
        """
        return self.source == SOURCE_COOKIE and bool(self.bid)

    def describe(self) -> str:
        """给日志/界面用的一句话描述。"""
        return f"source={self.source} fp={self.fingerprint[:12]}… bid={(self.bid or '-')[:8]}…"


# ==================== 环境读取 ====================
def _identity_mode() -> str:
    try:
        from config import IDENTITY_MODE  # 延迟导入，避免循环依赖
        mode = str(IDENTITY_MODE or _MODE_DUAL).strip().lower()
        return mode if mode in (_MODE_V1, _MODE_DUAL, _MODE_V2) else _MODE_DUAL
    except Exception:
        return _MODE_DUAL


def collect_user_agent() -> str:
    """采集 User-Agent（带降级链）。

    取不到时返回空串 —— 调用方会退化为会话级临时身份，
    **绝不再回退到 'unknown' 字面量**（那会让所有此类访问共用同一条记录）。
    """
    try:
        import streamlit as st
        headers = getattr(st.context, "headers", None)
        if not headers:
            return ""
        for key in ("User-Agent", "user-agent"):
            try:
                ua = headers.get(key)
            except Exception:
                ua = None
            if ua and str(ua).strip():
                return str(ua).strip()
        # 降级：Chromium 系客户端提示头（部分代理会剥掉 User-Agent）
        parts = []
        for key in ("sec-ch-ua", "sec-ch-ua-platform", "sec-ch-ua-mobile"):
            try:
                val = headers.get(key)
            except Exception:
                val = None
            if val:
                parts.append(str(val))
        return " ".join(parts).strip()
    except Exception:
        return ""


def _read_cookie_bid() -> Optional[str]:
    """从请求头 cookie 中读出浏览器持久化 ID（只读，原生能力）。"""
    try:
        import streamlit as st
        cookies = getattr(st.context, "cookies", None)
        if cookies is None:
            return None
        value = cookies.get(IDENTITY_COOKIE_NAME) if hasattr(cookies, "get") else None
        if value is None:
            try:
                value = cookies[IDENTITY_COOKIE_NAME]
            except Exception:
                value = None
        value = (value or "").strip().lower()
        return value if _BID_RE.match(value) else None
    except Exception:
        return None


def _session_salt() -> str:
    """会话级随机盐：让"取不到 UA"的访问彼此隔离（而不是共用一个账号）。"""
    try:
        import streamlit as st
        ss = st.session_state
        salt = ss.get("_identity_session_salt")
        if not salt:
            salt = uuid.uuid4().hex
            ss["_identity_session_salt"] = salt
        return salt
    except Exception:
        return uuid.uuid4().hex


# ==================== cookie 写入 ====================
def _cookie_pair(value: str, max_age: int) -> str:
    """拼出 document.cookie 赋值串。

    刻意用字符串拼接而非 format/f-string —— JS 函数体里全是花括号，
    用 format 会把它们当占位符解析（已踩过：ValueError: unexpected '{' in field name）。
    """
    return (
        IDENTITY_COOKIE_NAME + "=" + value
        + "; max-age=" + str(max_age)
        + "; path=/; SameSite=" + _COOKIE_SAMESITE
    )


def _cookie_script(bid: str) -> str:
    return (
        "<script>(function(){try{document.cookie='"
        + _cookie_pair(bid, COOKIE_MAX_AGE)
        + "';}catch(e){}})();</script>"
    )


def write_identity_cookie(bid: str) -> bool:
    """把浏览器持久化 ID 写入第一方 cookie。

    优先用 `st.html(..., unsafe_allow_javascript=True)`（Streamlit >= 1.5x，不入 iframe，
    脚本直接在主文档执行）；旧版本回退到 `components.html`（srcdoc iframe 带
    allow-same-origin + allow-scripts，同样可写父域 cookie）。

    失败不影响本次会话（本次仍沿用旧身份），只是下次访问无法切换到 v2。
    """
    if not is_valid_bid(bid):
        return False
    script = _cookie_script(bid)
    try:
        import streamlit as st
    except Exception:
        return False

    # 首选：原生 st.html + 允许 JS
    try:
        st.html(script, unsafe_allow_javascript=True)
        return True
    except TypeError:
        pass  # 老版本没有 unsafe_allow_javascript 参数
    except Exception:
        pass

    # 回退：components.html（高度 0，不可见）
    try:
        from streamlit.components.v1 import html as _components_html
        _components_html(script, height=0, width=0)
        return True
    except Exception:
        return False


# ==================== 滑动续期 ====================
def renew_identity_cookie(bid: str) -> bool:
    """把 cookie 的有效期重新计时（滑动窗口）。

    为什么必须做：浏览器对 cookie 有效期有 **400 天上限**（Chrome / Edge / Firefox
    均是如此，Safari 更严），而 max-age 只在**写入那一刻**开始计时，不会因为"用户
    又访问了一次"而自动延长。若不续期，天天使用的用户也会在第 400 天突然变成
    "新用户"——额度、转换历史、样式映射全部"凭空消失"。

    因此每次**新会话**（新开页面 / 刷新）都顺带重写一次 cookie，使它成为滑动窗口：
    只要用户在 400 天内访问过一次，身份就一直续下去。

    同一会话内只执行一次（session_state 标记），避免每次 rerun 都注入脚本。
    """
    if not is_valid_bid(bid):
        return False
    try:
        import streamlit as st
        if st.session_state.get("_identity_cookie_renewed"):
            return False
        st.session_state["_identity_cookie_renewed"] = True
    except Exception:
        pass
    return write_identity_cookie(bid)


def warn_if_embedded() -> None:
    """嵌入模式（?embed=true / iframe）下 cookie 会被当第三方 cookie 拦截，身份必然不稳定。

    这是"身份不稳定"最常见的外部原因之一，所以显式留一条日志，避免排查时抓瞎。
    """
    try:
        import streamlit as st
        if st.session_state.get("_identity_embedded_warned"):
            return
        st.session_state["_identity_embedded_warned"] = True
        if getattr(st.context, "is_embedded", False):
            logging.getLogger("WordStyle").warning(
                "[IDENTITY] 应用以 iframe 嵌入方式运行：浏览器会把 ws_bid 视为第三方 cookie 直接拦截，"
                "身份将退化为 UA 指纹（不稳定）。请让用户直接访问应用域名。"
            )
    except Exception:
        pass


# ==================== 主入口 ====================
def resolve_identity() -> Identity:
    """解析当前会话身份。任何异常都退化为"会话级临时身份"而不是抛错。"""
    warn_if_embedded()
    try:
        return _resolve_identity()
    except Exception:
        salt = _session_salt()
        return Identity(
            fingerprint=fingerprint_from_ua(f"fallback|{salt}"),
            source=SOURCE_FALLBACK,
            bid=None,
            legacy_fingerprint=None,
            user_agent="",
            should_write_cookie=False,
        )


def _resolve_identity() -> Identity:
    mode = _identity_mode()
    user_agent = collect_user_agent()
    ua_ok = is_trusted_legacy_input(user_agent)
    legacy_fp = fingerprint_from_ua(user_agent) if user_agent else None

    # 回滚档：完全回到 v1 行为
    if mode == _MODE_V1:
        if user_agent:
            return Identity(
                fingerprint=legacy_fp,
                source=SOURCE_LEGACY,
                bid=None,
                legacy_fingerprint=legacy_fp,
                user_agent=user_agent,
                should_write_cookie=False,
            )
        salt = _session_salt()
        return Identity(
            fingerprint=fingerprint_from_ua(f"fallback|{salt}"),
            source=SOURCE_FALLBACK,
            bid=None,
            legacy_fingerprint=None,
            user_agent="",
            should_write_cookie=False,
        )

    # 正常档：有 cookie → v2 身份
    bid = _read_cookie_bid()
    if bid:
        return Identity(
            fingerprint=fingerprint_from_bid(bid),
            source=SOURCE_COOKIE,
            bid=bid,
            # 同时带上 v1 指纹，供服务端"恰好一次"认领历史账号
            legacy_fingerprint=legacy_fp if ua_ok else None,
            user_agent=user_agent,
            should_write_cookie=False,
        )

    # 无 cookie（首次访问）：本次沿用 v1 身份（保证老用户本次不丢数据），
    # 同时准备写入 cookie —— 下次访问即切到 v2 并认领该历史账号。
    fresh_bid = new_bid()
    if user_agent:
        return Identity(
            fingerprint=legacy_fp,
            source=SOURCE_LEGACY,
            bid=fresh_bid,
            legacy_fingerprint=legacy_fp,
            user_agent=user_agent,
            should_write_cookie=True,
        )

    # UA 也拿不到 → 会话级临时身份（绝不与任何人共用）
    salt = _session_salt()
    return Identity(
        fingerprint=fingerprint_from_ua(f"fallback|{salt}"),
        source=SOURCE_FALLBACK,
        bid=fresh_bid,
        legacy_fingerprint=None,
        user_agent="",
        should_write_cookie=True,
    )


def clear_identity_cookie() -> None:
    """清除浏览器持久化 ID（仅供"重置设备身份"这类管理操作调用）。"""
    script = (
        "<script>(function(){try{document.cookie='"
        + _cookie_pair("", 0)
        + "';}catch(e){}})();</script>"
    )
    try:
        import streamlit as st
        st.html(script, unsafe_allow_javascript=True)
    except Exception:
        try:
            from streamlit.components.v1 import html as _components_html
            _components_html(script, height=0, width=0)
        except Exception:
            pass
