# -*- coding: utf-8 -*-
"""用户所在时区 —— 让文件名、时间戳按用户手表上的时间走，而不是服务器时间。

为什么需要这个模块
------------------
Streamlit 的 Python 代码跑在服务器上，`datetime.now()` 取的是服务器时间。
本项目本地开发是 GMT+8、Streamlit Cloud 部署的是 UTC，两者差 8 小时：
云端生成的结果文件名 `result_xxx_20261029_035000.docx` 会比用户看到的时间
早 8 小时，看起来像"转换发生在半夜"。浏览器才知道用户真正在哪个时区，
所以必须由前端把时区送回后端。

为什么用 cookie 而不是别的通道
------------------------------
- `st.query_params`：会污染地址栏，且每次改动都触发 rerun；
- `components.html`：多一层 iframe，写父域 cookie 更绕；
- cookie：本项目既有机制（identity.py 的身份 cookie 就走这条路），
  第一方、同源、不占地址栏、无需额外依赖。
因此这里完全复用 identity 的 cookie 策略（SameSite / 有效期一致），
保证两者在"iframe 嵌入"等场景下的行为相同。

存两份值：IANA 名（如 `Asia/Shanghai`）+ 当前 UTC 偏移分钟（东八区 = 480）。
- IANA 名能吃掉夏令时（交给 `zoneinfo.ZoneInfo`），
  但 Windows 上需要 pip 的 `tzdata` 包，不一定装了；
- 拿不到 tzdata 时退化为固定偏移 —— 对"此刻"的时间戳一样准确，
  只是不能还原历史日期的夏令时。文件名只用"此刻"，所以够用。

【st.html 的两条硬约束】（踩过的事故，改这个文件时务必遵守）
1. 脚本必须包在 `<script>...</script>` 里，否则不执行，
   而且整段源码会变成页面上可见的纯文本；
2. 正文里不能出现「`<` 紧跟字母/数字/!/」，否则 DOMPurify 会静默
   剥掉整条 script（不报错、不告警）。所以脚本里不要写紧凑的比较运算符。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger('WordStyle')

TZ_COOKIE_NAME = "ws_tz"
TZ_COOKIE_MAX_AGE = 2 * 365 * 24 * 3600  # 2 年（秒），与身份 cookie 一致

# 复用身份 cookie 的 SameSite 策略：嵌入场景（iframe）下两边行为必须一致，
# 否则会出现"身份写得上、时区写不上"这种半通不通的状态。
try:
    from identity import _COOKIE_SAMESITE as _SAMESITE
except Exception:  # pragma: no cover - identity 缺失时退化为常规值
    _SAMESITE = "Lax"

# 会话级缓存键：解析成功才缓存，失败不缓存（下一次 rerun 再试），
# 否则首帧拿不到 cookie 就会把"没有时区"这个状态钉死一整场会话。
_TZ_CACHE_KEY = "_user_tzinfo"
_PROBE_KEY = "_user_tz_probe_injected"


def _tz_script() -> str:
    """拼出写时区 cookie 的脚本。

    刻意用 `+` 字符串拼接，不用 f-string / format：JS 函数体里全是花括号，
    format 会把它们当占位符解析（identity.py 里已经踩过一次）。
    """
    return (
        "<script>(function(){try{"
        "var off=-new Date().getTimezoneOffset();"
        "var iana='';"
        "try{iana=Intl.DateTimeFormat().resolvedOptions().timeZone||'';}catch(e){}"
        "var v=encodeURIComponent(iana)+'|'+off;"
        "document.cookie='"
        + TZ_COOKIE_NAME + "='+v+'; max-age=" + str(TZ_COOKIE_MAX_AGE)
        + "; path=/; SameSite=" + _SAMESITE + "';"
        "}catch(e){}})();</script>"
    )


def ensure_timezone_cookie() -> bool:
    """把浏览器时区写进第一方 cookie。同一会话内只注入一次。

    注意：cookie 写下去之后，要等**下一次请求** Python 侧才能从
    `st.context.cookies` 读到；首帧仍需走回退逻辑。转换流程天然有
    多次 rerun（上传 → 配置 → 点转换），所以真正生成文件名时已经拿到了。
    """
    try:
        import streamlit as st
        if st.session_state.get(_PROBE_KEY):
            return False
        st.session_state[_PROBE_KEY] = True
        st.html(_tz_script(), unsafe_allow_javascript=True)
        return True
    except TypeError:
        pass  # 老版本没有 unsafe_allow_javascript 参数
    except Exception as e:
        logger.debug(f"[TZ] 时区探测脚本注入失败: {e}")

    try:
        from streamlit.components.v1 import html as _components_html
        _components_html(_tz_script(), height=0, width=0)
        return True
    except Exception as e:
        logger.debug(f"[TZ] 时区探测回退方案也失败: {e}")
        return False


def _read_cookie_tz() -> Optional[str]:
    """读时区 cookie 原始值（形如 `Asia%2FShanghai|480`）。"""
    try:
        import streamlit as st
        cookies = getattr(st.context, "cookies", None)
        if cookies is None:
            return None
        value = cookies.get(TZ_COOKIE_NAME) if hasattr(cookies, "get") else None
        if value is None:
            try:
                value = cookies[TZ_COOKIE_NAME]
            except Exception:
                value = None
        value = (value or "").strip()
        return value or None
    except Exception:
        return None


def _resolve_tzinfo() -> Optional[timezone or object]:
    """按 cookie 解析出 tzinfo；拿不到返回 None（调用方会回退）。"""
    raw = _read_cookie_tz()
    if not raw:
        return None

    iana, _, offset_part = raw.partition('|')

    # 首选 IANA：能正确处理夏令时
    if iana:
        try:
            from urllib.parse import unquote
            from zoneinfo import ZoneInfo
            return ZoneInfo(unquote(iana))
        except Exception:
            pass  # 没装 tzdata 或名字不认识 -> 退到偏移

    # 次选固定偏移：对"此刻"的时间戳同样准确
    try:
        minutes = int(offset_part)
        if -1440 < minutes < 1440:
            return timezone(timedelta(minutes=minutes))
    except (TypeError, ValueError):
        pass
    return None


def get_user_tzinfo():
    """取用户所在时区的 tzinfo。

    回退链：cookie 的 IANA 名 -> cookie 的 UTC 偏移 -> 服务器本地时区。
    最后一级保证任何环境下都能返回一个可用的 tzinfo，绝不抛异常。
    """
    try:
        import streamlit as st
        cached = st.session_state.get(_TZ_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:
        pass

    tz = _resolve_tzinfo()
    if tz is None:
        # 拿不到浏览器时区：退回服务器本地（与改动前的行为一致），
        # 至少保证文件名还能生成，不会因为时区问题让转换失败。
        tz = datetime.now().astimezone().tzinfo

    try:
        import streamlit as st
        st.session_state[_TZ_CACHE_KEY] = tz
    except Exception:
        pass
    return tz


def now_local():
    """用户所在时区下的当前时间（aware datetime）。"""
    return datetime.now(get_user_tzinfo())


def local_stamp(fmt: str = '%Y%m%d_%H%M%S') -> str:
    """用户所在时区下的时间字符串，默认给文件名用（如 20261029_115800）。"""
    return now_local().strftime(fmt)


def now_utc_iso() -> str:
    """当前时刻的 UTC 时间，ISO 格式且带偏移（如 2026-10-29T05:08:30+00:00）。

    用于要落库/落盘的时间戳（评论、反馈）。设计口径（用户 2026-10-29 拍板）：
    **存储统一记原始的服务器/UTC 时间，展示时再按用户本地时间渲染**。
    好处：
    1. 全系统口径统一 —— 后端 API 路径的 DB `created_at` 本来就是 UTC，
       本地 JSON 路径也存 UTC 后，两条路径的字面值完全一致，便于核对；
    2. 记录值不因提交者所在时区而异（纽约用户和东京用户同刻提交，存下的是
       同一个串），排序/对账只看一个口径；
    3. 用户看到的时间由展示侧 `format_local()` 按**查看者**时区渲染得到。
    为什么不存裸的 `2026-10-29 13:08:30`：裸串没有时区信息，`format_local()`
    无从换算，还会让跨时区的字符串排序排反。带上偏移锚定的是绝对时刻。
    """
    return datetime.now(timezone.utc).isoformat()


def _parse_any(value) -> Optional[datetime]:
    """尽力把各种时间戳字符串解析成 datetime；解析不了返回 None（调用方原样保留）。

    兼容三类历史/异构数据：
    - 带偏移的 ISO（本次改动后的新格式，含 `+00:00` / `Z`）；
    - 裸字符串 `2026-10-29 13:08:30`（改动前的老数据，无时区）；
    - 数据库直读的 datetime 对象。
    """
    if isinstance(value, datetime):
        return value
    s = (str(value) if value is not None else '').strip()
    if not s:
        return None
    # Python 3.10 及以下的 fromisoformat 不认 'Z'，统一换掉
    candidate = s[:-1] + '+00:00' if s.endswith(('Z', 'z')) else s
    try:
        return datetime.fromisoformat(candidate)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def format_local(value, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """把库里的时间戳按**查看者**所在时区显示（评论/反馈列表用）。

    - 带时区的值（新数据、数据库 timestamptz）→ 换算到查看者时区后格式化。
      这与微信/邮件的惯例一致：同一条评论，不同时区的人看到各自的本地时间。
    - 不带时区的裸串（改动前的历史数据）→ **原样返回，绝不平移**。
      老数据是按服务器本地时间写的，硬加/减 8 小时只会把已经对的时间改错，
      所以宁可保持原样。与 admin_web 的 `to_beijing()` 是同一套取舍。
    - 空值/垃圾值 → 原样返回，不吞掉内容。
    """
    dt = _parse_any(value)
    if dt is None:
        return '' if value is None else str(value)
    if dt.tzinfo is None:
        return dt.strftime(fmt)
    try:
        return dt.astimezone(get_user_tzinfo()).strftime(fmt)
    except Exception:
        return dt.strftime(fmt)


def sort_key_ts(value) -> float:
    """按时间戳做安全排序的键（配合 `sorted(..., key=sort_key_ts)`）。

    直接对字符串排序在带偏移的 ISO 混排时会出错，这里统一折算成 UTC epoch 秒。
    裸串按服务器本地时区解释（与写入时的口径一致）；完全解析不了返回 -inf，
    排在最末尾而不是抛异常。
    """
    dt = _parse_any(value)
    if dt is None:
        return float('-inf')
    if dt.tzinfo is None:
        try:
            dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        except Exception:
            return float('-inf')
    try:
        return dt.timestamp()
    except Exception:
        return float('-inf')


def describe_user_tz() -> str:
    """调试用：说明当前用的是哪个时区、从哪来的。"""
    raw = _read_cookie_tz()
    if not raw:
        return "未取到浏览器时区（首帧或脚本被拦截），回退服务器本地时间"
    iana, _, off = raw.partition('|')
    return f"cookie={raw}（IANA={iana or '无'}，UTC偏移={off or '无'}分钟）"
