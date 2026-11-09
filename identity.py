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

==================== 2026-11-09：Streamlit Community Cloud 读不到 cookie ====================
线上实测（bid-buddy.streamlit.app）：
  * 浏览器发出的 WebSocket 握手**带着** `Cookie: ws_bid=…`（CDP 抓包确认）；
  * 但应用侧 `st.context.cookies` **恒为空** —— Cloud 的代理在转发 WS 升级请求时
    丢弃了 Cookie 头（Streamlit 社区已知限制；`st.context.cookies` 正是从
    WS 握手取值的，见 `StarletteClientContext`）；
  * 铁证：库里线上用户的 `device_fingerprint` 与 `md5(真实 User-Agent)` 逐位相同。

后果：v2 在 Cloud 上从未生效，一直走 v1 `md5(UA)`。UA 里带浏览器版本号，
**浏览器自动更新（通常在重启后应用）→ 指纹变 → 新建账号 → 用户ID 变化**，
即用户反馈的"开关机一次就不一样"。同一原因也让 `ws_tz` 时区 cookie 在云端读不到。

修复：**URL 参数桥**。Cloud 上唯一能被 Python 在握手时读到的客户端状态是 URL
（`st.query_params`）。因此当既没有 URL 参数、又读不到 cookie 时：
    1) 本次渲染不创建用户（避免产生垃圾行），先写一个 `<script>`；
    2) 脚本读 `document.cookie`（读不到就新建一个），把 bid 写进**地址栏参数**
       `?ws_bid=…`（同源时替换顶层地址，Cloud 的外壳会把参数转发进 iframe）；
    3) 浏览器自动重载一次，这次 `st.query_params['ws_bid']` 就能被 Python 读到，
       身份进入 v2 并认领该浏览器的历史 UA 账号。
代价：每次**新进入**页面多一次约 1 秒的自动重载（地址栏带上参数后，刷新不再重载）。
防循环：脚本同时写入 `_ws_bid_bridge=1`，若重载后仍拿不到 bid（JS 被禁用等），
则不再重试、退回 UA 身份保证应用可用。
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
# [2026-11-09] URL 参数桥（Community Cloud 读不到 cookie 时的唯一可行通道）
# 参数名与 cookie 同名，便于对照；桥脚本会把它写进地址栏。
IDENTITY_QUERY_PARAM = "ws_bid"
BRIDGE_FLAG_PARAM = "_ws_bid_bridge"   # 防循环：脚本写入，服务端见到就说明已尝试过
COOKIE_MAX_AGE = 2 * 365 * 24 * 3600  # 2 年（秒）
_COOKIE_SAMESITE = "Lax"

_BID_RE = re.compile(r"^[0-9a-f]{32}$")
_V2_PREFIX = "ws2|"

# 身份来源（用于日志与界面提示）
SOURCE_COOKIE = "cookie"        # 命中了浏览器持久化 ID（正常态）
SOURCE_COOKIE_NEW = "cookie_new"  # 首次写入 cookie（本次仍用旧身份）
SOURCE_URL = "url_param"        # 从 URL 参数拿到 bid（Community Cloud 上的正常态）
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
    # [2026-11-09] URL 参数桥：本次渲染先不建用户，把 bid 带进地址栏后重载一次
    should_bridge: bool = False
    bridge_bid: Optional[str] = None

    @property
    def is_legacy(self) -> bool:
        return self.source in (SOURCE_LEGACY, SOURCE_FALLBACK)

    @property
    def is_trusted(self) -> bool:
        """身份是否可信到"可以认领一个历史账号"。"""
        return self.source in (SOURCE_COOKIE, SOURCE_URL, SOURCE_LEGACY) and bool(self.legacy_fingerprint)

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


# [2026-11-09] URL 参数桥 —— Community Cloud 上唯一能被服务端在握手时读到的通道。
# 为什么不是 localStorage / 组件 iframe：Cloud 把应用放在 sandboxed iframe 里，
# 组件 iframe 与原文档不同源，读不到主文档 cookie；而 URL 是 Streamlit 侧
# `st.query_params` 的原生能力，且 Cloud 的外壳会把顶层查询参数转发进 iframe。
def _read_query_bid() -> Optional[str]:
    """从 URL 查询参数读出浏览器持久化 ID（URL 参数桥的落点）。"""
    try:
        import streamlit as st
        params = getattr(st, "query_params", None)
        if params is None:
            return None
        value = params.get(IDENTITY_QUERY_PARAM) if hasattr(params, "get") else None
        if isinstance(value, (list, tuple)):      # 少数实现返回列表
            value = value[0] if value else None
        value = (value or "").strip().lower()
        return value if _BID_RE.match(value) else None
    except Exception:
        return None


def _bridge_already_tried() -> bool:
    """本次请求是否已经走过一次 URL 参数桥（防死循环）。"""
    try:
        import streamlit as st
        params = getattr(st, "query_params", None)
        if params is None:
            return False
        return bool(params.get(BRIDGE_FLAG_PARAM))
    except Exception:
        return False


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


# ==================== URL 参数桥（2026-11-09）====================
def bridge_script(bid: str) -> str:
    """生成 URL 参数桥脚本：把 bid 写进地址栏并重载一次。

    设计要点（每一条都对应一个踩过的坑）：
    1. **读 cookie 优先**：服务器读不到不代表浏览器里没有。若浏览器已有 bid，
       必须沿用它，否则等于把用户又换了一个身份（不能拿服务端新生成的覆盖）。
    2. **重载 iframe 自己的 URL（不是顶层）**：参数必须落在应用自身地址上，
       `st.query_params` 才 100% 能读到；改顶层地址要依赖 Cloud 外壳转发参数，
       万一不转发就会来回重载。顶层只做 `history.replaceState`（不导航），
       让地址栏也带上参数 —— 这样手动刷新时外壳若转发就免重载，不转发也最多再重载一次。
    3. **保留其它查询参数**：用 URL API 逐个 set，不会把 embed 等参数冲掉。
    4. **写入 `_ws_bid_bridge=1`**：服务端见到它就说明桥已尝试过，拿不到 bid 时
       不再重试（否则 JS 被禁用会无限重载）。
    5. 顺带重写一次 cookie（滑动续期），并用 try/catch 包住全部逻辑。
    """
    body = (
        "<script>(function(){try{"
        # 0) 客户端级防循环：sessionStorage 记上次尝试时间，5 秒内不重复重载。
        #    服务端的 `_ws_bid_bridge=1` 依赖"参数能被读到"，万一读不到就会来回刷，
        #    这一层与平台无关，是最后的保险。
        #    ⚠️ 比较必须写成 `last+5000>now`（不能用 `<`）：DOMPurify 见到「< 紧跟数字」
        #    会把整条 script 丢掉（不报错不告警），这是本模块最容易踩的坑。
        "var k='_ws_bid_bridge_ts',last=0;"
        "try{last=parseInt(sessionStorage.getItem(k)||'0',10)||0;}catch(e){}"
        "if(last+5000>Date.now()){return;}"
        "try{sessionStorage.setItem(k,String(Date.now()));}catch(e){}"
        "var re=/(?:^|;\\s*)" + IDENTITY_COOKIE_NAME + "=([0-9a-fA-F]{32})/;"
        "var m=document.cookie.match(re);"
        "var bid=m?m[1].toLowerCase():'" + bid + "';"
        "document.cookie='" + IDENTITY_COOKIE_NAME + "='+bid+"
        "'; max-age=" + str(COOKIE_MAX_AGE) + "; path=/; SameSite=" + _COOKIE_SAMESITE + "';"
        # ① 顶层地址栏同步（不导航，仅 replaceState）
        "try{if(window.top&&window.top!==window&&window.top.location.origin===location.origin){"
        "var t=new URL(window.top.location.href);"
        "t.searchParams.set('" + IDENTITY_QUERY_PARAM + "',bid);"
        "t.searchParams.set('" + BRIDGE_FLAG_PARAM + "','1');"
        "window.top.history.replaceState(null,'',t.toString());}}catch(e){}"
        # ② 应用自身地址：带参数后重载（st.query_params 必定能读到）
        "var u=new URL(location.href);"
        "u.searchParams.set('" + IDENTITY_QUERY_PARAM + "',bid);"
        "u.searchParams.set('" + BRIDGE_FLAG_PARAM + "','1');"
        "location.replace(u.toString());"
        "}catch(e){}})();</script>"
    )
    # DOMPurify 的硬约束：正文里出现「< 紧跟字母/数字」会把整条 script 丢掉（不报错）。
    # 这里的 JS 里不应出现任何比较运算，留一道自检防止后人改坏。
    if re.search(r"<[A-Za-z0-9_!/]", body.replace("<script", "").replace("</script", "")):
        raise ValueError("bridge_script 中含 DOMPurify 会吞掉的内容")
    return body


def render_bridge_and_stop(bid: str) -> None:
    """渲染"正在识别设备"占位页 + 桥脚本，然后终止本次脚本执行。

    为什么必须 stop：桥生效前不能创建用户。否则每进入一次就按 UA 建一行垃圾用户
    （云端读不到 cookie 时正是这样），且这些行还会被"历史账号认领"逻辑反复搬来搬去。
    """
    try:
        import streamlit as st
    except Exception:
        return
    try:
        st.markdown(
            "<div style='padding:1.2rem 0;color:#64748b;font-size:0.95rem;'>"
            "正在识别本机身份…</div>",
            unsafe_allow_html=True,
        )
        # 极端兜底：浏览器禁用 JS 时脚本不会执行，给一个可点击的链接（平时瞬间跳走，看不见）
        st.markdown(
            "<div style='font-size:0.8rem;color:#94a3b8;'>如果 3 秒内没有自动继续，"
            "<a href='?" + IDENTITY_QUERY_PARAM + "=" + bid
            + "&" + BRIDGE_FLAG_PARAM + "=1'>点此继续</a>（不记忆设备）</div>",
            unsafe_allow_html=True,
        )
        st.html(bridge_script(bid), unsafe_allow_javascript=True)
    except Exception as e:      # 占位页绝不能因为渲染失败把应用卡死
        logging.getLogger(__name__).warning(f"[IDENTITY] 桥接占位页渲染失败: {e}")
        return
    st.stop()


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

    # 正常档 1：URL 参数（[2026-11-09] Community Cloud 上的正常态）
    # 为什么 URL 排在 cookie 前面：Cloud 的 WS 握手拿不到 cookie，只有 URL 参数
    # 能进 `st.query_params`；自托管两种都有，取哪个结果都一样，所以统一先看 URL。
    bid = _read_query_bid()
    if bid:
        return Identity(
            fingerprint=fingerprint_from_bid(bid),
            source=SOURCE_URL,
            bid=bid,
            legacy_fingerprint=legacy_fp if ua_ok else None,
            user_agent=user_agent,
            should_write_cookie=False,
        )

    # 正常档 2：cookie（自托管 / 本地开发）
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

    # 两者都没有（首次访问，或 Cloud 读不到 cookie）：
    # 先走 URL 参数桥把 bid 带进地址栏，重载后再按 v2 建号；
    # 已尝试过桥仍拿不到（JS 被禁用等）才退回 v1，保证应用可用。
    fresh_bid = new_bid()
    if user_agent:
        if not _bridge_already_tried():
            return Identity(
                fingerprint=legacy_fp,
                source=SOURCE_LEGACY,
                bid=fresh_bid,
                legacy_fingerprint=legacy_fp,
                user_agent=user_agent,
                # 关键：不能在这里写 cookie —— 浏览器里可能已经有旧 bid，
                # 服务端读不到它，写新值等于把用户又换一个人。
                should_write_cookie=False,
                should_bridge=True,
                bridge_bid=fresh_bid,
            )
        return Identity(
            fingerprint=legacy_fp,
            source=SOURCE_LEGACY,
            bid=fresh_bid,
            legacy_fingerprint=legacy_fp,
            user_agent=user_agent,
            should_write_cookie=True,
        )

    # UA 也拿不到 → 会话级临时身份（绝不与任何人共用）
    # [2026-11-09] 先试一次 URL 桥：能拿到 bid 就能摆脱"每次都是新身份"。
    salt = _session_salt()
    if not _bridge_already_tried():
        return Identity(
            fingerprint=fingerprint_from_ua(f"fallback|{salt}"),
            source=SOURCE_FALLBACK,
            bid=fresh_bid,
            legacy_fingerprint=None,
            user_agent="",
            should_write_cookie=False,
            should_bridge=True,
            bridge_bid=fresh_bid,
        )
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
