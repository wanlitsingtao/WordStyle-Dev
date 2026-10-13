"""社区云署名徽章隐藏（实验性，可一键关闭）。

背景
----
访问 `xxx.streamlit.app` 时，Streamlit Community Cloud 返回的**不是** OSS 版
Streamlit 前端，而是**社区云自己的外壳页面**（`/-/build/assets/index-*.js`）。
外壳用一个**同源 iframe** 装载我们的应用：

    <iframe title="streamlitApp"
            sandbox="allow-forms allow-modals allow-popups
                     allow-popups-to-escape-sandbox allow-same-origin
                     allow-scripts allow-downloads"
            src="/~//+/..."></iframe>

并在 iframe **外面**（即外壳文档里）渲染右下角徽章：它由两部分组成，都是
那个 iframe 的**兄弟节点**——

    <a href="https://streamlit.io/cloud">  👑  Hosted with Streamlit  </a>
    <div> <img data-testid="appCreatorAvatar">  … Created by <用户名> </div>

因为徽章在**另一个文档**里，应用内 `st.markdown` / `st.html` 写的 CSS
**永远碰不到它**（CSS 不跨文档）。可行的办法只有一个：从应用内部注入脚本，
跨到**父文档**把它隐藏。由于 iframe 与外壳同源、且 sandbox 含 `allow-same-origin`，
`window.parent.document` 是可访问的（已实测）。

⚠️ 注入方式的硬约束（线上踩坑记录，2026-10-13）
----------------------------------------------
`st.html(..., unsafe_allow_javascript=True)` 的执行链有两个**反直觉**的硬约束，
少一个就会「不报错、但整段源码变成页面上的可见文字」。两条都已在线上实测复现。

【约束 1】必须用 <script> 标签包裹，否则**不执行**
    前端实现（`streamlit/static/static/js/Html.*.js`，已逐字核对）：

        DOMPurify(ADD_TAGS:['script','style'], FORCE_BODY:true) 净化
          → container.innerHTML = 净化结果
          → container.querySelectorAll('script').forEach(重建 script 元素并替换)  ← 此时才执行

    传**裸 JS 文本**（外面没有 script 标签）时：既没有 script 元素可供重建
    （innerHTML 插入的 script 本来就不执行），又会被当作 HTML 内容渲染出来
    （`FORCE_BODY:true` 还会把注释里的标签字面量解析成真实元素）→ **整段源码可见**。

【约束 2】脚本正文里不能出现「`<` + `[A-Za-z0-9_!/]`」，否则**整条被丢光**
    这是 DOMPurify（实测 3.4.14）的行为：命中时它把整个 script 元素连内容一起删掉，
    输出长度直接变成 0——**不报错、不告警、页面上什么都没有**，最难排查。
    逐字符实测的边界（`<` 后面跟什么）：

        a  Z  0  9  _  !  /          →  ❌ 整条丢光
        空格  =  \\  "  '  ?  +  -  *  <  >  中 …  →  ✅ 保留

    也就是说：**比较运算符请写成 `a < b`（`<` 后留空格）或 `a <= b`，注释里不要写
    标签字面量（写成「a 标签」即可）。** 由 `_PURIFY_KILLER` 在注入前硬校验
    ——宁可记警告不注入，也不要往页面上吐源码。

【已复现的事故】
    线上 `https://bid-buddy-dev.streamlit.app` 的应用文档里，
    `data-testid="stHtml"` 的容器下直接渲染出了一整段 JS 源码
    （含被解析成真实 `<a>` 元素的节点）。根因＝当时既没包 script 标签，
    注释里又写了标签字面量，两条约束同时踩中。

**结论：注入一律走 `badge_hider_html()`**，它负责补 script 外壳并做约束 2 的校验；
绝不要把 `_BADGE_HIDER_JS` 裸着交给 `st.html` / `components.html`。

⚠️ 风险须知
-----------
1. 这依赖社区云的内部 DOM 结构，**对方随时可能改**。徽章的 CSS Module 类名
   （形如 `_viewerBadge_1j65n_23`）**每次 Cloud 部署都会变**，因此这里**只按可见
   文本与 `data-testid` 匹配**，绝不认类名。
2. 该徽章是社区云**免费托管的署名**。隐藏它可能不符合平台意图，请自行判断是否合规。
3. 全部逻辑包在 try/catch 内，任何异常都不会影响应用本体；在**非社区云**环境
   （本地 `streamlit run`、自托管、被第三方页面嵌入）下是**空操作**。

开关
----
`config.HIDE_CLOUD_BADGE`，默认开启。无需改代码即可关闭：

    环境变量：      HIDE_CLOUD_BADGE=0
    Streamlit 密钥：hide_cloud_badge = false

若要彻底移除本功能：删掉本文件，并删除 `app.py` 中 import 与调用它的 2 行。

自检
----
在浏览器 DevTools 控制台（应用 iframe 内）输入 `__wsBadgeHide` 可看到运行时痕迹：

    {ran: 2, top: "reached", frame: true, hidden: true}

    ran    脚本被执行了几次
    top    是否爬到了外层「外壳」文档（none = 顶层运行/跨源，属正常空操作）
    frame  是否确认自己是外壳里的 streamlitApp iframe
    hidden 是否真的隐藏到了徽章节点
"""

import logging
import re

logger = logging.getLogger("WordStyle")

# 父文档里给被隐藏节点打的标记（同时用 class 与 data-*，便于事后排查）
_MARK_CLASS = "ws-badge-off"
_STYLE_ID = "ws-badge-hide-style"

# `<script>` 是 raw-text 元素：内容里出现 `</script` 会把它提前闭合。
# 这里不做「自动转义」——盲替换 `</` 会在比较运算符等位置制造语法错误；
# 改为硬校验，让违规在测试阶段就炸掉，而不是线上悄悄坏掉。
_SCRIPT_BREAK = re.compile(r"</\s*script", re.IGNORECASE)

# DOMPurify（实测 3.4.14）命中「`<` + `[A-Za-z0-9_!/]`」时，会把**整条 script
# 连内容一起丢掉**（输出长度直接变 0，不报错），故在注入前硬校验。
# 字符类刻意写成 ASCII：DOMPurify 的 \w 不含中文，`<用户名>` 这类写法实测安全。
_PURIFY_KILLER = re.compile(r"<[A-Za-z0-9_!/]")


class BadgeScriptUnsafe(ValueError):
    """脚本里含无法内联的序列，拒绝注入（宁可功能不生效，也不往页面上吐源码）。

    两种触发条件：`</script` 会提前闭合标签；「`<` + `[A-Za-z0-9_!/]`」会让
    DOMPurify 把整条 script 连内容一起丢掉。
    """


# 行为要点：
#   * 只隐藏、不 remove()：徽章由 React 管理，直接删节点可能让外壳报
#     "Failed to execute 'removeChild'" 而白屏；改 class + 样式表更安全。
#   * 用样式表而不是 inline style：React 重渲染不会清掉 class。
#   * 只认「我们（或我们的祖先窗口）就是那个 streamlitApp iframe」时才动手，
#     避免误伤别人的页面。
#   * 顶部写入 `window.__wsBadgeHide` 运行时痕迹：既供测试断言「确实执行了」，
#     也方便线上出问题时在控制台一眼看清走到哪一步。
_BADGE_HIDER_JS = r"""
(function () {
    'use strict';
    var MARK = 'ws-badge-off';
    var STYLE_ID = 'ws-badge-hide-style';

    // 可观测痕迹（测试断言 + 线上诊断都用它）
    var mark = window.__wsBadgeHide || (window.__wsBadgeHide = { ran: 0, top: 'none', frame: false, hidden: false });
    mark.ran += 1;

    try {
        // ---- 0. 爬到外层「外壳」文档（同源才有；跨源会抛 → 停在哪层算哪层）----
        var topWin = window, parentDoc = null;
        while (topWin.parent && topWin.parent !== topWin) {
            var upDoc = null;
            try { upDoc = topWin.parent.document; } catch (e) { upDoc = null; }
            if (!upDoc) { break; }
            topWin = topWin.parent;
            parentDoc = upDoc;
        }
        if (!parentDoc) { return; }              // 顶层运行 / 全部跨源 → 空操作
        mark.top = 'reached';

        // ---- 0b. 确认 streamlitApp iframe 里装的就是我们（或我们的祖先）----
        var me = parentDoc.querySelector('iframe[title="streamlitApp"]');
        if (!me) { return; }
        var meWin = null;
        try { meWin = me.contentWindow; } catch (e) { meWin = null; }
        if (!meWin) { return; }
        var w = window, g = 0, onChain = false;
        while (w && g++ < 6) {
            if (w === meWin) { onChain = true; break; }
            if (w === w.parent) { break; }
            try { w = w.parent; } catch (e) { break; }
        }
        if (!onChain) { return; }
        mark.frame = true;

        // ---- 1. 注入隐藏样式（按 class 隐藏，React 重渲染后依然有效）----
        if (!parentDoc.getElementById(STYLE_ID)) {
            var style = parentDoc.createElement('style');
            style.id = STYLE_ID;
            style.textContent = '.' + MARK + '{display:none !important;visibility:hidden !important;}';
            (parentDoc.head || parentDoc.documentElement).appendChild(style);
        }

        function hide(el) {
            if (!el || !el.classList) { return false; }
            if (el.classList.contains(MARK)) { return false; }
            el.classList.add(MARK);
            el.setAttribute('data-ws-badge-off', '1');
            return true;
        }

        function norm(text) {
            return (text || '').replace(/\s+/g, ' ').trim();
        }

        // ---- 2. 「Hosted with Streamlit」胶囊（皇冠图标与它同在一个 a 标签里）----
        // 注意：必须遍历**全部**匹配项并逐个标记，遇到已标记的不能提前 return——
        // 否则 React 重渲染挂出新徽章时会被已藏起来的旧节点挡住（实测踩过）。
        function hidePill() {
            var nodes = parentDoc.querySelectorAll('p, span, div, a');
            var changed = false;
            for (var i = 0; i < nodes.length; i++) {
                if (norm(nodes[i].textContent) !== 'Hosted with Streamlit') { continue; }
                var link = nodes[i].closest ? nodes[i].closest('a') : null;
                if (hide(link || nodes[i])) { changed = true; }
            }
            return changed;
        }

        // ---- 3. 「Created by <用户名>」+ 头像 ----
        // 优先用 data-testid 定位；万一社区云改了标记，再退化为按「Created by」文案定位。
        function creatorSeeds() {
            var seeds = [];
            var avatars = parentDoc.querySelectorAll('[data-testid="appCreatorAvatar"]');
            var i;
            for (i = 0; i < avatars.length; i++) { seeds.push(avatars[i]); }
            if (seeds.length) { return seeds; }
            var nodes = parentDoc.querySelectorAll('div, span, p');
            for (i = 0; i < nodes.length; i++) {
                var t = norm(nodes[i].textContent);
                if (t.length <= 80 && t.indexOf('Created by ') === 0 && !nodes[i].querySelector('iframe')) {
                    seeds.push(nodes[i]);
                }
            }
            return seeds;
        }

        function hideCreator() {
            var seeds = creatorSeeds();
            var changed = false;
            for (var i = 0; i < seeds.length; i++) {
                var node = seeds[i], guard = 0;
                while (node.parentElement && guard++ < 8) {
                    var up = node.parentElement;
                    if (up === parentDoc.body || up === parentDoc.documentElement) { break; }
                    if (up.querySelector('iframe')) { break; }   // 再往上就是装 iframe 的容器了
                    if (norm(up.textContent).length > 120) { break; }  // 已经爬过头
                    node = up;
                }
                if (hide(node)) { changed = true; }
            }
            return changed;
        }

        function sweep() {
            try {
                var a = hidePill();
                var b = hideCreator();
                if (a || b) { mark.hidden = true; }
            } catch (e) { /* 忽略 */ }
        }

        sweep();

        // ---- 4. 外壳是 React，状态一变可能把徽章重新挂回来 → 持续盯住 ----
        try {
            var pending = null;
            var observer = new MutationObserver(function () {
                if (pending) { return; }
                pending = setTimeout(function () { pending = null; sweep(); }, 120);
            });
            observer.observe(parentDoc.body, { childList: true, subtree: true });
        } catch (e) { /* 老浏览器没有 MutationObserver，忽略 */ }

        // ---- 5. 兜底轮询：外壳可能比本脚本晚渲染出徽章 ----
        // 不做「已隐藏就提前停」——留着它，万一定时器比观察器更可靠。
        var ticks = 0;
        var timer = setInterval(function () {
            sweep();
            ticks += 1;
            if (ticks >= 30) { clearInterval(timer); }
        }, 1000);
    } catch (e) { /* 任何异常都不允许影响应用本体 */ }
})();
"""


def badge_hider_script() -> str:
    """返回**裸**脚本源码。

    仅供 DOM 复刻测试「直接把这段字符串当脚本执行」时使用；
    真正注入页面请一律走 `badge_hider_html()`（下面会解释为什么）。
    """
    return _BADGE_HIDER_JS


def badge_hider_html() -> str:
    """返回补好 `<script>` 外壳、可直接交给 `st.html` / `components.html` 的负载。

    为什么必须包裹：见模块 docstring 的「注入方式的硬约束」。一句话——
    Streamlit 前端只重建并执行 `querySelectorAll('script')` 找到的元素，
    裸文本既不会执行，还会被当 HTML 渲染成**页面可见的源码**。

    Raises:
        BadgeScriptUnsafe: 脚本里出现 `</script`（内联会被提前闭合），
            或出现「`<` + `[A-Za-z0-9_!/]`」（DOMPurify 会把整条丢光）。
    """
    if _SCRIPT_BREAK.search(_BADGE_HIDER_JS):
        raise BadgeScriptUnsafe(
            "徽章脚本里出现了 `</script`：内联 <script> 会被提前闭合。"
            "请改写脚本（例如写成 '<' + '/script' 拼接）后再注入。"
        )
    killer = _PURIFY_KILLER.search(_BADGE_HIDER_JS)
    if killer:
        around = _BADGE_HIDER_JS[max(0, killer.start() - 30):killer.start() + 30].replace("\n", " ")
        raise BadgeScriptUnsafe(
            "徽章脚本里出现了 DOMPurify 会整条丢弃的序列 "
            + repr(killer.group(0)) + "（附近：..." + around + "...）。"
            "比较运算符请写成 `a < b`（< 后留空格）；注释里不要写标签字面量。"
        )
    return "<script>\n" + _BADGE_HIDER_JS + "\n</script>"


def hide_cloud_badge() -> bool:
    """把跨文档隐藏脚本注入到页面。返回是否注入成功。

    与 `identity.write_identity_cookie` 同样的双路径：优先 `st.html` +
    `unsafe_allow_javascript=True`（Streamlit ≥1.52，内容不进 iframe、脚本在
    应用主文档执行），失败则回退 `components.html`。
    两条路径**都必须传 `badge_hider_html()`**，不能传裸 JS。
    """
    try:
        import streamlit as st
    except Exception:
        return False

    try:
        payload = badge_hider_html()
    except BadgeScriptUnsafe as exc:
        logger.warning("[BADGE] 放弃注入：%s", exc)
        return False

    try:
        st.html(payload, unsafe_allow_javascript=True)
        return True
    except TypeError:
        pass  # 老版本没有 unsafe_allow_javascript 参数
    except Exception:
        pass

    try:
        from streamlit.components.v1 import html as _components_html
        _components_html(payload, height=0, width=0)
        return True
    except Exception:
        return False
