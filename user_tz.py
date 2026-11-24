# -*- coding: utf-8 -*-
"""用户所在时区 —— 让文件名、时间戳按用户手表上的时间走，而不是服务器时间。

为什么需要这个模块
------------------
Streamlit 的 Python 代码跑在服务器上，`datetime.now()` 取的是服务器时间。
本项目本地开发是 GMT+8、Streamlit Cloud 部署的是 UTC，两者差 8 小时：
云端生成的结果文件名 `result_xxx_20261029_035000.docx` 会比用户看到的时间
早 8 小时，看起来像"转换发生在半夜"。浏览器才知道用户真正在哪个时区，
所以必须由前端把时区送回后端。

为什么 2026-11-24 改成「URL 参数优先」
--------------------------------------
原设计只走 cookie（`ws_tz`），与 identity 的身份 cookie 同一套策略。但线上实测
（见 identity.py 顶部 2026-11-09 记录）：Streamlit Community Cloud 的代理会丢弃
WS 握手里的 Cookie 头，`st.context.cookies` 恒为空 —— 时区 cookie 同样读不到，
于是本模块一直退到「服务器本地时区」（云端 = UTC），「按用户本地时间显示」在线上
从未真正生效。本地开发是 GMT+8，看起来是对的，很容易误判。

现在的读取优先级：
  ① URL 参数 `ws_tz` —— 身份桥 `bridge_script()` 重载时顺带回传，零额外重载；
     管理后台等没有身份桥的独立入口，由 `ensure_timezone_bridge()` 自建一次桥。
  ② cookie `ws_tz` —— 自托管 / 本地开发路径，仍按原策略写，SameSite / 有效期
     与 identity 保持一致。
  ③ 服务器本地时区 —— 仅作回退，且**不缓存**，下一次 rerun 还会再试 ①②。
     老实现连回退值一起缓存，首帧没拿到 cookie 就把 UTC 钉死一整场会话。

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
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger('WordStyle')

TZ_COOKIE_NAME = "ws_tz"
TZ_COOKIE_MAX_AGE = 2 * 365 * 24 * 3600  # 2 年（秒），与身份 cookie 一致

# 复用身份模块的常量与 SameSite 策略：参数名必须一致，嵌入场景（iframe）下
# 两边行为也必须一致，否则会出现"身份写得上、时区写不上"这种半通不通的状态。
# identity 不能反过来 import user_tz（会成环），所以常量定义在 identity 侧。
try:
    from identity import _COOKIE_SAMESITE as _SAMESITE
    from identity import TIMEZONE_QUERY_PARAM as TZ_QUERY_PARAM
except Exception:  # pragma: no cover - identity 缺失时退化为同名常规值
    _SAMESITE = "Lax"
    TZ_QUERY_PARAM = "ws_tz"

# [2026-11-24] 独立时区桥（管理后台等没有身份桥的入口用）
TZ_BRIDGE_FLAG = "_ws_tz_bridge"
_TZ_BRIDGE_INJECTED_KEY = "_user_tz_bridge_injected"

# 会话级缓存键：只有「真实解析出浏览器时区」才写缓存；回退值绝不缓存，
# 否则首帧拿不到 URL/cookie 就会把服务器时区钉死一整场会话。
_TZ_CACHE_KEY = "_user_tzinfo"
_TZ_SOURCE_KEY = "_user_tz_source"
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


def _tz_bridge_script() -> str:
    """独立时区桥脚本：写 cookie + 把时区放进 URL 参数并重载一次。

    给「没有身份桥」的入口用（管理后台 admin_web.py 是独立 Streamlit 应用）。
    Cloud 上 cookie 读不到，只有 URL 参数能在握手时被 Python 读到，所以这里
    与 identity.bridge_script() 用同一思路，但只带时区、不带 bid。
    """
    body = (
        "<script>(function(){try{"
        "var off=-new Date().getTimezoneOffset();"
        "var iana='';"
        "try{iana=Intl.DateTimeFormat().resolvedOptions().timeZone||'';}catch(e){}"
        # cookie 值格式必须与 _tz_script() 完全一致：IANA 名单独编码，'|' 不编码，
        # 否则 _parse_tz_raw() 的 partition('|') 会找不到分隔符。
        "document.cookie='" + TZ_COOKIE_NAME + "='+encodeURIComponent(iana)+'|'+off"
        + "; max-age=" + str(TZ_COOKIE_MAX_AGE) + "; path=/; SameSite=" + _SAMESITE + "';"
        # URL 参数值用原始 IANA 名，URLSearchParams 会自动编码 '/' 等字符，
        # Python 侧 st.query_params 再自动解码回来；手动 encodeURIComponent 会被
        # 二次编码成 %25，反而解析不出 IANA 名。
        "var u=new URL(location.href);"
        "u.searchParams.set('" + TZ_QUERY_PARAM + "',iana+'|'+off);"
        "u.searchParams.set('" + TZ_BRIDGE_FLAG + "','1');"
        "location.replace(u.toString());"
        "}catch(e){}})();</script>"
    )
    # 与 identity.bridge_script 同一条硬约束：正文出现「< + 字母/数字」会被
    # DOMPurify 整段吞掉（不报错不告警），留一道自检防止后人改坏。
    if re.search(r"<[A-Za-z0-9_!/]", body.replace("<script", "").replace("</script", "")):
        raise ValueError("时区桥脚本中含 DOMPurify 会吞掉的内容")
    return body


def ensure_timezone_bridge() -> bool:
    """没有身份桥的入口用：确保本次会话能拿到浏览器时区。

    只在「会话里还没有时区、URL 里也没有、cookie 里也没有、且桥没尝试过」时
    注入一次脚本；脚本写 cookie 并把时区放进 URL 参数后重载一次。
    `_ws_tz_bridge=1` 是防循环标记：若重载后仍拿不到（JS 被禁用等），不再重试。

    ⚠️ 不调用 st.stop()：本帧照常渲染，JS 重载后下一帧 Python 就能读到参数。
    主应用走 identity 的身份桥（已顺带时区），不会调用本函数，两者不会同时
    注入两个 `location.replace` 抢导航。
    """
    try:
        import streamlit as st
        if st.session_state.get(_TZ_CACHE_KEY) is not None:
            return False
        if _read_query_tz() or _parse_tz_raw(_read_cookie_tz()) is not None:
            return False
        params = getattr(st, "query_params", None)
        already = bool(params.get(TZ_BRIDGE_FLAG)) if params is not None else False
        if already or st.session_state.get(_TZ_BRIDGE_INJECTED_KEY):
            return False
        st.session_state[_TZ_BRIDGE_INJECTED_KEY] = True
        st.html(_tz_bridge_script(), unsafe_allow_javascript=True)
        return True
    except TypeError:
        pass  # 老版本没有 unsafe_allow_javascript 参数，走下面 components.html 回退
    except Exception as e:
        logger.debug(f"[TZ] 时区桥注入失败: {e}")

    try:
        from streamlit.components.v1 import html as _components_html
        _components_html(_tz_bridge_script(), height=0, width=0)
        return True
    except Exception as e:
        logger.debug(f"[TZ] 时区桥回退方案也失败: {e}")
        return False


def clean_timezone_url() -> bool:
    """把时区桥留在地址栏的参数删掉（管理后台用）。

    ⚠️ 只在 capture_timezone_from_url() **成功**之后调用：那时 session_state 已有
    缓存，ensure_timezone_bridge() 不会再注入，删光参数也不会造成重载循环。
    主应用由 identity.clean_identity_url() 统一清理，不需要调用本函数。
    """
    try:
        import streamlit as st
        removed = False
        if TZ_QUERY_PARAM in st.query_params:
            del st.query_params[TZ_QUERY_PARAM]
            removed = True
        if TZ_BRIDGE_FLAG in st.query_params:
            del st.query_params[TZ_BRIDGE_FLAG]
            removed = True
        return removed
    except Exception:
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
        # 与 _read_query_tz 同一条防线：占位对象不是合法时区值，直接当作没取到。
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None
    except Exception:
        return None


def _read_query_tz() -> Optional[str]:
    """读 URL 参数里的时区原始值（形如 `Asia/Shanghai|480`）。

    Cloud 上身份桥 / 独立时区桥把浏览器时区写进地址栏，Python 在 WS 握手时
    就能从 `st.query_params` 读到 —— 这是绕开 Cookie 头被丢弃的唯一可靠通道。
    """
    try:
        import streamlit as st
        params = getattr(st, "query_params", None)
        if params is None:
            return None
        value = params.get(TZ_QUERY_PARAM) if hasattr(params, "get") else None
        if isinstance(value, (list, tuple)):  # 同名参数重复时 Streamlit 返回列表
            value = value[0] if value else None
        # 假 Streamlit / 精简上下文会返回占位对象，只接受字符串；否则下游
        # partition('|') 会抛 TypeError（管理后台首帧 import 时实测踩过）。
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None
    except Exception:
        return None


def _parse_tz_raw(raw) -> Optional[timezone or object]:
    """把 `IANA名|UTC偏移分钟` 解析成 tzinfo；解析不了返回 None。

    URL 参数与 cookie 共用这一份解析：URL 参数由 URLSearchParams 自动编解码，
    cookie 值里的 IANA 名是 encodeURIComponent 过的；`unquote` 对两者都幂等，
    所以不需要为两条通道各写一份解析逻辑。
    """
    if not raw:
        return None
    raw = str(raw).strip()
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


def _resolve_tzinfo() -> Optional[timezone or object]:
    """按 cookie 解析出 tzinfo（保留给老调用方）；拿不到返回 None。"""
    return _parse_tz_raw(_read_cookie_tz())


def capture_timezone_from_url() -> bool:
    """在地址栏参数被清理之前，把 URL 里的时区读进会话缓存。

    ⚠️ 调用顺序：必须在 identity.clean_identity_url() / clean_timezone_url()
    删参数**之前**执行。清理会触发 rerun，rerun 后 URL 已空，只能靠 session_state
    里的缓存记住浏览器时区 —— 这正是 Cloud 上修复「时区恒为 UTC」的关键一步。

    解析成功才写缓存；返回是否成功。任何异常都吞掉（时区只是显示优化）。
    """
    try:
        raw = _read_query_tz()
        if not raw:
            return False
        tz = _parse_tz_raw(raw)
        if tz is None:
            return False
        import streamlit as st
        st.session_state[_TZ_CACHE_KEY] = tz
        st.session_state[_TZ_SOURCE_KEY] = "url_param"
        return True
    except Exception:
        return False


def get_user_tzinfo():
    """取用户所在时区的 tzinfo。

    回退链（2026-11-24）：
      ① session_state 缓存（URL 参数或 cookie 解析成功的真实浏览器时区）
      ② URL 参数 `ws_tz`（Cloud 上由身份桥 / 独立时区桥回传）
      ③ cookie `ws_tz`（自托管 / 本地开发）
      ④ 服务器本地时区 —— **不缓存**，下一次 rerun 再试 ②③，避免首帧把
         「没有时区」钉死一整场会话（老实现连回退值也缓存，是线上退化成 UTC
         的原因之一）。
    最后一级保证任何环境下都能返回一个可用的 tzinfo，绝不抛异常。
    """
    try:
        import streamlit as st
        cached = st.session_state.get(_TZ_CACHE_KEY)
        if cached is not None:
            return cached
    except Exception:
        pass

    for source, raw in (("url_param", _read_query_tz()), ("cookie", _read_cookie_tz())):
        tz = _parse_tz_raw(raw)
        if tz is not None:
            try:
                import streamlit as st
                st.session_state[_TZ_CACHE_KEY] = tz
                st.session_state[_TZ_SOURCE_KEY] = source
            except Exception:
                pass
            return tz

    # 拿不到浏览器时区：退回服务器本地（与改动前的行为一致），
    # 至少保证文件名还能生成，不会因为时区问题让转换失败。
    return datetime.now().astimezone().tzinfo


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
    """调试用：说明当前用的是哪个时区、从哪来的。

    ⚠️ 管理后台在模块首帧就会调用它，任何异常都不能冒出去把整个后台打挂
    （2026-11-24 假 Streamlit 返回占位对象时踩过 TypeError）。
    """
    try:
        try:
            import streamlit as st
            source = st.session_state.get(_TZ_SOURCE_KEY) or ""
        except Exception:
            source = ""
        if not isinstance(source, str):
            source = ""
        raw_query = _read_query_tz()
        raw_cookie = _read_cookie_tz()
        raw = raw_query or raw_cookie or ""
        if not raw and not source:
            return "未取到浏览器时区（首帧或脚本被拦截），回退服务器本地时间（不缓存，下次 rerun 再试）"
        iana, _, off = raw.partition('|')
        via = source or ("url_param" if raw_query else "cookie")
        return f"来源={via}；值={raw or '已缓存'}（IANA={iana or '无'}，UTC偏移={off or '无'}分钟）"
    except Exception:
        return "时区来源未知（诊断信息获取失败，已降级）"
