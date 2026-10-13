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

⚠️ 风险须知（重要）
------------------
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
"""

import logging

logger = logging.getLogger("WordStyle")

# 父文档里给被隐藏节点打的标记（同时用 class 与 data-*，便于事后排查）
_MARK_CLASS = "ws-badge-off"
_STYLE_ID = "ws-badge-hide-style"

# 行为要点：
#   * 只隐藏、不 remove()：徽章由 React 管理，直接删节点可能让外壳报
#     "Failed to execute 'removeChild'" 而白屏；改 class + 样式表更安全。
#   * 用样式表而不是 inline style：React 重渲染不会清掉 class。
#   * 只认「我们就是那个 streamlitApp iframe」时才动手，避免误伤别人的页面。
_BADGE_HIDER_JS = r"""
(function () {
    'use strict';
    var MARK = 'ws-badge-off';
    var STYLE_ID = 'ws-badge-hide-style';
    try {
        // ---- 0. 拿到父文档（同源才有；跨源会抛 SecurityError → 直接放弃）----
        var parentDoc = null;
        try {
            if (window.parent && window.parent !== window) {
                parentDoc = window.parent.document;
            }
        } catch (e) { parentDoc = null; }
        if (!parentDoc) { return; }

        // ---- 0b. 确认我们就是社区云外壳里的那个 iframe，否则什么都不做 ----
        var me = parentDoc.querySelector('iframe[title="streamlitApp"]');
        if (!me || me.contentWindow !== window) { return; }

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

        // ---- 2. 「Hosted with Streamlit」胶囊（皇冠图标与它同在一个 <a> 里）----
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

        var everHidden = false;

        function sweep() {
            try {
                var a = hidePill();
                var b = hideCreator();
                if (a || b) { everHidden = true; }
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
    """返回注入用的脚本源码（单独暴露出来便于测试直接复用同一份字符串）。"""
    return _BADGE_HIDER_JS


def hide_cloud_badge() -> bool:
    """把跨文档隐藏脚本注入到页面。返回是否注入成功。

    与 identity.write_identity_cookie 同样的双路径：优先 `st.html` +
    `unsafe_allow_javascript=True`（Streamlit ≥1.52），失败则回退 `components.html`。
    """
    try:
        import streamlit as st
    except Exception:
        return False

    script = _BADGE_HIDER_JS

    try:
        st.html(script, unsafe_allow_javascript=True)
        return True
    except TypeError:
        pass  # 老版本没有 unsafe_allow_javascript 参数
    except Exception:
        pass

    try:
        from streamlit.components.v1 import html as _components_html
        _components_html(script, height=0, width=0)
        return True
    except Exception:
        return False
